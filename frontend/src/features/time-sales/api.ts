import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type { GuestTimeSaleInput, GuestTimeSaleResponse } from "./types";

function requireAccessToken(): string {
  const token = getAccessToken();

  if (!token) {
    throw new Error("AUTH_TOKEN_MISSING");
  }

  return token;
}

export function createGuestTimeSale(
  data: GuestTimeSaleInput,
): Promise<GuestTimeSaleResponse> {
  return apiRequest<GuestTimeSaleResponse>("/admin/time-sales", {
    method: "POST",
    token: requireAccessToken(),
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
}
