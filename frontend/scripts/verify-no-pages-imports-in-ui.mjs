#!/usr/bin/env node
/**
 * Ensures components/ and hooks/ never import from @/pages/ (layering rule).
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const src = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src');
const SCAN_DIRS = ['components', 'hooks'];
const PATTERN = /@\/pages\//;

const violations = [];

function walk(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(full);
    else if (/\.(tsx?|jsx?)$/.test(ent.name)) {
      const text = fs.readFileSync(full, 'utf8');
      if (PATTERN.test(text)) {
        violations.push(path.relative(src, full));
      }
    }
  }
}

for (const sub of SCAN_DIRS) {
  const root = path.join(src, sub);
  if (fs.existsSync(root)) walk(root);
}

if (violations.length) {
  console.error('components/hooks must not import @/pages/:');
  violations.forEach((v) => console.error(' ', v));
  process.exit(1);
}
console.log('OK: no @/pages/ imports in components/ or hooks/');
