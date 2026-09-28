import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import DashboardLayout from "./layouts/DashboardLayout";
import AuthLayout from "./layouts/AuthLayout";
import ProtectedRoute from "./routes/ProtectedRoute";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import DashboardPage from "./pages/dashboard/DashboardPage";
import AgentsListPage from "./pages/agents/AgentsListPage";
import AgentFormPage from "./pages/agents/AgentFormPage";
import KnowledgePage from "./pages/knowledge/KnowledgePage";
import PlaygroundPage from "./pages/playground/PlaygroundPage";
import LeadsPage from "./pages/leads/LeadsPage";
import HandoffInboxPage from "./pages/conversations/HandoffInboxPage";
import ApiKeysPage from "./pages/settings/ApiKeysPage";
import BillingPage from "./pages/billing/BillingPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<DashboardLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/agents" element={<AgentsListPage />} />
            <Route path="/agents/new" element={<AgentFormPage />} />
            <Route path="/agents/:id" element={<AgentFormPage />} />
            <Route path="/agents/:id/playground" element={<PlaygroundPage />} />
            <Route path="/knowledge" element={<KnowledgePage />} />
            <Route path="/leads" element={<LeadsPage />} />
            <Route path="/handoff" element={<HandoffInboxPage />} />
            <Route path="/api-keys" element={<ApiKeysPage />} />
            <Route path="/billing" element={<BillingPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
