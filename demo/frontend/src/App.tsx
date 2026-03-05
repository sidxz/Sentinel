import { Route, Routes } from "react-router-dom";
import { AuthGuard } from "./components/AuthGuard";
import { Layout } from "./components/Layout";
import { AuthCallback } from "./pages/AuthCallback";
import { Export } from "./pages/Export";
import { NoteDetail } from "./pages/NoteDetail";
import { NoteList } from "./pages/NoteList";

export default function App() {
  return (
    <Routes>
      {/* OAuth callback — outside AuthGuard since user isn't authenticated yet */}
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Authenticated routes */}
      <Route
        path="*"
        element={
          <AuthGuard>
            <Layout>
              <Routes>
                <Route path="/" element={<NoteList />} />
                <Route path="/notes" element={<NoteList />} />
                <Route path="/notes/export" element={<Export />} />
                <Route path="/notes/:id" element={<NoteDetail />} />
              </Routes>
            </Layout>
          </AuthGuard>
        }
      />
    </Routes>
  );
}
