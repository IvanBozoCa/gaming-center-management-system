import { config } from "./config";

interface ApiErrorPayload {
  detail?: string;
}

interface ApiRequestOptions
  extends RequestInit {
  token?: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(
    status: number,
    message: string,
  ) {
    super(message);

    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    token,
    headers,
    ...requestOptions
  } = options;

  const requestHeaders =
    new Headers(headers);

  requestHeaders.set(
    "Accept",
    "application/json",
  );

  if (token) {
    requestHeaders.set(
      "Authorization",
      `Bearer ${token}`,
    );
  }

  const response = await fetch(
    `${config.apiBaseUrl}${path}`,
    {
      ...requestOptions,
      headers: requestHeaders,
    },
  );

  if (!response.ok) {
    let message =
      `Request failed with status `
      + response.status;

    try {
      const payload =
        await response.json() as ApiErrorPayload;

      if (
        typeof payload.detail
        === "string"
      ) {
        message = payload.detail;
      }
    } catch {
      // Response without JSON body.
    }

    throw new ApiError(
      response.status,
      message,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return await response.json() as T;
}