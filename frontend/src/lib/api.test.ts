import { describe, expect, it } from "vitest";

import { ApiError, parseCookie } from "./api";

describe("parseCookie", () => {
  it("finds a cookie among several", () => {
    expect(parseCookie("a=1; csrf=abc123; b=2", "csrf")).toBe("abc123");
  });

  it("returns null when the cookie is absent", () => {
    expect(parseCookie("a=1; b=2", "csrf")).toBeNull();
  });

  it("decodes a URL-encoded value", () => {
    expect(parseCookie("csrf=a%2Fb%3Dc", "csrf")).toBe("a/b=c");
  });

  it("does not match a cookie whose name is a suffix of another", () => {
    // "admin_csrf" must not satisfy a lookup for "csrf".
    expect(parseCookie("admin_csrf=xyz", "csrf")).toBeNull();
  });

  it("handles a single cookie with no separator", () => {
    expect(parseCookie("csrf=onlyone", "csrf")).toBe("onlyone");
  });
});

describe("ApiError", () => {
  it("uses the backend's message field when present", () => {
    const error = new ApiError(400, { status: "error", message: "Choose a city from the list." });
    expect(error.message).toBe("Choose a city from the list.");
    expect(error.status).toBe(400);
  });

  it("falls back to a generic message when the body has none", () => {
    const error = new ApiError(500, { detail: "boom" });
    expect(error.message).toBe("Request failed with status 500");
  });

  it("falls back when the body isn't an object at all", () => {
    const error = new ApiError(502, "upstream unavailable");
    expect(error.message).toBe("Request failed with status 502");
  });
});
