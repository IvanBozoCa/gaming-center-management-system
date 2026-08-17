import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type {
  CustomerSummary,
  ListCustomersParams,
} from "./types";

function requireAccessToken(): string {
  const token = getAccessToken();

  if (!token) {
    throw new Error("AUTH_TOKEN_MISSING");
  }

  return token;
}

export function listCustomers(
  params: ListCustomersParams = {},
): Promise<CustomerSummary[]> {
  const searchParams = new URLSearchParams();

  const query = params.q?.trim();

  if (query) {
    searchParams.set("q", query);
  }

  if (typeof params.isActive === "boolean") {
    searchParams.set(
      "is_active",
      String(params.isActive),
    );
  }

  searchParams.set(
    "limit",
    String(params.limit ?? 50),
  );

  searchParams.set(
    "offset",
    String(params.offset ?? 0),
  );

  return apiRequest<CustomerSummary[]>(
    `/admin/customers?${searchParams.toString()}`,
    {
      token: requireAccessToken(),
    },
  );
}