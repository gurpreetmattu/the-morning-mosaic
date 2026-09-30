"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/**
 * Phone-only bottom bar that appears once the hero has scrolled out of view.
 * `targetId` is the hero element to watch. Content is usable without it.
 */
export function StickyCta({ targetId }: { targetId: string }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const el = document.getElementById(targetId);
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setShow(!entry.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, [targetId]);

  if (!show) return null;
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t-4 border-ink bg-paper-raised p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:hidden">
      <Link
        href="/signup"
        className="font-gothic block min-h-12 border-2 border-ink bg-ink px-5 py-3 text-center text-base font-bold tracking-[0.06em] text-paper uppercase"
      >
        Start my edition
      </Link>
    </div>
  );
}
