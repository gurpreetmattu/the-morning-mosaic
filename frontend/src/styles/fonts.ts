// Self-hosted, Latin-only fonts, served from this origin (no remote fonts).
//
// Loaded through next/font/local rather than plain @font-face so each family gets
// an automatically metric-adjusted fallback (size-adjust / ascent / descent
// overrides against Times New Roman or Arial). Without that, the swap from the
// fallback to the web font reflowed the landing page: Lighthouse measured a
// layout shift of 0.145 against the 0.05 budget in DESIGN.md section 13.
//
// `variable` exposes each family as a CSS custom property; design/tokens.json
// builds the --font-* tokens from these. Nothing is preloaded: with metric-matched
// fallbacks the swap costs no layout shift, and Lighthouse showed preloading five
// fonts delayed the render-blocking stylesheet (FCP/LCP 2.1 s -> 2.8 s on mobile).
// next/font needs literal paths, hence no shared prefix constant.
import localFont from "next/font/local";

export const masthead = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/abril-fatface/files/abril-fatface-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
  ],
  variable: "--nf-masthead",
  display: "swap",
  adjustFontFallback: "Times New Roman",
  fallback: ["Georgia", "serif"],
  preload: false,
});

export const headline = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/old-standard-tt/files/old-standard-tt-latin-400-italic.woff2",
      weight: "400",
      style: "italic",
    },
    {
      path: "../../node_modules/@fontsource/old-standard-tt/files/old-standard-tt-latin-700-normal.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--nf-headline",
  display: "swap",
  adjustFontFallback: "Times New Roman",
  fallback: ["Georgia", "serif"],
  preload: false,
});

export const body = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/libre-caslon-text/files/libre-caslon-text-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../node_modules/@fontsource/libre-caslon-text/files/libre-caslon-text-latin-400-italic.woff2",
      weight: "400",
      style: "italic",
    },
    {
      path: "../../node_modules/@fontsource/libre-caslon-text/files/libre-caslon-text-latin-700-normal.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--nf-body",
  display: "swap",
  adjustFontFallback: "Times New Roman",
  fallback: ["Georgia", "serif"],
  preload: false,
});

export const flag = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/alfa-slab-one/files/alfa-slab-one-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
  ],
  variable: "--nf-flag",
  display: "swap",
  adjustFontFallback: "Times New Roman",
  fallback: ["Rockwell", "serif"],
  preload: false,
});

export const ui = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/libre-franklin/files/libre-franklin-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
    // 600 is deliberately not loaded (font budget); the browser uses 700 for it.
    {
      path: "../../node_modules/@fontsource/libre-franklin/files/libre-franklin-latin-700-normal.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--nf-ui",
  display: "swap",
  adjustFontFallback: "Arial",
  fallback: ["Arial", "sans-serif"],
  preload: false,
});

export const mono = localFont({
  src: [
    {
      path: "../../node_modules/@fontsource/courier-prime/files/courier-prime-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../node_modules/@fontsource/courier-prime/files/courier-prime-latin-700-normal.woff2",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--nf-mono",
  display: "swap",
  adjustFontFallback: "Arial",
  fallback: ["ui-monospace", "Courier New", "monospace"],
  preload: false,
});

/** Class names that declare every font variable; put them on <html>. */
export const fontVariables = [masthead, headline, body, flag, ui, mono]
  .map((font) => font.variable)
  .join(" ");
