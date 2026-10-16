import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";

import { liveDateText } from "./format";
import { LiveDate } from "./LiveDate";

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("LiveDate", () => {
  it("shows the current IST date", () => {
    vi.useFakeTimers({ now: new Date("2026-12-31T20:00:00Z"), toFake: ["Date"] });
    render(<LiveDate initial="stale" />);
    // 20:00 UTC on 31 Dec is already 1 January in India.
    expect(screen.getByText("Friday, 1 January 2027")).toBeInTheDocument();
  });

  it("shows the current year", () => {
    vi.useFakeTimers({ now: new Date("2027-03-01T00:00:00Z"), toFake: ["Date"] });
    render(<LiveDate kind="year" initial="2026" />);
    expect(screen.getByText("2027")).toBeInTheDocument();
  });

  it("replaces a build-time date once the page hydrates days later", async () => {
    // Build: the page is prerendered on 5 October.
    vi.useFakeTimers({ now: new Date("2026-10-05T10:00:00Z"), toFake: ["Date"] });
    const html = renderToString(<LiveDate initial={liveDateText("long")} />);
    expect(html).toContain("Monday, 5 October 2026");

    // A reader opens it on 16 October.
    vi.setSystemTime(new Date("2026-10-16T10:00:00Z"));
    const container = document.createElement("div");
    container.innerHTML = html;
    document.body.appendChild(container);
    await act(async () => {
      hydrateRoot(container, <LiveDate initial="Monday, 5 October 2026" />);
    });

    expect(container.textContent).toBe("Friday, 16 October 2026");
  });
});
