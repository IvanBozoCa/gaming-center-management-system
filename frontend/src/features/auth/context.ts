import { createContext } from "react";

import type { CurrentUserResponse } from "./types";

export interface AuthContextValue {
  user: CurrentUserResponse | null;
  isLoading: boolean;
  establishSession: (token: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);
