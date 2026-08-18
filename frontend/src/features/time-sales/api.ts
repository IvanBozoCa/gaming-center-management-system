import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type {
  GuestTimeSaleInput,
  GuestTimeSaleResponse,
  RegisteredTimeSaleInput,
  RegisteredTimeSaleResponse,
} from "./types";

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
  return apiRequest<GuestTimeSaleResponse>(
    "/admin/time-sales",
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

export function createRegisteredTimeSale(
  data: RegisteredTimeSaleInput,
): Promise<RegisteredTimeSaleResponse> {
  return apiRequest<RegisteredTimeSaleResponse>(
    "/admin/time-sales",
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