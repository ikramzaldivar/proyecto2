import { Navigate, Route, Routes } from "react-router-dom";
import { AnnotateScreen } from "@/components/annotate/AnnotateScreen";
import { AppLayout } from "@/components/layout/AppLayout";
import { UploadScreen } from "@/components/upload/UploadScreen";
import { DashboardPage } from "@/pages/Dashboard";
import { AnalyzersPage } from "@/pages/quality/AnalyzersPage";
import { OverviewPage } from "@/pages/quality/OverviewPage";
import { SearchPage } from "@/pages/SearchPage";

export function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route
        path="/dashboard"
        element={
          <AppLayout>
            <DashboardPage />
          </AppLayout>
        }
      />
      {/* SearchPage se envuelve con AppLayout internamente (no aquí), porque
          necesita pasarle su propio contenido de filtros como sidebarExtra
          — ver SearchPage.tsx. */}
      <Route path="/search" element={<SearchPage />} />
      <Route
        path="/upload"
        element={
          <AppLayout>
            <UploadScreen />
          </AppLayout>
        }
      />
      {/* Seis vistas de calidad del Proyecto 2 (Frente 3). */}
      <Route
        path="/overview"
        element={
          <AppLayout>
            <OverviewPage />
          </AppLayout>
        }
      />
      <Route
        path="/analyzers"
        element={
          <AppLayout>
            <AnalyzersPage />
          </AppLayout>
        }
      />
      {/* Annotate es un modo de enfoque de pantalla completa a propósito: sin
          nav global, con su propio botón "Volver". Ver GlobalNav.tsx. */}
      <Route path="/annotate/:imageId" element={<AnnotateScreen />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
