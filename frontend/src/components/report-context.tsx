"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import type { Explanation } from "@/lib/workflow";
import type { EligibilityReport } from "@/lib/types";

const ReportContext = createContext<{
  report: EligibilityReport | null;
  explanation: Explanation | null;
  setExplanation: (value: Explanation | null) => void;
  setReport: (report: EligibilityReport | null) => void;
} | null>(null);
export function ReportProvider({ children }: { children: ReactNode }) {
  const [report, setReport] = useState<EligibilityReport | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  return (
    <ReportContext.Provider
      value={{ report, setReport, explanation, setExplanation }}
    >
      {children}
    </ReportContext.Provider>
  );
}
export const useOptionalReport = () => useContext(ReportContext);
export function useReport() {
  const context = useContext(ReportContext);
  if (!context) throw new Error("Report provider is required");
  return context;
}
