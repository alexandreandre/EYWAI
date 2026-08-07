#!/usr/bin/env bash
# Répare les serveurs MCP Supabase EYWAI (Claude Code).
# Ne jamais afficher SUPABASE_ACCESS_TOKEN en clair.
set -euo pipefail

# .claude/skills/fix-supabase/ → racine repo
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

MCP_JSON="$ROOT/.mcp.json"
SETTINGS_LOCAL="$ROOT/.claude/settings.local.json"
# State projet Claude Code (approvals MCP) — toujours ~/.claude.json
CLAUDE_JSON="$HOME/.claude.json"

PROD_REF="slleauhyjnmiawosvlcg"
TEST_REF="tlvkjwleahkmuzcegrde"
PROD_NAME="supabase-eywai-prod"
TEST_NAME="supabase-eywai-test"
FEATURES="database,docs,development,functions,branching,storage,debugging"

CANONICAL_MCP=$(cat <<EOF
{
  "mcpServers": {
    "$PROD_NAME": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--project-ref=$PROD_REF",
        "--features=$FEATURES"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "\${SUPABASE_ACCESS_TOKEN}"
      }
    },
    "$TEST_NAME": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--project-ref=$TEST_REF",
        "--features=$FEATURES"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "\${SUPABASE_ACCESS_TOKEN}"
      }
    }
  }
}
EOF
)

ok()   { printf '✔ %s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*"; }
fail() { printf '✘ %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }

step "1. Restaurer .mcp.json canonique"
printf '%s\n' "$CANONICAL_MCP" > "$MCP_JSON"
ok "écrit $MCP_JSON ($PROD_NAME → $PROD_REF, $TEST_NAME → $TEST_REF)"

step "2. Vérifier SUPABASE_ACCESS_TOKEN"
TOKEN=""
if [[ -f "$SETTINGS_LOCAL" ]]; then
  TOKEN="$(python3 - "$SETTINGS_LOCAL" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print((d.get("env") or {}).get("SUPABASE_ACCESS_TOKEN") or "")
PY
)"
fi
if [[ -z "$TOKEN" && -n "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
  TOKEN="$SUPABASE_ACCESS_TOKEN"
fi
if [[ -z "$TOKEN" ]]; then
  fail "Aucun SUPABASE_ACCESS_TOKEN dans .claude/settings.local.json ni dans l'environnement"
  echo "  → créer un Personal Access Token sur https://supabase.com/dashboard/account/tokens"
  echo "  → l'ajouter dans .claude/settings.local.json :"
  echo '     { "env": { "SUPABASE_ACCESS_TOKEN": "sbp_..." } }'
  exit 2
fi
ok "token présent (longueur ${#TOKEN}, non affiché)"

HTTP_CODE="$(curl -sS -o /tmp/eywai-sb-prod.json -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://api.supabase.com/v1/projects/${PROD_REF}" || true)"
if [[ "$HTTP_CODE" != "200" ]]; then
  fail "token invalide ou projet prod inaccessible (HTTP $HTTP_CODE)"
  python3 -c "import json; d=json.load(open('/tmp/eywai-sb-prod.json')); print(' ', d.get('message') or d)" 2>/dev/null || true
  exit 3
fi
ok "API Management OK pour prod ($PROD_REF)"

HTTP_TEST="$(curl -sS -o /tmp/eywai-sb-test.json -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://api.supabase.com/v1/projects/${TEST_REF}" || true)"
if [[ "$HTTP_TEST" != "200" ]]; then
  warn "projet test inaccessible (HTTP $HTTP_TEST) — on continue pour prod"
else
  ok "API Management OK pour test ($TEST_REF)"
fi

step "3. Persister le token (projet + global Claude)"
python3 - "$SETTINGS_LOCAL" "$TOKEN" "$PROD_NAME" "$TEST_NAME" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
token = sys.argv[2]
names = [sys.argv[3], sys.argv[4]]
d = json.loads(path.read_text()) if path.exists() else {}
env = d.setdefault("env", {})
env["SUPABASE_ACCESS_TOKEN"] = token
d["enabledMcpjsonServers"] = names
d["disabledMcpjsonServers"] = []
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(d, indent=2) + "\n")
print(f"écrit {path} (enabledMcpjsonServers={names})")
PY
ok "settings.local.json à jour"

# Correctif durable : VS Code / Claude lancés depuis le Dock n'héritent pas de ~/.zshrc.
# settings.local.json ne couvre que les sessions ouvertes DANS ce repo.
GLOBAL_SETTINGS="$HOME/.claude/settings.json"
python3 - "$GLOBAL_SETTINGS" "$TOKEN" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
token = sys.argv[2]
d = json.loads(path.read_text()) if path.exists() else {}
env = d.setdefault("env", {})
env["SUPABASE_ACCESS_TOKEN"] = token
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(d, indent=2) + "\n")
print(f"écrit {path} env.SUPABASE_ACCESS_TOKEN (len={len(token)})")
PY
ok "token aussi dans ~/.claude/settings.json (global)"

# Approvals .mcp.json : écrites ICI puis RE-écrites APRÈS tout appel `claude`
# (claude mcp list / add réécrit ~/.claude.json et EFFAÇAIT enabledMcpjsonServers).
write_approvals() {
  python3 - "$CLAUDE_JSON" "$ROOT" "$PROD_NAME" "$TEST_NAME" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
root = sys.argv[2]
names = [sys.argv[3], sys.argv[4]]
if not path.exists():
    print(f"ABSENT: {path}", file=sys.stderr)
    sys.exit(4)
d = json.loads(path.read_text())
proj = d.setdefault("projects", {}).setdefault(root, {})
proj["enabledMcpjsonServers"] = names
proj["disabledMcpjsonServers"] = []
path.write_text(json.dumps(d, indent=2) + "\n")
print(f"écrit {path} projects[{root}].enabledMcpjsonServers={names}")
PY
}

step "4. Approuver les serveurs projet dans ~/.claude.json"
write_approvals
ok "approvals projet activées"

step "5. Enregistrement scope local (bypass Pending approval)"
# Scope local = prioritaire sur .mcp.json, pas de gate « Use this MCP server? »,
# token injecté dans la config locale (hors git). C'est le mode durable.
if ! command -v claude >/dev/null 2>&1; then
  fail "binaire `claude` introuvable dans le PATH"
  exit 5
fi

claude mcp remove "$PROD_NAME" -s local >/dev/null 2>&1 || true
claude mcp add -s local \
  -e "SUPABASE_ACCESS_TOKEN=${TOKEN}" \
  -- "$PROD_NAME" npx -y @supabase/mcp-server-supabase@latest \
  "--project-ref=${PROD_REF}" \
  "--features=${FEATURES}" >/dev/null
ok "ajouté $PROD_NAME en scope local"

claude mcp remove "$TEST_NAME" -s local >/dev/null 2>&1 || true
claude mcp add -s local \
  -e "SUPABASE_ACCESS_TOKEN=${TOKEN}" \
  -- "$TEST_NAME" npx -y @supabase/mcp-server-supabase@latest \
  "--project-ref=${TEST_REF}" \
  "--features=${FEATURES}" >/dev/null
ok "ajouté $TEST_NAME en scope local"

# `claude mcp add` réécrit ~/.claude.json → restaurer les approvals tout de suite
write_approvals

step "6. Health-check Claude MCP"
LIST_OUT="$(claude mcp list 2>&1 || true)"
printf '%s\n' "$LIST_OUT"
# list réécrit encore ~/.claude.json
write_approvals

prod_ok=0
test_ok=0
echo "$LIST_OUT" | grep -q "$PROD_NAME:.*✔ Connected" && prod_ok=1 || true
echo "$LIST_OUT" | grep -q "$TEST_NAME:.*✔ Connected" && test_ok=1 || true

step "Résultat"
if [[ "$prod_ok" -eq 1 ]]; then
  ok "$PROD_NAME connecté (projet $PROD_REF — instance métier EYWAI)"
else
  fail "$PROD_NAME toujours hors service"
fi
if [[ "$test_ok" -eq 1 ]]; then
  ok "$TEST_NAME connecté (projet $TEST_REF)"
else
  warn "$TEST_NAME pas connecté (non bloquant si tu n'utilises que prod)"
fi

cat <<'EOF'

Prochaine étape DANS LA SESSION Claude Code :
  1. Tape /mcp → vérifie supabase-eywai-prod et supabase-eywai-test = Connected.
  2. Si tools absents dans le chat déjà ouvert → /mcp rafraîchir, sinon nouvelle session
     dans /Users/alex/Desktop/EYWAI/EYWAI (le scope local est lié à ce chemin).
  3. Smoke-test : execute_sql  select 1 as ok;  sur supabase-eywai-prod.
  Ne pas coller la sortie de `claude mcp get` (elle affiche le token).
EOF

if [[ "$prod_ok" -ne 1 ]]; then
  exit 1
fi
exit 0
