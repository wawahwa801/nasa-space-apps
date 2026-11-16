import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.dirname(fileURLToPath(import.meta.url));
const backend = process.env.BACKEND_URL || 'http://127.0.0.1:5000';
export default {
 outputFileTracingRoot: path.join(root, '..'),
 outputFileTracingIncludes: {'/nasa-dashboard/*':['../fire-dashboard/**/*']},
 async rewrites(){return process.env.VERCEL ? [] : [
 {source:'/api/:path*',destination:`${backend}/api/:path*`}];},
 experimental:{proxyTimeout:180000}
};
