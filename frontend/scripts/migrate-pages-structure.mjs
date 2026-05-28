#!/usr/bin/env node
/**
 * Moves pages/ files to admin|r|employee layout and rewrites @/pages/ imports.
 * Run from repo root: node frontend/scripts/migrate-pages-structure.mjs
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, '..');
const pagesDir = path.join(frontendRoot, 'src', 'pages');
const srcDir = path.join(frontendRoot, 'src');

const RH_ROOT = new Set([
  'Absences.tsx', 'Analytics.tsx', 'AnalyticsGestion.tsx', 'AnalyticsPaie.tsx',
  'AnnualReviewDetail.tsx', 'AnnualReviews.tsx', 'AugmentationsEtPromotions.tsx',
  'BadgeuseRh.tsx', 'BadgeuseRhScan.tsx', 'CatalogueFormations.tsx', 'CompanyPage.tsx',
  'CSE.tsx', 'Dashboard.tsx', 'Documents.tsx', 'EmployeeDetail.tsx', 'EmployeeExits.tsx',
  'ExitDocumentEdit.tsx', 'Exports.tsx', 'GroupDashboard.tsx', 'Habilitations.tsx',
  'Index.tsx', 'MedicalFollowUp.tsx', 'NotFound.tsx', 'Objectives.tsx', 'Payroll.tsx',
  'PayrollDetail.tsx', 'PayslipEdit.tsx', 'Planning.tsx', 'PromotionDetail.tsx',
  'Rates.tsx', 'Recruitment.tsx', 'ResidencePermits.tsx', 'Saisies.tsx', 'SaisiesEtAvances.tsx',
  'SalaryAdvances.tsx', 'SalarySeizures.tsx', 'Schedules.tsx', 'Simulation.tsx', 'Teams.tsx',
  'UserCreation.tsx', 'UserEdit.tsx', 'UserManagement.tsx', 'UserProfile.tsx', 'Expenses.tsx',
]);

function gitMv(from, to) {
  fs.mkdirSync(path.dirname(to), { recursive: true });
  try {
    execSync(`git mv "${from}" "${to}"`, { cwd: frontendRoot, stdio: 'pipe' });
  } catch {
    if (fs.existsSync(from)) {
      fs.renameSync(from, to);
    }
  }
}

function moveFile(rel) {
  const from = path.join(pagesDir, rel);
  if (!fs.existsSync(from)) return null;
  let destRel;
  const base = path.basename(rel);
  if (rel.startsWith('employee/') || rel === 'employee') return null;
  if (base === 'EmployeePlanning.tsx') destRel = 'employee/EmployeePlanning.tsx';
  else if (rel.startsWith('admin-eywai/')) destRel = rel.replace('admin-eywai/', 'admin/eywai/');
  else if (rel.startsWith('super-admin/')) destRel = rel.replace('super-admin/', 'admin/super/');
  else if (rel.startsWith('formation/')) destRel = `rh/${rel}`;
  else if (rel.startsWith('company/')) destRel = `rh/${rel}`;
  else if (rel.startsWith('cse/')) destRel = `rh/${rel}`;
  else if (rel.startsWith('manager/')) destRel = `rh/${rel}`;
  else if (rel.startsWith('support/')) destRel = `rh/${rel}`;
  else if (base === 'Login.tsx') destRel = 'rh/auth/Login.tsx';
  else if (base === 'ForgotPassword.tsx') destRel = 'rh/auth/ForgotPassword.tsx';
  else if (base === 'ResetPassword.tsx') destRel = 'rh/auth/ResetPassword.tsx';
  else if (base === 'OnboardingPage.tsx') destRel = 'rh/onboarding/OnboardingPage.tsx';
  else if (RH_ROOT.has(base) && !rel.includes('/')) destRel = `rh/${base}`;
  else if (base.endsWith('.backup')) destRel = `rh/${base}`;
  else return null;

  const to = path.join(pagesDir, destRel);
  gitMv(from, to);
  return { from: rel, to: destRel };
}

function walkRel(dir, base = '') {
  const out = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = base ? `${base}/${ent.name}` : ent.name;
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) out.push(...walkRel(full, rel));
    else if (/\.(tsx?|backup)$/.test(ent.name)) out.push(rel);
  }
  return out;
}

// Collect before moves
const allRel = walkRel(pagesDir);
const moves = [];
for (const rel of allRel.sort()) {
  const m = moveFile(rel);
  if (m) moves.push(m);
}

console.log('Git moves:', moves.length);

function rewriteImports(content) {
  let s = content;
  const rules = [
    ['@/pages/admin/eywai/', '@/pages/admin/eywai/'],
    ['@/pages/admin/super/', '@/pages/admin/super/'],
    ['@/pages/rh/formation/', '@/pages/rh/formation/'],
    ['@/pages/rh/company/', '@/pages/rh/company/'],
    ['@/pages/rh/cse/', '@/pages/rh/cse/'],
    ['@/pages/rh/manager/', '@/pages/rh/manager/'],
    ['@/pages/rh/support/', '@/pages/rh/support/'],
    ['@/pages/rh/auth/Login', '@/pages/rh/auth/Login'],
    ['@/pages/rh/auth/ForgotPassword', '@/pages/rh/auth/ForgotPassword'],
    ['@/pages/rh/auth/ResetPassword', '@/pages/rh/auth/ResetPassword'],
    ['@/pages/rh/onboarding/OnboardingPage', '@/pages/rh/onboarding/OnboardingPage'],
    ['@/pages/employee/EmployeePlanning', '@/pages/employee/EmployeePlanning'],
  ];
  for (const [from, to] of rules) {
    s = s.split(from).join(to);
  }
  const rhNames = [...RH_ROOT].map((f) => f.replace('.tsx', '')).sort((a, b) => b.length - a.length);
  for (const name of rhNames) {
    s = s.split(`@/pages/${name}`).join(`@/pages/rh/${name}`);
  }
  return s;
}

function walkRewrite(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory() && ent.name !== 'node_modules') walkRewrite(full);
    else if (/\.(tsx?|jsx?|mjs)$/.test(ent.name)) {
      const before = fs.readFileSync(full, 'utf8');
      const after = rewriteImports(before);
      if (after !== before) fs.writeFileSync(full, after);
    }
  }
}

walkRewrite(srcDir);
walkRewrite(path.join(frontendRoot, 'scripts'));
console.log('Import rewrite done.');
