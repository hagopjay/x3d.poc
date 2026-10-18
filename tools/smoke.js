// Load each page headless and require that its scene finishes loading. Exits non-zero on any failure.
// usage: node tools/smoke.js BASE_URL PAGE...
//
// This script must never hang. A wedged page (the renderer is stuck or dead and the browser has not noticed, which is what a
// crash held up by systemd-coredump looks like on a GitHub runner) never answers Playwright, so Playwright's own timeouts cannot
// be trusted to fire. Every wait below is therefore raced against a plain setTimeout, and the run always ends in process.exit.
//
// env  SMOKE_BROWSER        chromium (default): Playwright's full Chromium in new headless mode.
//                           chrome: the installed Google Chrome.
//                           shell: Playwright's chromium-headless-shell. Its V8 crashes on index.html and gobbler.html on
//                           GitHub's ubuntu-latest runners, so it is not the default.
//      CHROME_PATH          run this executable instead (local runs); wins over SMOKE_BROWSER.
//      SMOKE_PAGE_SECONDS   hard deadline for one page, browser launch included (default 90).
//      SMOKE_WEDGE_SECONDS  fail a page whose main thread has not answered for this long (default 30).
const { chromium } = require('playwright');
const [base, ...pages] = process.argv.slice(2);
const PAGE_MS = (Number(process.env.SMOKE_PAGE_SECONDS) || 90) * 1000;
const WEDGE_MS = (Number(process.env.SMOKE_WEDGE_SECONDS) || 30) * 1000;
const BROWSERS = { chromium: { channel: 'chromium' }, chrome: { channel: 'chrome' }, shell: {} };
const browserKind = process.env.SMOKE_BROWSER || 'chromium';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const secs = ms => (ms / 1000).toFixed(1);
const quit = code => { process.stdout.write('', () => process.exit(code)); setTimeout(() => process.exit(code), 2000); };

if (!base || !pages.length || !BROWSERS[browserKind]) {
  console.error('usage: node tools/smoke.js BASE_URL PAGE...   (SMOKE_BROWSER=' + Object.keys(BROWSERS).join('|') + ', got "' + browserKind + '")');
  quit(2);
}
// Backstop for anything the per-page logic misses: end the whole run, loudly.
setTimeout(() => { console.log('FAIL smoke test hit its overall deadline'); quit(1); }, pages.length * (PAGE_MS + 15000) + 30000);

// Resolves with null when the page's scene loaded cleanly, else with the reason it did not.
async function check(p) {
  const t0 = Date.now(), errors = [];
  let browser, settle, over = false;
  const settled = new Promise(r => { settle = r; });
  const fail = why => settle(why);
  const deadline = setTimeout(() => fail('no result after ' + secs(PAGE_MS) + ' s (hard deadline)'), PAGE_MS);
  (async () => {
    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : BROWSERS[browserKind]),
      args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
      timeout: PAGE_MS,
    });
    browser.on('disconnected', () => fail('the browser process died'));
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, locale: 'en-US' });
    page.on('crash', () => fail('the page crashed'));
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.status() >= 400 && !r.url().endsWith('favicon.ico')) errors.push(r.status() + ' ' + r.url()); });
    const resp = await page.goto(base + '/' + p, { waitUntil: 'domcontentloaded', timeout: PAGE_MS });
    if (resp && resp.status() >= 400) return fail('HTTP ' + resp.status() + ' for the page itself');
    // Poll with a heartbeat instead of waitForFunction: a page whose main thread is wedged never answers, and that must not
    // be able to block us.
    let lastAnswer = Date.now();
    while (!over) {
      const r = await Promise.race([page.evaluate(() => document.body.dataset.loaded || '').catch(() => 'error'), sleep(2000).then(() => null)]);
      if (r === '1') return settle(null);
      if (r !== null) lastAnswer = Date.now();
      else if (Date.now() - lastAnswer > WEDGE_MS) return fail('the page main thread stopped answering for ' + secs(Date.now() - lastAnswer) + ' s, so the browser has most likely crashed (on a GitHub runner `sudo dmesg | tail` shows a headless_shell or chrome segfault)');
      await sleep(250);
    }
  })().catch(e => fail('error: ' + String(e.message).split('\n')[0]));
  const why = await settled;
  over = true;
  clearTimeout(deadline);
  // A browser that is wedged or dying may never finish closing, so give it a few seconds and move on. Playwright kills any
  // browser still alive when this process exits.
  if (browser) await Promise.race([browser.close().catch(() => {}), sleep(5000)]);
  const took = ' (' + secs(Date.now() - t0) + ' s)';
  const seen = errors.length ? '  [page reported: ' + errors.slice(0, 3).join(' | ') + ']' : '';
  if (why) return { ok: false, text: why + took + seen };
  if (errors.length) return { ok: false, text: errors.slice(0, 3).join(' | ') + took };
  return { ok: true, text: took.trim() };
}

(async () => {
  console.log('smoke test: ' + pages.length + ' page(s) on ' + base + ' with ' + (process.env.CHROME_PATH ? 'CHROME_PATH=' + process.env.CHROME_PATH : 'SMOKE_BROWSER=' + browserKind) +
    ', ' + secs(PAGE_MS) + ' s per page');
  let failed = 0;
  for (const [i, p] of pages.entries()) {
    console.log('[' + (i + 1) + '/' + pages.length + '] loading ' + p + ' ...');
    const r = await check(p);
    console.log((r.ok ? 'ok   ' : 'FAIL ') + p + '  ' + r.text);
    if (!r.ok) failed++;
  }
  console.log(failed ? failed + ' of ' + pages.length + ' pages FAILED' : 'all ' + pages.length + ' pages ok');
  quit(failed ? 1 : 0);
})();
