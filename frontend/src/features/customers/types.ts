export interface CustomerSummary {
  id: string;
  username: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  available_seconds: number;
  reserved_seconds: number;
}

export interface ListCustomersParams {
  q?: string;
  isActive?: boolean;
  limit?: number;
  offset?: number;
}

export interface CustomerDetail {
  id: string;
  username: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  available_seconds: number;
  reserved_seconds: number;
}

export interface TimeWallet {
  available_seconds: number;
  reserved_seconds: number;
}

export type TimeTransactionType =
  | "PURCHASE"
  | "SESSION_RESERVE"
  | "SESSION_USAGE"
  | "SESSION_RELEASE"
  | "BONUS"
  | "ADJUSTMENT"
  | "REFUND";

export interface TimeTransaction {
  id: string;
  transaction_type: TimeTransactionType;
  available_seconds_delta: number;
  reserved_seconds_delta: number;
  actor_user_id: string | null;
  created_at: string;
}

export interface TimePurchaseResponse {
  transaction_id: string;
  customer_id: string;
  credited_seconds: number;
  available_seconds: number;
  reserved_seconds: number;
  transaction_type: string;
  created_at: string;
}

export interface RegisterCustomerInput {
  username: string;
  display_name: string;
  password: string;
}

export interface RegisteredCustomerResponse {
  id: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}
