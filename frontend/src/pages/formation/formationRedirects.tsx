import { Navigate, useLocation } from "react-router-dom";

import { RH_LEGACY_PATH_TO_HASH } from "@/pages/formation/formationTabRouting";

/** Anciennes routes RH → /formation#<onglet> */
export function RhFormationLegacyRedirect() {
  const { pathname, search } = useLocation();
  const hash = RH_LEGACY_PATH_TO_HASH[pathname] ?? "pilotage";
  return <Navigate to={{ pathname: "/formation", hash, search }} replace />;
}

const EMPLOYEE_LEGACY_HASH: Record<string, string> = {
  "/habilitations": "habilitations",
  "/objectives": "objectifs",
  "/catalogue-formations": "formations",
};

/** Anciennes routes collaborateur → /employee/formation#<onglet> */
export function EmployeeFormationLegacyRedirect() {
  const { pathname, search } = useLocation();
  const hash = EMPLOYEE_LEGACY_HASH[pathname] ?? "formations";
  return <Navigate to={{ pathname: "/employee/formation", hash, search }} replace />;
}
