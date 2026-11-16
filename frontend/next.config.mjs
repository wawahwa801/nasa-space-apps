const backend = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
export default {
 async rewrites(){return [
 {source:'/api/:path*',destination:`${backend}/api/:path*`},
 {source:'/insight-api/:path*',destination:`${backend}/api/:path*`},
 {source:'/hybrid/:path*',destination:`${backend}/api/hybrid/:path*`}];},
 experimental:{proxyTimeout:180000}
};
