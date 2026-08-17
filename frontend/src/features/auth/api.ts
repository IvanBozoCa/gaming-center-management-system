import { apiRequest } from "../../lib/http";

import type {
  CurrentUserResponse,
  LoginCredentials,
  TokenResponse,
} from "./types";

export async function login(
  credentials: LoginCredentials,
): Promise<TokenResponse> {
  const formData =
    new URLSearchParams();

  formData.set(
    "username",
    credentials.username,
  );

  formData.set(
    "password",
    credentials.password,
  );

  return apiRequest<TokenResponse>(
    "/auth/login",
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/x-www-form-urlencoded",
      },
      body: formData,
    },
  );
}

export function getCurrentUser(
  token: string,
): Promise<CurrentUserResponse> {
  return apiRequest<CurrentUserResponse>(
    "/auth/me",
    {
      token,
    },
  );
}