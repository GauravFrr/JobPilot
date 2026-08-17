/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.API_URL || 'http://api:8000'}/api/v1/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
