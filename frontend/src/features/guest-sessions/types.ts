export type GuestSessionTimeState = "RUNNING" | "EXHAUSTED";

export interface StartGuestSessionInput {
  station_id: string;
  authorized_seconds: number;
}

export interface GuestSessionStartResponse {
  session_id: string;
  station_id: string;
  authorized_seconds: number;
  session_type: "GUEST";
  session_status: "ACTIVE";
  station_status: "IN_USE";
  started_at: string;
}

export interface ActiveGuestSession {
  session_id: string;
  station_id: string;
  station_code: string;
  authorized_seconds: number;
  started_at: string;
  elapsed_seconds: number;
  remaining_seconds: number;
  time_state: GuestSessionTimeState;
}