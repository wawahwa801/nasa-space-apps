/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [{source:'/insight-api/:path*',destination:'http://127.0.0.1:5000/api/:path*'}, { source: '/hybrid/:path*', destination: 'http://127.0.0.1:5055/api/:path*' }];
  },
};
export default nextConfig;
