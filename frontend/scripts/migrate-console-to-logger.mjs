#!/usr/bin/env node
/**
 * Remplace console.* par log.* dans frontend/src (hors lib/logger.ts).
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(__dirname, '..', 'src');
const SKIP = new Set(['lib/logger.ts']);

const MAP = [
  [/console\.debug\(/g, 'log.debug('],
  [/console\.info\(/g, 'log.info('],
  [/console\.warn\(/g, 'log.warn('],
  [/console\.error\(/g, 'log.error('],
  [/console\.log\(/g, 'log.debug('],
];

function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p, files);
    else if (/\.(tsx?)$/.test(name)) files.push(p);
  }
  return files;
}

function relFromSrc(abs) {
  return path.relative(SRC, abs).replace(/\\/g, '/');
}

function migrate(file) {
  const rel = relFromSrc(file);
  if (SKIP.has(rel)) return false;

  let text = fs.readFileSync(file, 'utf8');
  if (!/console\.(log|debug|info|warn|error)\(/.test(text)) return false;

  for (const [re, rep] of MAP) text = text.replace(re, rep);

  if (!text.includes("from '@/lib/logger'") && !text.includes('from "@/lib/logger"')) {
    const importLine = "import { log } from '@/lib/logger';\n";
    const m = text.match(/^(['"]use client['"]\s*;\s*\n)/);
    if (m) text = m[0] + importLine + text.slice(m[0].length);
    else if (text.startsWith('/**') || text.startsWith('//')) {
      const end = text.indexOf('\n\n');
      const pos = end >= 0 ? end + 2 : 0;
      text = text.slice(0, pos) + importLine + text.slice(pos);
    } else {
      text = importLine + text;
    }
  }

  fs.writeFileSync(file, text);
  return true;
}

let n = 0;
for (const f of walk(SRC)) {
  if (migrate(f)) {
    console.log('migrated:', relFromSrc(f));
    n++;
  }
}
console.log('Done:', n, 'files');
