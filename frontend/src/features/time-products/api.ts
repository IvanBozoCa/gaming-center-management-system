import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type { TimeProduct } from "./types";

function requireAccessToken(): string {
  const token = getAccessToken();

  if (!token) {
    throw new Error("AUTH_TOKEN_MISSING");
  }

  return token;
}

export function listActiveTimeProducts(): Promise<TimeProduct[]> {
  return apiRequest<TimeProduct[]>("/admin/time-products?is_active=true", {
    token: requireAccessToken(),
  });
}
