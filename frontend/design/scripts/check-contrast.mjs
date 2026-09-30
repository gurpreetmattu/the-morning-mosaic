// WCAG contrast check over every token pair (DESIGN.md §20). Exits 1 on failure.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const t = JSON.parse(readFileSync(join(root, "tokens.json"), "utf8"));

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = c.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
// oklab-ish mix approximated in sRGB for the dark tint check
const mix = (a, b, pct) =>
  "#" +
  [1, 3, 5]
    .map((i) => {
      const v = Math.round(
        parseInt(a.slice(i, i + 2), 16) * pct + parseInt(b.slice(i, i + 2), 16) * (1 - pct),
      );
      return v.toString(16).padStart(2, "0");
    })
    .join("");

const checks = [];
for (const mode of ["light", "dark"]) {
  const c = t.colors[mode];
  for (const fg of ["ink", "ink-soft", "ink-muted", "press-red", "danger", "success", "warning"])
    for (const bg of ["paper", "paper-raised", "paper-sunk"])
      checks.push([`${mode}: ${fg} on ${bg}`, c[fg], c[bg], 4.5]);
  for (const [slug, g] of Object.entries(t.genres)) {
    const accent = mode === "light" ? g.accent : g.accentDark;
    const tint = mode === "light" ? g.tint : mix(g.accentDark, c.paper, 0.18);
    checks.push([`${mode}: ${slug} accent on paper`, accent, c.paper, 4.5]);
    checks.push([`${mode}: ${slug} accent on tint`, accent, tint, 4.5]);
    checks.push([`${mode}: ink on ${slug} tint`, c.ink, tint, 4.5]);
  }
}
let failed = 0;
for (const [name, fg, bg, min] of checks) {
  const r = ratio(fg, bg);
  if (r < min) {
    failed++;
    console.log(`FAIL ${r.toFixed(2)} < ${min}  ${name}  (${fg} on ${bg})`);
  }
}
console.log(`${checks.length - failed}/${checks.length} pairs pass`);
process.exit(failed ? 1 : 0);
