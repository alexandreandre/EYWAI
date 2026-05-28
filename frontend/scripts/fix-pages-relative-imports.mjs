#!/usr/bin/env node
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const pagesDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'pages');

function depthFromPages(filePath) {
  const rel = path.relative(pagesDir, filePath);
  return rel.split(path.sep).length - 1;
}

function walk(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(full);
    else if (/\.tsx?$/.test(ent.name)) {
      let text = fs.readFileSync(full, 'utf8');
      const depth = depthFromPages(full);
      const needed = depth + 1;
      const re = /from (['"])(\.\.\/)+/g;
      const updated = text.replace(re, (match, quote, _p) => {
        const currentLevels = (match.match(/\.\.\//g) || []).length;
        if (currentLevels >= needed) return match;
        return `from ${quote}${'../'.repeat(needed)}`;
      });
      if (updated !== text) {
        fs.writeFileSync(full, updated);
        console.log('Fixed', path.relative(pagesDir, full), `depth=${depth} -> ${needed} levels`);
      }
    }
  }
}

walk(pagesDir);
