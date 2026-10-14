/** @type {import('next').NextConfig} */
const nextConfig = {
  // Same-origin /api proxy -> avoids CORS and keeps the demo on one URL.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" },
    ];
  },
};

export default nextConfig;
