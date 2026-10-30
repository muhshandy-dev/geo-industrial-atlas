# Deploy ke Cloudflare Pages

1. Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git → pilih
   `muhshandy-dev/geo-industrial-atlas`.
2. Nama proyek: `geo-industrial-atlas` (alamat `geo-industrial-atlas.pages.dev` bila slug tersedia).
3. Production branch: `main`. Root directory: `web`.
4. Build command: `npm ci && npm run build`. Output directory: `dist`.
5. Environment variable: `NODE_VERSION` = `24` (Astro 7 butuh Node ≥ 22.23).
6. Setelah deploy, buka situs dan cek kelima bab di desktop dan ponsel.

Situs sepenuhnya statis (tanpa backend, tanpa layanan tile pihak ketiga), jadi tidak tidur saat sepi.
File terbesar sekitar 2,7 MB (di bawah batas 25 MiB per file).
