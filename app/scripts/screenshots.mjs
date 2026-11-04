// README screenshots at the Galaxy Tab S6 Lite's landscape size, from demo data only.
//
//   cd backend && PC_DATA_DIR=/tmp/pc-demo uv run piano-companion-demo
//   PC_MIDI_ENABLED=false PC_DATA_DIR=/tmp/pc-demo uv run piano-companion   # API on :8000
//   cd app && PI_URL=http://localhost:8000 npm run dev                       # app on :5173
//   node scripts/screenshots.mjs [http://localhost:5173] [../docs/screenshots]
import { chromium } from "playwright";

const base = process.argv[2] ?? "http://localhost:5173";
const out = process.argv[3] ?? new URL("../../docs/screenshots/", import.meta.url).pathname;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2, colorScheme: "dark" });
await page.goto(base);
await page.waitForLoadState("networkidle");

const tab = async (name) => {
  await page.getByRole("button", { name, exact: true }).first().click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);
};
const shot = async (name, opts = {}) => {
  await page.screenshot({ path: `${out}/${name}.png`, ...opts });
  console.log("wrote", name);
};

// A fresh browser has seen no achievements, so the first load records them without a notice.
await tab("Today");
await shot("today");

await tab("Technique");
await shot("technique");

await tab("Progress");
await shot("progress");
await page.getByRole("heading", { name: "Technique" }).evaluate((h) => h.scrollIntoView({ block: "start" }));
await page.locator("main").evaluate((m) => m.scrollBy(0, -28));
await page.waitForTimeout(300);
await shot("progress-technique");

await tab("Record");
await shot("record");

await tab("Library");
await page.getByRole("listitem").filter({ hasText: "Study in C" }).getByRole("button", { name: "Open" }).click();
await page.waitForSelector(".score svg", { timeout: 15000 });
await page.waitForTimeout(800);
await shot("score");

await browser.close();
