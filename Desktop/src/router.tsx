import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import App from "./App";
import { Dashboard } from "./routes/dashboard";
import { RunDetail } from "./routes/compute/RunDetail";
import { ModuleStore } from "./routes/modules/index";
import { ModuleDetail } from "./routes/modules/ModuleDetail";
import { Analytics } from "./routes/analytics";
import { QPUSettings } from "./routes/settings/QPUSettings";
import { DataIngest } from "./routes/workspace/DataIngest";
import { QuestionWorkspace } from "./routes/workspace/QuestionWorkspace";
import { ClaimDetail } from "./routes/workspace/ClaimDetail";
import { EvidenceExplorer } from "./routes/workspace/EvidenceExplorer";
import { ExportPanel } from "./routes/workspace/ExportPanel";

const rootRoute = createRootRoute({
  component: () => (
    <App>
      <Outlet />
    </App>
  ),
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Dashboard,
});

const runDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/compute/$runId",
  component: RunDetail,
});

const moduleStoreRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/modules",
  component: ModuleStore,
});

const moduleDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/modules/$domainId",
  component: ModuleDetail,
});

const analyticsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/analytics",
  component: Analytics,
});

const qpuSettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/qpu",
  component: QPUSettings,
});

const dataIngestRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/ingest",
  component: DataIngest,
});

const questionWorkspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/workspace/$workspaceId",
  component: QuestionWorkspace,
});

const claimDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/claims/$claimId",
  component: ClaimDetail,
});

const evidenceExplorerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/evidence/$runId",
  component: EvidenceExplorer,
});

const exportPanelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/export/$runId",
  component: ExportPanel,
});

export const routeTree = rootRoute.addChildren([
  dashboardRoute,
  runDetailRoute,
  moduleStoreRoute,
  moduleDetailRoute,
  analyticsRoute,
  qpuSettingsRoute,
  dataIngestRoute,
  questionWorkspaceRoute,
  claimDetailRoute,
  evidenceExplorerRoute,
  exportPanelRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
