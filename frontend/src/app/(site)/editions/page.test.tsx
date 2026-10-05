import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ArchiveIndexPage from "./page";

function stubArchive(body: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok, json: async () => body })),
  );
}

const render_ = async (before?: string) =>
  render(await ArchiveIndexPage({ searchParams: Promise.resolve({ before }) }));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ArchiveIndexPage", () => {
  it("groups editions by month and links each to /editions/<date>", async () => {
    stubArchive({
      editions: [
        { edition_date: "2026-10-02", edition_number: 3 },
        { edition_date: "2026-09-30", edition_number: 2 },
        { edition_date: "2026-09-29", edition_number: 1 },
      ],
      has_more: false,
    });

    await render_();

    expect(screen.getByRole("heading", { name: "October 2026" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "September 2026" })).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Wednesday, 30 September 2026/ });
    expect(link).toHaveAttribute("href", "/editions/2026-09-30");
    expect(link).toHaveTextContent("No. 2");
  });

  it("offers older editions using the oldest date shown", async () => {
    stubArchive({
      editions: [{ edition_date: "2026-09-29", edition_number: 1 }],
      has_more: true,
    });

    await render_();

    expect(screen.getByRole("link", { name: /Older editions/ })).toHaveAttribute(
      "href",
      "/editions?before=2026-09-29",
    );
  });

  it("shows a friendly note when nothing is published yet", async () => {
    stubArchive({ editions: [], has_more: false });

    await render_();

    expect(screen.getByText(/The presses are warming up/)).toBeInTheDocument();
  });

  it("says the archive is unavailable when the backend is down", async () => {
    stubArchive({}, false);

    await render_();

    expect(screen.getByRole("alert")).toHaveTextContent("The archive is unavailable right now.");
  });
});
