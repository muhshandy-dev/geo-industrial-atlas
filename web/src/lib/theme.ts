// Warna peta per tema. Palet kategori dan ramp sudah divalidasi (skrip validate_palette dataviz):
// titik RS #C0508A / damkar #B07400 (terang), #D7669F / #C08A16 (gelap);
// ramp teal dan terakota: monoton, ujung terang >= 2:1 terhadap permukaan.
export type Mode = "light" | "dark";

export interface MapColors {
  sea: string;
  land: string;
  landNoData: string;
  kabLine: string;
  provLine: string;
  select: string;
  ink: string;
  ring: string;
  rs: string;
  damkar: string;
  nonAdmin: string;
  teal: string[];
  terra: string[];
}

export const COLORS: Record<Mode, MapColors> = {
  light: {
    sea: "#dce8e3",
    land: "#efe7d3",
    landNoData: "#e9e0c9",
    kabLine: "#cdbf9c",
    provLine: "#6f6248",
    select: "#0a4f49",
    ink: "#1d2b29",
    ring: "#f5efe0",
    rs: "#c0508a",
    damkar: "#b07400",
    nonAdmin: "#7ea6c4",
    teal: ["#6cb3a7", "#4b998d", "#2e7e73", "#176158", "#0a433d"],
    terra: ["#e0956c", "#c9734a", "#aa552f", "#843e1d", "#5c280f"],
  },
  dark: {
    sea: "#0c1514",
    land: "#1b2725",
    landNoData: "#1b2725",
    kabLine: "#2f403d",
    provLine: "#8e9a92",
    select: "#f2d58a",
    ink: "#ece6d6",
    ring: "#101a19",
    rs: "#d7669f",
    damkar: "#c08a16",
    nonAdmin: "#3f6c8c",
    teal: ["#1f5e56", "#277368", "#33897d", "#4fa598", "#88cbc0"],
    terra: ["#7e3d1b", "#984b24", "#b45f33", "#d27e51", "#edac88"],
  },
};

export function currentMode(): Mode {
  if (typeof document === "undefined") return "light";
  const t = document.documentElement.dataset.theme;
  if (t === "light" || t === "dark") return t;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
