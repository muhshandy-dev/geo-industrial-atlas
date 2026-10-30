const nf = new Intl.NumberFormat("id-ID");
export const fmt = (n: number | null | undefined, d = 0) =>
  n == null || Number.isNaN(n) ? "–" : new Intl.NumberFormat("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d }).format(n);
export const int = (n: number | null | undefined) => (n == null ? "–" : nf.format(n));
export const pct = (x: number | null | undefined, d = 1) => (x == null ? "–" : `${fmt(x * 100, d)}%`);
export const km = (m: number) => (m >= 1000 ? `${fmt(m / 1000, 1)} km` : `${fmt(m)} m`);
