import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { SessionProvider } from "./hooks/session";
import { ArchitecturePage } from "./pages/ArchitecturePage";
import { ChatPage } from "./pages/ChatPage";
import { DataPage } from "./pages/DataPage";
import { EvalPage } from "./pages/EvalPage";
import { MemoryPage } from "./pages/MemoryPage";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:threadId" element={<ChatPage />} />
            <Route path="/memoria" element={<MemoryPage />} />
            <Route path="/datos" element={<DataPage />} />
            <Route path="/evaluacion" element={<EvalPage />} />
            <Route path="/arquitectura" element={<ArchitecturePage />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  </StrictMode>,
);
