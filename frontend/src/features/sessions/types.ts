export type SessionTimeState = "RUNNING" | "EXHAUSTED";

export interface ActiveRegisteredSession {
  session_id: string;

  station_id: string;
  station_code: string;

  customer_id: string;
  customer_username: string;
  customer_display_name: string;

  authorized_seconds: number;
  started_at: string;

  elapsed_seconds: number;
  remaining_seconds: number;

  time_state: SessionTimeState;
}

export interface StartRegisteredSessionInput {
  station_id: string;
  customer_id: string;
  authorized_seconds: number;
}

export interface RegisteredSessionStartResponse {
  session_id: string;
  station_id: string;
  customer_id: string;

  authorized_seconds: number;
  available_seconds: number;
  reserved_seconds: number;

  station_status: "IN_USE";
  started_at: string;
}

export interface ExtendRegisteredSessionInput {
  additional_seconds: number;
}

export interface RegisteredSessionExtensionResponse {
  session_id: string;
  station_id: string;
  customer_id: string;

  additional_seconds: number;
  authorized_seconds: number;

  available_seconds: number;
  reserved_seconds: number;

  session_status: "ACTIVE";
  started_at: string;
}

export interface RegisteredSessionFinishResponse {
  session_id: string;
  station_id: string;
  customer_id: string;

  authorized_seconds: number;
  consumed_seconds: number;
  released_seconds: number;

  available_seconds: number;
  reserved_seconds: number;

  session_status: "FINISHED";
  station_status: "AVAILABLE";

  started_at: string;
  ended_at: string;
}

export interface FinishedRegisteredSession {
  session_id: string;

  station_id: string;
  station_code: string;

  customer_id: string;
  customer_username: string;
  customer_display_name: string;

  authorized_seconds: number;
  consumed_seconds: number;
  released_seconds: number;

  started_at: string;
  ended_at: string;
}

export interface ListRegisteredSessionHistoryParams {
  customerId?: string;
  stationId?: string;
  limit?: number;
  offset?: number;
}