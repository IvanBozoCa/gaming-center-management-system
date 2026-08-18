export interface GuestTimeSaleInput {
  sale_type: "GUEST";
  time_product_id: string;
  station_id: string;
}

export interface GuestTimeSaleResponse {
  sale_id: string;
  sale_type: "GUEST";

  time_product_id: string;
  product_name: string;
  duration_seconds: number;
  price_clp: number;

  station_id: string;
  usage_session_id: string;

  session_status: string;
  station_status: string;

  started_at: string;
  created_at: string;
}

export interface RegisteredTimeSaleInput {
  sale_type: "REGISTERED";
  time_product_id: string;
  customer_id: string;
}

export interface RegisteredTimeSaleResponse {
  sale_id: string;
  sale_type: "REGISTERED";

  time_product_id: string;
  product_name: string;
  duration_seconds: number;
  price_clp: number;

  customer_id: string;
  time_transaction_id: string;

  available_seconds: number;
  reserved_seconds: number;

  created_at: string;
}