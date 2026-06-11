import { Navigate, useLocation } from "react-router-dom";

/** Anciennes routes RH → /formation#<onglet> (+ sous-onglet si pertinent). */
const RH_LEGACY_REDIRECTS: Record<string, { hash: string; search?: string }> = {
  "/habilitations": { hash: "conformite", search: "?sub=habilitations" },
  "/objectives": { hash: "developpement", search: "?sub=objectifs" },
  "/catalogue-formations": { hash: "formations", search: "?sub=catalogue" },
};

export function RhFormationLegacyRedirect() {
  const { pathname, search } = useLocation();
  const target = RH_LEGACY_REDIRECTS[pathname] ?? { hash: "pilotage" };
  const mergedSearch = search || target.search || "";
  return (
    <Navigate
      to={{ pathname: "/formation", hash: target.hash, search: mergedSearch }}
      replace
    />
  );
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
