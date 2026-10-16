import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockFetch } from "@/lib/test-fetch";
import type { MeResponse, SiteConfig } from "@/lib/types";
import PreferencesPage from "./page";

const CONFIG: SiteConfig = {
  genres: [
    { key: "india", display_name: "India", blurb: "" },
    { key: "sports", display_name: "Sports", blurb: "" },
  ],
  cities: [{ id: "mumbai", name: "Mumbai", state: "Maharashtra" }],
  delivery_slots: ["06:00:00", "07:00:00"],
  frequencies: ["daily", "weekdays"],
  edition_preferences: ["india", "mixed", "global"],
  policy_operator_name: "The Morning Mosaic",
  policy_version: "2026-09-29",
  policy_contact_email: "privacy@example.com",
};

const ME: MeResponse = {
  email: "asha@example.com",
  name: "Asha",
  city_id: "mumbai",
  status: "active",
  delivery_slot: "07:00:00",
  frequency: "daily",
  edition_preference: "mixed",
  language: "en",
  genres: ["india"],
  keywords: ["isro"],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PreferencesPage, server trouble", () => {
  it("offers a retry instead of the sign-in form when the backend fails", async () => {
    mockFetch({
      "/api/me": { status: 500, body: {} },
      "/api/config": { body: CONFIG },
    });
    render(<PreferencesPage />);

    expect(await screen.findByText(/couldn.t load your subscription/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });
});

describe("PreferencesPage, signed out", () => {
  it("asks for an email instead of showing the dashboard", async () => {
    mockFetch({
      "/api/me": { status: 401, body: { message: "Not signed in." } },
      "/api/config": { body: CONFIG },
    });
    render(<PreferencesPage />);

    expect(await screen.findByText("Manage your subscription")).toBeInTheDocument();
    expect(screen.queryByText("Your subscription")).not.toBeInTheDocument();
  });

  it("sends a magic link and shows the confirmation", async () => {
    mockFetch({
      "/api/me": { status: 401, body: { message: "Not signed in." } },
      "/api/config": { body: CONFIG },
      "/api/login": { body: { status: "sent", message: "Check your email for a link." } },
    });
    render(<PreferencesPage />);
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Email"), "asha@example.com");
    await user.click(screen.getByRole("button", { name: "Send sign-in link" }));

    expect(await screen.findByText("Check your email for a link.")).toBeInTheDocument();
  });
});

describe("PreferencesPage, signed in", () => {
  it("shows the reader's current preferences", async () => {
    mockFetch({ "/api/me": { body: ME }, "/api/config": { body: CONFIG } });
    render(<PreferencesPage />);

    expect(await screen.findByText(/Signed in as asha@example.com/)).toBeInTheDocument();
    expect((screen.getByRole("checkbox", { name: /India/ }) as HTMLInputElement).checked).toBe(
      true,
    );
    expect((screen.getByRole("checkbox", { name: /Sports/ }) as HTMLInputElement).checked).toBe(
      false,
    );
  });

  it("saves the edited genres and keywords", async () => {
    const { fetchMock } = mockFetch({
      "/api/me": { body: ME },
      "/api/config": { body: CONFIG },
    });
    render(<PreferencesPage />);
    const user = userEvent.setup();

    await screen.findByText(/Signed in as/);
    await user.click(screen.getByRole("checkbox", { name: /Sports/ }));

    // The PATCH response feeds straight back into the form.
    fetchMock.mockImplementationOnce(async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ ...ME, genres: ["india", "sports"] }),
    }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    const patchCall = fetchMock.mock.calls.find(
      ([path, init]) => path === "/api/me" && init?.method === "PATCH",
    );
    const payload = JSON.parse(String(patchCall![1].body));
    expect(payload.genres.sort()).toEqual(["india", "sports"]);
    expect(payload.keywords).toEqual(["isro"]);
  });

  it("toggles pause and resume", async () => {
    const { fetchMock } = mockFetch({
      "/api/me": { body: ME },
      "/api/config": { body: CONFIG },
    });
    render(<PreferencesPage />);
    const user = userEvent.setup();

    await screen.findByText(/Signed in as/);
    fetchMock.mockImplementationOnce(async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ ...ME, status: "paused" }),
    }));
    await user.click(screen.getByRole("button", { name: "Pause delivery" }));

    expect(await screen.findByText("Delivery paused.")).toBeInTheDocument();
    expect(screen.getByText(/· Paused/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume delivery" })).toBeInTheDocument();
    const pauseCall = fetchMock.mock.calls.find(([path]) => path === "/api/me/pause");
    expect(pauseCall).toBeDefined();
  });

  it("refuses to save with no genres or no city, without calling the backend", async () => {
    const { fetchMock } = mockFetch({
      "/api/me": { body: { ...ME, genres: [] } },
      "/api/config": { body: CONFIG },
    });
    render(<PreferencesPage />);
    const user = userEvent.setup();

    await screen.findByText(/Signed in as/);
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Choose at least one genre.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
  });

  it("asks for confirmation before deleting the account", async () => {
    mockFetch({ "/api/me": { body: ME }, "/api/config": { body: CONFIG } });
    render(<PreferencesPage />);
    const user = userEvent.setup();

    await screen.findByText(/Signed in as/);
    expect(screen.queryByText("Confirm delete")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete my account" }));

    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeInTheDocument();
    expect(screen.getByText("This removes your personal data permanently.")).toBeInTheDocument();
  });

  it("shows a save error from the backend rather than a generic one", async () => {
    const { fetchMock } = mockFetch({
      "/api/me": { body: ME },
      "/api/config": { body: CONFIG },
    });
    render(<PreferencesPage />);
    const user = userEvent.setup();

    await screen.findByText(/Signed in as/);
    fetchMock.mockImplementationOnce(async () => ({
      ok: false,
      status: 400,
      text: async () => JSON.stringify({ message: "That city is not on the list." }),
    }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("That city is not on the list.")).toBeInTheDocument();
  });
});
