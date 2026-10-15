// x3d.poc edge: static files + first-party beacon + public stats + admin. Node stdlib only.
'use strict';
const http = require('http'), fs = require('fs'), path = require('path'), zlib = require('zlib'), crypto = require('crypto');
const ROOT = process.env.SITE_ROOT || '/site';
const PORT = +process.env.PORT || 8080;
const PROJECT = process.env.GOOGLE_CLOUD_PROJECT || '';
const DATASET = process.env.BQ_DATASET || 'x3d_poc';
const ADMIN = (process.env.ADMIN_EMAILS || '').toLowerCase().split(',').filter(Boolean);
const OAUTH_CLIENT = process.env.OAUTH_CLIENT_ID || '';
const RATE_REQ_MIN = +process.env.RATE_REQ_MIN || 600, RATE_MB_HOUR = +process.env.RATE_MB_HOUR || 400;
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.wasm': 'application/wasm', '.woff2': 'font/woff2', '.x3d': 'model/x3d+xml',
  '.x3dz': 'application/octet-stream', '.txt': 'text/plain; charset=utf-8', '.glb': 'model/gltf-binary', '.ply': 'application/octet-stream', '.md': 'text/plain; charset=utf-8' };
const COMPRESS = new Set(['.html', '.js', '.css', '.json', '.svg', '.x3d', '.txt', '.md']);
const started = Date.now();
const live = { reqs: 0, bytes: 0, s5xx: 0, recent: [] };           // per-instance, admin shows BigQuery for the global view
let buf = [];                                                        // BigQuery rows waiting to flush

const salt = () => 'x3d.poc/' + new Date().toISOString().slice(0, 10) + '/' + (process.env.HASH_SALT || 'k');
const hashIp = ip => crypto.createHash('sha256').update(salt() + ip).digest('hex').slice(0, 12);
const clientIp = req => (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
const uaClass = ua => /bot|crawl|spider|curl|python|wget|headless/i.test(ua || '') ? 'bot' : /mobile|iphone|android/i.test(ua || '') ? 'mobile' : 'desktop';
const refHost = r => { try { return new URL(r).host; } catch { return ''; } };

// --- rate limit: per hashed ip, fixed windows ---
const buckets = new Map();
function limited(h, bytes) {
  const now = Date.now(); let b = buckets.get(h);
  if (!b || now - b.t0 > 3600e3) { b = { t0: now, m0: now, reqs: 0, bytes: 0 }; buckets.set(h, b); }
  if (now - b.m0 > 60e3) { b.m0 = now; b.reqs = 0; }
  b.reqs++; b.bytes += bytes || 0;
  return b.reqs > RATE_REQ_MIN || b.bytes > RATE_MB_HOUR * 1048576;
}
setInterval(() => { const c = Date.now() - 7200e3; for (const [k, v] of buckets) if (v.t0 < c) buckets.delete(k); }, 600e3).unref();

// --- BigQuery over REST with the metadata-server token (no client library) ---
let tok = { v: '', exp: 0 };
async function token() {
  if (tok.v && Date.now() < tok.exp) return tok.v;
  const r = await fetch('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token', { headers: { 'Metadata-Flavor': 'Google' } });
  const j = await r.json(); tok = { v: j.access_token, exp: Date.now() + (j.expires_in - 60) * 1000 }; return tok.v;
}
async function bq(method, url, body) {
  const r = await fetch('https://bigquery.googleapis.com/bigquery/v2' + url, { method, headers: { Authorization: 'Bearer ' + await token(), 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });
  return r.json();
}
async function flush() {
  if (!buf.length || !PROJECT) { if (!PROJECT) buf = []; return; }
  const rows = buf.splice(0, 500);
  try { await bq('POST', `/projects/${PROJECT}/datasets/${DATASET}/tables/events/insertAll`, { rows: rows.map(json => ({ json })), skipInvalidRows: true, ignoreUnknownValues: true }); }
  catch (e) { console.error(JSON.stringify({ severity: 'WARNING', msg: 'bq flush failed', err: String(e) })); }
}
setInterval(flush, 2000).unref();
const rec = row => { buf.length < 5000 && buf.push({ ts: new Date().toISOString(), ...row }); };
async function query(sql) {
  const j = await bq('POST', `/projects/${PROJECT}/queries`, { query: sql, useLegacySql: false, timeoutMs: 8000, maxResults: 500 });
  const f = (j.schema && j.schema.fields || []).map(x => x.name);
  return (j.rows || []).map(r => Object.fromEntries(r.f.map((c, i) => [f[i], c.v])));
}
const T = () => `\`${PROJECT}.${DATASET}.events\``;

// --- public stats (aggregates only), cached 10 s ---
let statsCache = { t: 0, v: null };
async function publicStats() {
  if (Date.now() - statsCache.t < 10e3 && statsCache.v) return statsCache.v;
  if (!PROJECT) return { as_of: new Date().toISOString(), degraded: true, loads_today: 0, visitors_24h: 0, visitors_7d: 0, now_viewing: 0, demos: [] };
  const [tot] = await query(`SELECT COUNTIF(kind='page' AND TIMESTAMP_TRUNC(ts,DAY)=TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(),DAY)) loads_today,
    COUNT(DISTINCT IF(kind='page' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 1 DAY),ip,NULL)) visitors_24h,
    COUNT(DISTINCT IF(kind='page' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 7 DAY),ip,NULL)) visitors_7d,
    COUNT(DISTINCT IF(kind='page' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 5 MINUTE),ip,NULL)) now_viewing
    FROM ${T()} WHERE ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 7 DAY) AND ua!='bot'`);
  const demos = await query(`SELECT path demo, COUNT(*) loads, APPROX_QUANTILES(load_ms,2)[OFFSET(1)] median_load_ms FROM ${T()}
    WHERE kind='beacon' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 7 DAY) AND load_ms>0 GROUP BY demo ORDER BY loads DESC LIMIT 20`);
  statsCache = { t: Date.now(), v: { as_of: new Date().toISOString(), window: 'bots excluded; ip is a daily salted hash', ...tot, demos } }; return statsCache.v;
}

// --- admin: Google sign-in, allow-list ---
async function adminOk(req) {
  const m = /^Bearer (.+)$/.exec(req.headers.authorization || ''); if (!m || !ADMIN.length) return false;
  try { const j = await (await fetch('https://oauth2.googleapis.com/tokeninfo?id_token=' + encodeURIComponent(m[1]))).json();
    return j.email_verified === 'true' && ADMIN.includes((j.email || '').toLowerCase()) && (!OAUTH_CLIENT || j.aud === OAUTH_CLIENT); } catch { return false; }
}
async function adminData() {
  const [now] = await query(`SELECT COUNTIF(status>=500) s5xx, COUNT(*) reqs, SUM(bytes) bytes FROM ${T()} WHERE kind='req' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 1 HOUR)`);
  const stream = await query(`SELECT ts,kind,path,status,bytes,ms,ip,ua,ref,err FROM ${T()} ORDER BY ts DESC LIMIT 100`);
  const top = await query(`SELECT ip, COUNT(*) reqs, SUM(bytes) bytes FROM ${T()} WHERE kind='req' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 1 HOUR) GROUP BY ip ORDER BY bytes DESC LIMIT 10`);
  const errs = await query(`SELECT ts,path,err,ua FROM ${T()} WHERE kind='beacon' AND err!='' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 1 DAY) ORDER BY ts DESC LIMIT 50`);
  const paths = await query(`SELECT path, COUNT(*) reqs FROM ${T()} WHERE kind='page' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 1 DAY) GROUP BY path ORDER BY reqs DESC LIMIT 15`);
  const refs = await query(`SELECT ref, COUNT(*) n FROM ${T()} WHERE kind='page' AND ref!='' AND ts>TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 7 DAY) GROUP BY ref ORDER BY n DESC LIMIT 10`);
  return { hour: now, stream, top_ips_by_bytes: top, beacon_errors: errs, pages_24h: paths, referrers_7d: refs, instance: { uptime_s: Math.round((Date.now() - started) / 1000), reqs: live.reqs, bytes: live.bytes, s5xx: live.s5xx } };
}

const send = (res, code, body, headers = {}) => { res.writeHead(code, { 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'strict-origin-when-cross-origin', ...headers }); res.end(body); };
function serveFile(req, res, file, ip, t0) {
  fs.stat(file, (e, st) => {
    if (e || !st.isFile()) return send(res, 404, 'not found', { 'Content-Type': 'text/plain' });
    const ext = path.extname(file).toLowerCase(), ct = TYPES[ext] || 'application/octet-stream';
    const immutable = /\/(vendor|data|gifts)\//.test(file) || /\.(wasm|woff2|png|jpg|webp)$/.test(file);
    const h = { 'Content-Type': ct, 'Cache-Control': immutable ? 'public, max-age=31536000, immutable' : 'public, max-age=300', 'Accept-Ranges': 'bytes', ETag: `"${st.size}-${st.mtimeMs | 0}"` };
    if (req.headers['if-none-match'] === h.ETag) return send(res, 304, '', h);
    const accEnc = req.headers['accept-encoding'] || '', ok = (code, n) => { live.reqs++; live.bytes += n; rec({ kind: ext === '.html' ? 'page' : 'req', path: new URL(req.url, 'http://x').pathname, status: code, bytes: n, ms: Date.now() - t0, ip: hashIp(ip), ua: uaClass(req.headers['user-agent']), ref: refHost(req.headers.referer) }); };
    if (COMPRESS.has(ext) && /gzip/.test(accEnc) && st.size < 20e6) {
      res.writeHead(200, { ...h, 'Content-Encoding': 'gzip', Vary: 'Accept-Encoding' }); let n = 0;
      return fs.createReadStream(file).pipe(zlib.createGzip()).on('data', c => n += c.length).on('end', () => ok(200, n)).pipe(res);
    }
    const r = /bytes=(\d*)-(\d*)/.exec(req.headers.range || '');
    if (r) { const a = r[1] ? +r[1] : st.size - +r[2], b = r[2] && r[1] ? +r[2] : st.size - 1;
      res.writeHead(206, { ...h, 'Content-Range': `bytes ${a}-${b}/${st.size}`, 'Content-Length': b - a + 1 }); ok(206, b - a + 1); return fs.createReadStream(file, { start: a, end: b }).pipe(res); }
    res.writeHead(200, { ...h, 'Content-Length': st.size }); ok(200, st.size); fs.createReadStream(file).pipe(res);
  });
}

http.createServer(async (req, res) => {
  const t0 = Date.now(), ip = clientIp(req), u = new URL(req.url, 'http://x'), p = decodeURIComponent(u.pathname);
  try {
    if (p === '/health') return send(res, 200, 'ok');
    if (limited(hashIp(ip), 0)) { live.s5xx += 0; return send(res, 429, 'slow down', { 'Retry-After': '60' }); }
    if (p === '/_t' && req.method === 'POST') {
      let b = ''; req.on('data', c => { b += c; if (b.length > 4096) req.destroy(); });
      req.on('end', () => { try { const j = JSON.parse(b); rec({ kind: 'beacon', path: String(j.p || '').slice(0, 120), load_ms: Math.min(+j.l || 0, 600000), fps: Math.min(+j.f || 0, 240), err: String(j.e || '').slice(0, 300), ip: hashIp(ip), ua: uaClass(req.headers['user-agent']), status: 204 }); } catch {} send(res, 204, ''); });
      return;
    }
    if (p === '/stats.json') return send(res, 200, JSON.stringify(await publicStats().catch(() => ({ as_of: new Date().toISOString(), degraded: true, loads_today: 0, visitors_24h: 0, visitors_7d: 0, now_viewing: 0, demos: [] }))), { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=10', 'Access-Control-Allow-Origin': '*' });
    if (p === '/admin') return send(res, 200, fs.readFileSync(path.join(ROOT, '_admin.html'), 'utf8').replace('__CLIENT_ID__', OAUTH_CLIENT), { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    if (p === '/admin/data') { if (!await adminOk(req)) return send(res, 401, 'sign in'); return send(res, 200, JSON.stringify(await adminData()), { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); }
    let rel = p.endsWith('/') ? p + 'index.html' : p;
    const file = path.normalize(path.join(ROOT, rel));
    if (!file.startsWith(ROOT) || path.basename(file) === '_admin.html') return send(res, 404, 'not found');
    if (limited(hashIp(ip), 0)) return send(res, 429, 'slow down');
    serveFile(req, res, file, ip, t0);
  } catch (e) { live.s5xx++; console.error(JSON.stringify({ severity: 'ERROR', msg: String(e) })); send(res, 500, 'error'); }
}).listen(PORT, () => console.log(JSON.stringify({ severity: 'INFO', msg: 'x3d.poc edge up', port: PORT, root: ROOT })));
