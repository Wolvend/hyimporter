import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

try {
  const storedTheme = window.localStorage.getItem("voxelviewer.theme");
  if (storedTheme === "dark" || storedTheme === "light") {
    document.documentElement.setAttribute("data-theme", storedTheme);
  }
} catch {
  // Ignore storage access errors and use CSS default theme.
}

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing root element");
}
createRoot(root).render(<App />);
