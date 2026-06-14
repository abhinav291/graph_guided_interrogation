/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // PDF upload runs Docling + many Groq calls — allow long proxy waits in dev.
  experimental: {
    proxyTimeout: 300_000,
  },
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
