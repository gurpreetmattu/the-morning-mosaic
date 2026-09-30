# DESIGN.md — The Morning Mosaic (Website)

> **Design direction: Retro Broadsheet ("Newsprint & Spot Ink")**: a vintage print look with newsprint paper, heavy ink, one spot colour per genre, halftone, rubber stamps and postage-stamp genre cards. See §1 and §6.0.
>
> Single source of truth for the website's design. Claude Code: read this file fully before creating or changing any UI. If a request conflicts with this file, follow this file and say so. If this file is silent, choose the option that best fits the Principles in §2 and record the decision in §22 (Decision Log).

Scope: the Next.js website only (marketing, subscribe flow, preference pages, sample and archive pages, trust pages). Newsletter email and A4 PDF templates share the same tokens (§17) but are specified in their own docs.

Environment: everything runs locally (`npm run dev`, FastAPI on localhost, local Postgres, local mail catcher). Nothing in this design depends on any hosted service, third-party script, CDN, analytics or tracker.

---

## 1. Product and Design Vision

**Product.** The Morning Mosaic is a personalized AI newsletter for readers in India. Readers pick from 10 genres (India, Politics, Business, Technology, AI, Sports, Gaming, Bollywood, Hollywood, Music), choose a city and a delivery time between 6:00 and 9:00 AM IST, and receive one newspaper-styled email each morning: masthead, city weather, market strip, a 60-second summary, 4–6 stories per chosen genre, extras (scores, releases, quote of the day) and an A4 PDF. Weekends bring a recap edition.

**What the website must do.**
1. Make the reader understand the product in under 10 seconds.
2. Let them subscribe in under 60 seconds on a phone.
3. Prove, visibly, that the content is grounded and traceable (this is the differentiator, not decoration).
4. Give them full control afterwards (change genres, city, time, pause, unsubscribe) without a login.

**Design direction: Retro Broadsheet ("Newsprint & Spot Ink").**
The site looks like a well-run mid-century newspaper that happens to be interactive: yellowed newsprint paper, heavy black ink, one bold spot colour per section, halftone dots, thick and double rules, rubber stamps and postmarks, postage-stamp genre cards, ticket stubs and split-flap time boards. The retro look is a *printing* aesthetic (letterpress, offset, halftone), not an arcade, VHS or synthwave one. Only the Gaming section borrows pixel styling, locally.

**Emotional targets.** Trustworthy. Nostalgic without being fussy. Tactile. Warm. Precise. Quietly delightful.

**Anti-targets.** Not costume or kitsch: no fake tattered edges, coffee stains, sepia filters over content, faux-antique clutter or "Ye Olde" copy. Not a startup landing page. Not synthwave/neon/CRT. Not a cluttered news portal. Not a 3D showcase. The goal is a 1950s paper run by an efficient modern newsroom, not a themed restaurant.

---

## 2. Design Principles (use these to break ties)

1. **Newspaper first.** Every screen should feel like a page of a well-edited paper: nameplate, ears, rules, columns, kickers, datelines, serif headlines.
2. **Two-ink discipline.** Each view uses paper, black ink and at most one genre spot colour. Press Red is reserved for stamps, ribbons and the "Extra" moments. This constraint is what makes it look printed instead of themed.
3. **Tactile, not skeuomorphic.** Retro devices (block shadows, stamps, perforations, halftone) are flat, crisp CSS/SVG, not photoreal textures or heavy filters.
4. **Trust is visible.** Sources, citations, dates, "how we report" and licence credits are first-class UI, never buried. Rubber stamps like VERIFIED and SAMPLE carry real meaning, never fake authority.
5. **Legibility beats nostalgia.** Textures, misregistration and rotation are allowed only where they cannot harm reading. Body text sits on clean paper.
6. **Restraint over spectacle.** One meaningful animation per screen beats five decorative ones. Motion behaves like a press and a stamp, in stepped, mechanical beats.
7. **Mobile is the primary canvas.** Design at 360px wide first. Most readers will subscribe and read on phones, often on slower networks.
8. **Genres are the personality.** Paper and ink form the frame; each of the 10 genres brings its own spot colour and its own period motif inside that frame.
9. **Honest by construction.** No fake subscriber counts, testimonials, "as seen in" logos, urgency timers or invented stats.
10. **Accessible and fast by default.** WCAG 2.2 AA is the floor; ornaments are SVG/CSS; no third-party assets.
11. **One system.** Website, email and PDF share tokens so they read as one publication.

---

## 3. Audience and Context

- **Who:** English-reading adults in India, mixed technical comfort, interested in staying informed in 5–10 minutes without doomscrolling.
- **Devices:** predominantly Android phones (360–412px wide), some desktop. Assume mid-range hardware and variable 4G.
- **Language:** English (India) in v1. Layouts must tolerate strings up to ~30% longer and leave room for Hindi/Devanagari later (§18).
- **Formats:** Times in IST (`6:30 AM IST`). Dates as `Wednesday, 30 September 2026`. Currency as `₹`. Large numbers in lakh/crore where a reader would expect it (market strip and business copy). Use `en-IN` locale formatting.
- **Trust posture:** many readers are wary of AI-written news. The design must answer "where did this come from?" before they ask.

---

## 4. Brand and Voice

**Name usage.** "The Morning Mosaic" (title case, with "The"). In tight spaces: "Morning Mosaic". Never abbreviate to "TMM" in UI.

**Tagline (primary).** *The morning paper, set to your interests.*

**Supporting line.** Pick your genres. Get one newspaper-style email every morning. Every story cited. Nothing invented.

**Voice.**
- Plain, warm, confident. Short sentences. No hype words ("revolutionary", "supercharge", "game-changing").
- Explain the AI honestly: "AI helps us summarise. Every sentence is checked against its source. If we can't verify a story, we drop it."
- Never anthropomorphise the AI ("our AI thinks…"). Say "we" for the publication.
- Errors are calm and specific, with a next step.
- Vintage flavour is seasoning, not the meal: "Morning Edition", "Stop press" and "Extra!" belong in headings, kickers and stamps. Instructions, errors, consent and legal text stay in plain modern language.

**Microcopy reference.**

| Moment | Copy |
|---|---|
| Primary CTA | Start my edition |
| Secondary CTA | See a sample edition |
| Genre step title | What do you want to read? |
| Genre helper | Pick at least one. Each genre brings 4–6 stories. |
| City step title | Where should we check the weather? |
| Time step title | When should it arrive? |
| Time helper | Choose any time from 6:00 to 9:00 AM IST. |
| Email step title | Where should we send it? |
| Consent | Email me The Morning Mosaic every morning at my chosen time. I can change or stop this any time. |
| Submit | Confirm and subscribe |
| Success | Check your inbox. We've sent a link to confirm. Your first edition arrives after you confirm. |
| Invalid email | That email doesn't look right. Check for typos, like a missing @ or domain. |
| Network error | We couldn't reach the server. Your choices are saved. Try again. |
| Unsubscribe done | You're unsubscribed. No more emails. Changed your mind? Subscribe again any time. |
| Edition delayed (status page) | Today's edition is delayed. We'd rather be late than wrong. |
| 404 | This page went missing. Here's the front page. |

---

## 5. Information Architecture

### 5.1 Sitemap

```
/                          Landing (front page)
/subscribe                 4-step subscribe flow
/subscribe/check-email     Confirmation-sent screen
/confirm/[token]           Email confirmation result
/preferences/[token]       Change genres / city / time / pause
/unsubscribe/[token]       One-click unsubscribe result
/sample                    Rendered sample edition (web version, printable)
/editions                  Archive index
/editions/[date]           A past edition (web version)
/how-we-report             Trust: sources, method, corrections, licensing
/feedback                  Feedback form
/status                    Today's edition status (and apology notices)
/privacy                   Privacy notice
/terms                     Terms
not-found, error           Custom pages
```

### 5.2 Global navigation

- **Desktop:** slim top bar, left-aligned wordmark "The Morning Mosaic", right-aligned links: *Sample · How we report · Archive · Subscribe (button)*. Above it, the dateline bar (§9.1).
- **Mobile:** wordmark + Subscribe button + menu button. Menu opens a full-height sheet with the same links, large tap targets, focus trapped, `Esc` closes.
- Subscribe button is always reachable, but hidden on `/subscribe` itself.
- Footer: About/How we report, Sample, Archive, Status, Feedback, Privacy, Terms, "Built as a solo portfolio project" line, and the text version of the date/edition number.

### 5.3 Core user flows

1. **First-time visitor → subscriber:** Landing → *Start my edition* → 4 steps → check-email → email link → `/confirm/[token]` → done.
2. **Skeptic → convinced:** Landing → trust section → *How we report* → *Sample* → Subscribe.
3. **Subscriber → change preferences:** Email footer link → `/preferences/[token]` → save → inline confirmation.
4. **Subscriber → leave:** Email footer link → `/unsubscribe/[token]` → confirmed (with optional one-tap reason and a resubscribe link).

---

## 6. Design Tokens

Tokens live in `web/design/tokens.json` and are generated into CSS variables, the Tailwind theme and the email/PDF token file (§17). Never hard-code a hex value, font size or spacing value in a component; use a token.

### 6.0 Retro style guide (the rules of the look)

The nine retro devices, and where each is allowed:

| # | Device | What it is | Where it's used | Where it is NOT used |
|---|---|---|---|---|
| 1 | Nameplate and ears | Big masthead with boxed "ears" left and right (weather, motto) | Landing masthead, sample and archive pages | Forms, dense settings pages (compact wordmark only) |
| 2 | Heavy rules | Thick, double, dotted and "column" rules in ink | Everywhere as structure | As decoration around every element |
| 3 | Block shadows | Hard, un-blurred offset shadow (`3px 3px 0`) | Buttons, cards, popovers, edition preview | Text, inputs at rest, anything inside body copy |
| 4 | Halftone | Dot-pattern fills made with CSS radial gradients in the genre spot colour | Genre section backgrounds, image placeholders, hero band | Behind body text at more than 6% visual strength |
| 5 | Stamps and postmarks | Rotated (±2–6°) rubber-stamp badges and circular cancel marks | SAMPLE, VERIFIED, SUBSCRIBED, EXTRA, DROPPED IF UNSURE | Any control label, any text the reader must read to proceed |
| 6 | Perforations and tickets | Notched or perforated edges via CSS/SVG masks | Genre "postage stamp" cards, step tickets, time stubs | Inputs, long text blocks |
| 7 | Misregistration | Spot-colour layer offset 2px behind black display type | Display headings ≥ 40px only | Body text, small headings, buttons |
| 8 | Stepped motion | `steps()` easing for print-like beats (tape, flip, stamp thunk) | Motion inventory in §10 | Anything that must feel instant |
| 9 | Vintage voice | Light period wording ("Morning Edition", "Stop press", "Extra!") | Headings, kickers, stamps | Instructions, errors, legal text (plain language only) |

Hard "no" list for the look: sepia or brown filters over photos or content, torn-paper edges, coffee rings, wood or leather textures, CRT scanlines or flicker, neon glow, chromatic-aberration text, vaporwave gradients, fake wear that lowers contrast.

### 6.1 Neutral colors (newsprint and ink)

| Token | Light ("Morning edition") | Dark ("Late edition") | Use |
|---|---|---|---|
| `--paper` | `#F0E6CB` | `#1A150F` | Page background (newsprint) |
| `--paper-raised` | `#F8F0DC` | `#241D15` | Cards, inputs, popovers |
| `--paper-sunk` | `#E4D8B8` | `#100D09` | Wells, footer, code |
| `--ink` | `#1C1915` | `#F0E4C8` | Primary text, heavy rules, block shadows |
| `--ink-soft` | `#40382C` | `#D2C5A8` | Secondary text |
| `--ink-muted` | `#6A5F4C` | `#A19676` | Captions, metadata (≥ 4.5:1 on paper) |
| `--rule` | `#1C1915` | `#F0E4C8` | Heavy rules |
| `--rule-soft` | `#C9B98F` | `#4A3F30` | Hairlines, dividers |
| `--highlight` | `#F2C94C` | `#6B5514` | Marker-yellow selection, active citation |
| `--press-red` | `#B72A1A` | `#F08A78` | Stamps, ribbons, "Extra" moments only |
| `--danger` | `#A4231A` | `#F2867F` | Errors (always icon + text) |
| `--success` | `#1E6B3A` | `#7FCB9E` | Confirmations (always icon + text) |
| `--warning` | `#7F5600` | `#E8B84A` | Cautions (always icon + text) |

Theme switching: default follows `prefers-color-scheme`; a footer/nav toggle ("Morning edition / Late edition") overrides and stores the choice in `localStorage`. Apply the theme before first paint to avoid a flash. Late edition is the same paper printed at night: dark warm brown-black with cream ink, same rules and stamps.

### 6.2 Genre themes ("spot inks")

Each genre defines a spot-ink accent (for text, icons and rules on paper), a tint (section wash / halftone base), a dark-mode accent, and a period motif (SVG/CSS). Set on a section wrapper as `data-genre="ai"` so components read `--g-accent`, `--g-tint`, `--g-motif`.

| Genre | Slug | Accent (light) | Tint (light) | Accent (dark) | Retro motif |
|---|---|---|---|---|---|
| India | `india` | `#A63F08` | `#F6DCC3` | `#F2A672` | Block-print border with jali lattice |
| Politics | `politics` | `#7A1F3D` | `#EBD0D3` | `#E58AA6` | Campaign-button badges, stars and stripes rule |
| Business | `business` | `#1E5B3A` | `#D6E4CF` | `#7FCB9E` | Engraved banknote guilloche border, ticker tape |
| Technology | `technology` | `#0E6B78` | `#CFE3DF` | `#6CC7D4` | Blueprint graph-paper grid |
| AI | `ai` | `#5B3FA6` | `#DDD5E9` | `#B7A2F0` | Punched paper tape and teleprinter dashes |
| Sports | `sports` | `#1D4ED8` | `#D2DDEE` | `#8FA9F5` | Pennant flags and stadium-ticket stripes |
| Gaming | `gaming` | `#A11A6B` | `#EFD1E0` | `#EE8BC6` | 8-bit pixel-step corners, arcade marquee dots |
| Bollywood | `bollywood` | `#7F5600` | `#F3E0A8` | `#E8B84A` | Hand-painted cinema-poster burst, marigold scallop edge |
| Hollywood | `hollywood` | `#3D4A5C` | `#D9DCDD` | `#A9B7C8` | Marquee light bulbs, film-strip perforations |
| Music | `music` | `#556308` | `#E1E6BC` | `#B5C74E` | Vinyl groove rings, record-sleeve frame |

Rules:
- Accent on `--paper` must meet 4.5:1 for text; verify with the contrast script in §20 and adjust the token, not the component. Dark-mode tints are computed: `color-mix(in oklab, var(--g-accent) 18%, var(--paper))`.
- Genre is never identified by colour alone. Kicker text, motif and icon always accompany the accent.
- Motifs are inline SVG or CSS only (≤ 2 KB each), decorative (`aria-hidden`), and never carry meaning.
- Only one genre spot ink is active inside any section. Never mix two genre accents in one component.
- Outside genre sections (nav, hero, footer) the frame is `--ink` on paper, with `--press-red` for stamps. There is no separate "brand colour".
- Halftone fill recipe: `radial-gradient(circle at center, var(--g-accent) 0 1.2px, transparent 1.6px) 0 0 / 6px 6px`, at ≤ 18% opacity on section backgrounds, ≤ 6% wherever text sits on it.

### 6.3 Typography

Fonts are self-hosted from npm (`@fontsource` / `@fontsource-variable` packages) so the site works offline. Always define fallbacks and `font-display: swap`. Subset to Latin.

| Role | Font | Fallback stack | Notes |
|---|---|---|---|
| Masthead and display | Abril Fatface (400) | `"Playfair Display", Georgia, serif` | Fat Didone poster face; masthead and page H1 only |
| Headlines and subheads | Old Standard TT (700, italic 400) | `Georgia, "Times New Roman", serif` | 19th-century "Modern" newspaper headline face |
| Body / story text | Libre Caslon Text (400, 700, italic 400) | `Georgia, "Times New Roman", serif` | Warm, readable, period-correct |
| Section flags and stamps | Alfa Slab One (400) | `Rockwell, "Courier New", serif` | Very short strings only (≤ 3 words) |
| UI, labels, kickers, buttons | Libre Franklin (400/600/700) | `"Franklin Gothic Medium", "Arial Narrow", Arial, sans-serif` | Classic news gothic; kickers uppercase, tracked |
| Typewriter details | Courier Prime (400) | `"Courier New", monospace` | Datelines, ticket labels, stamp sub-lines; ≥ 14px, never body. (Special Elite dropped: 53 KB against the §13 font budget; see Decision Log) |
| Numerals and data | Courier Prime (400/700) | `ui-monospace, Menlo, monospace` | Market strip, times, scores, tabular figures |
| Devanagari (reserved, v2) | Noto Serif Devanagari | `serif` | Not loaded in v1 |

Type scale (fluid `clamp(min, preferred, max)`):

| Token | Size | Line height | Tracking | Usage |
|---|---|---|---|---|
| `--fs-masthead` | `clamp(2.5rem, 8.5vw, 7rem)` | 0.95 | -0.01em | Nameplate only |
| `--fs-display` | `clamp(2rem, 5vw, 3.75rem)` | 1.05 | -0.01em | Page H1 (Abril Fatface) |
| `--fs-h2` | `clamp(1.5rem, 3vw, 2.25rem)` | 1.15 | 0 | Section titles (Old Standard TT 700) |
| `--fs-h3` | `clamp(1.25rem, 2vw, 1.5rem)` | 1.25 | 0 | Sub-sections |
| `--fs-headline` | `1.375rem` | 1.25 | 0 | Story headlines |
| `--fs-body` | `1.0625rem` (17px) | 1.65 | 0 | Body copy |
| `--fs-ui` | `1rem` (16px) | 1.4 | 0 | Buttons, inputs (never below 16px on inputs) |
| `--fs-small` | `0.875rem` | 1.5 | 0 | Captions, metadata |
| `--fs-kicker` | `0.75rem` | 1.2 | 0.14em, uppercase | Kickers, labels |

Text rules:
- Measure for body: 60–70 characters (`max-width: 65ch`). Long articles may use 2–3 newspaper columns from `lg` (`column-count`, `column-rule: 1px solid var(--rule-soft)`), never on phones.
- Headlines use `text-wrap: balance`; body uses `text-wrap: pretty`; hyphenation on (`hyphens: auto`) in multi-column text.
- Real typographic characters: curly quotes, dashes, ₹, ellipsis, non-breaking space before units and times.
- Drop caps (Abril Fatface, 3 lines tall, `--press-red` or genre accent) on the first paragraph of the sample lead story and How-we-report intro only.
- Misregistration effect (device 7): `text-shadow: 2px 2px 0 var(--g-accent, var(--press-red))` on display headings ≥ 40px only; disabled under `prefers-contrast: more`.
- Links in body: underlined, `text-underline-offset: 0.2em`, 1px (2px on hover/focus).

### 6.4 Spacing, borders, shadows, textures

- **Spacing scale (4px base):** `4, 8, 12, 16, 24, 32, 48, 64, 96, 128` → `--space-1` … `--space-10`. Section rhythm: 64px mobile, 96px desktop.
- **Radius:** essentially none. `--radius-0: 0` for almost everything; `--radius-round: 999px` only for circular postmarks and small pills. Corners come from perforation/notch masks, not rounding.
- **Borders and rules:** `--border-thick: 2px solid var(--ink)` (cards, buttons, inputs), `--rule-hair: 1px solid var(--rule-soft)`, `--rule-thin: 1px solid var(--rule)`, `--rule-heavy: 4px solid var(--rule)`, `--rule-double: 4px double var(--rule)`, `--rule-dotted: 2px dotted var(--rule)`. Masthead sits between a heavy rule and a double rule.
- **Block shadows (hard, no blur):** `--block-1: 3px 3px 0 var(--ink)`, `--block-2: 6px 6px 0 var(--ink)`, `--block-genre: 4px 4px 0 var(--g-accent)`. Pressed state collapses the shadow (`translate(3px, 3px)` + `box-shadow: 0 0 0`).
- **Textures:** paper grain via one tiny tiled SVG/PNG noise (≤ 4 KB) at 4–5% opacity on `--paper`; halftone via CSS gradients (§6.2); fold crease on the edition preview via a 1px `linear-gradient` line at 8% opacity. All textures are disabled under `prefers-contrast: more` and `prefers-reduced-transparency`. No SVG `feTurbulence` on large areas (performance).
- **Stamp geometry:** rectangular stamps use a 3px double border; round postmarks use two concentric 2px rings; rotation between -6° and +4°; text stays horizontal within the rotated box (no curved text needed; a simple arc via SVG `textPath` is allowed for postmarks only, ≤ 24 characters, `aria-hidden`).

### 6.5 Layout grid and breakpoints

| Breakpoint | Min width | Columns | Gutter | Page padding |
|---|---|---|---|---|
| base (phone) | 0 (design at 360) | 4 | 16px | 16px |
| `sm` | 640px | 8 | 20px | 24px |
| `md` | 768px | 8 | 24px | 32px |
| `lg` | 1024px | 12 | 24px | 32px |
| `xl` | 1280px | 12 | 24px | auto (max content 1200px) |

- Max content width 1200px; reading column 65ch; edition preview max 720px.
- Editorial sections use vertical column rules between columns from `lg` up.
- No horizontal scroll at any width from 320px up. Wide content (tables, market strip) scrolls inside its own container with a visible affordance.
- Safe-area insets respected on mobile sticky bars.

---

## 7. Imagery, Iconography and Ornament

- **No stock photography and no AI-generated imagery** on marketing pages. The identity is typographic and ornamental: rules, stamps, halftone, motifs and the nameplate.
- **Image treatment (story images on sample/archive pages):** images render as clean, honest photos with a thin 2px ink frame and a credit line. Optional *halftone mode* is applied only to decorative placeholders, never to real news photos, so the reader is never shown an altered photograph as evidence. Consistent 3:2 crop, `object-fit: cover`, explicit width/height to prevent layout shift. Credit line: `Photo: Name / Source, Licence`. If licence data is missing, the image is not shown.
- **Placeholder art (marketing only):** halftone blocks in the genre spot ink with a period motif; never pretending to be a photograph.
- **Edition preview** is real HTML/CSS from `fixtures/sample-edition.json`, not a screenshot.
- **Icons:** one set, `lucide-react`, drawn at 2px stroke to match thick ink rules, 20px default (24px in nav), paired with text unless universally understood (menu, close). Genre icons may be custom SVG line drawings in period style (pennant, reel, record, joystick, ticker, etc.), 24px, `currentColor`. No emoji as icons.
- **Ornaments:** fleurons (❦-style SVG), asterism dividers, corner brackets, and the "mosaic" mark (10 small squares, one per genre spot ink) used as a section divider.
- **Favicon and app icon:** an Abril Fatface "M" reversed out of an ink square with a Press Red corner tab; SVG source plus PNG fallback.
- **Social/OG image:** static local file in nameplate style.

---

## 8. Component Library

General rules:
- Build each component once in `src/components/`, driven by tokens, with all states implemented (default, hover, focus-visible, active, disabled, loading, error where applicable).
- Copy-in components from React Bits, 21st.dev or Componentry are raw material only and must pass §19.
- Every interactive element is keyboard-operable, has a visible focus ring, and a hit target ≥ 44×44px on touch (24×24px minimum on pointer-only dense UI).
- Focus ring: 3px `--ink` outline plus 2px `--paper` inner gap, visible on any background (`:focus-visible` only). With block shadows present, the ring sits outside the shadow.

### 8.1 Dateline bar
Thin strip above the nameplate in Special Elite / Libre Franklin kicker style: left `Wednesday, 30 September 2026`, centre `Morning Edition · Vol. I · No. —` (edition number counted from launch, omitted if unknown), right `Price: Free`. Bordered below by `--rule-thin`. On pages where the city is known, city and temperature appear in the left ear instead.

### 8.2 Masthead (nameplate with ears)
- Centre: "The Morning Mosaic" in `--fs-masthead`, Abril Fatface, with misregistration shadow (device 7) on `md` and up.
- **Left ear:** boxed weather chip (city + condition; "India" if no city known). **Right ear:** boxed motto "Every line cited. Nothing invented." in Old Standard TT italic. Ears collapse below the nameplate on phones as a two-up row.
- Beneath: heavy rule, a row with tagline (italic) and "Est. 2026 · Morning Edition · 6–9 AM IST", then a double rule.
- The "mosaic" mark (10 tiny squares in genre spot inks) may sit either side of the tagline. Decorative only.
- Inner pages: compact nameplate (`--fs-h2`), sticky 56px bar on scroll with wordmark and Subscribe button.

### 8.3 Buttons
| Variant | Look | Use |
|---|---|---|
| Primary | `--ink` fill, `--paper` text, `--border-thick`, `--block-genre` or `--block-1` shadow, Libre Franklin 700 16px, 48px tall, uppercase optional with 0.06em tracking | One per view: Start my edition, Confirm and subscribe |
| Secondary | `--paper-raised` fill, `--border-thick`, `--block-1` shadow, `--ink` text | See a sample edition |
| Text link | Underlined ink text, arrow "→" | Tertiary actions |
| Genre-tinted | `--g-accent` fill, paper text, inside a genre section only | Read more within sample sections |

States: hover lifts by 1px (shadow grows to 4px 4px); active collapses the shadow and translates 3px 3px (a physical "press"); disabled at 45% opacity with dashed border and `aria-disabled`, no shadow; loading keeps the label, adds a spinner icon, sets `aria-busy`. Never replace the label with "Loading…".

### 8.4 Genre card ("postage stamp", the signature component)
- **Look:** each genre is a postage stamp: perforated edge (SVG/CSS mask), inner 2px frame in the genre spot ink, halftone tint fill, a period motif along the top, genre name in Alfa Slab One (kicker size), a one-line blurb in Libre Caslon, and a "denomination" corner numeral (1–10, decorative).
- **Layout:** ≥ 44px touch target as a whole card; 2-column grid on phone, 3 on `md`, 5 on `xl` (two rows of five), slight alternating tilt (±1°) on `lg`+ only, removed on hover/focus and under reduced motion.
- **Semantics:** a checkbox inside a `<label>` (native). Group is `<fieldset><legend>`.
- **States:**
  - Default: `--paper-raised`, perforated edge, `--block-1`.
  - Hover/focus-visible: perforation edge darkens, shadow grows, tilt straightens.
  - Selected: tint fills solid with halftone, 3px inner border in `--g-accent`, a **postmark** (circular cancel mark with the text "IN", or "SUBSCRIBED" on larger cards) stamps onto the corner, plus a visible check icon and visually-hidden "Selected".
  - Disabled: not used in v1.
- **Selection animation:** "stamp thunk": postmark scales 1.3→1 with a 2px shake, 280ms `steps(4)`; tint wash follows (350ms). Instant under reduced motion.
- **Keyboard:** Tab moves through cards, Space toggles.
- **Live region** announces "AI selected. 3 genres chosen."

### 8.5 Form controls
- **Text input:** `--paper-raised`, `--border-thick`, no radius, 48px tall, 16px minimum font, visible label above in kicker style (never placeholder-only), helper text below in Special Elite 14px or Libre Franklin, error state with `--danger` border, icon, and message linked by `aria-describedby`. Focus state: ring plus a `--block-genre` shadow.
- **Email input:** `type="email"`, `inputmode="email"`, `autocomplete="email"`, `autocapitalize="none"`, `spellcheck="false"`. Never block paste.
- **City combobox:** ARIA combobox pattern over a local list of Indian cities (name, state). Type-ahead, arrows, Enter, `Esc`. Result list styled as a typed "directory listing" with hairline dotted leaders between city and state. Invalid: "Pick a city from the list. Can't find yours? Choose the nearest one."
- **Time selector ("departure board"):** radio group of ticket-stub buttons in 15-minute steps (6:00 … 9:00 AM IST), notched sides, Courier Prime numerals; selected stub inverts (ink fill, paper text) and gets a small "punched" hole. Scrollable row on phones, wrapped grid on desktop. Default 7:00 AM. The readout above the stubs is a **split-flap display** (each digit in its own flap cell, flipping when the value changes; `aria-hidden`) paired with visually-hidden text "Arrives around 7:00 AM IST". Step size lives in one constant.
- **Consent checkbox:** unchecked by default, 24px square box with a stamped ✕/✓ mark inside a 44px label target, full consent sentence from §4, link to Privacy.
- **Validation:** on blur and on submit, never per keystroke. On submit error, focus the summary or first invalid field and announce it.
- **Autofill and hydration:** inputs keep typed values and focus after hydration; test by typing before the page finishes loading.

### 8.6 Stepper ("ticket stub")
Each subscribe step header is a ticket: perforated left edge, "ADMIT ONE" micro-label in Special Elite, large numeral in Abril Fatface, and "Step 2 of 4: City". The completed steps' tickets are shown torn-in-half (simple clipped ticket halves, decorative) and remain clickable to go back. Back always preserves entries. Each step is a real `h2` and receives focus on step change.

### 8.7 Edition preview (hero component)
- A faithful mini-front-page on newsprint: nameplate, dateline, 60-second summary box, two sample story blocks from different genres (each with its own spot ink and citation markers), weather ear, market strip.
- Framed as a sheet of paper: `--block-2` shadow, faint fold crease, grain texture, slight -1° tilt on `lg`+ (straightens on hover/focus).
- A red rubber stamp "SAMPLE" (rotated -6°, `--press-red`, 3px double border) sits across a corner. It must remain visible in every state; it is never removed on the marketing site.
- Hovering/tapping a citation marker opens the citation popover; a "PDF" tab shows the A4 layout thumbnail.
- Content from `fixtures/sample-edition.json`, always labelled Sample. Never presented as today's real news.

### 8.8 Citation marker and source popover
- Marker: superscript numeral `¹` as a `<button>` (min 24px target, padded), in `--g-accent`, with a small circle outline like an old footnote mark.
- Popover: styled as a small "index card" (`--paper-raised`, `--border-thick`, `--block-1`), showing source name, publication time in Courier Prime, "Read original" link, and the line "Quoted from the source text." Opens on click/tap/Enter, closes on `Esc` or outside click; hover-open is enhancement only.
- A numbered "Sources" list ends each story (no-JS and print fallback).
- Active citation highlights the supporting sentence with `--highlight` (marker-pen style, slightly uneven underline via `background-image`, no blur).

### 8.9 Market strip ("ticker tape")
Horizontal band on `--paper-sunk` with dotted top and bottom rules; items in Courier Prime with arrow icon **and** text ("▲ 0.42%"), separated by small asterisms. Static sample data on the site; the tape "prints" in with stepped motion once on view (§10 #6) but never scrolls as a marquee. Phones: horizontal scroll inside its own container with an edge cue.

### 8.10 Weather chip
Boxed ear-style chip: icon + temperature + city + condition text ("31°C · Pune · Partly cloudy") in Libre Franklin/Courier Prime. Sample uses fixture data.

### 8.11 60-second summary box
Bordered box (`--border-thick`) with heavy top rule, a Press Red "STOP PRESS" flag in Alfa Slab One and kicker "60-SECOND SUMMARY", 5–6 one-line bullets in Old Standard TT each ending with a citation marker, `--block-1` shadow.

### 8.12 Extras blocks
- **Scores:** scoreboard-style table (Courier Prime, hairline dotted rows, pennant icon).
- **Releases:** "programme listing" with dates in a left gutter and dotted leaders.
- **Quote of the day:** oversized italic Old Standard TT with large fleuron quote marks and attribution beneath, framed with double rules.
Each uses the genre spot ink where placed in a genre section, otherwise ink.

### 8.13 Stamps and badges (new)
| Stamp | Text | Colour | Meaning | Where |
|---|---|---|---|---|
| Sample | SAMPLE | Press Red | Content is illustrative | Edition preview, `/sample` |
| Verified | VERIFIED · EVERY CLAIM CHECKED | Ink or genre ink | The pipeline's verification step, explained on How we report | Trust section, How we report |
| Dropped | DROPPED IF UNSURE | Press Red | Policy stamp, not tied to a specific story | Trust section |
| Extra | EXTRA! · WEEKEND RECAP | Press Red | Weekend edition marker | Archive, recap cards |
| Subscribed | IN / SUBSCRIBED | Genre ink | Selected genre | Genre cards, confirm page |
Rules: stamps carry true information only; never used as fake "awards" or endorsements; never the only cue for state; always have an accessible text equivalent (real text inside, not an image); decorative rotation ≤ 6°; one large stamp per view.

### 8.14 Dividers and ornaments (new)
Fleuron divider, asterism (⁂) divider, dotted-leader lines, corner brackets, and the mosaic mark. All inline SVG, `aria-hidden`, colours from tokens.

### 8.15 Feedback and alerts
Inline alert styled as a **telegram slip**: `--paper-raised`, dashed top and bottom border, icon + text + optional action, `role="status"` (polite) or `role="alert"` (errors). No auto-dismissing toasts for anything requiring action.

### 8.16 FAQ accordion
Native `<details>/<summary>`, plus/minus rule icon, dotted separators, "Q." and "A." in Alfa Slab One at kicker size. Only one open by default.

### 8.17 Footer
`--paper-sunk` with heavy top rule, colophon-style layout ("Set in Abril Fatface, Old Standard TT and Libre Caslon. Printed nowhere. Delivered every morning."), four columns on desktop stacking on phone. Includes the theme toggle and a Corrections link.

### 8.18 Skeletons, empty and error states
- Skeletons use paper-sunk blocks with a slow stepped opacity blink (steps(2), 1.6s); disabled under reduced motion.
- Empty states are typographic ("No editions yet. The presses are warming up.") with a next action.
- Every network call has an error state with retry.

---

## 9. Page Specifications

### 9.1 Landing page `/`

Section order (top to bottom):

1. **Dateline bar + Nameplate with ears** (masthead reveal on first visit per session).
2. **Stop-press strip** (optional, one line, Press Red flag): "Now printing: the morning edition, set to your interests." Static, not a marquee.
3. **Hero**: H1 (`--fs-display`, Abril Fatface): "The morning paper, set to your interests." Supporting line. Primary CTA *Start my edition*, secondary *See a sample edition*. Beside/below: the **Edition preview** (§8.7) with its SAMPLE stamp. Small line under CTAs: "Free. 6–9 AM IST. Unsubscribe in one click."
4. **How it works** as three ticket-stub columns: 1 Pick your genres, 2 Choose city and time, 3 Read your edition every morning. Optional telegram-style flourish in the small heading only ("PICK · CHOOSE · READ").
5. **The stamp sheet**: heading "Ten genres. Your mix." All 10 genre stamps laid out as a sheet of postage stamps with a perforated border; selecting here carries the choice into `/subscribe` via query string (nothing stored yet).
6. **What's inside an edition**: an annotated anatomy diagram of the edition (nameplate, weather, market strip, 60-second summary, stories, extras, PDF, weekend recap) with numbered callouts styled as "specimen plates". Annotated diagram on desktop, numbered list on phone.
7. **Grounded, not invented** (trust block): three claims with proof: *Every sentence cites a source*, *Every claim is checked before it's published* (VERIFIED stamp), *If we're in doubt, the story is dropped* (DROPPED IF UNSURE stamp). Includes an interactive citation demo. Link to *How we report*.
8. **Weekend recap and PDF** teaser: two cards, the recap card carrying the EXTRA! ribbon.
9. **FAQ**: What does it cost? Which sources do you use? Is the AI making things up? What if an edition is late? Can I change my genres? How do I unsubscribe? What do you do with my email?
10. **Final CTA band**: heavy-rule band with the primary CTA.
11. **Footer (colophon).**

Wireframe (desktop):

```
┌──────────────────────────────────────────────────────────────┐
│ Wed, 30 Sep 2026     Morning Edition · Vol. I      Price: Free│
├──────────────────────────────────────────────────────────────┤
│ ┌─────────┐    THE  MORNING  MOSAIC     ┌───────────────────┐ │
│ │ WEATHER │  (Abril Fatface, offset ink) │ Every line cited. │ │
│ │  ear    │                              │ Nothing invented. │ │
│ └─────────┘                              └───────────────────┘ │
│ ════════════════════════════════════════════════════════════ │
│  The morning paper, set to your interests.  Est. 2026 · 6–9 AM│
│ ═══════════════════════════════════════════════════════════  │
├─────────────────────────────┬────────────────────────────────┤
│ H1 + supporting line        │   ┌──────────────────────┐     │
│ [START MY EDITION][SAMPLE]  │   │ EDITION PREVIEW      │▒    │
│ Free · 6–9 AM IST           │   │  [SAMPLE] stamp      │▒    │
│                             │   └──────────────────────┘▒    │
├─────────────────────────────┴────────────────────────────────┤
│  ▣ 1 Pick genres │ ▣ 2 City and time │ ▣ 3 Read every morning │
├──────────────────────────────────────────────────────────────┤
│  ┏━┓ ┏━┓ ┏━┓ ┏━┓ ┏━┓   ← perforated genre stamps (2 rows)    │
│  ┗━┛ ┗━┛ ┗━┛ ┗━┛ ┗━┛                                          │
└──────────────────────────────────────────────────────────────┘
```

Mobile: single column; ears stack under the nameplate; hero CTA full width; preview below CTAs at 100% width; a sticky bottom bar with *Start my edition* appears after the hero scrolls out (hidden on `/subscribe`).

### 9.2 Subscribe flow `/subscribe`

Four steps on one route with client-side step state and a `?step=` param so Back/refresh works. Progress kept in memory (and `sessionStorage` for refresh safety). No account.

| Step | Content | Validation |
|---|---|---|
| 1 Genres | 10 genre cards; running count | At least 1 selected |
| 2 City | City combobox; "Weather for your city appears in your edition." | Must match list |
| 3 Time | Time selector + live preview line | Always valid (default 7:00 AM) |
| 4 Email | Email input, consent checkbox, submit | Valid email + consent checked |

Layout: single centered column (max 640px) on phone/tablet; from `lg`, a two-column layout with the form on the left and a sticky **"Your edition"** preview on the right that updates live: selected genre sections in their themes, city weather chip, delivery time, and estimated story count (`selected genres × 4–6`).

Behaviour:
- Step change animation: 24px slide + fade, 250ms; focus moves to the new step's heading.
- Submit shows a loading button state; on success routes to `/subscribe/check-email`; on error shows inline alert with retry and keeps all entries.
- Duplicate email: friendly message "You're already on the list. We've sent a link to update your preferences." (Never reveal whether an address exists beyond this neutral phrasing.)
- Double opt-in: no edition is sent until the confirmation link is used.

### 9.3 Check-your-email `/subscribe/check-email`
Large envelope ornament (SVG), headline "Check your inbox", the email echoed back, steps "Open the email → tap Confirm", a "Wrong address? Start again" link, and a "Resend" link that is rate-limited with a visible countdown. Local dev note: the message is visible in the local mail catcher.

### 9.4 Confirm `/confirm/[token]`
States: confirming (skeleton), success ("You're in. Your first edition arrives tomorrow around 7:00 AM IST." with summary of choices and link to preferences), expired/invalid ("This link has expired. Request a new one."). Success includes the big "IN" stamp thunk landing on the summary card (once, §10 #11).

### 9.5 Preferences `/preferences/[token]`
Same genre cards, city combobox and time selector as the flow, prefilled. Extra controls: *Pause emails* (date range or "until I resume"), *Weekend recap on/off*, *Unsubscribe* (secondary, at the bottom). Autosave is not used; explicit *Save changes* with inline success alert. Unsaved-change warning on navigation.

### 9.6 Unsubscribe `/unsubscribe/[token]`
One click completes it (no login, no dark patterns). Confirmation message, optional one-tap reason chips (Too many emails / Not my genres / Wrong time / Other) that are truly optional, and a *Resubscribe* link. Never guilt-trip.

### 9.7 Sample edition `/sample`
Full web rendering of a sample edition, exactly mirroring email structure and genre themes. Sticky mini-nav to jump to genre sections. Printable: a print stylesheet outputs A4 with the same masthead, single-page-per-genre breaks, sources list included. Clearly labelled "Sample edition — not today's news".

### 9.8 Archive `/editions` and `/editions/[date]`
Chronological list (by month) of past editions with date, edition number, genres covered and a "recap" badge on weekends. Individual edition page = web version of the email. If none exist locally, empty state links to the sample edition.

### 9.9 How we report `/how-we-report`
The trust page; treat as a flagship page. Sections: *Where stories come from* (whitelisted RSS feeds and news APIs, listed by name), *How a story is built* (collect → cluster → rank → summarise strictly from source text → cite every sentence → verify every claim → publish or drop), a diagram of the pipeline, *What we do when we're unsure* (drop the story), *Images and licensing*, *Corrections policy*, *Limits* (honest statement of what the system can get wrong), *Contact*. Include a real worked example: source text → summary sentence → citation.

### 9.10 Status `/status`
Shows today's edition state: Scheduled / Sending / Sent / Delayed / Not sent. If an apology edition was sent, show its message. Plain, calm, no jargon.

### 9.11 Feedback `/feedback`
Short form: what happened (select: Wrong or unclear story / Wrong genre / Timing / Design/readability / Other), free text, optional email for reply. Confirmation inline. Honeypot field for spam, no CAPTCHA.

### 9.12 Privacy and Terms
Long-form reading pages using the article layout (65ch, generous leading, table of contents at `lg`). Privacy states plainly what is collected (email, genres, city, delivery time), why, retention, and that no third-party trackers are used.

### 9.13 404 and error
Masthead intact, headline in voice (§4), link back to front page and sample, search-free.

---

## 10. Motion Design

Philosophy: motion behaves like a press, a stamp and a station board: deliberate, mechanical, brief, and often *stepped* rather than smooth. It explains state changes and adds one moment of delight per screen.

**Tokens.**

| Token | Value |
|---|---|
| `--dur-fast` | 120ms (hover, press) |
| `--dur-base` | 200ms (popovers, toggles) |
| `--dur-slow` | 300ms (reveals, step change) |
| `--dur-draw` | 500ms (rules drawing, tape print) |
| `--ease-press` | `cubic-bezier(0.2, 0.7, 0.2, 1)` |
| `--ease-inout` | `cubic-bezier(0.65, 0, 0.35, 1)` |
| `--ease-step-4` / `--ease-step-8` | `steps(4, end)` / `steps(8, end)` (retro stepped beats) |

**Motion inventory (complete list; add nothing without updating this table).**

| # | Where | Effect | Timing | Library |
|---|---|---|---|---|
| 1 | Landing dateline, first visit per session | Typewriter reveal of the dateline text | ≤ 600ms, `steps(24)` | CSS |
| 2 | Landing nameplate, first visit per session | Letters "press in" (scale 1.04→1, opacity 0→1, 40ms stagger); misregistration shadow settles from 6px to 2px; heavy rule draws left to right | ≤ 900ms total | GSAP |
| 3 | Section entrances | Fade + 8px rise, once per element | 300ms | CSS + IntersectionObserver |
| 4 | Genre card select | Postmark "stamp thunk" (scale 1.3→1, 2px shake) then tint wash | 280ms + 350ms | CSS `steps()` + `clip-path` |
| 5 | Edition preview on load | Sheet unfolds (scaleY 0.96→1, opacity) and settles; optional ≤ 12px scroll parallax | 500ms | GSAP |
| 6 | Market strip, once on view | Tape "prints" in, item by item | 8 steps, ≤ 600ms | CSS |
| 7 | Time selector value change | Split-flap: each digit flips top-to-bottom | 180ms per digit, `steps(3)` | CSS/Motion |
| 8 | Citation popover | Fade + 4px rise | 150ms | CSS |
| 9 | Buttons | Press collapses the block shadow, 3px translate; no bounce or scale | 120ms | CSS |
| 10 | Subscribe step change | 24px slide + fade; ticket half tears away; heading receives focus | 250ms | Motion |
| 11 | Confirm success | Big stamp "IN" thunks onto the summary card, once | 400ms | Motion |
| 12 | Skeleton | Stepped opacity blink | `steps(2)`, 1.6s loop | CSS |
| 13 | Theme toggle | Cross-fade of colour tokens ("lights down on the press room") | 200ms | CSS |

**Rules.**
- Animate only `transform`, `opacity` and `clip-path`. Never animate layout properties.
- `prefers-reduced-motion: reduce` removes every effect above; end states appear instantly. No parallax, draw-ins, flips, shakes or blinks.
- No autoplay video, no looping decorative animation (skeleton blink is the only loop), no marquee, no scroll-jacking, no cursor-follow effects, no flicker, nothing flashing more than 3 times per second.
- Motion must never delay interactivity: content is in the DOM and usable before its animation starts; nothing gates the CTA.
- GSAP and heavy animation code are lazy-loaded only where needed. Target ≤ 60 KB gzipped for all animation libraries combined on the landing page.
- 3D (Three.js) is out of scope for v1.

---

## 11. Accessibility Requirements (WCAG 2.2 AA minimum)

**Structure and semantics**
- One `<h1>` per page, logical heading order, landmarks (`header`, `nav`, `main`, `footer`), skip-to-content link as the first focusable element.
- `lang="en-IN"` on `<html>`; page titles unique and descriptive ("Subscribe – The Morning Mosaic").
- Use native elements first (`button`, `a`, `input`, `fieldset`, `details`); ARIA only to fill gaps.

**Keyboard and focus**
- Everything operable by keyboard; no keyboard traps; logical tab order.
- Visible focus indicator on every interactive element (§8). Use `:focus-visible`.
- Route or step changes move focus to the new heading; modals and the mobile menu trap focus and restore it on close.

**Color and contrast**
- Text 4.5:1 (large text 3:1); UI components and focus rings 3:1. Verified in both Morning and Late editions and for every genre accent.
- Never rely on color alone: up/down arrows with text in the market strip, icons plus text on alerts, kicker labels on genres.
- Retro devices must not cost legibility: text over any texture (grain, halftone, fold crease) is measured against the darkest region behind it; misregistration shadows are off under `prefers-contrast: more`; stamps are real text with an accessible equivalent and are never the only carrier of state; no scanline, flicker or flash effects.

**Targets and input**
- Touch targets ≥ 44×44px; pointer-only dense controls ≥ 24×24px with adequate spacing.
- Inputs 16px minimum font on mobile; never disable zoom (`maximum-scale` must not be set to 1); never block paste.
- Labels always visible and programmatically associated. Errors identified in text, linked with `aria-describedby`, and announced.
- Provide `autocomplete` attributes where applicable.

**Media and motion**
- All informative images have alt text; decorative ones `alt=""`/`aria-hidden`.
- Reduced motion honored (§10). No content flashes more than 3 times per second.

**Dynamic updates**
- Live regions (`aria-live="polite"`) for genre count, time preview, form success; `role="alert"` for errors.

**Reading and zoom**
- Layout works at 400% zoom and 320px width without two-dimensional scrolling (except data tables/strip inside their own scroller).
- Text can be resized to 200% without loss of content.

**Testing.** Automated (`@axe-core/playwright`) on every page in both themes plus manual keyboard-only run-through and a screen-reader spot check (NVDA or VoiceOver) of the subscribe flow before a page is considered done.

---

## 12. Responsive Behavior

| Area | Phone (< 640) | Tablet (640–1023) | Desktop (≥ 1024) |
|---|---|---|---|
| Nav | Wordmark + Subscribe + menu sheet | Same as phone or inline links | Inline links |
| Hero | Stacked, CTA full width | Stacked, wider preview | Two columns |
| Genre grid | 2 columns | 3 columns | 5 columns |
| Subscribe flow | Single column, sticky bottom "Next" bar with safe-area padding | Single column, 640px | Two columns with live "Your edition" preview |
| Edition anatomy | Numbered list | Numbered list + small diagram | Annotated diagram |
| Market strip | Horizontal scroll with fade cue | Wrapped/scroll | Full row |
| Footer | Stacked | 2 columns | 4 columns |

Rules: design at 360px first; test 320px for overflow; use container-relative sizing and `clamp()`; images have intrinsic size attributes; no fixed heights on text containers; `100dvh` (not `100vh`) for full-height sheets.

---

## 13. Performance Budgets

Measured locally with Lighthouse (mobile preset, throttled) and Playwright.

| Metric | Target |
|---|---|
| Largest Contentful Paint (landing, throttled 4G, mid-tier device) | ≤ 2.5s |
| Cumulative Layout Shift | ≤ 0.05 |
| Interaction to Next Paint | ≤ 200ms |
| JS shipped on landing (gzipped) | ≤ 180 KB total, ≤ 60 KB for animation |
| Total page weight (landing) | ≤ 500 KB excluding fonts, ≤ 200 KB fonts |
| Fonts | Self-hosted, subset, variable where possible, `font-display: swap`, preload the masthead face only |
| Images | Modern formats, explicit dimensions, lazy-load below the fold, none needed above the fold |

Rules: server-render marketing pages; ship client JS only for interactive islands (genre picker, form, citation popover, theme toggle); ornaments are inline SVG/CSS; no third-party scripts of any kind; avoid layout shift from fonts with metric-matched fallbacks (`size-adjust`).

---

## 14. Content and Copy Rules

- Headlines in sentence case, no exclamation marks, no emoji.
- Numbers: `en-IN` grouping (`1,00,000`), `₹`, 24-hour never used in UI (use `7:00 AM IST`).
- Dates: `Wednesday, 30 September 2026`; compact `30 Sep 2026`.
- Sample content must be plausible but clearly labelled **Sample**, never presented as real reporting and never attributed to real publications unless it is genuinely quoted from them with attribution.
- Never show made-up subscriber numbers, testimonials, ratings, press logos or countdown urgency.
- Button labels are verbs that describe the outcome. Link text is descriptive ("Read how we report", not "Click here").
- Explain jargon once, in plain words ("citation" = "a link to the exact source of a sentence").

---

## 15. Data Contracts the UI Depends On

The frontend talks to the FastAPI server on `http://localhost:8000` (configured via `NEXT_PUBLIC_API_BASE_URL`). Design assumes these shapes; if the API differs, adapt the adapter layer, not the components.

```ts
type Genre = { id: string; slug: GenreSlug; name: string; blurb: string; sampleHeadline: string };
type City = { id: string; name: string; state: string };
type Preferences = { email: string; genres: GenreSlug[]; cityId: string; deliveryTime: "HH:MM"; weekendRecap: boolean; pausedUntil?: string | null };

// Endpoints the UI uses
// GET  /genres                      -> Genre[]
// GET  /cities?q=                   -> City[]
// POST /subscriptions               -> 202 { status: "confirmation_sent" } | 409 duplicate (neutral message)
// GET  /confirm/{token}             -> { status: "confirmed" | "expired" }
// GET  /preferences/{token}         -> Preferences
// PUT  /preferences/{token}         -> Preferences
// POST /unsubscribe/{token}         -> { status: "unsubscribed" }
// GET  /editions?month=YYYY-MM      -> EditionSummary[]
// GET  /editions/{date}             -> Edition
// GET  /status/today                -> { state: "scheduled"|"sending"|"sent"|"delayed"|"not_sent"; message?: string }
// POST /feedback                    -> 204
```

Development fallback: when the API is unreachable, the site reads `fixtures/*.json` (genres, cities, sample-edition) so design work never blocks on the backend. A visible "Using sample data" chip appears in dev only.

---

## 16. Code Structure and Conventions (frontend)

```
web/
  design/
    tokens.json                 # source of truth for all tokens
    scripts/build-tokens.mjs    # generates CSS vars, Tailwind theme, email/PDF tokens
  fixtures/
    genres.json  cities.json  sample-edition.json
  src/
    app/                        # Next.js App Router routes (see §5.1)
    components/
      ui/                       # Button, Input, Combobox, Fieldset, Alert, Accordion...
      editorial/                # Masthead, Dateline, GenreCard, EditionPreview, Citation, MarketStrip...
      flow/                     # SubscribeFlow, Stepper, steps
    lib/                        # api client, formatters (en-IN), a11y helpers
    styles/
      tokens.css                # generated
      globals.css
      print.css
  tests/
    e2e/                        # Playwright specs + screenshot baselines
```

Conventions:
- TypeScript strict. Tailwind for utility styling, mapped to tokens (expose CSS variables through the Tailwind theme: `@theme` in v4 or `theme.extend` in v3). No arbitrary hex values or pixel values in class names.
- Server components by default; `"use client"` only where interaction is needed.
- Components take `data-genre` from context, never accept raw color props.
- Forms use native `<form>` semantics with progressive enhancement where feasible (the subscribe form should still post successfully if JS is slow to load).
- Formatting helpers centralize `en-IN` dates, times and numbers.
- Tokens change only in `tokens.json`; regenerate with `npm run tokens`.

Example generated token CSS (illustrative):

```css
:root {
  /* Morning edition */
  --paper: #F0E6CB; --paper-raised: #F8F0DC; --paper-sunk: #E4D8B8;
  --ink: #1C1915; --ink-soft: #40382C; --ink-muted: #6A5F4C;
  --rule: #1C1915; --rule-soft: #C9B98F;
  --highlight: #F2C94C; --press-red: #B72A1A;

  --radius-0: 0; --radius-round: 999px;
  --border-thick: 2px solid var(--ink);
  --rule-heavy: 4px solid var(--rule);
  --rule-double: 4px double var(--rule);
  --block-1: 3px 3px 0 var(--ink);
  --block-2: 6px 6px 0 var(--ink);
  --block-genre: 4px 4px 0 var(--g-accent, var(--ink));

  --dur-fast: 120ms; --dur-base: 200ms; --dur-slow: 300ms; --dur-draw: 500ms;
  --ease-press: cubic-bezier(0.2, 0.7, 0.2, 1);
  --ease-step-4: steps(4, end);

  --font-masthead: "Abril Fatface", "Playfair Display", Georgia, serif;
  --font-headline: "Old Standard TT", Georgia, serif;
  --font-body: "Libre Caslon Text", Georgia, serif;
  --font-flag: "Alfa Slab One", Rockwell, "Courier New", serif;
  --font-ui: "Libre Franklin", "Franklin Gothic Medium", Arial, sans-serif;
  --font-type: "Special Elite", "Courier New", monospace;
  --font-data: "Courier Prime", ui-monospace, Menlo, monospace;
}
:root[data-theme="dark"] {
  /* Late edition */
  --paper: #1A150F; --paper-raised: #241D15; --paper-sunk: #100D09;
  --ink: #F0E4C8; --ink-soft: #D2C5A8; --ink-muted: #A19676;
  --rule: #F0E4C8; --rule-soft: #4A3F30;
  --highlight: #6B5514; --press-red: #F08A78;
}

/* Genre spot inks */
[data-genre="ai"] { --g-accent: #5B3FA6; --g-tint: #DDD5E9; }
:root[data-theme="dark"] [data-genre="ai"] {
  --g-accent: #B7A2F0;
  --g-tint: color-mix(in oklab, var(--g-accent) 18%, var(--paper));
}

/* Device 4: halftone fill */
.halftone {
  background:
    radial-gradient(circle at center, var(--g-accent) 0 1.2px, transparent 1.6px) 0 0 / 6px 6px,
    var(--g-tint);
}
.halftone--text-safe { background-blend-mode: multiply; opacity: 1; } /* keep dot layer ≤ 6% where text sits */

/* Device 3: block-shadow button with physical press */
.btn { border: var(--border-thick); box-shadow: var(--block-genre); transition: transform var(--dur-fast) var(--ease-press), box-shadow var(--dur-fast) var(--ease-press); }
.btn:hover { transform: translate(-1px, -1px); box-shadow: 4px 4px 0 var(--ink); }
.btn:active { transform: translate(3px, 3px); box-shadow: 0 0 0 var(--ink); }

/* Device 7: misregistration, display sizes only */
.display-misreg { text-shadow: 2px 2px 0 var(--g-accent, var(--press-red)); }
@media (max-width: 767px), (prefers-contrast: more) { .display-misreg { text-shadow: none; } }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
@media (prefers-contrast: more) {
  :root { --rule-soft: var(--ink-muted); }
  .grain, .halftone { background-image: none; }
}
```

---

## 17. Email and PDF Parity

- The email and A4 PDF read from the same `tokens.json` (colours, genre spot inks, type roles, rule styles), so the retro identity carries across.
- **Email constraints:** table-based layout, inline CSS, 600px max width. Web-safe fallbacks: Georgia for Abril Fatface/Old Standard TT/Libre Caslon, Arial for Libre Franklin, Courier New for Special Elite/Courier Prime. Newsprint paper as the background colour with an ivory content panel; heavy and double rules as CSS borders; block shadows approximated with a solid offset border on the bottom/right where supported (degrade to a plain 2px border). Halftone, stamps and postmarks are small inlined PNGs with meaningful `alt` text (e.g. "Verified stamp"). No animation; text-only fallback; dark-mode-safe colours (Late edition palette applied via `prefers-color-scheme` where supported).
- **PDF:** A4, same nameplate with ears, genre sections in their spot inks with halftone header bands, sources list at the foot of each section, print-safe colours (no reliance on textures; grain is dropped).
- The website's `/sample` page and the sample email share the same fixture so they cannot drift.

---

## 18. Internationalization and Future Hindi

- v1 ships English (India). Do not bake text into images; keep all copy in one `content/` module so translation is possible later.
- Allow 30% longer strings in buttons, nav and cards; avoid fixed widths.
- Reserve Noto Serif Devanagari as a fallback; keep line-height ≥ 1.7 for Devanagari when added.
- Use logical CSS properties (`margin-inline`, `padding-block`) so RTL scripts (e.g. Urdu) would not require rewrites.

---

## 19. Adopting Copy-In Components (React Bits, 21st.dev, Componentry)

These are raw material, not the design. Before any copied component ships:

1. **Fit:** does it serve an item in the Motion Inventory (§10) or a component in §8? If not, don't add it.
2. **Restyle:** replace all colors, fonts, radii, shadows and easings with tokens; remove neon, glow, blur, chrome and any gradient that isn't the halftone or paper recipe from §6.
3. **Weight:** check bundle impact; reject anything that pushes past the budgets in §13. No WebGL/canvas above the fold.
4. **Accessibility:** add keyboard support, focus states, ARIA and reduced-motion handling; verify with axe and by keyboard.
5. **Dependencies:** prefer components with no extra runtime dependencies; record the source and license in `docs/third-party.md`.
6. **Visual review:** screenshot at 360px and 1280px in both themes; it must look like it belongs to the retro broadsheet.

Good candidates: text reveals and typewriter effects for the dateline, a split-flap/flip-board component for the time readout, a grid pattern adapted into the postage-stamp genre sheet, a stacked-card or fold effect for the edition preview, a flowing/hover menu adapted for mobile navigation, subtle paper-grain backgrounds. Bad fits: aurora/galaxy/light-rain backgrounds, glassmorphism, neon glow, cubes, blobs, 3D scenes, cursor trails, CRT/scanline effects.

**Reference board (for humans).** Search terms for Pinterest or similar: "broadsheet front page layout", "editorial newspaper website", "Swiss editorial grid", "masthead typography", "print-era Indian daily layout". Save the references you choose into `docs/references/` with a one-line note about what you're borrowing (typography, rules, density), so decisions stay traceable.

---

## 20. Quality Assurance (local, automated and manual)

**Playwright visual and behavior checks** (run with `npx playwright test`):
- Viewports: 360×800, 390×844, 768×1024, 1280×800, 1536×900.
- Modes: Morning edition, Late edition, `reducedMotion: "reduce"`, and forced-colors/high-contrast emulation.
- For every route: full-page screenshot baseline, no horizontal overflow, no console errors, no failed requests to non-localhost origins.
- Subscribe flow: complete happy path; each validation error; back/forward; refresh mid-flow; slow-network run (type before hydration completes).
- Keyboard: tab through each page, verify visible focus and skip link; genre cards toggle with Space; combobox with arrows/Enter/Esc; menu sheet traps focus.

**Automated audits:**
- `@axe-core/playwright` on every route in both themes, zero serious/critical violations.
- Contrast check script over all token pairs (paper × ink levels, paper × each genre accent, tint × accent, both themes).
- Lighthouse (mobile) local run meeting §13 targets.

**Manual checklist before a page counts as done:**
- [ ] Matches the page spec in §9 and only uses components in §8.
- [ ] No hard-coded colors, fonts or spacing values.
- [ ] Works at 320px and at 400% zoom.
- [ ] Reads well in Late edition.
- [ ] Retro devices used only where §6.0 allows; textures never behind body text beyond the §6.2 limits; at most one large stamp per view.
- [ ] Contrast measured against the darkest texture region behind any text.
- [ ] Reduced motion tested.
- [ ] Copy follows §4 and §14; no lorem ipsum, no fake proof.
- [ ] Screenshots reviewed and baselines updated intentionally.

---

## 21. Build Order (recommended)

1. Tokens pipeline (`tokens.json` → CSS/Tailwind), fonts (Abril Fatface, Old Standard TT, Libre Caslon Text, Alfa Slab One, Libre Franklin, Special Elite, Courier Prime), base styles, Morning/Late theme, paper grain and halftone utilities.
2. Fixtures and API adapter with dev fallback.
3. Core UI: Button, Input, Fieldset, Alert, Focus ring, Skip link.
4. Editorial components: Dateline, Masthead, GenreCard, Citation, MarketStrip, EditionPreview.
5. Subscribe flow with live "Your edition" preview and validation.
6. Landing page (all sections, masthead reveal, preview).
7. Check-email, confirm, preferences, unsubscribe.
8. Sample edition, archive, print stylesheet.
9. How we report, status, feedback, privacy, terms, 404/error.
10. Accessibility, performance and visual QA pass; update baselines.
11. Token export for email/PDF parity check.

---

## 22. Hard Rules for Claude Code

**Always**
- Read this file first; use tokens; implement all states; write semantic HTML.
- Apply the retro devices exactly where §6.0 allows and nowhere else.
- Use real content or clearly labelled sample content.
- Verify each UI change in a browser via Playwright screenshots at mobile and desktop widths before calling it done.
- Keep everything working offline and on localhost.

**Never**
- Add third-party scripts, analytics, trackers, remote fonts, CDN assets or external network calls.
- Use sepia/brown filters over photos or content, torn-paper edges, coffee rings, wood or leather textures, CRT scanlines or flicker, neon glow, vaporwave gradients, glassmorphism, blob shapes, stock 3D, emoji icons, or hero videos.
- Alter real news photographs (halftone is for decorative placeholders only), or use a stamp to imply endorsement, awards or verification that didn't happen.
- Use more than one genre spot ink in a single section, or more than one large stamp per view.
- Invent subscriber counts, testimonials, ratings, press logos or urgency timers.
- Use color as the only carrier of meaning.
- Disable zoom, block paste, or remove focus outlines.
- Animate layout properties or add motion that isn't in §10.
- Introduce a new font, color, radius or shadow without adding it to `tokens.json` and this file.

---

## 23. Decision Log

Record any deviation or new decision here (date, decision, reason).

| Date | Decision | Reason |
|---|---|---|
| — | Initial design system written | Baseline |
| 2026-09-30 | Design direction set to Retro Broadsheet (newsprint, spot ink, halftone, stamps, postage-stamp genre cards). Day/Night renamed Morning/Late edition; typography, shadows (hard block), radii (none), motion (stepped) and genre accents revised | Owner requested a retro theme |
| 2026-09-30 | Code lives in `frontend/` (not `web/`); tokens at `frontend/design/tokens.json` | Matches the existing repo layout |
| 2026-09-30 | Cloudflare Turnstile is the one permitted third-party script (subscribe step only); "localhost-only" wording dropped | CLAUDE.md requires Turnstile on signup and a production Cloud Run deployment |
| 2026-09-30 | Subscribe flow adds first name, frequency, keywords, edition preference, 18+ and consent fields; time slots are 30 minutes; the preferences "weekend recap" toggle is replaced by the frequency choice | CLAUDE.md product decisions take precedence |
| 2026-09-30 | `--ink-muted` #6A5F4C→#605644 and `--press-red` #B72A1A→#AC2717 (light) | Failed 4.5:1 on `--paper-sunk`; fixed in the token per §6.2 |
| 2026-09-30 | Theme toggle label names the target ("Switch to Late edition") | A bare "Morning edition" label was ambiguous next to the current theme |
| 2026-09-30 | Stamp perforation is a scalloped mask band around a solid interior; hard shadow via `filter: drop-shadow` because `box-shadow` is clipped by masks | Rendering constraint of the postage-stamp card |
| 2026-09-30 | Email/PDF width 600px (was 640px) and email/PDF theme generated from `tokens.json` | §17 parity |
| 2026-09-30 | Subscribe result renders in place ("Check your inbox") instead of a separate `/subscribe/check-email` route; no Resend link yet | No resend endpoint exists; avoids passing the email through the URL |
| 2026-09-30 | Explicit consent checkbox added to step 4 using the §4 sentence, alongside the existing 18+ box | DPDP consent at signup; §8.5 |
| 2026-09-30 | Route group `(flow)` (wide, no Subscribe button in nav) for `/subscribe`; `(site)` narrow for other pages; `(landing)` full width | Different width needs per page type |
| 2026-09-30 | `/confirm/[token]` and `/unsubscribe/[token]` stay backend-rendered (restyled in `backend/app/api/pages.py`) instead of Next pages | Link-scanner safety (GET never changes state) and the strict `default-src 'none'` CSP require script-free pages on the same origin |
| 2026-09-30 | Route is `/editions` for the archive index; `/archive` and `/archive/:date` redirect permanently | §5.1 sitemap |
| 2026-09-30 | Genre-card postmark moved into a reserved footer row (numeral left, postmark right) | It covered blurb text at top-right and bottom-right |
| 2026-09-30 | Email/PDF/archive theme is generated from `tokens.json` by `npm run tokens:backend` (palette.json + genres.yaml `theme:`), guarded by CI and `test_design_sync.py` | §17 parity without a second source of truth |
| 2026-09-30 | Email type is Georgia / Arial / Courier New; no web fonts | Mail clients don't load them reliably; §17 fallbacks |
| 2026-09-30 | PDF pages are white (not newsprint) with ink rules and the genre spot ink | Print-safe: no full-bleed tint, no textures (§17) |
| 2026-09-30 | Backend tagline changed to "The morning paper, set to your interests." (was "India's morning, in the pieces that matter.") | Matches the tagline in DESIGN.md §4, already used on the site |
| 2026-09-30 | Genres' `theme.rule` is now the hairline colour (`rule-soft`); heavy rules are ink from the shared palette | Ink rules are the print look; genre theme keeps only accent, tint and hairline |
| 2026-09-30 | Typewriter face is Courier Prime (already loaded for figures); Special Elite and the Libre Franklin 600 file are no longer loaded | Landing fonts were 246 KB against the 200 KB budget in §13; now 172 KB |
| 2026-09-30 | Genre-card numeral drawn at full opacity | The faded numeral failed axe colour-contrast in both themes |
| 2026-09-30 | Subscribe page has a visible h1 "Start my edition" | §11 requires one h1 per page; the page had none |
| 2026-09-30 | Screenshot baselines are not committed; screenshots are saved per run (and uploaded from CI) for review | Font rendering differs between Windows and Linux, so pixel diffs would be noisy |
| 2026-09-30 | Reveal motion is CSS-only (no GSAP), triggered by `<html data-reveal>` set by the pre-paint script only on the first landing-page visit of a session | §10 #1, #2, #5; keeps the animation budget at 0 KB and avoids a flash |
| 2026-09-30 | `animation-delay` is also zeroed under prefers-reduced-motion | Staggered elements would otherwise stay hidden for their delay |
| 2026-09-30 | §10 #3 section entrances not built | Scroll-triggered hiding would leave content invisible in screenshots and to axe until scrolled |
| 2026-09-30 | Playwright runs with reduced motion by default; `motion.spec.ts` opts back in | Screenshots and axe scans must not catch a half-played animation |
| 2026-09-30 | Fonts load through `next/font/local` (from the `@fontsource` files) with `adjustFontFallback`, and `--font-*` tokens are built from its `--nf-*` variables | Lighthouse measured a 0.145 layout shift from font swapping (budget 0.05); metric-matched fallbacks bring it to 0 |
| 2026-09-30 | No font is preloaded | Preloading five fonts delayed the render-blocking stylesheet (LCP 2.1 s -> 2.8 s on simulated mobile); with matched fallbacks the swap shifts nothing |
| 2026-09-30 | Below-the-fold landing sections use `content-visibility: auto` | Cut the initial layout cost of the 7,000px page: TBT 410 ms -> 170-300 ms, performance 81 -> 88-95 |
| 2026-09-30 | Test viewports now include 320x568 | The §11 floor and what 400% zoom reflows to |
| 2026-09-30 | `experimental.inlineCss: true` in next.config.ts | Removes the render-blocking stylesheet request: mobile LCP 2.3-2.9 s -> 1.7-1.9 s, performance 79-86 -> 92-96. Trade-off: CSS not cached separately (~10 KB compressed). Experimental flag: re-check on Next upgrades |
| 2026-09-30 | Nameplate is always two lines ("The Morning" / "Mosaic") | A width-dependent break meant the fallback fit on one line and the web font wrapped to two on desktop, shifting the page (CLS 0.22) |
| 2026-09-30 | `content-visibility: auto` only on landing sections well below the fold | On the sections nearest the fold the guessed placeholder height was visible as layout shift |
| 2026-09-30 | Performance test scrolls the whole page and runs at desktop and phone sizes | Field CLS includes shifts while scrolling; the earlier check missed the regressions above |
| 2026-09-30 | Built §10 #7 (split-flap time readout) and #10 (step slide), CSS-only; the readout is aria-hidden beside a real "Arrives around ..." sentence | Motion inventory; flip only on changed characters keeps it meaningful |
| 2026-09-30 | §10 #11 (confirm stamp) not put on the check-your-inbox screen | That screen shows before the reader confirms; a "subscribed" stamp would state something untrue (§8.13: stamps carry true information only) |

