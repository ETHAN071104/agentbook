import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, useLocation } from "react-router-dom";

import { App } from "./App";
import { GuestSessionProvider } from "./guest/GuestSessionProvider";
import "@fontsource/outfit/400.css";
import "@fontsource/outfit/500.css";
import "@fontsource/outfit/600.css";
import "@fontsource/outfit/700.css";
import "@fontsource/outfit/800.css";
import "./styles/index.css";
import "./styles/app-theme.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Application root element is missing.");
}

function AppBootstrap() {
  const location = useLocation();

  if (location.pathname === "/") {
    return <App />;
  }

  return (
    <GuestSessionProvider>
      <App />
    </GuestSessionProvider>
  );
}

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <AppBootstrap />
    </BrowserRouter>
  </StrictMode>,
);
