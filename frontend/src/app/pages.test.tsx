import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import NotFound from "./not-found";
import HowWeReportPage from "./(site)/how-we-report/page";
import SamplePage from "./(landing)/sample/page";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SamplePage", () => {
  it("has a way back to the front page", () => {
    render(<SamplePage />);
    expect(screen.getByRole("link", { name: /Back to the front page/ })).toHaveAttribute(
      "href",
      "/",
    );
  });

  it("is clearly labelled as a sample and never as today's news", () => {
    render(<SamplePage />);

    expect(screen.getByText("Sample")).toBeInTheDocument();
    expect(screen.getByText(/Not today's news/)).toBeInTheDocument();
    // Every story is followed by a numbered source list.
    expect(screen.getByRole("heading", { name: "Sources" })).toBeInTheDocument();
  });
});

describe("HowWeReportPage", () => {
  it("shows the contact email from /api/config", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ policy_contact_email: "privacy@example.com" }),
      })),
    );

    render(await HowWeReportPage());

    expect(screen.getByRole("link", { name: "privacy@example.com" })).toHaveAttribute(
      "href",
      "mailto:privacy@example.com",
    );
    expect(screen.getByRole("heading", { name: "Corrections" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Limits" })).toBeInTheDocument();
  });

  it("still renders when the backend is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, json: async () => ({}) })),
    );

    render(await HowWeReportPage());

    expect(screen.getByRole("heading", { name: "How we report" })).toBeInTheDocument();
  });
});

describe("NotFound", () => {
  it("keeps the masthead and links back to the front page", () => {
    render(<NotFound />);

    expect(screen.getByText("This page went missing.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to the front page/ })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
  });
});
