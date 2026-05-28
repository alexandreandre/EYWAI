#!/usr/bin/env node
/**
 * Fails if legacy @/pages/ import paths remain outside shim files.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.join(__dirname, '..', 'src');

const LEGACY_PATTERNS = [
  /@\/pages\/admin-eywai\//,
  /@\/pages\/super-admin\//,
  /@\/pages\/formation\//,
  /@\/pages\/company\//,
  /@\/pages\/cse\//,
  /@\/pages\/manager\//,
  /@\/pages\/support\//,
  /@\/pages\/(Login|ForgotPassword|ResetPassword|OnboardingPage|EmployeePlanning)(['"])/,
  /@\/pages\/(Dashboard|Employees|Absences|Planning|Payroll|Analytics)(['"])/,
];

const SHIM_MARK = 'shim temporaire';

function walk(dir, hits = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory() && ent.name !== 'node_modules') walk(full, hits);
    else if (/\.(tsx?|jsx?)$/.test(ent.name)) {
      const text = fs.readFileSync(full, 'utf8');
      if (text.includes(SHIM_MARK)) return;
      const rel = path.relative(srcDir, full);
      for (const re of LEGACY_PATTERNS) {
        if (re.test(text)) {
          hits.push({ file: rel, pattern: re.source });
        }
      }
    }
  }
  return hits;
}

const hits = walk(srcDir);
if (hits.length) {
  console.error('Legacy @/pages/ imports found:');
  for (const h of hits) console.error(' ', h.file, h.pattern);
  process.exit(1);
}
console.log('No legacy page import paths outside shims.');
