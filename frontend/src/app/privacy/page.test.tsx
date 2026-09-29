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
  policy_version: "2026-09-29",
  policy_contact_email: "gurpreetsinghmattu2002@gmail.com",
};

describe("PrivacyPage", () => {
  it("shows the real operator name, policy version, and contact email from /api/config", async () => {
    stubConfigFetch(REAL_CONFIG);

    render(await PrivacyPage());

    expect(screen.getByText(/Applies to The Morning Mosaic/)).toBeInTheDocument();
    expect(screen.getByText(/Last updated: 2026-09-29/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "gurpreetsinghmattu2002@gmail.com" })).toHaveAttribute(
      "href",
      "mailto:gurpreetsinghmattu2002@gmail.com",
    );
  });

  it("falls back gracefully when the config fetch fails, rather than showing a placeholder", async () => {
    stubConfigFetch(null, false);

    render(await PrivacyPage());

    expect(screen.getByText(/Applies to The Morning Mosaic/)).toBeInTheDocument();
    // No bracketed placeholder text survives, even in the fallback path.
    expect(screen.queryByText(/\[.*\]/)).not.toBeInTheDocument();
  });

  it("no longer shows any bracketed placeholder", async () => {
    stubConfigFetch(REAL_CONFIG);

    const { container } = render(await PrivacyPage());

    expect(container.textContent).not.toMatch(/\[.*\]/);
  });
});
