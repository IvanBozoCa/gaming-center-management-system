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