#!/usr/bin/env node
/**
 * Generates re-export shim files at legacy paths (see pages-migration-map.json).
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const mapPath = path.join(__dirname, 'pages-migration-map.json');
const pagesDir = path.join(__dirname, '..', 'src', 'pages');

if (!fs.existsSync(mapPath)) {
  console.error('Run pages-inventory.mjs first');
  process.exit(1);
}

const { migrations } = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
let count = 0;

for (const [oldImport, newImport] of Object.entries(migrations)) {
  const oldRel = oldImport.replace('@/pages/', '') + '.tsx';
  const shimPath = path.join(pagesDir, oldRel);
  if (fs.existsSync(shimPath)) {
    const content = fs.readFileSync(shimPath, 'utf8');
    if (!content.includes('shim temporaire')) continue;
  }
  fs.mkdirSync(path.dirname(shimPath), { recursive: true });
  const body = `// shim temporaire — réexport vers le nouveau chemin
export { default } from '${newImport}';
export * from '${newImport}';
`;
  fs.writeFileSync(shimPath, body);
  count++;
}

console.log('Wrote', count, 'shim files');
