import { Suspense, lazy } from "react";
import { Navigate, useRoutes } from "react-router-dom";
import { Skeleton } from "antd";
import { AppShell } from "./shell";

const ChatPage = lazy(async () => ({ default: (await import("../pages/ChatPage")).ChatPage }));
const SystemDashboardPage = lazy(async () => ({ default: (await import("../pages/SystemDashboardPage")).SystemDashboardPage }));
const ModuleWorkbenchPage = lazy(async () => ({ default: (await import("../pages/ModuleWorkbenchPage")).ModuleWorkbenchPage }));
const NotFoundPage = lazy(async () => ({ default: (await import("../pages/NotFoundPage")).NotFoundPage }));

export function AppRouter() {
  const element = useRoutes([
    { path: "/", element: <Navigate to="/chat" replace /> },
    {
      path: "/",
      element: <AppShell />,
      children: [
        { path: "chat", element: <ChatPage /> },
        { path: "system", element: <SystemDashboardPage /> },
        { path: "modules/:moduleKey", element: <ModuleWorkbenchPage /> },
      ],
    },
    { path: "*", element: <NotFoundPage /> },
  ]);

  return (
    <Suspense
      fallback={
        <div className="route-skeleton">
          <Skeleton active paragraph={{ rows: 3 }} />
          <Skeleton active paragraph={{ rows: 4 }} />
        </div>
      }
    >
      {element}
    </Suspense>
  );
}
