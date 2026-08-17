import { apiRequest } from "../../lib/http";

import type {
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