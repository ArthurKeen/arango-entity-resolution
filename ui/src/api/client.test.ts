import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  AUTH_TOKEN_STORAGE_KEY,
  fetchApi,
  getAuthToken,
  setAuthToken,
} from "./client";

describe("API authentication", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("keeps the token in session storage", () => {
    setAuthToken("  secret-token  ");

    expect(getAuthToken()).toBe("secret-token");
    expect(sessionStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe("secret-token");

    setAuthToken("");
    expect(getAuthToken()).toBeNull();
  });

  it("sends the configured token as a bearer credential", async () => {
    setAuthToken("secret-token");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchApi("/api/health");

    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.headers).toMatchObject({
      Authorization: "Bearer secret-token",
    });
  });
});
