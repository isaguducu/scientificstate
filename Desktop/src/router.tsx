import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { Dashboard } from "./routes/dashboard";
import { RunDetail } from "./routes/compute/RunDetail";
import { ModuleStore } from "./routes/modules/index";
import { ModuleDetail } from "./routes/modules/ModuleDetail";
import { Analytics } from "./routes/analytics";

const rootRoute = createRootRoute({
  component: () => <Outlet />,
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

export const routeTree = rootRoute.addChildren([
  dashboardRoute,
  runDetailRoute,
  moduleStoreRoute,
  moduleDetailRoute,
  analyticsRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
