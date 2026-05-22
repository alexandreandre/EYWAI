import { createContext, useContext, type ReactNode } from "react";
import type { CseTabId } from "@/lib/cseLabels";

export type CsePageContextValue = {
  activeTab: CseTabId;
  setActiveTab: (tab: CseTabId) => void;
  highlightElectedMemberId: string | null;
  setHighlightElectedMemberId: (id: string | null) => void;
  mandateAlertsCount: number;
  electionAlertsCount: number;
};

const CsePageContext = createContext<CsePageContextValue | null>(null);

export function CsePageProvider({
  value,
  children,
}: {
  value: CsePageContextValue;
  children: ReactNode;
}) {
  return <CsePageContext.Provider value={value}>{children}</CsePageContext.Provider>;
}

export function useCsePage(): CsePageContextValue {
  const ctx = useContext(CsePageContext);
  if (!ctx) {
    throw new Error("useCsePage must be used within CsePageProvider");
  }
  return ctx;
}

export function useCsePageOptional(): CsePageContextValue | null {
  return useContext(CsePageContext);
}
