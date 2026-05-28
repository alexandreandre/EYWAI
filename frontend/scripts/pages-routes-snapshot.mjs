#!/usr/bin/env node
/**
 * Snapshot / compare route paths in App.tsx and lazy export names in lazyPages.ts.
 * Usage:
 *   node scripts/pages-routes-snapshot.mjs           # write baseline
 *   node scripts/pages-routes-snapshot.mjs --compare # fail if drift
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, '..');
const baselinePath = path.join(__dirname, '.baseline', 'pages-routes.json');
const appPath = path.join(frontendRoot, 'src', 'App.tsx');
const lazyPath = path.join(frontendRoot, 'src', 'app', 'lazyPages.ts');

function extractRoutePaths(appSource) {
  const paths = [];
  const re = /<Route\s+[^>]*path=["']([^"']+)["']/g;
  let m;
  while ((m = re.exec(appSource)) !== null) {
    paths.push(m[1]);
  }
  return paths.sort();
}

function extractLazyExports(lazySource) {
  const names = [];
  const re = /^export const (\w+)/gm;
  let m;
  while ((m = re.exec(lazySource)) !== null) {
    names.push(m[1]);
  }
  const re2 = /^export \{([^}]+)\}/gm;
  while ((m = re2.exec(lazySource)) !== null) {
    m[1]
      .split(',')
      .map((s) => s.trim().split(/\s+as\s+/)[0].trim())
      .filter(Boolean)
      .forEach((n) => names.push(n));
  }
  return [...new Set(names)].sort();
}

function readSnapshot() {
  const appSource = fs.readFileSync(appPath, 'utf8');
  const lazySource = fs.readFileSync(lazyPath, 'utf8');
  return {
    generatedAt: new Date().toISOString(),
    routePaths: extractRoutePaths(appSource),
    lazyExportNames: extractLazyExports(lazySource),
  };
}

function compare(a, b, label) {
  const onlyA = a.filter((x) => !b.includes(x));
  const onlyB = b.filter((x) => !a.includes(x));
  if (onlyA.length || onlyB.length) {
    console.error(`Drift in ${label}:`);
    if (onlyA.length) console.error('  removed:', onlyA);
    if (onlyB.length) console.error('  added:', onlyB);
    return false;
  }
  return true;
}

const compareMode = process.argv.includes('--compare');
const snapshot = readSnapshot();

if (compareMode) {
  if (!fs.existsSync(baselinePath)) {
    console.error('Missing baseline:', baselinePath);
    process.exit(1);
  }
  const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const okRoutes = compare(baseline.routePaths, snapshot.routePaths, 'routePaths');
  const okLazy = compare(baseline.lazyExportNames, snapshot.lazyExportNames, 'lazyExportNames');
  if (!okRoutes || !okLazy) process.exit(1);
  console.log('Routes snapshot OK:', snapshot.routePaths.length, 'paths,', snapshot.lazyExportNames.length, 'lazy exports');
} else {
  fs.mkdirSync(path.dirname(baselinePath), { recursive: true });
  fs.writeFileSync(baselinePath, JSON.stringify(snapshot, null, 2) + '\n');
  console.log('Wrote baseline:', baselinePath);
  console.log('  routePaths:', snapshot.routePaths.length);
  console.log('  lazyExportNames:', snapshot.lazyExportNames.length);
}
