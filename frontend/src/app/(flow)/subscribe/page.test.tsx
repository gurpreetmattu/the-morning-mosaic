import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockFetch } from "@/lib/test-fetch";
import type { SiteConfig } from "@/lib/types";
import SubscribePage from "./page";

const CONFIG: SiteConfig = {
  genres: [
    { key: "india", display_name: "India", blurb: "" },
    { key: "sports", display_name: "Sports", blurb: "" },
  ],
  cities: [
    { id: "mumbai", name: "Mumbai", state: "Maharashtra" },
    { id: "delhi", name: "Delhi", state: "Delhi" },
  ],
  delivery_slots: ["06:00:00", "06:30:00", "07:00:00", "07:30:00"],
  frequencies: ["daily", "weekdays"],
  edition_preferences: ["india", "mixed", "global"],
  policy_operator_name: "The Morning Mosaic",
  policy_version: "2026-09-29",
  policy_contact_email: "privacy@example.com",
};

type User = ReturnType<typeof userEvent.setup>;

beforeEach(() => {
  sessionStorage.clear();
  window.history.pushState({}, "", "/subscribe");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const next = (user: User) => user.click(screen.getByRole("button", { name: "Next" }));

async function chooseCity(user: User, typed = "Mum") {
  await user.type(screen.getByLabelText("City"), typed);
  await user.click(await screen.findByRole("option", { name: /Mumbai/ }));
}

/** Genres -> City -> Time, leaving the reader on the "You" step. */
async function reachEmailStep(user: User) {
  await user.click(await screen.findByRole("checkbox", { name: /India/ }));
  await next(user);
  await chooseCity(user);
  await next(user);
  await next(user);
  await screen.findByLabelText("Email");
}

async function fillAndSubmit(user: User, { age = true, consent = true } = {}) {
  await user.type(screen.getByLabelText("Name"), "Asha");
  await user.type(screen.getByLabelText("Email"), "asha@example.com");
  if (age) await user.click(screen.getByLabelText(/confirm I am 18/));
  if (consent) await user.click(screen.getByLabelText(/Email me The Morning Mosaic/));
  await user.click(screen.getByRole("button", { name: "Confirm and subscribe" }));
}

describe("SubscribePage", () => {
  it("loads the genre stamps from /api/config", async () => {
    mockFetch({ "/api/config": { body: CONFIG } });
    render(<SubscribePage />);

    expect(await screen.findByRole("checkbox", { name: /India/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Sports/ })).toBeInTheDocument();
  });

  it("shows an error notice when the config fails to load", async () => {
    mockFetch({ "/api/config": { status: 500, body: { message: "boom" } } });
    render(<SubscribePage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't load the signup form.");
  });

  it("preselects genres passed in the query string", async () => {
    window.history.pushState({}, "", "/subscribe?genres=sports,nonsense");
    mockFetch({ "/api/config": { body: CONFIG } });
    render(<SubscribePage />);

    expect(await screen.findByRole("checkbox", { name: /Sports/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /India/ })).not.toBeChecked();
  });

  describe("steps", () => {
    beforeEach(() => {
      mockFetch({ "/api/config": { body: CONFIG } });
    });

    it("will not leave the genre step with nothing chosen", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      await screen.findByRole("checkbox", { name: /India/ });

      await next(user);

      expect(await screen.findByRole("alert")).toHaveTextContent("Choose at least one genre.");
    });

    it("toggling a genre twice leaves it unselected", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      const india = await screen.findByRole("checkbox", { name: /India/ });

      await user.click(india);
      expect(india).toBeChecked();
      await user.click(india);
      expect(india).not.toBeChecked();
    });

    it("requires a city chosen from the list", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      await user.click(await screen.findByRole("checkbox", { name: /India/ }));
      await next(user);

      await user.type(screen.getByLabelText("City"), "Atlantis");
      await next(user);

      expect(await screen.findByRole("alert")).toHaveTextContent("Pick a city from the list.");
    });

    it("moves focus to the new step heading and keeps entries when going back", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      await user.click(await screen.findByRole("checkbox", { name: /India/ }));
      await next(user);

      expect(
        screen.getByRole("heading", { name: "Where should we check the weather?" }),
      ).toHaveFocus();

      await user.click(screen.getByRole("button", { name: "Back" }));
      expect(screen.getByRole("checkbox", { name: /India/ })).toBeChecked();
    });

    it("updates the Your edition panel as choices are made", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      await user.click(await screen.findByRole("checkbox", { name: /India/ }));
      await next(user);
      await chooseCity(user);

      const panel = screen.getByRole("complementary", { name: "Your edition" });
      expect(panel).toHaveTextContent("India");
      expect(panel).toHaveTextContent("Mumbai");
      expect(panel).toHaveTextContent("7:00 AM IST");
    });

    it("refuses to submit without confirming age", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      await reachEmailStep(user);

      await fillAndSubmit(user, { age: false });

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "This service is for readers aged 18 and over.",
      );
    });

    it("refuses to submit without consent", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      await reachEmailStep(user);

      await fillAndSubmit(user, { consent: false });

      expect(await screen.findByRole("alert")).toHaveTextContent("Please tick the box");
    });

    it("rejects a malformed email before calling the API", async () => {
      const user = userEvent.setup();
      render(<SubscribePage />);
      await reachEmailStep(user);

      await user.type(screen.getByLabelText("Name"), "Asha");
      await user.type(screen.getByLabelText("Email"), "asha-at-example");
      await user.click(screen.getByRole("button", { name: "Confirm and subscribe" }));

      expect(await screen.findByRole("alert")).toHaveTextContent("That email doesn't look right.");
    });
  });

  describe("submitting", () => {
    it("sends the expected payload and shows the check-your-inbox screen", async () => {
      const { fetchMock } = mockFetch({
        "/api/config": { body: CONFIG },
        "/api/signup": { body: { status: "pending", message: "Check your inbox." } },
      });
      const user = userEvent.setup();
      render(<SubscribePage />);
      await reachEmailStep(user);

      await fillAndSubmit(user);

      expect(await screen.findByRole("heading", { name: "Check your inbox" })).toBeInTheDocument();
      const call = fetchMock.mock.calls.find(([path]) => path === "/api/signup");
      expect(call).toBeDefined();
      const payload = JSON.parse(String(call![1].body));
      expect(payload).toMatchObject({
        name: "Asha",
        email: "asha@example.com",
        city_id: "mumbai",
        genres: ["india"],
        delivery_slot: "07:00",
        frequency: "daily",
        edition_preference: "mixed",
        keywords: [],
        age_confirmed: true,
      });
      // No Turnstile site key in the test env, so the field is absent, not null.
      expect("turnstile_token" in payload).toBe(false);
    });

    it("never stores the name or email in sessionStorage", async () => {
      mockFetch({ "/api/config": { body: CONFIG } });
      const user = userEvent.setup();
      render(<SubscribePage />);
      await reachEmailStep(user);
      await user.type(screen.getByLabelText("Name"), "Asha");
      await user.type(screen.getByLabelText("Email"), "asha@example.com");

      const stored = sessionStorage.getItem("mm-subscribe-draft") ?? "";
      expect(stored).toContain("mumbai");
      expect(stored).not.toContain("Asha");
      expect(stored).not.toContain("asha@example.com");
    });

    it("shows a waitlisted heading when the backend waitlists the signup", async () => {
      mockFetch({
        "/api/config": { body: CONFIG },
        "/api/signup": { body: { status: "waitlisted", message: "You're on the list." } },
      });
      const user = userEvent.setup();
      render(<SubscribePage />);
      await reachEmailStep(user);

      await fillAndSubmit(user);

      await waitFor(() => {
        expect(screen.getByText("You're on the waitlist")).toBeInTheDocument();
      });
    });

    it("surfaces the backend's error message when signup fails", async () => {
      mockFetch({
        "/api/config": { body: CONFIG },
        "/api/signup": { status: 400, body: { message: "Choose a city from the list." } },
      });
      const user = userEvent.setup();
      render(<SubscribePage />);
      await reachEmailStep(user);

      await fillAndSubmit(user);

      expect(await screen.findByRole("alert")).toHaveTextContent("Choose a city from the list.");
    });
  });
});
