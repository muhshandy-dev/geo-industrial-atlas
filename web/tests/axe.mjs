// K13: pemeriksaan aksesibilitas otomatis (axe) di 5 bab, terang dan gelap, desktop dan ponsel.
// Jalankan: npm run build && npx astro preview, lalu node tests/axe.mjs http://localhost:4321/
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const { AxeBuilder } = await import("@axe-core/playwright");

const url = process.argv[2] ?? "http://localhost:4321/";
const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
let total = 0;
for (const [w, h] of [[1440, 900], [390, 844]]) {
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    for (const tab of ["peta", "jarak", "uji", "sens", "data"]) {
      await page.click(`#tab-${tab}`);
      await page.waitForTimeout(600);
      const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      total += r.violations.length;
      for (const v of r.violations) console.log(`${w} ${scheme} ${tab}: ${v.id} (${v.nodes.length}) ${v.nodes[0]?.target} ${v.nodes[0]?.failureSummary?.slice(0, 160)}`);
    }
    await ctx.close();
  }
}
await browser.close();
console.log(`axe: ${total} pelanggaran`);
process.exit(total ? 1 : 0);
