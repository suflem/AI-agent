import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "antd/dist/reset.css";
import "./styles/global.css";
import { AppRouter } from "./app/router";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { UiThemeProvider } from "./theme/ThemeContext";

const queryClient = new QueryClient();
const Router = import.meta.env.VITE_ROUTER_MODE === "hash" ? HashRouter : BrowserRouter;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <UiThemeProvider>
        <QueryClientProvider client={queryClient}>
          <Router>
            <AppRouter />
          </Router>
        </QueryClientProvider>
      </UiThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
