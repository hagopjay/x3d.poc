const { chromium } = require(process.env.PWPATH || 'playwright');
const pages = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  for (const p of pages) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    const logs = [];
    page.on('console', m => { if (['error','warning'].includes(m.type())) logs.push(m.type() + ': ' + m.text().slice(0, 200)); });
    page.on('pageerror', e => logs.push('pageerror: ' + e.message.slice(0, 200)));
    const t0 = Date.now();
    await page.goto('http://127.0.0.1:8766/' + p, { waitUntil: 'domcontentloaded' });
    let ok = false;
    try { await page.waitForFunction(() => document.body.dataset.loaded === '1', null, { timeout: 150000 }); ok = true; } catch (e) {}
    await page.waitForTimeout(+(process.env.WAIT||4000));
    const name = p.replace('.html', '');
    await page.screenshot({ path: 'demo-shots/' + name + '.png', timeout: 170000 }).catch(e => console.log('screenshot failed', e.message.slice(0,80)));
    const info = await page.evaluate(() => ({ busy: document.getElementById('busy')?.textContent, hidden: document.getElementById('busy')?.hidden, load: document.getElementById('loadinfo')?.textContent, hud: document.getElementById('hud')?.textContent }));
    console.log(p, ok ? 'LOADED' : 'NOT LOADED', ((Date.now() - t0) / 1000).toFixed(1) + 's', JSON.stringify(info), '\n   ' + logs.slice(0, 6).join('\n   '));
    await page.close();
  }
  await browser.close();
})();
