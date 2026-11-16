import {proxyService} from '../../../lib/service-proxy';
export const dynamic='force-dynamic';
export const maxDuration=180;
async function handle(request,{params}) {
 const route=(await params).path.join('/');
 const allowed={environment:['GET'],runs:['GET'],compare:['GET'],simulate:['POST']};
 if (!Object.hasOwn(allowed,route)) return new Response('Not found',{status:404});
 if (!allowed[route].includes(request.method)) return new Response('Method not allowed',{status:405});
 return proxyService(request,'hybrid/'+route,'BACKEND_URL','http://127.0.0.1:5000');
}
export {handle as GET,handle as POST};
