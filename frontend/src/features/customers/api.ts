import { getAccessToken } from "../auth/storage";
import { apiRequest } from "../../lib/http";

import type {
  CustomerDetail,
  CustomerSummary,
  ListCustomersParams,
  TimeTransaction,
  TimeWallet,
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

export function getCustomer(
  customerId: string,
): Promise<CustomerDetail> {
  return apiRequest<CustomerDetail>(
    `/admin/customers/${customerId}`,
    {
      token: requireAccessToken(),
    },
  );
}

export function getCustomerWallet(
  customerId: string,
): Promise<TimeWallet> {
  return apiRequest<TimeWallet>(
    `/admin/customers/${customerId}/wallet`,
    {
      token: requireAccessToken(),
    },
  );
}

export function listCustomerTransactions(
  customerId: string,
  limit = 20,
  offset = 0,
): Promise<TimeTransaction[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  return apiRequest<TimeTransaction[]>(
    `/admin/customers/${customerId}/time-transactions?${params.toString()}`,
    {
      token: requireAccessToken(),
    },
  );
}