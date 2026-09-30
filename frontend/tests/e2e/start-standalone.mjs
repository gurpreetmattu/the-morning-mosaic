// Starts the production build the way the Docker image does: the self-contained
// `.next/standalone/server.js` (next.config.ts sets output: "standalone"), which
// `next start` warns it does not support. The standalone folder needs the static
// assets and `public/` copied beside it, which the Dockerfile also does.
import { cpSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
cpSync("public", ".next/standalone/public", { recursive: true });

process.env.HOSTNAME = "0.0.0.0";
await import(pathToFileURL(resolve(".next/standalone/server.js")).href);
