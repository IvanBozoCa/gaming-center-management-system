import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type {
  ActiveRegisteredSession,
  RegisteredSessionStartResponse,
  StartRegisteredSessionInput,
} from "./types";

function requireAccessToken(): string {
  const token = getAccessToken();

  if (!token) {
    throw new Error("AUTH_TOKEN_MISSING");
  }

  return token;
}

export function listActiveRegisteredSessions(): Promise<
  ActiveRegisteredSession[]
> {
  return apiRequest<ActiveRegisteredSession[]>("/admin/sessions/active", {
    token: requireAccessToken(),
  });
}

export function startRegisteredSession(
  data: StartRegisteredSessionInput,
): Promise<RegisteredSessionStartResponse> {
  return apiRequest<RegisteredSessionStartResponse>("/admin/sessions", {
    method: "POST",
    token: requireAccessToken(),
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
}
