// Enforces the DESIGN.md section 13 budgets with Lighthouse (mobile, simulated slow 4G) against a
// production build. Run `npm run build` first, then `npm run perf:lighthouse`.
//
// Lighthouse is noisy (it moved by seconds of blocking time when the machine was busy), so this
// takes the MEDIAN of several runs and gives the score and blocking time some slack. The two
// numbers DESIGN.md sets hard limits for, LCP and CLS, are held to those limits exactly.
import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import * as chromeLauncher from "chrome-launcher";
import lighthouse from "lighthouse";
import perfConfig from "lighthouse/core/config/perf-config.js";

const PORT = 3100;
const API_PORT = 8000;
const RUNS = Number(process.env.LH_RUNS ?? 3);
const URL = `http://localhost:${PORT}/`;

// Limits can be overridden from the environment (LH_MAX_LCP, LH_MAX_CLS, LH_MAX_TBT,
// LH_MIN_SCORE), e.g. to loosen them on a slow CI runner or to prove the check can fail.
const num = (name, fallback) => (process.env[name] ? Number(process.env[name]) : fallback);
const BUDGETS = {
  lcp: {
    limit: num("LH_MAX_LCP", 2500),
    unit: "ms",
    label: "Largest Contentful Paint (DESIGN.md 13: 2.5 s)",
  },
  cls: {
    limit: num("LH_MAX_CLS", 0.05),
    unit: "",
    label: "Cumulative Layout Shift (DESIGN.md 13: 0.05)",
  },
  tbt: {
    limit: num("LH_MAX_TBT", 600),
    unit: "ms",
    label: "Total Blocking Time (guard rail for INP <= 200 ms)",
  },
  score: {
    limit: num("LH_MIN_SCORE", 80),
    unit: "",
    label: "Performance score (minimum)",
    min: true,
  },
};

const children = [];
function start(cmd, args, env) {
  const child = spawn(cmd, args, { env: { ...process.env, ...env }, stdio: "ignore" });
  children.push(child);
  return child;
}
function stopAll() {
  for (const child of children) child.kill();
}
process.on("exit", stopAll);
process.on("SIGINT", () => process.exit(130));

async function waitFor(url, tries = 60) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url);
      if (res.status < 500) return;
    } catch {
      /* not up yet */
    }
    await sleep(500);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

const median = (values) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];

start("node", ["tests/e2e/mock-api.mjs"], { MOCK_API_PORT: String(API_PORT) });
start("node", ["tests/e2e/start-standalone.mjs"], {
  PORT: String(PORT),
  BACKEND_ORIGIN: `http://127.0.0.1:${API_PORT}`,
});
await waitFor(URL);

const chrome = await chromeLauncher.launch({
  chromeFlags: ["--headless=new", "--no-sandbox"],
});

const samples = { lcp: [], cls: [], tbt: [], score: [] };
try {
  for (let i = 0; i < RUNS; i++) {
    const result = await lighthouse(
      URL,
      { port: chrome.port, output: "json", logLevel: "error", formFactor: "mobile" },
      perfConfig,
    );
    const { audits, categories } = result.lhr;
    samples.lcp.push(audits["largest-contentful-paint"].numericValue);
    samples.cls.push(audits["cumulative-layout-shift"].numericValue);
    samples.tbt.push(audits["total-blocking-time"].numericValue);
    samples.score.push(Math.round(categories.performance.score * 100));
    console.log(
      `run ${i + 1}: LCP ${Math.round(samples.lcp[i])} ms, CLS ${samples.cls[i].toFixed(3)}, ` +
        `TBT ${Math.round(samples.tbt[i])} ms, score ${samples.score[i]}`,
    );
  }
} finally {
  await chrome.kill();
}

let failed = false;
console.log(`\nMedian of ${RUNS} runs:`);
for (const [key, budget] of Object.entries(BUDGETS)) {
  const value = median(samples[key]);
  const ok = budget.min ? value >= budget.limit : value <= budget.limit;
  if (!ok) failed = true;
  const shown = key === "cls" ? value.toFixed(3) : Math.round(value);
  console.log(
    `  ${ok ? "PASS" : "FAIL"}  ${budget.label}: ${shown}${budget.unit} (limit ${budget.limit}${budget.unit})`,
  );
}
process.exit(failed ? 1 : 0);
