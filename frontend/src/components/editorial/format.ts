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
