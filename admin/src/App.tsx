import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Permissions } from "./pages/Permissions";
import { UserDetail } from "./pages/UserDetail";
import { Users } from "./pages/Users";
import { WorkspaceDetail } from "./pages/WorkspaceDetail";
import { Workspaces } from "./pages/Workspaces";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/users" element={<Users />} />
        <Route path="/users/:id" element={<UserDetail />} />
        <Route path="/workspaces" element={<Workspaces />} />
        <Route path="/workspaces/:id" element={<WorkspaceDetail />} />
        <Route path="/permissions" element={<Permissions />} />
      </Routes>
    </Layout>
  );
}
