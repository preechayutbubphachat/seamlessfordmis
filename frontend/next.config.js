/** @type {import('next').NextConfig} */
const isDevelopment = process.env.NODE_ENV === "development";

// D4: DESKTOP_STATIC=1 enables static export for the Desktop Local Edition.
// Default build (LAN edition, `next build` + `next start`/server.js) is unchanged.
const isDesktopStatic = process.env.DESKTOP_STATIC === "1";

const nextConfig = {
  reactStrictMode: true,
  // Keep dev and production artifacts separate so `next build` does not poison the
  // active dev server with stale chunk references such as `./765.js`.
  distDir: isDevelopment ? ".next-dev" : ".next",
  ...(isDesktopStatic
    ? {
        output: "export",
        // folder/index.html layout so FastAPI StaticFiles(html=True) maps URLs cleanly
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {}),
};

module.exports = nextConfig;
