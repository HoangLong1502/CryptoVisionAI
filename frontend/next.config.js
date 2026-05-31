/** @type {import('next').NextConfig} */
const backendOrigin =
  (process.env.INTERNAL_API_URL || 'http://127.0.0.1:5566/api/v1').replace(/\/api\/v1\/?$/i, '');

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendOrigin}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
