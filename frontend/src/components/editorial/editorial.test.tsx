import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Citation } from "./Citation";
import { StampSheet } from "./StampSheet";

describe("StampSheet", () => {
  it("starts with a plain signup link and carries chosen genres in the query", async () => {
    const user = userEvent.setup();
    render(<StampSheet />);

    expect(screen.getByRole("link", { name: "Start my edition" })).toHaveAttribute(
      "href",
      "/subscribe",
    );

    await user.click(screen.getByRole("checkbox", { name: /AI/ }));
    await user.click(screen.getByRole("checkbox", { name: /Sports/ }));

    expect(screen.getByRole("link", { name: "Start my edition" })).toHaveAttribute(
      "href",
      "/subscribe?genres=ai,sports",
    );
    expect(screen.getByText("2 genres chosen.")).toBeInTheDocument();
  });

  it("offers only the genres that are switched on", () => {
    render(<StampSheet />);

    expect(screen.getAllByRole("checkbox")).toHaveLength(5);
    expect(screen.queryByRole("checkbox", { name: /Music/ })).not.toBeInTheDocument();
  });
});

describe("Citation", () => {
  it("opens a source card on click and closes it on Escape", async () => {
    const user = userEvent.setup();
    render(<Citation n={2} source="Example Desk" time="5:40 AM IST" sample />);

    const marker = screen.getByRole("button", { name: "Source 2: Example Desk" });
    expect(marker).toHaveAttribute("aria-expanded", "false");

    await user.click(marker);
    expect(screen.getByRole("dialog")).toHaveTextContent("Example Desk");
    expect(screen.getByRole("dialog")).toHaveTextContent("Sample source. Not a real link.");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
