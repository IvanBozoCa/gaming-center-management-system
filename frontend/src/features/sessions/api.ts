import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type {
  ActiveRegisteredSession,
  ExtendRegisteredSessionInput,
  RegisteredSessionExtensionResponse,
  RegisteredSessionFinishResponse,
  RegisteredSessionStartResponse,
  StartRegisteredSessionInput,
  FinishedRegisteredSession,
  ListRegisteredSessionHistoryParams,
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

export function extendRegisteredSession(
  sessionId: string,
  data: ExtendRegisteredSessionInput,
): Promise<RegisteredSessionExtensionResponse> {
  return apiRequest<RegisteredSessionExtensionResponse>(
    `/admin/sessions/${sessionId}/extend`,
    {
      method: "POST",
      token: requireAccessToken(),
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    },
  );
}

export function finishRegisteredSession(
  sessionId: string,
): Promise<RegisteredSessionFinishResponse> {
  return apiRequest<RegisteredSessionFinishResponse>(
    `/admin/sessions/${sessionId}/finish`,
    {
      method: "POST",
      token: requireAccessToken(),
    },
  );
}

export function listRegisteredSessionHistory(
  params: ListRegisteredSessionHistoryParams = {},
): Promise<FinishedRegisteredSession[]> {
  const searchParams = new URLSearchParams();

  if (params.customerId) {
    searchParams.set("customer_id", params.customerId);
  }

  if (params.stationId) {
    searchParams.set("station_id", params.stationId);
  }

  searchParams.set("limit", String(params.limit ?? 20));

  searchParams.set("offset", String(params.offset ?? 0));

  return apiRequest<FinishedRegisteredSession[]>(
    `/admin/sessions/history?${searchParams.toString()}`,
    {
      token: requireAccessToken(),
    },
  );
}
