import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type { CreateStationInput, Station } from "./types";

function requireAccessToken(): string {
  const token = getAccessToken();

  if (!token) {
    throw new Error("AUTH_TOKEN_MISSING");
  }

  return token;
}

export function listStations(): Promise<Station[]> {
  return apiRequest<Station[]>("/admin/stations", {
    token: requireAccessToken(),
  });
}

export function createStation(data: CreateStationInput): Promise<Station> {
  return apiRequest<Station>("/admin/stations", {
    method: "POST",
    token: requireAccessToken(),
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
}
