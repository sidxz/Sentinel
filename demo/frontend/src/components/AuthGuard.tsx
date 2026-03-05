import { createContext, useContext, useEffect, useState } from "react";
import type { UserInfo } from "../api/notes";
import { fetchMe } from "../api/notes";
import { getToken } from "../api/client";
import { Login } from "../pages/Login";

const UserContext = createContext<UserInfo | null>(null);

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within AuthGuard");
  return ctx;
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-300" />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return <UserContext.Provider value={user}>{children}</UserContext.Provider>;
}
