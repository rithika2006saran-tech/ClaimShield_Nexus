import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "./components/ThemeProvider";
import App from "./App";
import "./index.css";
import { ErrorBoundary } from "./components/ErrorBoundary";

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><ErrorBoundary><ThemeProvider defaultTheme="dark"><BrowserRouter><App /></BrowserRouter></ThemeProvider></ErrorBoundary></React.StrictMode>);
