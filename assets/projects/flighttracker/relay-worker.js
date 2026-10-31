// Flight Globe relay: a Cloudflare Worker that forwards live ADS-B lookups.
//
// Why it exists: adsb.lol and airplanes.live do not send CORS headers, so a
// page on mauriciosousa.github.io is not allowed to read their answers. This
// Worker fetches the same URL server-side and adds the header.
//
// Routes (anything else returns 404, so it is not an open proxy):
//   /adsb.lol/v2/callsign/<CS>        -> https://api.adsb.lol/v2/callsign/<CS>
//   /airplanes.live/v2/callsign/<CS>  -> https://api.airplanes.live/v2/callsign/<CS>
//   (also /v2/hex/<HEX> and /v2/reg/<REG> on both)
//
// Deploy: Cloudflare dashboard > Workers & Pages > Create > Worker >
// "Hello World", Deploy, then Edit code, replace everything with this file,
// Deploy again. Paste the workers.dev URL into Flight Globe's
// "Live data relay" field, or into RELAY_DEFAULT in index.html.

const UPSTREAM = {
  'adsb.lol': 'https://api.adsb.lol',
  'airplanes.live': 'https://api.airplanes.live',
};

// Pages allowed to read through the relay. Add more origins here if you
// host the tracker somewhere else (for example 'http://localhost:8000').
const ALLOWED_ORIGINS = ['https://mauriciosousa.github.io'];

const ROUTE = /^\/(adsb\.lol|airplanes\.live)(\/v2\/(?:callsign|hex|reg)\/[A-Za-z0-9-]{1,10})$/;

export default {
  async fetch(request) {
    const origin = request.headers.get('Origin') || '';
    const cors = {
      'Access-Control-Allow-Origin': ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Max-Age': '86400',
      'Vary': 'Origin',
    };
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });

    const url = new URL(request.url);
    if (url.pathname === '/' || url.pathname === '') {
      return new Response('Flight Globe relay is running.', { headers: { ...cors, 'Content-Type': 'text/plain' } });
    }
    const m = url.pathname.match(ROUTE);
    if (request.method !== 'GET' || !m) {
      return new Response('Not found', { status: 404, headers: { ...cors, 'Content-Type': 'text/plain' } });
    }

    let upstream;
    try {
      upstream = await fetch(UPSTREAM[m[1]] + m[2], {
        headers: { 'Accept': 'application/json', 'User-Agent': 'FlightGlobe-relay (personal flight display)' },
        cf: { cacheTtl: 10, cacheEverything: true }, // at most one upstream call per callsign every 10 s
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: 'upstream unreachable' }), { status: 502, headers: { ...cors, 'Content-Type': 'application/json' } });
    }
    const headers = new Headers(cors);
    headers.set('Content-Type', upstream.headers.get('Content-Type') || 'application/json');
    headers.set('Cache-Control', 'public, max-age=10');
    return new Response(upstream.body, { status: upstream.status, headers });
  },
};
