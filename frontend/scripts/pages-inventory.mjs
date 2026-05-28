#!/usr/bin/env node
/**
 * Inventories page files and @/pages/ import references; writes migration map JSON.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, '..');
const pagesDir = path.join(frontendRoot, 'src', 'pages');
const srcDir = path.join(frontendRoot, 'src');
const outPath = path.join(__dirname, 'pages-migration-map.json');

const RH_ROOT_FILES = [
  'Absences.tsx',
  'Analytics.tsx',
  'AnalyticsGestion.tsx',
  'AnalyticsPaie.tsx',
  'AnnualReviewDetail.tsx',
  'AnnualReviews.tsx',
  'AugmentationsEtPromotions.tsx',
  'BadgeuseRh.tsx',
  'BadgeuseRhScan.tsx',
  'CatalogueFormations.tsx',
  'CompanyPage.tsx',
  'CSE.tsx',
  'Dashboard.tsx',
  'Documents.tsx',
  'EmployeeDetail.tsx',
  'EmployeeExits.tsx',
  'ExitDocumentEdit.tsx',
  'Exports.tsx',
  'GroupDashboard.tsx',
  'Habilitations.tsx',
  'Index.tsx',
  'MedicalFollowUp.tsx',
  'NotFound.tsx',
  'Objectives.tsx',
  'Payroll.tsx',
  'PayrollDetail.tsx',
  'PayslipEdit.tsx',
  'Planning.tsx',
  'PromotionDetail.tsx',
  'Rates.tsx',
  'Recruitment.tsx',
  'ResidencePermits.tsx',
  'Saisies.tsx',
  'SaisiesEtAvances.tsx',
  'SalaryAdvances.tsx',
  'SalarySeizures.tsx',
  'Schedules.tsx',
  'Simulation.tsx',
  'Teams.tsx',
  'UserCreation.tsx',
  'UserEdit.tsx',
  'UserManagement.tsx',
  'UserProfile.tsx',
  'Expenses.tsx',
];

function walk(dir, acc = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(full, acc);
    else if (ent.name.endsWith('.tsx') || ent.name.endsWith('.ts')) acc.push(full);
  }
  return acc;
}

function toImportPath(absFile) {
  const rel = path.relative(path.join(srcDir, 'pages'), absFile).replace(/\\/g, '/');
  const withoutExt = rel.replace(/\.(tsx|ts)$/, '');
  return `@/pages/${withoutExt}`;
}

function buildTargetPath(relFromPages) {
  const norm = relFromPages.replace(/\\/g, '/');
  if (norm.startsWith('employee/')) return norm;
  if (norm === 'EmployeePlanning.tsx') return 'employee/EmployeePlanning.tsx';
  if (norm.startsWith('admin-eywai/')) return norm.replace('admin-eywai/', 'admin/eywai/');
  if (norm.startsWith('super-admin/')) return norm.replace('super-admin/', 'admin/super/');
  if (norm.startsWith('formation/')) return `rh/${norm}`;
  if (norm.startsWith('company/')) return `rh/${norm}`;
  if (norm.startsWith('cse/')) return `rh/${norm}`;
  if (norm.startsWith('manager/')) return `rh/${norm}`;
  if (norm.startsWith('support/')) return `rh/${norm}`;
  if (norm === 'Login.tsx') return 'rh/auth/Login.tsx';
  if (norm === 'ForgotPassword.tsx') return 'rh/auth/ForgotPassword.tsx';
  if (norm === 'ResetPassword.tsx') return 'rh/auth/ResetPassword.tsx';
  if (norm === 'OnboardingPage.tsx') return 'rh/onboarding/OnboardingPage.tsx';
  if (RH_ROOT_FILES.includes(path.basename(norm))) return `rh/${path.basename(norm)}`;
  return norm;
}

const files = walk(pagesDir);
const map = {};
for (const f of files) {
  const rel = path.relative(pagesDir, f);
  const target = buildTargetPath(rel);
  if (rel !== target) {
    map[toImportPath(f)] = `@/pages/${target.replace(/\.(tsx|ts)$/, '')}`;
  }
}

const importRefs = {};
function scanImports(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory() && ent.name !== 'node_modules') scanImports(full);
    else if (/\.(tsx?|jsx?)$/.test(ent.name)) {
      const text = fs.readFileSync(full, 'utf8');
      const re = /@\/pages\/[A-Za-z0-9_./-]+/g;
      let m;
      while ((m = re.exec(text)) !== null) {
        importRefs[m[0]] = (importRefs[m[0]] || 0) + 1;
      }
    }
  }
}
scanImports(srcDir);

const out = {
  generatedAt: new Date().toISOString(),
  fileCount: files.length,
  migrations: map,
  importReferenceCounts: importRefs,
};
fs.writeFileSync(outPath, JSON.stringify(out, null, 2) + '\n');
console.log('Wrote', outPath, '-', Object.keys(map).length, 'path migrations');
