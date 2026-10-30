// Hitung ulang coverage di browser dari points.json.
// Logika ini cermin dari src/geo_atlas/scenario.py; tes paritas (tests/parity.test.ts)
// memastikan hasilnya identik dengan Python untuk 216 skenario.

export type Industri = "sempit" | "luas";
export type Fasilitas = "mentah" | "nama" | "osm" | "damkar";
export type Batas = "penuh" | "sederhana";
export type Luar = "buang" | "terdekat_1km";

export interface Scenario {
  industri: Industri;
  conf: number; // 0, 0.5, 0.7
  rs: Fasilitas;
  radius: number; // km
  batas: Batas;
  luar: Luar;
}

export interface Points {
  columns: string[];
  n: number;
  data: Record<string, number[]>;
}

export interface Kab {
  id: number;
  nm: string;
  pv: string;
  pvn: string;
  adm: number;
  km2: number;
  [k: string]: number | string;
}

export const CONF_SCALE = 1000;
export const MIN_POINTS_FOR_RANK = 10;

export function facColumn(rs: Fasilitas, conf: number): string {
  if (rs === "osm") return "d_rs_osm";
  const c = String(Math.round(conf * 100)).padStart(2, "0");
  return rs === "damkar" ? `d_damkar_c${c}` : `d_rs_${rs}_c${c}`;
}

export function kabColumn(batas: Batas, luar: Luar): string {
  return `kab_${batas === "penuh" ? "p" : "s"}${luar === "terdekat_1km" ? "t" : "b"}`;
}

export interface KabResult {
  n: Int32Array; // indeks = kab_id
  nCov: Int32Array;
}

export interface Result {
  n: number;
  nCov: number;
  shareCov: number | null;
  kab: KabResult;
  selected: Uint8Array; // 1 bila titik masuk skenario
  covered: Uint8Array; // 1 bila dalam radius
}

export function compute(pts: Points, nKab: number, s: Scenario): Result {
  const d = pts.data;
  const confMin = Math.round(s.conf * CONF_SCALE);
  const kabArr = d[kabColumn(s.batas, s.luar)];
  const dist = d[facColumn(s.rs, s.conf)];
  const limit = s.radius * 1000;
  const kn = new Int32Array(nKab);
  const kc = new Int32Array(nKab);
  const selected = new Uint8Array(pts.n);
  const covered = new Uint8Array(pts.n);
  let n = 0;
  let nCov = 0;
  for (let i = 0; i < pts.n; i++) {
    if (d.conf[i] < confMin) continue;
    if (s.industri === "sempit" && d.sempit[i] !== 1) continue;
    const k = kabArr[i];
    if (k < 0) continue;
    selected[i] = 1;
    n++;
    kn[k]++;
    if (dist[i] <= limit) {
      covered[i] = 1;
      nCov++;
      kc[k]++;
    }
  }
  return { n, nCov, shareCov: n ? nCov / n : null, kab: { n: kn, nCov: kc }, selected, covered };
}

export function rankUnderserved(r: KabResult, kab: Kab[]): number[] {
  const rows: { id: number; u: number; n: number }[] = [];
  for (const k of kab) {
    const n = r.n[k.id];
    if (k.adm === 1 && n >= MIN_POINTS_FOR_RANK) rows.push({ id: k.id, u: n - r.nCov[k.id], n });
  }
  // Pecahan eksak: u1/n1 > u2/n2  <=>  u1*n2 > u2*n1 (bilangan bulat, aman di bawah 2^53).
  rows.sort((a, b) => {
    const lhs = b.u * a.n;
    const rhs = a.u * b.n;
    if (lhs !== rhs) return lhs - rhs;
    if (a.u !== b.u) return b.u - a.u;
    return a.id - b.id;
  });
  return rows.map((x) => x.id);
}

export function rankDensity(r: KabResult, kab: Kab[]): number[] {
  const rows: { id: number; dens: number }[] = [];
  for (const k of kab) {
    const n = r.n[k.id];
    if (k.adm === 1 && n > 0) rows.push({ id: k.id, dens: n / k.km2 });
  }
  rows.sort((a, b) => (b.dens !== a.dens ? b.dens - a.dens : a.id - b.id));
  return rows.map((x) => x.id);
}

export function scenarioKey(s: Scenario): string {
  const c = Number.isInteger(s.conf) ? s.conf.toFixed(1) : String(s.conf);
  return `${s.industri}|${c}|${s.rs}|${s.radius}|${s.batas}|${s.luar}`;
}
