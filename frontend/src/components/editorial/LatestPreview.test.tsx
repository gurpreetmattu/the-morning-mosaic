import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { LatestPreview } from "./LatestPreview";

const latest = {
  edition_date: "2026-10-04",
  edition_number: 5,
  items: [
    { genre: "india", headline: "Corridor cleared", one_liner: "Ministers approved it." },
    { genre: "ai", headline: "Model released", one_liner: "A lab published a model." },
  ],
};

describe("LatestPreview", () => {
  it("shows real headlines, links to the full edition and carries no Sample label", () => {
    render(<LatestPreview latest={latest} />);

    expect(screen.getByRole("heading", { name: "Corridor cleared" })).toBeInTheDocument();
    expect(screen.getByText("Ministers approved it.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Read the full edition/ })).toHaveAttribute(
      "href",
      "/editions/2026-10-04",
    );
    expect(screen.queryByText(/sample/i)).not.toBeInTheDocument();
  });
});
