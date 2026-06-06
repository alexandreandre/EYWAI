import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

const baselinePath = path.resolve(__dirname, '../../scripts/.baseline/pages-routes.json');

function readRouteConstants(frontendRoot: string): Record<string, string> {
  const badgeuseRoutesPath = path.resolve(frontendRoot, 'src/lib/badgeuseRoutes.ts');
  const source = fs.readFileSync(badgeuseRoutesPath, 'utf8');
  const constants: Record<string, string> = {};
  const re = /export const (\w+) = ['"]([^'"]+)['"]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(source)) !== null) {
    constants[m[1]] = m[2];
  }
  return constants;
}

function extractRoutePaths(appSource: string, routeConstants: Record<string, string>): string[] {
  const paths: string[] = [];
  const literalRe = /<Route\s+[^>]*path=["']([^"']+)["']/g;
  let m: RegExpExecArray | null;
  while ((m = literalRe.exec(appSource)) !== null) {
    paths.push(m[1]);
  }
  const constRe = /<Route\s+[^>]*path=\{([A-Z_][A-Z0-9_]*)\}/g;
  while ((m = constRe.exec(appSource)) !== null) {
    const resolved = routeConstants[m[1]];
    if (resolved) paths.push(resolved);
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
    const frontendRoot = path.resolve(__dirname, '../..');
    const appSource = fs.readFileSync(path.resolve(frontendRoot, 'src/App.tsx'), 'utf8');
    const lazySource = fs.readFileSync(path.resolve(__dirname, 'lazyPages.ts'), 'utf8');
    const routeConstants = readRouteConstants(frontendRoot);

    expect(extractRoutePaths(appSource, routeConstants)).toEqual(baseline.routePaths);
    expect(extractLazyExports(lazySource)).toEqual(baseline.lazyExportNames);
  });
});
