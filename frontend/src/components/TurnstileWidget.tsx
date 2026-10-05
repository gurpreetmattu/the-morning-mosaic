"use client";

import { useEffect, useId, useRef, useState } from "react";

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement,
        options: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback": () => void;
          "error-callback": () => void;
        },
      ) => string;
      reset: (widgetId: string) => void;
      remove: (widgetId: string) => void;
    };
  }
}

let scriptPromise: Promise<void> | null = null;

function loadTurnstileScript(): Promise<void> {
  scriptPromise ??= new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
    if (existing) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("failed to load Turnstile"));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

/**
 * Cloudflare's bot check on signup (CLAUDE.md). Renders nothing if no site
 * key is configured — the backend already treats a missing secret as "skip
 * outside prod, refuse in prod" (app/api/security.py:verify_turnstile), so a
 * dev environment with no Cloudflare account still has a working signup form.
 */
export function TurnstileWidget({
  onToken,
  resetKey = 0,
}: {
  /** Called with a fresh token, or "" once the token expired or the check failed. */
  onToken: (token: string) => void;
  /** Change this after each submit: a Turnstile token works once and expires in minutes. */
  resetKey?: number;
}) {
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  const containerId = useId();
  const widgetId = useRef<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (resetKey > 0 && widgetId.current && window.turnstile) {
      window.turnstile.reset(widgetId.current);
    }
  }, [resetKey]);

  useEffect(() => {
    if (!siteKey) return;
    let cancelled = false;

    loadTurnstileScript()
      .then(() => {
        if (cancelled) return;
        const container = document.getElementById(containerId);
        if (!container || !window.turnstile) return;
        widgetId.current = window.turnstile.render(container, {
          sitekey: siteKey,
          callback: onToken,
          "expired-callback": () => onToken(""),
          "error-callback": () => onToken(""),
        });
      })
      .catch(() => {
        // Let a later render retry the script, and tell the reader why signup will be refused.
        scriptPromise = null;
        if (!cancelled) setLoadFailed(true);
      });

    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) {
        window.turnstile.remove(widgetId.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onToken is stable from the caller
  }, [siteKey, containerId]);

  if (!siteKey) return null;
  return (
    <>
      <div id={containerId} className="mb-4" />
      {loadFailed && (
        <p role="alert" className="font-gothic mb-4 text-sm text-danger">
          The spam check couldn&rsquo;t load. Check your connection or any content blocker, then
          reload this page.
        </p>
      )}
    </>
  );
}
