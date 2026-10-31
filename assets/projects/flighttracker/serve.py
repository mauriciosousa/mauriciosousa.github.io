#!/usr/bin/env python3
"""
Flight Globe local helper.

Opening index.html straight from disk shows the globe and the route, but the live
ADS-B services (adsb.lol, airplanes.live) refuse requests that come from a web page,
including a local file. This helper runs on your Mac, asks those services on the
page's behalf, and also serves the page itself.

Start:  double-click "Start Flight Globe.command", or run   python3 serve.py
Use:    http://127.0.0.1:8765   (a double-clicked index.html also works while this runs)
Stop:   close the Terminal window, or press Ctrl+C.

Python standard library only; nothing to install.
"""
import http.server
import json
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

PORT = int(os.environ.get('FLIGHT_GLOBE_PORT', '8765'))
HERE = os.path.dirname(os.path.abspath(__file__))

UPSTREAM = {
    'adsb.lol': 'https://api.adsb.lol',
    'airplanes.live': 'https://api.airplanes.live',
    'adsbdb': 'https://api.adsbdb.com',
}
# Only these lookups are relayed; anything else under /relay/ is a 404.
ROUTES = [
    re.compile(r'^/relay/(adsb\.lol|airplanes\.live)(/v2/(?:callsign|hex|reg)/[A-Za-z0-9-]{1,10})$'),
    re.compile(r'^/relay/(adsbdb)(/v0/callsign/[A-Za-z0-9]{1,10})$'),
]
CACHE_SECONDS = 8  # the page asks once a minute; this just avoids double calls


def _ssl_context():
    # python.org builds on macOS ship without root certificates; certifi fixes that when present.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


SSL = _ssl_context()
CACHE = {}
LOCK = threading.Lock()


def fetch(url):
    now = time.time()
    with LOCK:
        hit = CACHE.get(url)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1:]
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': 'FlightGlobe/1.0 (personal flight display)',
    })
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL if url.startswith('https:') else None) as r:
            out = (r.status, r.headers.get('Content-Type', 'application/json'), r.read())
    except urllib.error.HTTPError as e:
        out = (e.code, (e.headers.get('Content-Type') if e.headers else None) or 'text/plain', e.read() or b'')
    except Exception as e:  # network down, DNS, certificates
        reason = str(getattr(e, 'reason', e))
        if 'CERTIFICATE' in reason.upper():
            reason += ('  -> Python cannot verify HTTPS certificates. Run "Install Certificates.command" '
                       'in your Python folder (Applications/Python 3.x), or: pip3 install certifi')
        print(f'  ! {url}\n    {reason}', flush=True)
        return (502, 'application/json', json.dumps({'error': reason}).encode())
    with LOCK:
        CACHE[url] = (now,) + out
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def _send(self, status, ctype, body):
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/relay', '/relay/'):
            return self._send(200, 'text/plain; charset=utf-8', b'Flight Globe helper is running.')
        if path.startswith('/relay/'):
            for rx in ROUTES:
                m = rx.match(path)
                if m:
                    return self._send(*fetch(UPSTREAM[m.group(1)] + m.group(2)))
            return self._send(404, 'text/plain', b'Not found')
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass  # keep the Terminal window quiet; problems are printed by fetch()


def main():
    url = f'http://127.0.0.1:{PORT}/'
    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError:
        print(f'Port {PORT} is already in use, so the helper is probably running already. Opening {url}')
        webbrowser.open(url)
        return
    print(f'Flight Globe helper is running at {url}\n'
          f'Keep this window open while you use the tracker. Press Ctrl+C to stop.', flush=True)
    if '--no-browser' not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
