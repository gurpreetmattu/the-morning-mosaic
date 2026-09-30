import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import StatusPage from "./page";

function stubStatusFetch(body: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok, json: async () => body })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StatusPage", () => {
  it("shows operational when nothing is degraded", async () => {
    stubStatusFetch({ degraded: false, message: null, updated_at: null });

    render(await StatusPage());

    expect(screen.getByText(/All systems operational/)).toBeInTheDocument();
  });

  it("shows the real incident message when degraded", async () => {
    stubStatusFetch({
      degraded: true,
      message: "Emails are delayed; we're on it.",
      updated_at: "2026-10-05T06:00:00Z",
    });

    render(await StatusPage());

    expect(screen.getByText("Emails are delayed; we're on it.")).toBeInTheDocument();
    expect(screen.queryByText(/All systems operational/)).not.toBeInTheDocument();
  });

  it("falls back to a generic message when degraded with none given", async () => {
    stubStatusFetch({ degraded: true, message: null, updated_at: "2026-10-05T06:00:00Z" });

    render(await StatusPage());

    expect(screen.getByText(/aware of an issue/)).toBeInTheDocument();
  });

  it("shows an error rather than a blank page when the fetch fails", async () => {
    stubStatusFetch(null, false);

    render(await StatusPage());

    expect(screen.getByText(/couldn.t load the current status/)).toBeInTheDocument();
  });
});
