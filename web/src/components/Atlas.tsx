import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import MapView, { type Choropleth, type FC, type LayerKey, type PointLayers } from "./MapView";
import { HBars, RampLegend, RangeBars } from "./Charts";
import {
  compute, rankDensity, rankUnderserved, scenarioKey,
  type Batas, type Fasilitas, type Industri, type Kab, type Luar, type Points, type Scenario,
} from "../lib/scenario";
import { COLORS, currentMode, type Mode } from "../lib/theme";
import { fmt, int, pct } from "../lib/format";

type Results = any;
interface Facilities {
  rs: { lon: number[]; lat: number[]; conf: number[]; nama: number[] };
  damkar: { lon: number[]; lat: number[]; conf: number[] };
  rs_osm: { lon: number[]; lat: number[] };
  ind_osm: { lon: number[]; lat: number[]; km2: number[] };
}
interface Data { pts: Points; kab: Kab[]; fac: Facilities; kabGeo: FC; provGeo: FC }

const CHAPTERS = [
  { id: "peta", no: "1", label: "Peta industri" },
  { id: "jarak", no: "2", label: "Jarak ke fasilitas" },
  { id: "uji", no: "3", label: "Uji kebenaran" },
  { id: "sens", no: "4", label: "Ubah asumsi" },
  { id: "data", no: "5", label: "Data & batas" },
] as const;
type Chapter = (typeof CHAPTERS)[number]["id"];

const FAS_LABEL: Record<Fasilitas, string> = {
  nama: "Rumah sakit (nama jelas)",
  mentah: "Semua label \"hospital\"",
  osm: "Rumah sakit OSM",
  damkar: "Pemadam kebakaran",
};
const ASUMSI_LABEL: Record<string, string> = {
  radius: "Radius", rs: "Definisi RS", conf: "Ambang keyakinan", industri: "Definisi industri",
  batas: "Versi batas", luar: "Titik di luar batas",
};
const EMPTY: FC = { type: "FeatureCollection", features: [] };
const DENS_BREAKS = [1, 5, 20, 100]; // titik per 1.000 km2
const UNCOV_BREAKS = [0.05, 0.15, 0.3, 0.5];
const FREQ_BREAKS = [0.1, 0.25, 0.5, 0.75];

function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

function pointsFC(lon: number[], lat: number[], keep?: (i: number) => boolean, props?: (i: number) => Record<string, number>): FC {
  const features: GeoJSON.Feature[] = [];
  for (let i = 0; i < lon.length; i++) {
    if (keep && !keep(i)) continue;
    features.push({ type: "Feature", properties: props ? props(i) : {}, geometry: { type: "Point", coordinates: [lon[i], lat[i]] } });
  }
  return { type: "FeatureCollection", features };
}

function Seg<T extends string | number>({ label, value, options, onChange }: {
  label: string; value: T; options: { v: T; l: string }[]; onChange: (v: T) => void;
}) {
  return (
    <div className="ctl" role="group" aria-label={label}>
      <span className="lbl">{label}</span>
      <div className="seg">
        {options.map((o) => (
          <button key={String(o.v)} type="button" aria-pressed={o.v === value} onClick={() => onChange(o.v)}>{o.l}</button>
        ))}
      </div>
    </div>
  );
}

export default function Atlas({ results }: { results: Results }) {
  const R = results;
  const base: Scenario = R.provenance.base_scenario;
  const [chapter, setChapter] = useState<Chapter>("peta");
  const [data, setData] = useState<Data | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("light");
  const [sel, setSel] = useState<number | null>(null);
  const [s, setS] = useState<Scenario>(base);
  const [vis, setVis] = useState<Record<LayerKey, boolean>>({
    ind: true, indOsm: false, rs: false, rsOsm: false, damkar: false, special: true, prov: true, kab: true,
  });

  useEffect(() => {
    const get = (f: string) => fetch(`/data/${f}`).then((r) => { if (!r.ok) throw new Error(f); return r.json(); });
    Promise.all([get("points.json"), get("kab.json"), get("facilities.json"), get("kab.geojson"), get("provinsi.geojson")])
      .then(([pts, kab, fac, kabGeo, provGeo]) => setData({ pts, kab: kab.kab, fac, kabGeo, provGeo }))
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    setMode(currentMode());
    const obs = new MutationObserver(() => setMode(currentMode()));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => setMode(currentMode());
    mq.addEventListener("change", on);
    return () => { obs.disconnect(); mq.removeEventListener("change", on); };
  }, []);

  // lapisan default per bab
  useEffect(() => {
    const v: Record<Chapter, Partial<Record<LayerKey, boolean>>> = {
      peta: { ind: true, indOsm: false, rs: false, rsOsm: false, damkar: false, special: false },
      jarak: { ind: true, indOsm: false, rs: s.rs === "nama" || s.rs === "mentah", rsOsm: s.rs === "osm", damkar: s.rs === "damkar", special: false },
      uji: { ind: false, indOsm: false, rs: false, rsOsm: false, damkar: false, special: true },
      sens: { ind: false, indOsm: false, rs: false, rsOsm: false, damkar: false, special: false },
      data: { ind: true, indOsm: true, rs: true, rsOsm: true, damkar: true, special: false },
    };
    setVis((old) => ({ ...old, ...v[chapter] }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapter]);

  const kabById = useMemo(() => {
    const m = new Map<number, Kab>();
    data?.kab.forEach((k) => m.set(k.id, k));
    return m;
  }, [data]);
  const nKab = data?.kab.length ?? 0;
  const nonAdminIds = useMemo(() => (data ? data.kab.filter((k) => k.adm === 0).map((k) => k.id) : []), [data]);

  const baseRes = useMemo(() => (data ? compute(data.pts, nKab, base) : null), [data]);
  const curRes = useMemo(() => (data ? compute(data.pts, nKab, s) : null), [data, s]);
  const gridRow = useMemo(() => R.sensitivity.rows.find((r: any) => r.key === scenarioKey(s)), [s]);

  const densityTop = useMemo(() => (baseRes && data ? rankDensity(baseRes.kab, data.kab) : []), [baseRes]);
  const underTop = useMemo(() => (curRes && data ? rankUnderserved(curRes.kab, data.kab) : []), [curRes]);
  const freq: Record<string, number> = R.sensitivity.top10_underserved_frequency;
  const nScen: number = R.sensitivity.n_scenarios;

  // koroplet per bab
  const choro: Choropleth | null = useMemo(() => {
    if (!data || !baseRes || !curRes) return null;
    const vals: (number | null)[] = new Array(nKab).fill(null);
    const faded: boolean[] = new Array(nKab).fill(false);
    if (chapter === "peta") {
      for (const k of data.kab) if (k.adm === 1 && baseRes.kab.n[k.id] > 0) vals[k.id] = (baseRes.kab.n[k.id] / k.km2) * 1000;
      return { values: vals, breaks: DENS_BREAKS, ramp: "teal" };
    }
    if (chapter === "jarak") {
      for (const k of data.kab) {
        const n = curRes.kab.n[k.id];
        if (k.adm === 1 && n > 0) { vals[k.id] = (n - curRes.kab.nCov[k.id]) / n; faded[k.id] = n < 10; }
      }
      return { values: vals, faded, breaks: UNCOV_BREAKS, ramp: "terra" };
    }
    if (chapter === "sens") {
      for (const [k, v] of Object.entries(freq)) vals[Number(k)] = v / nScen;
      return { values: vals, breaks: FREQ_BREAKS, ramp: "terra" };
    }
    return null;
  }, [chapter, data, baseRes, curRes]);

  const points: PointLayers = useMemo(() => {
    if (!data || !curRes || !baseRes) return { ind: EMPTY, indOsm: EMPTY, rs: EMPTY, rsOsm: EMPTY, damkar: EMPTY, special: EMPTY };
    const d = data.pts.data;
    const f = data.fac;
    const res = chapter === "jarak" ? curRes : baseRes;
    const cmin = Math.round(s.conf * 1000);
    const confFilter = chapter === "jarak";
    return {
      ind: pointsFC(d.lon, d.lat, (i) => res.selected[i] === 1, (i) => ({ c: res.covered[i] })),
      indOsm: pointsFC(f.ind_osm.lon, f.ind_osm.lat),
      rs: pointsFC(f.rs.lon, f.rs.lat, (i) => (!confFilter || f.rs.conf[i] >= cmin) && (chapter !== "jarak" || s.rs === "mentah" || f.rs.nama[i] === 1)),
      rsOsm: pointsFC(f.rs_osm.lon, f.rs_osm.lat),
      damkar: pointsFC(f.damkar.lon, f.damkar.lat, (i) => !confFilter || f.damkar.conf[i] >= cmin),
      special: pointsFC(d.lon, d.lat, (i) => d.kab_pb[i] !== d.kab_sb[i] || (d.kab_pb[i] < 0 && d.kab_pt[i] >= 0)),
    };
  }, [data, curRes, baseRes, chapter, s.conf, s.rs]);

  const counts = {
    ind: points.ind.features.length, indOsm: points.indOsm.features.length, rs: points.rs.features.length,
    rsOsm: points.rsOsm.features.length, damkar: points.damkar.features.length, special: points.special.features.length,
  };

  const tooltip = (id: number) => {
    const k = kabById.get(id);
    if (!k) return "";
    let line = "";
    if (chapter === "peta" && baseRes) line = `${int(baseRes.kab.n[id])} titik industri tercatat`;
    if (chapter === "jarak" && curRes) {
      const n = curRes.kab.n[id];
      line = n ? `${pct((n - curRes.kab.nCov[id]) / n)} dari ${int(n)} titik di luar ${s.radius} km` : "tidak ada titik industri tercatat";
    }
    if (chapter === "sens") line = `${pct((freq[String(id)] ?? 0) / nScen, 0)} skenario masuk 10 besar`;
    if (k.adm === 0) line = "bukan wilayah administratif (danau/waduk/hutan)";
    return `<b>${esc(k.nm)}</b><br/><span style="color:var(--ink-3)">${esc(k.pvn)}</span>${line ? `<br/>${esc(line)}` : ""}`;
  };

  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = CHAPTERS.findIndex((c) => c.id === chapter);
    let j = i;
    if (e.key === "ArrowRight") j = (i + 1) % CHAPTERS.length;
    else if (e.key === "ArrowLeft") j = (i - 1 + CHAPTERS.length) % CHAPTERS.length;
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = CHAPTERS.length - 1;
    else return;
    e.preventDefault();
    setChapter(CHAPTERS[j].id);
    document.getElementById(`tab-${CHAPTERS[j].id}`)?.focus();
  };

  const c = COLORS[mode];
  const cov = R.coverage;
  const chk = R.checks;
  const selKab = sel != null ? kabById.get(sel) : undefined;

  return (
    <div className="atlas">
      <section className="panel" aria-label="Cerita dan kontrol">
        <div className="chapters" role="tablist" aria-label="Bab atlas" onKeyDown={onTabKey}>
          {CHAPTERS.map((ch) => (
            <button key={ch.id} id={`tab-${ch.id}`} role="tab" type="button" aria-selected={chapter === ch.id}
              aria-controls="chapter-panel" tabIndex={chapter === ch.id ? 0 : -1} onClick={() => setChapter(ch.id)}>
              <span className="no">{ch.no}</span>{ch.label}
            </button>
          ))}
        </div>
        <div className="chapter" id="chapter-panel" role="tabpanel" aria-labelledby={`tab-${chapter}`}>
          {err && <p className="note warn" role="alert">Data gagal dimuat ({err}). Muat ulang halaman.</p>}

          <KabPicker kab={data?.kab ?? []} value={sel} onChange={setSel} />
          {selKab && (
            <KabCard k={selKab} res={chapter === "jarak" ? curRes : baseRes} s={chapter === "jarak" ? s : base}
              rank={underTop.indexOf(selKab.id)} onClose={() => setSel(null)} />
          )}

          {chapter === "peta" && (
            <>
              <div className="kicker">Bab 1 · Peta industri</div>
              <h2>Di mana titik industri tercatat?</h2>
              <p className="lead">
                Atlas ini memasangkan titik pabrik dan manufaktur dari Overture Maps ke 514 kabupaten/kota
                (batas wilayah BPS), lalu mengukur seberapa dekat titik itu ke rumah sakit dan pemadam kebakaran.
              </p>
              <div className="hero">
                <div className="stat"><div className="v">{int(cov.national_counts_in_indonesia.industri_sempit_semua_conf)}</div><div className="l">titik manufaktur tercatat di Indonesia (semua skor keyakinan)</div></div>
                <div className="stat"><div className="v">{baseRes ? int(baseRes.n) : "…"}</div><div className="l">dipakai di skenario dasar (keyakinan ≥ 0,5)</div></div>
                <div className="stat"><div className="v">{int(cov.n_admin_kab - cov.kab_zero.industri_overture_sempit_c50)}</div><div className="l">dari {cov.n_admin_kab} kab/kota punya minimal satu titik</div></div>
                <div className="stat"><div className="v">{fmt(cov.national_counts_in_indonesia.osm_industri_luas_km2, 0)} km²</div><div className="l">kawasan industri di OpenStreetMap (pembanding)</div></div>
              </div>
              <p>
                Warna peta menunjukkan kepadatan: jumlah titik per 1.000 km² luas wilayah. Luas dihitung di proyeksi
                sama-luas, bukan dari derajat lintang-bujur.
              </p>
              <div className="note warn">
                Ini titik yang <b>tercatat</b> di sumber data terbuka, bukan jumlah pabrik sebenarnya. Daerah kota
                tercatat lebih lengkap daripada daerah terpencil.
              </div>
              <h3>10 kab/kota terpadat</h3>
              <KabTable ids={densityTop.slice(0, 10)} kabById={kabById} onPick={setSel}
                cols={[{ h: "Titik", f: (id) => int(baseRes?.kab.n[id]) }, { h: "per 1.000 km²", f: (id) => fmt(((baseRes?.kab.n[id] ?? 0) / (kabById.get(id)?.km2 ?? 1)) * 1000, 0) }]} />
              <p style={{ fontSize: 13 }}>{R.statements.find((x: any) => x.id === "density_top10")?.kab_ids.length ?? 0} kab/kota teratas tetap di 10 besar pada semua {nScen} skenario asumsi (lihat bab 4).</p>
            </>
          )}

          {chapter === "jarak" && (
            <>
              <div className="kicker">Bab 2 · Jarak ke fasilitas</div>
              <h2>Seberapa dekat industri ke rumah sakit dan pemadam?</h2>
              <p className="lead">
                Untuk tiap titik industri dihitung jarak garis lurus ke fasilitas terdekat (geodesik di bumi elips).
                Titik dianggap terjangkau bila jaraknya tidak lebih dari radius yang dipilih.
              </p>
              <div className="hero">
                <div className="stat"><div className="v">{curRes ? pct(curRes.shareCov) : "…"}</div><div className="l">titik industri dalam {s.radius} km dari {FAS_LABEL[s.rs].toLowerCase()}</div></div>
                <div className="stat"><div className="v">{curRes ? int(curRes.n - curRes.nCov) : "…"}</div><div className="l">dari {curRes ? int(curRes.n) : "…"} titik berada di luar radius</div></div>
              </div>
              <div className="controls">
                <Seg label="Fasilitas" value={s.rs} onChange={(v: Fasilitas) => setS({ ...s, rs: v })}
                  options={(["nama", "mentah", "osm", "damkar"] as Fasilitas[]).map((v) => ({ v, l: FAS_LABEL[v] }))} />
                <div className="ctl">
                  <label htmlFor="radius">Radius: <span className="num">{s.radius} km</span></label>
                  <input id="radius" type="range" min={1} max={30} step={1} value={s.radius}
                    onChange={(e) => setS({ ...s, radius: Number(e.target.value) })} aria-valuetext={`${s.radius} kilometer`} />
                </div>
                <Seg label="Ambang skor keyakinan titik" value={s.conf} onChange={(v: number) => setS({ ...s, conf: v })}
                  options={[{ v: 0, l: "Semua" }, { v: 0.5, l: "≥ 0,5" }, { v: 0.7, l: "≥ 0,7" }]} />
                <Seg label="Definisi industri" value={s.industri} onChange={(v: Industri) => setS({ ...s, industri: v })}
                  options={[{ v: "sempit", l: "Manufaktur saja" }, { v: "luas", l: "+ perusahaan industri" }]} />
                <Seg label="Versi batas wilayah" value={s.batas} onChange={(v: Batas) => setS({ ...s, batas: v })}
                  options={[{ v: "penuh", l: "Resolusi penuh" }, { v: "sederhana", l: "Disederhanakan" }]} />
                <Seg label="Titik di luar garis batas (pantai)" value={s.luar} onChange={(v: Luar) => setS({ ...s, luar: v })}
                  options={[{ v: "buang", l: "Buang" }, { v: "terdekat_1km", l: "Ambil kab terdekat ≤ 1 km" }]} />
                <div className={`parity ${gridRow ? "ok" : ""}`} role="status">
                  {gridRow
                    ? (curRes && curRes.n === gridRow.n && curRes.nCov === gridRow.n_cov
                      ? <>✓ Angka ini sama persis dengan hasil pipeline Python (skenario {R.sensitivity.rows.indexOf(gridRow) + 1} dari {nScen}).</>
                      : <>✗ Tidak sama dengan pipeline Python. Laporkan.</>)
                    : <>Kombinasi ini dihitung di browser; pipeline Python menyimpan radius 5, 10, 20 km untuk definisi RS.</>}
                </div>
                <button type="button" className="linkbtn" onClick={() => setS(base)}>Kembalikan ke skenario dasar</button>
              </div>
              {s.rs === "damkar" && (
                <div className="note warn">Data pemadam sangat tidak lengkap: hanya {int(cov.national_counts_in_indonesia.damkar)} titik, dan {cov.kab_zero.damkar_overture} dari {cov.n_admin_kab} kab/kota tidak punya satu pun. Angka rendah di sini sebagian besar mencerminkan data yang hilang.</div>
              )}
              {s.rs === "mentah" && (
                <div className="note warn">Label "hospital" mentah juga berisi klinik ({pct(cov.rs_mentah_name_mix.klinik, 0)}) dan puskesmas ({pct(cov.rs_mentah_name_mix.puskesmas, 0)}), jadi jaraknya terlihat lebih dekat dari kenyataan rumah sakit.</div>
              )}
              <h3>Kab/kota dengan porsi titik terjauh</h3>
              <p style={{ fontSize: 13.5 }}>Hanya kab/kota dengan minimal 10 titik industri. Di peta, kab/kota dengan kurang dari 10 titik digambar pudar.</p>
              <KabTable ids={underTop.slice(0, 10)} kabById={kabById} onPick={setSel}
                cols={[
                  { h: "Titik", f: (id) => int(curRes?.kab.n[id]) },
                  { h: `> ${s.radius} km`, f: (id) => { const n = curRes?.kab.n[id] ?? 0; return pct(n ? (n - (curRes?.kab.nCov[id] ?? 0)) / n : null, 0); } },
                ]} />
              <p style={{ fontSize: 13 }}>Peringkat ini <b>tidak kokoh</b>: berubah banyak saat asumsi diganti (bab 4).</p>
            </>
          )}

          {chapter === "uji" && (
            <>
              <div className="kicker">Bab 3 · Uji kebenaran</div>
              <h2>Bisakah peta ini dipercaya?</h2>
              <p className="lead">Setiap langkah spasial dicek dengan cara kedua yang independen. Hasilnya di bawah, apa adanya.</p>
              <Check ok t="Spatial join diulang dengan dua mesin"
                d={<>GeoPandas (GEOS) dan DuckDB spatial memberi kab/kota yang sama untuk {int(chk.join.penuh.engine_check.n_identical)} dari {int(chk.join.penuh.engine_check.n_points)} titik ({pct(chk.join.penuh.engine_check.agreement, 2)}), di batas penuh dan disederhanakan.</>} />
              <Check ok t="Kasus sulit dengan jawaban diketahui"
                d={<>11 kasus buatan (di dalam, tepat di garis batas, di sudut, di lubang poligon, di pulau, di laut) benar 100% di kedua mesin. Titik tepat di garis batas masuk kab/kota dengan nomor terkecil.</>} />
              <Check ok t="Titik di luar Indonesia terbuang"
                d={<>{int(chk.join.penuh.n_outside_all_polygons)} titik di kotak pencarian jatuh di luar semua kab/kota, kebanyakan di Malaysia ({int(chk.join.penuh.outside_by_addr_country.MY)}) dan Singapura ({int(chk.join.penuh.outside_by_addr_country.SG)}). Tidak ada titik berlabel negara lain yang masuk kab/kota. {int(chk.join.penuh.n_pulled_by_nearest_1km)} titik di pantai bisa ditarik ke kab/kota terdekat bila asumsi "≤ 1 km" dipilih.</>} />
              <Check ok={chk.address.agreement >= 0.9} t="Provinsi hasil peta cocok dengan alamat"
                d={<>Untuk {int(chk.address.n_region_recognized)} titik yang alamatnya menyebut provinsi, {pct(chk.address.agreement, 1)} cocok dengan provinsi hasil spatial join. Hanya {pct(cov.address_completeness.share_with_region_text, 0)} titik punya teks provinsi, jadi ini cek sampel, bukan sensus.</>} />
              <Check ok t="Jarak memakai bumi elips"
                d={<>Jarak dihitung dengan geodesik WGS84. Rumus bola (haversine) meleset sampai {pct(chk.sphere_vs_ellipsoid.haversine_max_rel_err, 2)}, dan cara "derajat dikali 111 km" sampai {pct(chk.sphere_vs_ellipsoid.planar_degree_max_rel_err, 1)}. Sampel {chk.distance.sample_n} titik dibandingkan dengan pencarian semua pasangan: selisih {fmt(chk.distance.max_abs_diff_m_vs_bruteforce, 0)} m.</>} />
              <Check ok={chk.area.penuh.pass} t="Luas dihitung di proyeksi sama-luas"
                d={<>Selisih luas proyeksi Lambert sama-luas dengan luas geodesik paling besar {pct(chk.area.penuh.laea_max_rel_err, 3)}. Bila memakai Web Mercator (proyeksi peta web biasa), luas meleset sampai {pct(chk.area.penuh.mercator_max_rel_err, 1)}.</>} />
              <Check ok={false} info t="Lapisan batas punya catatan"
                d={<>Tidak ada geometri rusak dan tidak ada tumpang tindih. Ada {chk.topology.penuh.gap_count} celah kecil ({fmt(chk.topology.penuh.gap_total_km2, 1)} km²). {chk.topology.penuh.n_non_admin_units} unit bukan kab/kota (danau, waduk, hutan; biru di peta) dikeluarkan dari peringkat. Batas provinsi OSM 2017 berbeda dengan batas kab/kota BPS 2020 di {chk.nesting.n_below_99pct} kab/kota; provinsi dipilih dari irisan terbesar.</>} />
              <p style={{ fontSize: 13.5 }}>
                Titik gelap di peta: {int(counts.special)} titik industri yang pindah kab/kota saat batas disederhanakan
                ({pct(chk.join.penuh_vs_sederhana.share_changed, 2)} dari semua titik) atau yang hanya masuk lewat
                aturan pantai ≤ 1 km.
              </p>
            </>
          )}

          {chapter === "sens" && (
            <>
              <div className="kicker">Bab 4 · Ubah asumsi</div>
              <h2>Apa yang berubah bila asumsi diganti?</h2>
              <p className="lead">
                Enam asumsi diubah bersamaan: {nScen} kombinasi. Sebuah kesimpulan disebut <b>kokoh</b> hanya bila
                bertahan di semua kombinasi.
              </p>
              {R.statements.map((st: any) => (
                <div className="check" key={st.id}>
                  <span>{st.kokoh === true ? <span className="badge ok">Kokoh</span> : st.kokoh === false ? <span className="badge no">Tidak kokoh</span> : <span className="badge info">Info</span>}</span>
                  <span className="t" style={{ fontWeight: 500 }}>{st.teks}</span>
                </div>
              ))}
              <h3>Rentang coverage nasional</h3>
              <p style={{ fontSize: 13.5 }}>Batang = rentang dari semua kombinasi lain; garis = skenario dasar.</p>
              <RangeBars rows={[5, 10, 20].map((r) => {
                const sub = R.sensitivity.rows.filter((x: any) => x.radius === r);
                const b = sub.find((x: any) => x.key === scenarioKey({ ...base, radius: r }));
                return { label: `Radius ${r} km`, lo: Math.min(...sub.map((x: any) => x.share_cov)), hi: Math.max(...sub.map((x: any) => x.share_cov)), base: b?.share_cov };
              })} />
              <h3>Asumsi mana yang paling berpengaruh?</h3>
              <p style={{ fontSize: 13.5 }}>Rata-rata perubahan coverage nasional (poin persen) bila hanya satu asumsi diubah.</p>
              <HBars unit=" pp" max={Math.max(...R.influence.map((x: any) => x.rata_pp))}
                rows={R.influence.map((x: any) => ({ label: ASUMSI_LABEL[x.asumsi] ?? x.asumsi, v: x.rata_pp, title: `maksimum ${fmt(x.maks_pp, 1)} pp` }))} />
              <h3>Seberapa sering masuk 10 besar "terjauh dari RS"?</h3>
              <p style={{ fontSize: 13.5 }}>Warna peta = persen kombinasi tempat kab/kota masuk 10 besar.</p>
              <KabTable ids={Object.keys(freq).slice(0, 10).map(Number)} kabById={kabById} onPick={setSel}
                cols={[{ h: "Skenario", f: (id) => pct((freq[String(id)] ?? 0) / nScen, 0) }]} />
              <p style={{ fontSize: 13.5 }}>
                Kecocokan peringkat dengan skenario dasar (Kendall tau, median):{" "}
                <b>{fmt(median(R.sensitivity.rows.map((x: any) => x.tau_underserved)), 2)}</b> untuk "terjauh dari RS",{" "}
                <b>{fmt(median(R.sensitivity.rows.map((x: any) => x.tau_density)), 2)}</b> untuk kepadatan. Nilai 1 berarti urutan sama persis.
              </p>
            </>
          )}

          {chapter === "data" && (
            <>
              <div className="kicker">Bab 5 · Data & batas</div>
              <h2>Dari mana datanya, dan apa yang tidak boleh disimpulkan?</h2>
              <table>
                <thead><tr><th>Lapisan</th><th>Sumber</th><th>Lisensi</th></tr></thead>
                <tbody>
                  <tr><td>Batas kab/kota (514 + 5 unit air/hutan)</td><td>geoBoundaries IDN ADM2, dari BPS + OCHA (2020)</td><td>CC BY 3.0 IGO</td></tr>
                  <tr><td>Batas provinsi (hierarki)</td><td>geoBoundaries IDN ADM1, dari OpenStreetMap (2017)</td><td>ODbL 1.0</td></tr>
                  <tr><td>Titik industri, RS, pemadam</td><td>Overture Maps Places, rilis {R.provenance.overture_release}</td><td>CDLA-Permissive-2.0</td></tr>
                  <tr><td>Kawasan industri dan RS (pembanding)</td><td>Overture Base land use, dari OpenStreetMap</td><td>ODbL 1.0</td></tr>
                </tbody>
              </table>
              <h3>Kelengkapan data</h3>
              <table>
                <thead><tr><th>Lapisan</th><th className="r">Titik</th><th className="r">Kab/kota kosong</th></tr></thead>
                <tbody>
                  <tr><td>Manufaktur (Overture, keyakinan ≥ 0,5)</td><td className="r">{int(cov.national_counts_in_indonesia.industri_sempit_semua_conf)}*</td><td className="r">{cov.kab_zero.industri_overture_sempit_c50}</td></tr>
                  <tr><td>Kawasan industri OSM</td><td className="r">{int(cov.national_counts_in_indonesia.osm_industri_poligon)}</td><td className="r">{cov.kab_zero.industri_osm}</td></tr>
                  <tr><td>Label "hospital" (mentah)</td><td className="r">{int(cov.national_counts_in_indonesia.rs_mentah)}</td><td className="r">{cov.kab_zero.rs_overture_mentah}</td></tr>
                  <tr><td>Rumah sakit (nama jelas, ≥ 0,5)</td><td className="r">{int(cov.national_counts_in_indonesia.rs_nama)}*</td><td className="r">{cov.kab_zero.rs_overture_nama_c50}</td></tr>
                  <tr><td>Rumah sakit OSM</td><td className="r">{int(cov.national_counts_in_indonesia.rs_osm)}</td><td className="r">{cov.kab_zero.rs_osm}</td></tr>
                  <tr><td>Pemadam kebakaran</td><td className="r">{int(cov.national_counts_in_indonesia.damkar)}</td><td className="r">{cov.kab_zero.damkar_overture}</td></tr>
                </tbody>
              </table>
              <p style={{ fontSize: 12.5 }}>* jumlah titik semua skor keyakinan; kolom kab/kota kosong memakai keyakinan ≥ 0,5.</p>
              <h3>Dua sumber, satu arah?</h3>
              <p>
                Jumlah titik manufaktur Overture per kab/kota dibandingkan dengan luas kawasan industri OSM:
                korelasi peringkat Spearman <b>{fmt(cov.cross_source.industri_overture_vs_osm_area.spearman, 2)}</b>.
                Untuk rumah sakit: <b>{fmt(cov.cross_source.rs_overture_nama_vs_osm.spearman, 2)}</b>. Searah, tetapi jauh dari sama;
                kedua sumber sama-sama tidak lengkap.
              </p>
              <h3>Yang tidak diklaim</h3>
              <ul style={{ paddingLeft: 18, color: "var(--ink-2)", fontSize: 14 }}>
                <li>Bukan jumlah resmi pabrik atau rumah sakit. Data BPS/Kemenkes belum dipakai sebagai pembanding.</li>
                <li>Jarak adalah garis lurus, bukan waktu tempuh lewat jalan.</li>
                <li>Hasil ini tidak menjelaskan sebab apa pun; hanya letak titik yang tercatat.</li>
                <li>Label "hospital" Overture banyak berisi klinik dan puskesmas ({pct(cov.rs_mentah_name_mix.klinik, 0)} dan {pct(cov.rs_mentah_name_mix.puskesmas, 0)}).</li>
              </ul>
              <p style={{ fontSize: 13 }}>
                Peta dasar digambar dari lapisan batas sendiri; tidak ada layanan tile pihak ketiga.
                Kode dan cara mengulang: <span className="num">geo-atlas fetch &amp;&amp; geo-atlas run</span>.
              </p>
            </>
          )}
        </div>
      </section>

      <section className="mapwrap" aria-label="Peta">
        {data && (
          <MapView kabGeo={data.kabGeo} provGeo={data.provGeo} mode={mode} choro={choro} points={points} visible={vis}
            indStyle={chapter === "jarak" ? "coverage" : "plain"} nonAdminIds={nonAdminIds} showNonAdmin={chapter === "uji"}
            selectedKab={sel} onSelectKab={setSel} tooltip={tooltip} />
        )}
        {!data && !err && <div className="map-status" role="status">Memuat data…</div>}
        <Legend chapter={chapter} c={c} vis={vis} setVis={setVis} counts={counts} rs={s.rs} radius={s.radius} />
        <div className="attrib">Batas: geoBoundaries/BPS (CC BY 3.0 IGO) · Titik: Overture Maps · © kontributor OpenStreetMap (ODbL)</div>
      </section>
    </div>
  );
}

function median(xs: (number | null)[]) {
  const v = xs.filter((x): x is number => x != null).sort((a, b) => a - b);
  if (!v.length) return null;
  const m = Math.floor(v.length / 2);
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

function Check({ ok, info, t, d }: { ok: boolean; info?: boolean; t: string; d: React.ReactNode }) {
  return (
    <div className="check">
      <span>{info ? <span className="badge info">Catatan</span> : ok ? <span className="badge ok">✓ Lulus</span> : <span className="badge no">✗ Gagal</span>}</span>
      <span className="t">{t}</span>
      <span className="d">{d}</span>
    </div>
  );
}

function KabTable({ ids, kabById, onPick, cols }: {
  ids: number[]; kabById: Map<number, Kab>; onPick: (id: number) => void; cols: { h: string; f: (id: number) => string }[];
}) {
  if (!ids.length) return <p>Memuat…</p>;
  return (
    <table>
      <thead><tr><th>#</th><th>Kab/kota</th>{cols.map((c) => <th key={c.h} className="r">{c.h}</th>)}</tr></thead>
      <tbody>
        {ids.map((id, i) => {
          const k = kabById.get(id);
          return (
            <tr key={id} className="clickable" onClick={() => onPick(id)}>
              <td className="num">{i + 1}</td>
              <td><button type="button" className="linkbtn" onClick={(e) => { e.stopPropagation(); onPick(id); }}>{k?.nm}</button><div style={{ fontSize: 12, color: "var(--ink-3)" }}>{k?.pvn}</div></td>
              {cols.map((c) => <td key={c.h} className="r">{c.f(id)}</td>)}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function KabPicker({ kab, value, onChange }: { kab: Kab[]; value: number | null; onChange: (id: number | null) => void }) {
  const sorted = useMemo(() => [...kab].filter((k) => k.adm === 1).sort((a, b) => a.nm.localeCompare(b.nm, "id")), [kab]);
  return (
    <div className="ctl" style={{ marginBottom: 14 }}>
      <label htmlFor="kabpick">Cari kab/kota</label>
      <select id="kabpick" value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}>
        <option value="">Pilih dari {sorted.length || 514} kab/kota…</option>
        {sorted.map((k) => <option key={k.id} value={k.id}>{k.nm} ({k.pvn})</option>)}
      </select>
    </div>
  );
}

function KabCard({ k, res, s, rank, onClose }: { k: Kab; res: ReturnType<typeof compute> | null; s: Scenario; rank: number; onClose: () => void }) {
  const n = res?.kab.n[k.id] ?? 0;
  const nc = res?.kab.nCov[k.id] ?? 0;
  return (
    <div className="kabcard" aria-live="polite">
      <h3>{k.nm}</h3>
      <div className="sub">{k.pvn} · {fmt(k.km2, 0)} km²</div>
      <dl>
        <dt>Titik industri (skenario aktif)</dt><dd>{int(n)}</dd>
        <dt>Dalam {s.radius} km dari {FAS_LABEL[s.rs].toLowerCase()}</dt><dd>{n ? pct(nc / n, 0) : "–"}</dd>
        <dt>Kawasan industri OSM</dt><dd>{fmt(Number(k.osm_ind_km2 ?? 0), 2)} km²</dd>
        <dt>Rumah sakit (nama jelas / OSM)</dt><dd>{int(Number(k.ov_rs ?? 0))} / {int(Number(k.osm_rs ?? 0))}</dd>
        <dt>Pemadam tercatat</dt><dd>{int(Number(k.ov_fire ?? 0))}</dd>
        {rank >= 0 && <><dt>Peringkat "terjauh dari fasilitas"</dt><dd>{rank + 1}</dd></>}
      </dl>
      <button type="button" className="linkbtn" onClick={onClose} style={{ marginTop: 8 }}>Tutup</button>
    </div>
  );
}

function Legend({ chapter, c, vis, setVis, counts, rs, radius }: {
  chapter: Chapter; c: (typeof COLORS)["light"]; vis: Record<LayerKey, boolean>;
  setVis: (f: (v: Record<LayerKey, boolean>) => Record<LayerKey, boolean>) => void;
  counts: Record<string, number>; rs: Fasilitas; radius: number;
}) {
  const [open, setOpen] = useState(true);
  useEffect(() => { if (matchMedia("(max-width: 900px)").matches) setOpen(false); }, []);
  const row = (k: LayerKey, label: string, sw: React.ReactNode, cnt?: number) => (
    <label className="row" key={k}>
      <input type="checkbox" checked={vis[k]} onChange={(e) => setVis((v) => ({ ...v, [k]: e.target.checked }))} />
      {sw}<span>{label}</span>{cnt != null && <span className="cnt">{int(cnt)}</span>}
    </label>
  );
  return (
    <details className="legend" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Legenda & lapisan <span aria-hidden="true">{open ? "−" : "+"}</span></summary>
      <div className="body">
        {chapter === "peta" && <div className="grp"><RampLegend title="Titik industri per 1.000 km²" colors={c.teal} labels={["≤1", "≤5", "≤20", "≤100", ">100"]} extra="Polos tanpa warna = tidak ada titik tercatat" /></div>}
        {chapter === "jarak" && <div className="grp"><RampLegend title={`Porsi titik di luar ${radius} km`} colors={c.terra} labels={["<5%", "<15%", "<30%", "<50%", "≥50%"]} extra="Pudar = kurang dari 10 titik" /></div>}
        {chapter === "sens" && <div className="grp"><RampLegend title="Persen skenario masuk 10 besar" colors={c.terra} labels={["<10%", "<25%", "<50%", "<75%", "≥75%"]} /></div>}
        <div className="grp">
          <div className="grp-t">Titik</div>
          {chapter === "jarak" ? (
            <>
              {row("ind", "Industri di luar radius", <span className="sw" style={{ background: c.ink }} />)}
              <div style={{ fontSize: 11.5, color: "var(--ink-3)", margin: "0 0 4px 24px" }}>Titik kecil samar = dalam radius</div>
            </>
          ) : row("ind", "Industri (Overture)", <span className="sw" style={{ background: c.ink }} />, counts.ind)}
          {row("indOsm", "Kawasan industri (OSM)", <span className="sw hollow" style={{ color: c.ink }} />, counts.indOsm)}
          {row("rs", rs === "mentah" && chapter === "jarak" ? "Label hospital (Overture)" : "Rumah sakit (Overture)", <span className="sw" style={{ background: c.rs }} />, counts.rs)}
          {row("rsOsm", "Rumah sakit (OSM)", <span className="sw hollow" style={{ color: c.rs }} />, counts.rsOsm)}
          {row("damkar", "Pemadam kebakaran", <span className="sw" style={{ background: c.damkar }} />, counts.damkar)}
          {chapter === "uji" && row("special", "Titik yang pindah kab/kota", <span className="sw" style={{ background: c.ink, boxShadow: `0 0 0 2px ${c.ring}, 0 0 0 3px ${c.ink}` }} />, counts.special)}
        </div>
        <div className="grp">
          <div className="grp-t">Wilayah</div>
          {row("prov", "Batas provinsi", <span className="sw sq" style={{ background: "transparent", border: `2px solid ${c.provLine}` }} />)}
          {row("kab", "Batas kab/kota", <span className="sw sq" style={{ background: "transparent", border: `1px solid ${c.kabLine}` }} />)}
          {chapter === "uji" && <div className="row"><span className="sw sq" style={{ background: c.nonAdmin, marginLeft: 24 }} /><span>Danau, waduk, hutan (bukan kab/kota)</span></div>}
        </div>
      </div>
    </details>
  );
}
