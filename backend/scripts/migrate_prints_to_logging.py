#!/usr/bin/env python3
"""
Migration : print() → logging dans backend/app.
Préserve le code éventuellement sur la même ligne après print().
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
SKIP = {"core/logging.py"}

PAYROLL_PREFIXES = ("modules/payroll/",)
WARNING_MARKERS = re.compile(
    r"ERREUR|ERROR|❌|\[WARNING\]|⚠|WARN:|Avertissement|Échec|invalide",
    re.I,
)
INFO_MARKERS = re.compile(r"^INFO:|\[SCRAPING\]|terminé|créé|généré|succès|✅|✓", re.I)


def module_logger_name(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").removesuffix(".py").split("/")
    if parts[0] == "app":
        parts = parts[1:]
    return ".".join(parts)


def is_payroll_file(rel_path: str) -> bool:
    return any(rel_path.startswith(p) for p in PAYROLL_PREFIXES)


def infer_level(source: str, to_stderr: bool) -> str:
    if WARNING_MARKERS.search(source):
        return "warning"
    if INFO_MARKERS.search(source) and to_stderr:
        return "info"
    return "debug"


def build_call(level: str, debug_fn: str, msg_unparsed: str) -> str:
    if level == "debug":
        return f"{debug_fn}(logger, {msg_unparsed})"
    return f"logger.{level}({msg_unparsed})"


def migrate_file(path: Path) -> bool:
    rel = str(path.relative_to(APP_ROOT.parent / "app"))
    if rel in SKIP:
        return False

    text = path.read_text(encoding="utf-8")
    if "print(" not in text:
        return False

    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    mod_name = module_logger_name(rel)
    payroll = is_payroll_file(rel)
    debug_fn = "log_payroll_debug" if payroll else "log_app_debug"


    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "print"):
            continue

        to_stderr = any(
            kw.arg == "file"
            and isinstance(kw.value, ast.Attribute)
            and kw.value.attr == "stderr"
            for kw in node.keywords
        )
        src = ast.get_source_segment(text, node) or ""
        level = infer_level(src, to_stderr)
        if node.args:
            msg_unparsed = ast.unparse(node.args[0])
        else:
            msg_unparsed = '""'
        new_call = build_call(level, debug_fn, msg_unparsed)

        lineno = node.lineno - 1
        end_lineno = (node.end_lineno or node.lineno) - 1
        col = node.col_offset
        end_col = node.end_col_offset or len(lines[lineno].rstrip("\n"))

        # Code après le print sur la même ligne
        line = lines[lineno]
        line_no_nl = line.rstrip("\n\r")
        suffix = line_no_nl[end_col:].strip()
        indent = line_no_nl[:col]
        base_indent = line_no_nl[: len(line_no_nl) - len(line_no_nl.lstrip())]

        if end_lineno == lineno:
            if suffix:
                replacement = f"{indent}{new_call}\n{base_indent}{suffix}\n"
            else:
                replacement = f"{indent}{new_call}\n"
            lines[lineno] = replacement
        else:
            # print multiligne : remplacer la plage entière
            before = lines[lineno][:col]
            after_last = lines[end_lineno]
            after_part = after_last[(node.end_col_offset or 0) :]
            merged = f"{before}{new_call}\n"
            if after_part.strip():
                merged += f"{base_indent}{after_part.strip()}\n"
            lines[lineno] = merged
            for i in range(lineno + 1, end_lineno + 1):
                lines[i] = ""

    new_text = "".join(lines)

    # traceback.print_exc
    new_text = re.sub(
        r"traceback\.print_exc\([^)]*\)",
        'logger.exception("Exception")',
        new_text,
    )

    needs_logger = "logger." in new_text or debug_fn in new_text
    if not needs_logger:
        return False

    import_block = f"from app.core.logging import get_logger, {debug_fn}\n"
    logger_line = f'\nlogger = get_logger("{mod_name}")\n'

    if "get_logger" not in new_text:
        insert_at = 0
        if new_text.startswith('"""') or new_text.startswith("'''"):
            q = '"""' if new_text.startswith('"""') else "'''"
            end = new_text.find(q, 3) + 3
            insert_at = new_text.find("\n", end) + 1
        fut = re.search(r"^from __future__ import .+\n", new_text[insert_at:], re.M)
        if fut:
            insert_at += fut.end()
        new_text = new_text[:insert_at] + import_block + new_text[insert_at:]

    if f'logger = get_logger("{mod_name}")' not in new_text:
        m = re.search(r"from app\.core\.logging import[^\n]+\n", new_text)
        if m:
            pos = m.end()
            new_text = new_text[:pos] + logger_line + new_text[pos:]

    # Retirer import sys / traceback orphelins
    if re.search(r"^import sys\s*$", new_text, re.M) and "sys." not in new_text.replace(
        "import sys", ""
    ):
        new_text = re.sub(r"^import sys\n", "", new_text, flags=re.M)
    if re.search(r"^import traceback\s*$", new_text, re.M) and "traceback." not in new_text:
        new_text = re.sub(r"^import traceback\n", "", new_text, flags=re.M)

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    for path in sorted(APP_ROOT.rglob("*.py")):
        rel = str(path.relative_to(APP_ROOT))
        if rel in SKIP:
            continue
        if migrate_file(path):
            print(f"migrated: {rel}")
            changed += 1
    print(f"Done: {changed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
