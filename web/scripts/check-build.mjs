// K11: situs statis, tiap file < 25 MiB, tanpa URL tile/layanan eksternal di bundel.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const dist = new URL("../dist/", import.meta.url).pathname;
const LIMIT = 25 * 1024 * 1024;
const files = [];
const walk = (d) => readdirSync(d).forEach((f) => { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : files.push(p); });
walk(dist);
let fail = false;
let total = 0;
for (const f of files) {
  const s = statSync(f).size;
  total += s;
  if (s >= LIMIT) { console.error(`TERLALU BESAR: ${f} ${s}`); fail = true; }
}
const html = readFileSync(join(dist, "index.html"), "utf8");
const external = /https?:\/\/[^"'`\s)]*(?:tiles?|maptiler|openfreemap|mapbox|arcgis|carto)[^"'`\s)]*/gi;
for (const f of files.filter((x) => /\.(js|html|css)$/.test(x))) {
  const t = readFileSync(f, "utf8");
  const m = (t.match(external) || []).filter((u) => !/github\.com|maplibre\.org\/maplibre-style-spec/.test(u));
  if (m.length) { console.error(`URL eksternal di ${f}: ${[...new Set(m)].slice(0, 5).join(", ")}`); fail = true; }
}
for (const need of ["CC BY 3.0 IGO", "CDLA-Permissive-2.0", "ODbL"]) {
  if (!html.includes(need)) { console.error(`Atribusi hilang: ${need}`); fail = true; }
}
console.log(`${files.length} file, total ${(total / 1048576).toFixed(2)} MiB, terbesar ${(Math.max(...files.map((f) => statSync(f).size)) / 1048576).toFixed(2)} MiB`);
if (fail) process.exit(1);
console.log("check-build OK");
