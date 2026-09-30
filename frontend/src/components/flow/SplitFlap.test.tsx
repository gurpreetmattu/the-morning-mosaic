import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { SplitFlap } from "./SplitFlap";

const cells = (container: HTMLElement) => [...container.querySelectorAll(".flap")];
const flipped = (container: HTMLElement) =>
  cells(container)
    .filter((el) => el.classList.contains("flap-anim"))
    .map((el) => el.textContent);

describe("SplitFlap", () => {
  it("shows one cell per character and flips nothing on first render", () => {
    const { container } = render(<SplitFlap text="7:00 AM IST" />);

    expect(cells(container)).toHaveLength(11);
    expect(flipped(container)).toEqual([]);
  });

  it("is decorative: hidden from assistive technology", () => {
    const { container } = render(<SplitFlap text="7:00 AM IST" />);

    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("flips only the characters that changed", () => {
    const { container, rerender } = render(<SplitFlap text="7:00 AM IST" />);

    rerender(<SplitFlap text="7:30 AM IST" />);

    expect(flipped(container)).toEqual(["3"]);
    expect(
      cells(container)
        .map((el) => el.textContent?.replace(" ", " "))
        .join(""),
    ).toBe("7:30 AM IST");
  });

  it("flips every digit that differs when the hour changes too", () => {
    const { container, rerender } = render(<SplitFlap text="7:30 AM IST" />);

    rerender(<SplitFlap text="8:00 AM IST" />);

    expect(flipped(container)).toEqual(["8", "0"]);
  });
});
