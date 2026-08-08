export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** localStorage key holding the current reviewer's display name (attribution). */
export const REVIEWER_STORAGE_KEY = "er-ui-reviewer";
/** sessionStorage key for the API bearer token; cleared when the tab closes. */
export const AUTH_TOKEN_STORAGE_KEY = "er-ui-auth-token";

export function getAuthToken(): string | null {
  try {
    return sessionStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string): void {
  try {
    const trimmed = token.trim();
    if (trimmed) {
      sessionStorage.setItem(AUTH_TOKEN_STORAGE_KEY, trimmed);
    } else {
      sessionStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    }
  } catch {
    // Storage can be unavailable in hardened/private browser contexts.
  }
}

function reviewerHeader(): Record<string, string> {
  try {
    const name = localStorage.getItem(REVIEWER_STORAGE_KEY);
    return name ? { "X-Reviewer": name } : {};
  } catch {
    return {};
  }
}

function authHeader(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchApi<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = path.startsWith("/api/") ? path : `/api/${path}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...reviewerHeader(),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string; message?: string };
      message = body.detail ?? body.message ?? message;
    } catch {
      // response body wasn't JSON
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
