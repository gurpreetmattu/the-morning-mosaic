// en-IN formatting helpers; all dates are IST (CLAUDE.md: India only).
const TZ = "Asia/Kolkata";

export function formatLongDate(date: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-IN", {
    timeZone: TZ,
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("weekday")}, ${get("day")} ${get("month")} ${get("year")}`;
}

/** "07:30:00" or "07:30" -> "7:30 AM IST" (slots are always IST, 24h on the wire). */
export function formatSlot(slot: string): string {
  const [h, m] = slot.split(":").map(Number);
  const hour12 = h % 12 === 0 ? 12 : h % 12;
  return `${hour12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"} IST`;
}
