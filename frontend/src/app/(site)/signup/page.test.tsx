import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockFetch } from "@/lib/test-fetch";
import type { SiteConfig } from "@/lib/types";
import SignupPage from "./page";

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
  policy_contact_email: "gurpreetsinghmattu2002@gmail.com",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SignupPage", () => {
  it("loads the form from /api/config", async () => {
    mockFetch({ "/api/config": { body: CONFIG } });
    render(<SignupPage />);

    expect(await screen.findByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByText("Mumbai, Maharashtra")).toBeInTheDocument();
    expect(screen.getByText("India")).toBeInTheDocument();
    expect(screen.getByText("Sports")).toBeInTheDocument();
  });

  it("shows an error notice when the config fails to load", async () => {
    mockFetch({ "/api/config": { status: 500, body: { message: "boom" } } });
    render(<SignupPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't load the signup form.",
    );
  });

  describe("once loaded", () => {
    beforeEach(async () => {
      mockFetch({ "/api/config": { body: CONFIG } });
      render(<SignupPage />);
      await screen.findByLabelText("Name");
    });

    it("refuses to submit with no genre chosen", async () => {
      const user = userEvent.setup();
      await user.type(screen.getByLabelText("Name"), "Asha");
      await user.type(screen.getByLabelText("Email"), "asha@example.com");
      await user.click(screen.getByLabelText(/confirm I am 18/));

      await user.click(screen.getByRole("button", { name: "Sign up" }));

      expect(await screen.findByRole("alert")).toHaveTextContent("Choose at least one genre.");
    });

    it("refuses to submit without confirming age", async () => {
      const user = userEvent.setup();
      await user.type(screen.getByLabelText("Name"), "Asha");
      await user.type(screen.getByLabelText("Email"), "asha@example.com");
      await user.click(screen.getByLabelText("India"));

      await user.click(screen.getByRole("button", { name: "Sign up" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "This service is for readers aged 18 and over.",
      );
    });

    it("toggling a genre twice leaves it unselected", async () => {
      const user = userEvent.setup();
      const india = screen.getByLabelText("India") as HTMLInputElement;

      await user.click(india);
      expect(india.checked).toBe(true);
      await user.click(india);
      expect(india.checked).toBe(false);
    });

    it("submits the expected payload and shows the confirmation", async () => {
      const { fetchMock } = mockFetch({
        "/api/config": { body: CONFIG },
        "/api/signup": { body: { status: "pending", message: "Check your inbox." } },
      });
      const user = userEvent.setup();

      await user.type(screen.getByLabelText("Name"), "Asha");
      await user.type(screen.getByLabelText("Email"), "asha@example.com");
      await user.click(screen.getByLabelText("India"));
      await user.click(screen.getByLabelText(/confirm I am 18/));
      await user.click(screen.getByRole("button", { name: "Sign up" }));

      expect(await screen.findByText("Check your inbox.")).toBeInTheDocument();
      expect(screen.getByText("Check your email")).toBeInTheDocument();

      const signupCall = fetchMock.mock.calls.find(([path]) => path === "/api/signup");
      expect(signupCall).toBeDefined();
      const payload = JSON.parse(String(signupCall![1].body));
      expect(payload).toMatchObject({
        name: "Asha",
        email: "asha@example.com",
        genres: ["india"],
        age_confirmed: true,
      });
      // No Turnstile site key is configured in the test env, so the widget
      // renders nothing and the field is simply absent, not sent as null.
      expect("turnstile_token" in payload).toBe(false);
    });

    it("shows a waitlisted heading when the backend waitlists the signup", async () => {
      mockFetch({
        "/api/config": { body: CONFIG },
        "/api/signup": { body: { status: "waitlisted", message: "You're on the list." } },
      });
      const user = userEvent.setup();

      await user.type(screen.getByLabelText("Name"), "Asha");
      await user.type(screen.getByLabelText("Email"), "asha@example.com");
      await user.click(screen.getByLabelText("India"));
      await user.click(screen.getByLabelText(/confirm I am 18/));
      await user.click(screen.getByRole("button", { name: "Sign up" }));

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

      await user.type(screen.getByLabelText("Name"), "Asha");
      await user.type(screen.getByLabelText("Email"), "asha@example.com");
      await user.click(screen.getByLabelText("India"));
      await user.click(screen.getByLabelText(/confirm I am 18/));
      await user.click(screen.getByRole("button", { name: "Sign up" }));

      expect(await screen.findByRole("alert")).toHaveTextContent("Choose a city from the list.");
    });
  });
});
