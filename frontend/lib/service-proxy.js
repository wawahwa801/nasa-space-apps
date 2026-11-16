// Bindings resolve at request time, not during the Next.js build.
export async function proxyService(request, route, envName, local) {
 const base = process.env[envName] || (process.env.VERCEL ? null : local);
 if (!base) return Response.json({error:`${envName} service is not configured`},{status:503});
 const target = new URL(base);
 target.pathname = target.pathname.replace(/\/$/, '') + '/api/' + route;
 target.search = new URL(request.url).search;
 try {
  const upstream = await fetch(target, {
   method:request.method,
   headers:{'Content-Type':'application/json',
    ...(request.headers.get('X-Model-ID') ? {'X-Model-ID':request.headers.get('X-Model-ID')} : {})},
   body:request.method === 'POST' ? await request.text() : undefined,
   cache:'no-store',signal:AbortSignal.timeout(170000)
  });
  return new Response(upstream.body,{status:upstream.status,headers:{'Content-Type':upstream.headers.get('Content-Type') || 'application/json','Cache-Control':'no-store'}});
 } catch {return Response.json({error:'Service is temporarily unavailable. Please retry.'},{status:503});}
}
