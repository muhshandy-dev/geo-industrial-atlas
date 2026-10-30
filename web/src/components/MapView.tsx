import { useEffect, useRef, useState } from "react";
import type { Map as MLMap, GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { COLORS, type Mode } from "../lib/theme";

export type FC = GeoJSON.FeatureCollection;
export type Ramp = "teal" | "terra";

export interface Choropleth {
  values: (number | null)[]; // indeks = kab_id
  faded?: boolean[];
  breaks: number[]; // 4 ambang untuk 5 kelas
  ramp: Ramp;
}

export interface PointLayers {
  ind: FC;
  indOsm: FC;
  rs: FC;
  rsOsm: FC;
  damkar: FC;
  special: FC;
}

export type LayerKey = "ind" | "indOsm" | "rs" | "rsOsm" | "damkar" | "special" | "prov" | "kab";

interface Props {
  kabGeo: FC;
  provGeo: FC;
  mode: Mode;
  choro: Choropleth | null;
  points: PointLayers;
  visible: Record<LayerKey, boolean>;
  indStyle: "plain" | "coverage";
  nonAdminIds: number[];
  showNonAdmin: boolean;
  selectedKab: number | null;
  onSelectKab: (id: number | null) => void;
  tooltip: (kabId: number) => string;
}

const INDONESIA: [[number, number], [number, number]] = [[94.8, -11.2], [141.2, 6.2]];

function fillExpr(choro: Choropleth | null, mode: Mode): any {
  const c = COLORS[mode];
  if (!choro) return c.land;
  const ramp = c[choro.ramp];
  const step: any[] = ["step", ["feature-state", "v"], ramp[0]];
  choro.breaks.forEach((b, i) => step.push(b, ramp[i + 1]));
  return ["case", ["!=", ["typeof", ["feature-state", "v"]], "number"], c.landNoData, step];
}

// sisakan ruang untuk legenda di layar lebar
const pad = () =>
  typeof window !== "undefined" && window.innerWidth > 900 ? { top: 20, bottom: 20, left: 20, right: 300 } : 12;

const radius = (base: number): any => ["interpolate", ["linear"], ["zoom"], 4, base, 7, base * 1.8, 11, base * 3];
// zoom harus di tingkat teratas ekspresi; kondisi per titik masuk ke tiap anak tangga
const radiusIf = (cond: any, a: number, b: number): any =>
  ["interpolate", ["linear"], ["zoom"], 4, ["case", cond, a, b], 7, ["case", cond, a * 1.8, b * 1.8], 11, ["case", cond, a * 3, b * 3]];

export default function MapView(p: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; html: string } | null>(null);
  const latest = useRef(p);
  latest.current = p;

  // buat peta sekali
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const mod: any = await import("maplibre-gl");
      const ml = mod.default ?? mod;
      ml.setWorkerUrl(workerUrl);
      if (cancelled || !ref.current) return;
      const c = COLORS[latest.current.mode];
      const map = new ml.Map({
        container: ref.current,
        style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": c.sea } }] },
        bounds: INDONESIA,
        fitBoundsOptions: { padding: pad() },
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        maxZoom: 13,
        minZoom: 2,
      });
      map.touchZoomRotate.disableRotation();
      map.addControl(new ml.NavigationControl({ showCompass: false }), "top-left");
      map.getCanvas().setAttribute("aria-label", "Peta kabupaten/kota Indonesia. Data yang sama tersedia sebagai tabel di panel.");
      map.on("load", () => {
        const P = latest.current;
        map.addSource("kab", { type: "geojson", data: P.kabGeo, promoteId: "id" });
        map.addSource("prov", { type: "geojson", data: P.provGeo });
        map.addLayer({ id: "kab-fill", type: "fill", source: "kab", paint: { "fill-color": c.land, "fill-opacity": 1 } });
        map.addLayer({ id: "kab-nonadmin", type: "fill", source: "kab", filter: ["in", ["get", "id"], ["literal", []]], paint: { "fill-color": c.nonAdmin, "fill-opacity": 0.85 } });
        map.addLayer({ id: "kab-line", type: "line", source: "kab", paint: { "line-color": c.kabLine, "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.3, 9, 1] } });
        map.addLayer({ id: "prov-line", type: "line", source: "prov", paint: { "line-color": c.provLine, "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.8, 9, 2] } });
        map.addLayer({ id: "kab-select", type: "line", source: "kab", filter: ["==", ["get", "id"], -1], paint: { "line-color": c.select, "line-width": 2.5 } });
        for (const k of ["indOsm", "rsOsm", "rs", "damkar", "ind", "special"] as const) {
          map.addSource(k, { type: "geojson", data: P.points[k] });
        }
        map.addLayer({ id: "indOsm", type: "circle", source: "indOsm", paint: { "circle-radius": radius(1.6), "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": c.ink, "circle-stroke-width": 1.1 } });
        map.addLayer({ id: "ind", type: "circle", source: "ind", paint: { "circle-radius": radius(1.3), "circle-color": c.ink, "circle-opacity": 0.75 } });
        map.addLayer({ id: "rsOsm", type: "circle", source: "rsOsm", paint: { "circle-radius": radius(2.2), "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": c.rs, "circle-stroke-width": 1.4 } });
        map.addLayer({ id: "rs", type: "circle", source: "rs", paint: { "circle-radius": radius(1.6), "circle-color": c.rs, "circle-stroke-color": c.ring, "circle-stroke-width": 0.6 } });
        map.addLayer({ id: "damkar", type: "circle", source: "damkar", paint: { "circle-radius": radius(2.4), "circle-color": c.damkar, "circle-stroke-color": c.ring, "circle-stroke-width": 1 } });
        map.addLayer({ id: "special", type: "circle", source: "special", paint: { "circle-radius": radius(3), "circle-color": c.ink, "circle-stroke-color": c.ring, "circle-stroke-width": 1.5 } });

        map.on("mousemove", "kab-fill", (e: MapMouseEvent & { features?: any[] }) => {
          const f = e.features?.[0];
          if (!f) return;
          map.getCanvas().style.cursor = "pointer";
          setTip({ x: e.point.x, y: e.point.y, html: latest.current.tooltip(f.properties.id) });
        });
        map.on("mouseleave", "kab-fill", () => { map.getCanvas().style.cursor = ""; setTip(null); });
        map.on("click", "kab-fill", (e: MapMouseEvent & { features?: any[] }) => {
          const f = e.features?.[0];
          if (f) latest.current.onSelectKab(f.properties.id);
        });
        map.resize();
        map.fitBounds(INDONESIA, { padding: pad(), duration: 0 });
        setReady(true);
      });
      mapRef.current = map;
    })();
    return () => { cancelled = true; mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  // warna tema
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const c = COLORS[p.mode];
    map.setPaintProperty("bg", "background-color", c.sea);
    map.setPaintProperty("kab-line", "line-color", c.kabLine);
    map.setPaintProperty("prov-line", "line-color", c.provLine);
    map.setPaintProperty("kab-select", "line-color", c.select);
    map.setPaintProperty("kab-nonadmin", "fill-color", c.nonAdmin);
    map.setPaintProperty("indOsm", "circle-stroke-color", c.ink);
    map.setPaintProperty("rsOsm", "circle-stroke-color", c.rs);
    map.setPaintProperty("rs", "circle-color", c.rs);
    map.setPaintProperty("rs", "circle-stroke-color", c.ring);
    map.setPaintProperty("damkar", "circle-color", c.damkar);
    map.setPaintProperty("damkar", "circle-stroke-color", c.ring);
    map.setPaintProperty("special", "circle-color", c.ink);
    map.setPaintProperty("special", "circle-stroke-color", c.ring);
    map.setPaintProperty("ind", "circle-color", c.ink);
    map.setPaintProperty("ind", "circle-stroke-color", c.ring);
    map.setPaintProperty("kab-fill", "fill-color", fillExpr(p.choro, p.mode));
  }, [p.mode, ready, p.choro]);

  // nilai koroplet
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const vals = p.choro?.values ?? [];
    const faded = p.choro?.faded ?? [];
    for (const f of p.kabGeo.features) {
      const id = (f.properties as any).id as number;
      map.setFeatureState({ source: "kab", id }, { v: p.choro ? vals[id] ?? null : null, faded: !!faded[id] });
    }
    map.setPaintProperty("kab-fill", "fill-opacity", ["case", ["boolean", ["feature-state", "faded"], false], 0.5, 1]);
  }, [p.choro, ready, p.kabGeo]);

  // gaya titik industri
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (p.indStyle === "coverage") {
      map.setPaintProperty("ind", "circle-radius", radiusIf(["==", ["get", "c"], 0], 2.4, 1.1));
      map.setPaintProperty("ind", "circle-opacity", ["case", ["==", ["get", "c"], 0], 1, 0.3]);
      map.setPaintProperty("ind", "circle-stroke-width", ["case", ["==", ["get", "c"], 0], 1, 0]);
    } else {
      map.setPaintProperty("ind", "circle-radius", radius(1.3));
      map.setPaintProperty("ind", "circle-opacity", 0.75);
      map.setPaintProperty("ind", "circle-stroke-width", 0);
    }
  }, [p.indStyle, ready]);

  // data titik
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    for (const k of ["indOsm", "rsOsm", "rs", "damkar", "ind", "special"] as const) {
      (map.getSource(k) as GeoJSONSource | undefined)?.setData(p.points[k]);
    }
  }, [p.points, ready]);

  // visibilitas lapisan
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const v = (b: boolean) => (b ? "visible" : "none");
    for (const k of ["indOsm", "rsOsm", "rs", "damkar", "ind", "special"] as const) map.setLayoutProperty(k, "visibility", v(p.visible[k]));
    map.setLayoutProperty("prov-line", "visibility", v(p.visible.prov));
    map.setLayoutProperty("kab-line", "visibility", v(p.visible.kab));
    map.setFilter("kab-nonadmin", ["in", ["get", "id"], ["literal", p.showNonAdmin ? p.nonAdminIds : []]]);
  }, [p.visible, p.showNonAdmin, p.nonAdminIds, ready]);

  // kab terpilih
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setFilter("kab-select", ["==", ["get", "id"], p.selectedKab ?? -1]);
    if (p.selectedKab != null) {
      const f = p.kabGeo.features.find((x) => (x.properties as any).id === p.selectedKab);
      if (f) {
        const b = bbox(f.geometry);
        map.fitBounds(b, { padding: typeof pad() === "number" ? 40 : { top: 60, bottom: 60, left: 60, right: 320 }, maxZoom: 9, duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 600 });
      }
    }
  }, [p.selectedKab, ready, p.kabGeo]);

  return (
    <>
      <div ref={ref} className="map" role="region" aria-label="Peta atlas" />
      {!ready && <div className="map-status" role="status">Memuat peta…</div>}
      {tip && (
        <div className="tooltip" style={{ left: Math.min(tip.x + 14, (ref.current?.clientWidth ?? 400) - 250), top: tip.y + 14 }}
          dangerouslySetInnerHTML={{ __html: tip.html }} />
      )}
    </>
  );
}

function bbox(g: GeoJSON.Geometry): [[number, number], [number, number]] {
  let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
  const walk = (c: any) => {
    if (typeof c[0] === "number") {
      x0 = Math.min(x0, c[0]); y0 = Math.min(y0, c[1]); x1 = Math.max(x1, c[0]); y1 = Math.max(y1, c[1]);
    } else c.forEach(walk);
  };
  walk((g as any).coordinates);
  return [[x0, y0], [x1, y1]];
}
