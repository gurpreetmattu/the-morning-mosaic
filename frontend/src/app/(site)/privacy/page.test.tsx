import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import PrivacyPage from "./page";

function stubConfigFetch(body: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok, json: async () => body })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const REAL_CONFIG = {
  policy_operator_name: "The Morning Mosaic",
  policy_version: "2026-10-16",
  policy_contact_email: "privacy@example.com",
};

describe("PrivacyPage", () => {
  it("shows the operator name, policy version and contact email from /api/config", async () => {
    stubConfigFetch(REAL_CONFIG);

    render(await PrivacyPage());

    expect(screen.getByText(/Applies to The Morning Mosaic/)).toBeInTheDocument();
    expect(screen.getByText(/Last updated: 2026-10-16/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "privacy@example.com" })).toHaveAttribute(
      "href",
      "mailto:privacy@example.com",
    );
  });

  it("shows no address and no fake version when the config fetch fails", async () => {
    stubConfigFetch(null, false);

    const { container } = render(await PrivacyPage());

    expect(screen.getByText(/Applies to The Morning Mosaic/)).toBeInTheDocument();
    expect(screen.getByText(/contact address could not be loaded/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /@/ })).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Last updated/);
    expect(container.textContent).not.toMatch(/unavailable/i);
    // No personal address is baked into the page.
    expect(container.textContent).not.toMatch(/gurpreet/i);
  });

  it("has no bracketed placeholder text", async () => {
    stubConfigFetch(REAL_CONFIG);

    const { container } = render(await PrivacyPage());

    expect(container.textContent).not.toMatch(/\[.*\]/);
  });

  it("says plainly that it has not had legal review", async () => {
    stubConfigFetch(REAL_CONFIG);

    render(await PrivacyPage());

    expect(screen.getByText(/has not yet been reviewed by a lawyer/)).toBeInTheDocument();
  });

  it("discloses cookies, local storage and the services that handle data", async () => {
    stubConfigFetch(REAL_CONFIG);

    render(await PrivacyPage());

    expect(screen.getByRole("heading", { name: /Cookies and what we store/ })).toBeInTheDocument();
    expect(screen.getByText(/do not use analytics or advertising trackers/)).toBeInTheDocument();
    for (const name of ["Google", "Neon", "Cloudflare Turnstile", "OpenWeatherMap"]) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
  });
});
