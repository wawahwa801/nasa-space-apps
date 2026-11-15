/** @type {import('next').NextConfig} */

// The Flask backend (backend/app.py). /api/* is proxied to it so the page and
// the embedded fire dashboard can call it without cross-origin requests.
const backend = process.env.BACKEND_URL || "http://127.0.0.1:5000";

const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  experimental: {
    // Reasoning models can take over a minute to answer (default is 30 s).
    proxyTimeout: 180_000,
  },
};

export default nextConfig;
