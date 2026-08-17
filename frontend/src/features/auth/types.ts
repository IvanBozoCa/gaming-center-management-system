export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export type UserRole =
  | "ADMIN"
  | "CUSTOMER";

export interface CurrentUserResponse {
  id: string;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface LoginCredentials {
  username: string;
  password: string;
}