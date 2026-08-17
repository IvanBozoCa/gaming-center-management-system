import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type { ActiveRegisteredSession } from "./types";

function requireAccessToken(): string {
  const token = getAccessToken();

  if (!token) {
    throw new Error("AUTH_TOKEN_MISSING");
  }

  return token;
}

export function listActiveRegisteredSessions():
  Promise<ActiveRegisteredSession[]> {
  return apiRequest<ActiveRegisteredSession[]>(
    "/admin/sessions/active",
    {
      token: requireAccessToken(),
    },
  );
}