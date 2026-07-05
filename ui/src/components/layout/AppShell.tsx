import { Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Sun, Moon } from "lucide-react";
import { fetchApi } from "../../api/client";
import { useTheme } from "../../hooks/useTheme";
import { Sidebar } from "./Sidebar";
import { ReviewerChip } from "./ReviewerChip";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/review": "Review Queue",
  "/clusters": "Clusters",
  "/pipeline": "Pipeline",
  "/golden": "Golden Records",
  "/resolve": "Resolve Entity",
  "/profile": "Data Profile",
  "/tuner": "Threshold Tuner",
  "/config": "Config Builder",
  "/export": "Export",
};

interface HealthResponse {
  status: string;
  version: string;
  database_connected: boolean;
}

export function AppShell() {
  const location = useLocation();
  const { theme, toggle } = useTheme();

  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => fetchApi<HealthResponse>("/api/health"),
    retry: false,
    refetchInterval: 30_000,
  });

  const dbConnected = health.data?.database_connected ?? true;
  const serverDown = health.isError;

  const title =
    pageTitles[location.pathname] ??
    (location.pathname.startsWith("/clusters/")
      ? "Cluster Detail"
      : location.pathname.startsWith("/golden/")
        ? "Golden Record"
        : "Entity Resolution");

  return (
    <div className="flex h-screen bg-white dark:bg-gray-800">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        {serverDown && (
          <div className="bg-red-600 px-4 py-2 text-center text-sm font-medium text-white">
            Cannot reach the API server. Is it still running?
          </div>
        )}
        {!serverDown && !dbConnected && (
          <div className="bg-amber-500 px-4 py-2 text-center text-sm font-medium text-white">
            No database connection — start ArangoDB and restart with connection options.
          </div>
        )}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 dark:border-gray-700 px-6">
          <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggle}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              title={theme === "dark" ? "Light mode" : "Dark mode"}
              className="inline-flex items-center rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-1.5 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              {theme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
            </button>
            <ReviewerChip />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
