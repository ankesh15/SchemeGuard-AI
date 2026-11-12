"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import type { EligibilityReport } from "@/lib/types";

const ReportContext = createContext<{
  report: EligibilityReport | null;
  setReport: (report: EligibilityReport | null) => void;
} | null>(null);
export function ReportProvider({ children }: { children: ReactNode }) {
  const [report, setReport] = useState<EligibilityReport | null>(null);
  return (
    <ReportContext.Provider value={{ report, setReport }}>
      {children}
    </ReportContext.Provider>
  );
}
export function useReport() {
  const context = useContext(ReportContext);
  if (!context) throw new Error("Report provider is required");
  return context;
}
