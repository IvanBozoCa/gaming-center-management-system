import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type {
  ActiveGuestSession,
  GuestSessionFinishResponse,
  GuestSessionStartResponse,
  StartGuestSessionInput,
  FinishedGuestSession,
  ListGuestSessionHistoryParams,
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

export function finishGuestSession(
  sessionId: string,
): Promise<GuestSessionFinishResponse> {
  return apiRequest<GuestSessionFinishResponse>(
    `/admin/guest-sessions/${sessionId}/finish`,
    {
      method: "POST",
      token: requireAccessToken(),
    },
  );
}

export function listGuestSessionHistory(
  params: ListGuestSessionHistoryParams = {},
): Promise<FinishedGuestSession[]> {
  const searchParams = new URLSearchParams();

  if (params.stationId) {
    searchParams.set("station_id", params.stationId);
  }

  searchParams.set("limit", String(params.limit ?? 20));
  searchParams.set("offset", String(params.offset ?? 0));

  return apiRequest<FinishedGuestSession[]>(
    `/admin/guest-sessions/history?${searchParams.toString()}`,
    {
      token: requireAccessToken(),
    },
  );
}