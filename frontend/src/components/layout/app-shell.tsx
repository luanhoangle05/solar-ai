import type { ReactNode } from "react";
import { loadFrontendDataResult } from "@/lib/frontend-data.server";
import { DataError } from "@/components/shared/data-error";
import { Sidebar } from "./sidebar";
import { TopHeader } from "./top-header";
export async function AppShell({ children }: { children: ReactNode }) {
  const result = await loadFrontendDataResult();
  return <div className="app-shell"><a href="#main-content" className="skip-link">Skip to content</a><TopHeader data={result.ok ? result.data : undefined} /><div className="app-body"><Sidebar /><main id="main-content" tabIndex={-1} className="workspace">{result.ok ? children : <DataError message={result.error.message} details={result.error.details} />}</main></div></div>;
}
