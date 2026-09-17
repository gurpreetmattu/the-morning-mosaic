import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockFetch } from "@/lib/test-fetch";
import type {
  CorrectionSummary,
  NoticeBatchSummary,
  RunSummary,
  StuckDelivery,
  WithdrawalSummary,
} from "@/lib/types";
import AdminPage from "./page";

const RUNS: RunSummary[] = [
  {
    id: "r1",
    job: "build",
    edition_date: "2026-10-05",
    status: "succeeded",
    started_at: "2026-10-05T04:15:00Z",
    finished_at: "2026-10-05T04:20:00Z",
    deadline_at: null,
    detail: null,
  },
];

const STUCK: StuckDelivery[] = [];
const NOTICES: NoticeBatchSummary[] = [
  {
    edition_date: "2026-10-05",
    status: "held",
    recipient_count: 12,
    expires_at: "2026-10-05T06:30:00Z",
    decided_at: null,
    decided_by: null,
  },
];
const WITHDRAWALS: WithdrawalSummary[] = [];
const CORRECTIONS: CorrectionSummary[] = [];

function dashboardRoutes(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    "/admin/api/me": { body: { email: "owner@example.com" } },
    "/admin/api/runs": { body: RUNS },
    "/admin/api/deliveries/stuck": { body: STUCK },
    "/admin/api/notices": { body: NOTICES },
    "/admin/api/withdrawals": { body: WITHDRAWALS },
    "/admin/api/corrections": { body: CORRECTIONS },
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AdminPage, signed out", () => {
  it("shows the sign-in form", async () => {
    mockFetch({ "/admin/api/me": { status: 401, body: { message: "Not signed in." } } });
    render(<AdminPage />);

    expect(await screen.findByText("Admin sign-in")).toBeInTheDocument();
  });

  it("sends a magic link", async () => {
    mockFetch({
      "/admin/api/me": { status: 401, body: { message: "Not signed in." } },
      "/admin/api/login": { body: { status: "sent", message: "Check your email." } },
    });
    render(<AdminPage />);
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Email"), "owner@example.com");
    await user.click(screen.getByRole("button", { name: "Send sign-in link" }));

    expect(await screen.findByText("Check your email.")).toBeInTheDocument();
  });
});

describe("AdminPage, signed in", () => {
  it("shows the loaded dashboard data", async () => {
    mockFetch(dashboardRoutes());
    render(<AdminPage />);

    expect(await screen.findByText("build")).toBeInTheDocument();
    expect(screen.getByText("None flagged.")).toBeInTheDocument();
    expect(screen.getByText(/2026-10-05 — held \(12 recipients\)/)).toBeInTheDocument();
  });

  it("shows a dashboard-load error rather than a blank page", async () => {
    mockFetch(dashboardRoutes({ "/admin/api/runs": { status: 500, body: { message: "boom" } } }));
    render(<AdminPage />);

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("approves a held notice batch", async () => {
    const { fetchMock } = mockFetch(dashboardRoutes());
    render(<AdminPage />);
    const user = userEvent.setup();

    await screen.findByRole("button", { name: "Approve" });
    fetchMock.mockImplementationOnce(async () => ({ ok: true, status: 200, text: async () => "" }));
    await user.click(screen.getByRole("button", { name: "Approve" }));

    const approveCall = fetchMock.mock.calls.find(([path]) =>
      String(path).includes("/admin/api/notices/2026-10-05/approve"),
    );
    expect(approveCall).toBeDefined();
  });

  it("submits a story withdrawal with its reason", async () => {
    const { fetchMock } = mockFetch(dashboardRoutes());
    render(<AdminPage />);
    const user = userEvent.setup();

    await screen.findByText("Admin dashboard");
    await user.type(screen.getByLabelText("Story ID", { selector: "#story-id" }), "story-123");
    await user.type(screen.getByLabelText("Reason"), "Facts changed after publication.");
    fetchMock.mockImplementationOnce(async () => ({ ok: true, status: 200, text: async () => "" }));
    await user.click(screen.getByRole("button", { name: "Withdraw" }));

    const withdrawCall = fetchMock.mock.calls.find(([path]) =>
      String(path).includes("/admin/api/stories/story-123/withdraw"),
    );
    expect(withdrawCall).toBeDefined();
    expect(JSON.parse(String(withdrawCall![1].body))).toEqual({
      reason: "Facts changed after publication.",
    });
    // The form clears once the withdrawal succeeds.
    expect(
      (screen.getByLabelText("Story ID", { selector: "#story-id" }) as HTMLInputElement).value,
    ).toBe("");
  });

  it("submits a correction with its description", async () => {
    const { fetchMock } = mockFetch(dashboardRoutes());
    render(<AdminPage />);
    const user = userEvent.setup();

    await screen.findByText("Admin dashboard");
    await user.type(screen.getByLabelText("Story ID", { selector: "#correction-story-id" }), "s-9");
    await user.type(
      screen.getByLabelText("What was wrong, and what's correct"),
      "The figure was wrong.",
    );
    fetchMock.mockImplementationOnce(async () => ({ ok: true, status: 200, text: async () => "" }));
    await user.click(screen.getByRole("button", { name: "Record correction" }));

    const correctCall = fetchMock.mock.calls.find(([path]) =>
      String(path).includes("/admin/api/stories/s-9/correct"),
    );
    expect(correctCall).toBeDefined();
    expect(JSON.parse(String(correctCall![1].body))).toEqual({
      description: "The figure was wrong.",
    });
  });

  it("shows no withdraw/suppress controls once a notice is no longer held", async () => {
    mockFetch(
      dashboardRoutes({
        "/admin/api/notices": {
          body: [{ ...NOTICES[0], status: "approved" }],
        },
      }),
    );
    render(<AdminPage />);

    await screen.findByText(/2026-10-05 — approved/);
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suppress" })).not.toBeInTheDocument();
  });
});
