import { useEffect, useState } from "react";

import { checkUserPermission } from "@/api/permissions";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";

const PAYROLL_ANALYTICS_VIEW = "payroll.analytics.view";

export function usePayrollAnalyticsAccess() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const viewOpt = useViewOptional();
  const [customAllowed, setCustomAllowed] = useState<boolean | null>(null);

  const companyId = activeCompany?.company_id ?? null;
  const roleInCompany = activeCompany?.role ?? user?.role;
  const isSuperAdmin = Boolean(user?.is_super_admin);

  const isRhSystemRole =
    isSuperAdmin ||
    roleInCompany === "admin" ||
    roleInCompany === "rh" ||
    roleInCompany === "collaborateur_rh";

  const isCollaborateurRhEmployeeView =
    Boolean(viewOpt?.isCollaborateurRh && viewOpt.viewMode === "collaborateur");

  useEffect(() => {
    if (!user?.id || !companyId || roleInCompany !== "custom") {
      setCustomAllowed(null);
      return;
    }
    let cancelled = false;
    void checkUserPermission(user.id, companyId, PAYROLL_ANALYTICS_VIEW)
      .then((res) => {
        if (!cancelled) setCustomAllowed(res.has_permission);
      })
      .catch(() => {
        if (!cancelled) setCustomAllowed(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.id, companyId, roleInCompany]);

  const canViewRh =
    isRhSystemRole ||
    (roleInCompany === "custom" && customAllowed === true);

  const canView = Boolean(companyId && canViewRh && !isCollaborateurRhEmployeeView);

  const isReadOnly = roleInCompany === "collaborateur_rh" && !isSuperAdmin;

  return {
    user,
    companyId,
    roleInCompany,
    isSuperAdmin,
    canView,
    isReadOnly,
    scope: isSuperAdmin ? ("group" as const) : ("company" as const),
    isCollaborateurRhEmployeeView,
    canGeneratePayroll:
      canView &&
      !isReadOnly &&
      (isSuperAdmin || roleInCompany === "admin" || roleInCompany === "rh"),
  };
}
