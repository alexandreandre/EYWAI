#!/usr/bin/env node
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const pagesDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'pages');
const MARKER = 'shim temporaire';
let removed = 0;

function walk(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      walk(full);
      try {
        if (fs.readdirSync(full).length === 0) fs.rmdirSync(full);
      } catch {
        /* ignore */
      }
    } else if (ent.name.endsWith('.tsx') || ent.name.endsWith('.ts')) {
      const text = fs.readFileSync(full, 'utf8');
      if (text.includes(MARKER)) {
        fs.unlinkSync(full);
        removed++;
      }
    }
  }
}

walk(pagesDir);
console.log('Removed', removed, 'shim files');
