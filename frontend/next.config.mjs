/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [{ source: '/hybrid/:path*', destination: 'http://127.0.0.1:5055/api/:path*' }];
  },
};
export default nextConfig;
