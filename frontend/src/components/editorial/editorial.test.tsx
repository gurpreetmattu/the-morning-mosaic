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
      "/signup",
    );

    await user.click(screen.getByRole("checkbox", { name: /AI/ }));
    await user.click(screen.getByRole("checkbox", { name: /Music/ }));

    expect(screen.getByRole("link", { name: "Start my edition" })).toHaveAttribute(
      "href",
      "/signup?genres=ai,music",
    );
    expect(screen.getByText("2 genres chosen.")).toBeInTheDocument();
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
