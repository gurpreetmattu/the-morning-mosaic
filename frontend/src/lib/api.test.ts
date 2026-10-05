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

  it("uses FastAPI's string detail", () => {
    expect(new ApiError(401, { detail: "Sign in required." }).message).toBe("Sign in required.");
  });

  it("never shows a validation error list", () => {
    const error = new ApiError(422, { detail: [{ loc: ["body", "email"], msg: "bad" }] });
    expect(error.message).toBe("Please check the details you entered and try again.");
  });

  it("explains rate limiting", () => {
    expect(new ApiError(429, null).message).toBe(
      "Too many attempts. Please wait a few minutes and try again.",
    );
  });

  it("falls back to a generic message for server errors and non-object bodies", () => {
    const generic = "Something went wrong on our side. Please try again in a moment.";
    expect(new ApiError(500, {}).message).toBe(generic);
    expect(new ApiError(502, "upstream unavailable").message).toBe(generic);
  });
});
