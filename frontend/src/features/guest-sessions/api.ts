import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type {
  ActiveGuestSession,
  GuestSessionStartResponse,
  StartGuestSessionInput,
} from "./types";

function requireAccessToken(): string {
  const token = getAccessToken();

  if (!token) {
    throw new Error("AUTH_TOKEN_MISSING");
  }

  return token;
}

export function listActiveGuestSessions(): Promise<ActiveGuestSession[]> {
  return apiRequest<ActiveGuestSession[]>("/admin/guest-sessions/active", {
    token: requireAccessToken(),
  });
}

export function startGuestSession(
  data: StartGuestSessionInput,
): Promise<GuestSessionStartResponse> {
  return apiRequest<GuestSessionStartResponse>("/admin/guest-sessions", {
    method: "POST",
    token: requireAccessToken(),
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
}
