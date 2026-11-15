"""Run: python3 physics-flex2/app.py [--port 5054] [--model fitted.json]."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from model import INDEX, fit, predict, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5054)
    parser.add_argument('--fit', metavar='MEASUREMENTS_CSV')
    parser.add_argument('--output', default='fitted.json')
    parser.add_argument('--model')
    args = parser.parse_args()
    if args.fit:
        result = fit(args.fit)
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
        print(f"Wrote {args.output}; {len(result['training_runs'])} training runs, {len(result['held_out'])} held-out results")
        return
    fitted = json.loads(Path(args.model).read_text()) if args.model else None
    if fitted:
        import hashlib
        if fitted['source_index_sha256'] != hashlib.sha256(INDEX.read_bytes()).hexdigest():
            raise ValueError('Model and source index do not match')

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, kind='application/json'):
            raw = json.dumps(body, allow_nan=False).encode() if kind == 'application/json' else body
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == '/':
                self.reply(200, Path(__file__).with_name('index.html').read_bytes(), 'text/html; charset=utf-8')
            elif self.path == '/api/runs':
                self.reply(200, dict(records=records(), fitted=fitted is not None))
            else:
                self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            if self.path != '/api/predict':
                self.reply(404, {'error': 'Not found'})
                return
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 16000:
                    raise ValueError('Expected JSON body of at most 16000 bytes')
                query = json.loads(self.rfile.read(size))
                self.reply(200, predict(query, fitted))
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                self.reply(400, {'error': str(exc)})

    server = HTTPServer(('127.0.0.1', args.port), Handler)
    print(f'FLEX-2 droplet baseline: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
