"""Run: python3 server.py --port 8010 (localhost only)."""
import argparse
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from model import example, ensemble, validate
ROOT=Path(__file__).resolve().parent
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'web'),**kw)
    def reply(self,status,payload):
        raw=json.dumps(payload,allow_nan=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/api/example': return self.reply(200,example())
        return super().do_GET()
    def do_POST(self):
        if self.path not in ['/api/validate','/api/simulate']: return self.reply(404,{'error':'Unknown endpoint'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=200000: raise ValueError('Request must be 1–200000 bytes')
            s=json.loads(self.rfile.read(length));validate(s)
            return self.reply(200,ensemble(s) if self.path=='/api/simulate' else {'valid':True})
        except (ValueError,TypeError,KeyError,OverflowError) as e: return self.reply(400,{'error':str(e)})
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8010);args=parser.parse_args();print(f'http://localhost:{args.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
