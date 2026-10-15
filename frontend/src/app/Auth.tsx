import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  get,
  refreshSession,
  send,
  setInstitution,
  setToken,
} from "../services/api";
import type { AuthResult, User } from "../types/domain";
interface AuthContext {
  user: User | null;
  loading: boolean;
  tenant: string;
  chooseTenant: (id: string) => void;
  login: (data: unknown) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
  can: (permission: string) => boolean;
}
const Context = createContext<AuthContext | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [tenant, setTenant] = useState("");
  const queryClient = useQueryClient();
  useEffect(() => {
    let mounted = true;
    refreshSession()
      .then((r) => {
        if (mounted) setUser(r.user);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setLoading(false);
      });
    const expired = () => {
      setUser(null);
      queryClient.clear();
    };
    window.addEventListener("session-expired", expired);
    return () => {
      mounted = false;
      window.removeEventListener("session-expired", expired);
    };
  }, [queryClient]);
  const reload = useCallback(
    async () => setUser(await get<User>("/auth/me")),
    [],
  );
  const login = async (data: unknown) => {
    const result = await send<AuthResult>("/auth/login", data);
    setToken(result.access_token);
    setUser(result.user);
    queryClient.clear();
  };
  const logout = async () => {
    await send("/auth/logout");
    setToken("");
    setInstitution("");
    setTenant("");
    setUser(null);
    queryClient.clear();
  };
  const chooseTenant = (id: string) => {
    setInstitution(id);
    setTenant(id);
    queryClient.clear();
  };
  return (
    <Context.Provider
      value={{
        user,
        loading,
        tenant,
        chooseTenant,
        login,
        logout,
        reload,
        can: (permission) => user?.permissions.includes(permission) || false,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useAuth() {
  const context = useContext(Context);
  if (!context) throw new Error("Auth provider missing");
  return context;
}
