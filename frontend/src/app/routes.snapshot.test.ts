import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

const baselinePath = path.resolve(__dirname, '../../scripts/.baseline/pages-routes.json');

function extractRoutePaths(appSource: string): string[] {
  const paths: string[] = [];
  const re = /<Route\s+[^>]*path=["']([^"']+)["']/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(appSource)) !== null) {
    paths.push(m[1]);
  }
  return paths.sort();
}

function extractLazyExports(lazySource: string): string[] {
  const names: string[] = [];
  const re = /^export const (\w+)/gm;
  let m: RegExpExecArray | null;
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

describe('routes snapshot (post pages migration)', () => {
  it('matches baseline route paths and lazy export names', () => {
    const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf8')) as {
      routePaths: string[];
      lazyExportNames: string[];
    };
    const appSource = fs.readFileSync(path.resolve(__dirname, '../App.tsx'), 'utf8');
    const lazySource = fs.readFileSync(path.resolve(__dirname, 'lazyPages.ts'), 'utf8');

    expect(extractRoutePaths(appSource)).toEqual(baseline.routePaths);
    expect(extractLazyExports(lazySource)).toEqual(baseline.lazyExportNames);
  });
});
