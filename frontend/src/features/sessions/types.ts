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
