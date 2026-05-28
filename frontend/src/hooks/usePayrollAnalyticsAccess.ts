import { useEffect, useState } from "react";

import { checkUserPermission } from "@/api/permissions";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";
import { isPlatformAdmin } from "@/lib/platformAdmin";

const PAYROLL_ANALYTICS_VIEW = "payroll.analytics.view";

export function usePayrollAnalyticsAccess() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const viewOpt = useViewOptional();
  const [customAllowed, setCustomAllowed] = useState<boolean | null>(null);

  const companyId = activeCompany?.company_id ?? null;
  const roleInCompany = activeCompany?.role ?? user?.role;
  const platformAdmin = isPlatformAdmin(user);

  const isRhSystemRole =
    platformAdmin ||
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

  const isReadOnly = roleInCompany === "collaborateur_rh" && !platformAdmin;

  return {
    user,
    companyId,
    roleInCompany,
    isPlatformAdmin: platformAdmin,
    canView,
    isReadOnly,
    scope: platformAdmin ? ("group" as const) : ("company" as const),
    isCollaborateurRhEmployeeView,
    canGeneratePayroll:
      canView &&
      !isReadOnly &&
      (platformAdmin || roleInCompany === "admin" || roleInCompany === "rh"),
  };
}
