import { fmt, pct } from "../lib/format";

export function RangeBars({ rows }: { rows: { label: string; lo: number; hi: number; base?: number }[] }) {
  return (
    <div className="bars" role="list">
      {rows.map((r) => (
        <div className="bar" role="listitem" key={r.label}
          aria-label={`${r.label}: ${pct(r.lo)} sampai ${pct(r.hi)}${r.base != null ? `, skenario dasar ${pct(r.base)}` : ""}`}>
          <span>{r.label}</span>
          <span className="track" title={`${pct(r.lo)} – ${pct(r.hi)}`}>
            <span className="range" style={{ left: `${r.lo * 100}%`, width: `${Math.max(0.6, (r.hi - r.lo) * 100)}%` }} />
            {r.base != null && <span className="tick" style={{ left: `calc(${r.base * 100}% - 1px)` }} />}
          </span>
          <span className="val">{fmt(r.lo * 100, 0)}–{fmt(r.hi * 100, 0)}%</span>
        </div>
      ))}
    </div>
  );
}

export function HBars({ rows, max, unit = "" }: { rows: { label: string; v: number; title?: string }[]; max: number; unit?: string }) {
  return (
    <div className="bars" role="list">
      {rows.map((r) => (
        <div className="bar" role="listitem" key={r.label} aria-label={`${r.label}: ${fmt(r.v, 1)}${unit}`}>
          <span>{r.label}</span>
          <span className="track" title={r.title ?? `${fmt(r.v, 1)}${unit}`}>
            <span className="fill" style={{ width: `${Math.max(0.8, (r.v / max) * 100)}%` }} />
          </span>
          <span className="val">{fmt(r.v, 1)}{unit}</span>
        </div>
      ))}
    </div>
  );
}

export function RampLegend({ colors, labels, title, extra }: { colors: string[]; labels: string[]; title: string; extra?: string }) {
  return (
    <div>
      <div className="grp-t">{title}</div>
      <div className="ramp" aria-hidden="true">{colors.map((c) => <span key={c} style={{ background: c }} />)}</div>
      <div className="ramp-l" aria-hidden="true">{labels.map((l, i) => <span key={i}>{l}</span>)}</div>
      <p className="sr-only">{title}: kelas {labels.join(", ")}</p>
      {extra && <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 4 }}>{extra}</div>}
    </div>
  );
}
