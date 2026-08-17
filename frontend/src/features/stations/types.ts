export type StationStatus = "AVAILABLE" | "IN_USE" | "MAINTENANCE" | "OFFLINE";

export type AdminStationStatus = "AVAILABLE" | "MAINTENANCE" | "OFFLINE";

export interface Station {
  id: string;
  code: string;
  status: StationStatus;
  created_at: string;
  updated_at: string;
}

export interface CreateStationInput {
  code: string;
}
