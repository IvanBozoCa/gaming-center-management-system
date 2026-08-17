import {
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { setUnauthorizedHandler } from "../../lib/http";
import { getCurrentUser } from "./api";
import { AuthContext } from "./context";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "./storage";
import type { CurrentUserResponse } from "./types";

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<CurrentUserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    clearAccessToken();
    setUser(null);
  }, []);

  const establishSession = useCallback(async (token: string) => {
    setAccessToken(token);

    try {
      const currentUser = await getCurrentUser(token);

      if (currentUser.role !== "ADMIN" || !currentUser.is_active) {
        clearAccessToken();
        setUser(null);
        throw new Error("ADMIN_ROLE_REQUIRED");
      }

      setUser(currentUser);
    } catch (error) {
      clearAccessToken();
      setUser(null);
      throw error;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    setUnauthorizedHandler(logout);

    async function restoreSession() {
      const token = getAccessToken();

      if (!token) {
        if (!cancelled) {
          setIsLoading(false);
        }
        return;
      }

      try {
        const currentUser = await getCurrentUser(token);

        if (cancelled) {
          return;
        }

        if (currentUser.role !== "ADMIN" || !currentUser.is_active) {
          logout();
          return;
        }

        setUser(currentUser);
      } catch {
        if (!cancelled) {
          logout();
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
      setUnauthorizedHandler(null);
    };
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{ user, isLoading, establishSession, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}
