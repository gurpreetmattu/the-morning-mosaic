import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { LiveDate } from "./LiveDate";

afterEach(() => {
  vi.useRealTimers();
});

describe("LiveDate", () => {
  it("shows the current IST date, not a date fixed at build time", () => {
    vi.useFakeTimers({ now: new Date("2026-12-31T20:00:00Z"), toFake: ["Date"] });
    render(<LiveDate />);
    // 20:00 UTC on 31 Dec is already 1 January in India.
    expect(screen.getByText("Friday, 1 January 2027")).toBeInTheDocument();
  });

  it("shows the current year", () => {
    vi.useFakeTimers({ now: new Date("2027-03-01T00:00:00Z"), toFake: ["Date"] });
    render(<LiveDate kind="year" />);
    expect(screen.getByText("2027")).toBeInTheDocument();
  });
});
