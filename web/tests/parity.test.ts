// K9: angka yang dihitung ulang di browser sama persis dengan Python untuk semua skenario.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { compute, rankDensity, rankUnderserved, scenarioKey, type Kab, type Points, type Scenario } from "../src/lib/scenario.ts";

const dir = new URL("../public/data/", import.meta.url);
const pts: Points = JSON.parse(readFileSync(new URL("points.json", dir), "utf8"));
const kab: Kab[] = JSON.parse(readFileSync(new URL("kab.json", dir), "utf8")).kab;
const res = JSON.parse(readFileSync(new URL("results.json", dir), "utf8"));
const nKab = kab.length;

test("216 skenario: n, n_cov, share_cov, 10 besar identik dengan Python", () => {
  const rows = res.sensitivity.rows;
  assert.equal(rows.length, 216);
  for (const row of rows) {
    const s: Scenario = { industri: row.industri, conf: row.conf, rs: row.rs, radius: row.radius, batas: row.batas, luar: row.luar };
    assert.equal(scenarioKey(s), row.key);
    const r = compute(pts, nKab, s);
    assert.equal(r.n, row.n, row.key);
    assert.equal(r.nCov, row.n_cov, row.key);
    // results.json membulatkan ke 6 desimal
    assert.equal(Math.round((r.shareCov as number) * 1e6) / 1e6, row.share_cov, row.key);
    assert.deepEqual(rankUnderserved(r.kab, kab).slice(0, 10), row.top10_underserved, row.key);
    assert.deepEqual(rankDensity(r.kab, kab).slice(0, 10), row.top10_density, row.key);
    assert.equal(rankUnderserved(r.kab, kab).length, row.n_ranked, row.key);
  }
});

test("skenario dasar sama dengan ringkasan", () => {
  const b = res.provenance.base_scenario;
  const r = compute(pts, nKab, b);
  assert.equal(r.n, res.base.n);
  assert.equal(r.nCov, res.base.n_cov);
});

test("damkar dapat dihitung dan memakai kolom jarak yang ada", () => {
  for (const conf of [0, 0.5, 0.7]) {
    const r = compute(pts, nKab, { industri: "sempit", conf, rs: "damkar", radius: 10, batas: "penuh", luar: "buang" });
    assert.ok(r.n > 0 && r.nCov <= r.n);
  }
});
