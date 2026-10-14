// Load each page headless and require that its scene finishes loading. Exits non-zero on any failure.
const { chromium } = require('playwright');
const [base, ...pages] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  let failed = 0;
  for (const p of pages) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, locale: 'en-US' });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.status() >= 400 && !r.url().endsWith('favicon.ico')) errors.push(r.status() + ' ' + r.url()); });
    let ok = true;
    try { await page.goto(base + '/' + p, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => document.body.dataset.loaded === '1', null, { timeout: 120000 }); }
    catch (e) { ok = false; }
    console.log((ok && !errors.length ? 'ok   ' : 'FAIL ') + p + (errors.length ? '  ' + errors.slice(0, 3).join(' | ') : ''));
    if (!ok || errors.length) failed++;
    await page.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
