"use client";

import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";

function currentTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const listeners = new Set<() => void>();
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

/** Morning edition / Late edition switch. The choice is stored in localStorage only. */
export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, currentTheme, () => "light" as Theme);
  const next: Theme = theme === "dark" ? "light" : "dark";

  function toggle() {
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("mm-theme", next);
    } catch {
      // Private mode: the choice just lasts for this page view.
    }
    listeners.forEach((cb) => cb());
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="kicker min-h-11 border-2 border-ink px-3 text-ink hover:bg-paper-sunk"
    >
      {theme === "dark" ? "Switch to Morning edition" : "Switch to Late edition"}
    </button>
  );
}
