import { access, constants } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontendRoot = fileURLToPath(new URL("..", import.meta.url));
const viteBin = path.join(frontendRoot, "node_modules", ".bin", "vite");
const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";

async function viteReady() {
  try {
    await access(viteBin, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function installFrontendDeps() {
  const env = { ...process.env };
  delete env.npm_config_prefix;
  delete env.NPM_CONFIG_PREFIX;

  return spawnSync(
    npmCmd,
    ["install", "--prefix", frontendRoot, "--no-fund", "--no-audit"],
    {
      cwd: frontendRoot,
      stdio: "inherit",
      env,
    },
  );
}

if (!(await viteReady())) {
  console.error(
    "Dépendances frontend manquantes ou incomplètes (binaire vite introuvable).",
  );
  console.error("Installation automatique dans frontend/…\n");

  const install = installFrontendDeps();

  if (install.status !== 0 || !(await viteReady())) {
    console.error(
      "\nÉchec. Depuis le dossier frontend, exécutez : npm run reinstall",
    );
    process.exit(1);
  }

  console.error("Dépendances installées.\n");
}
