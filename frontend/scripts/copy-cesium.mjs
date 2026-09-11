// Copies the Cesium static build (Workers/Assets/Widgets) into public/cesium
// so Cesium is fully self-hosted — no CDN, no Cesium ion dependency (§11.4).
// Runs on postinstall / dev / prebuild.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const src = join(root, "..", "node_modules", "cesium", "Build", "Cesium");
const dest = join(root, "..", "public", "cesium");

if (!existsSync(src)) {
  console.error(`cesium build not found at ${src} — run npm install first`);
  process.exit(1);
}
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
console.log(`copied Cesium static build -> ${dest}`);
