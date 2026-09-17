import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// Explicit rather than relying on React Testing Library's auto-cleanup,
// which only self-registers when it finds a *global* afterEach — this
// project doesn't turn on Vitest's `globals` option.
afterEach(cleanup);
