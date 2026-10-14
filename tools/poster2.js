const { chromium } = require(process.env.PWPATH);
const [pg, out, waitMs, dark] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto('http://127.0.0.1:8766/' + pg, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.body.dataset.loaded === '1', null, { timeout: 200000 });
  await page.evaluate((dark) => { if (dark !== '1') document.body.classList.remove('lights-out'); PX.clean(true); document.querySelector('.ui').style.opacity = 0; }, dark);
  await page.waitForTimeout(+waitMs);
  await page.screenshot({ path: out, type: 'jpeg', quality: 84, timeout: 170000 });
  await browser.close(); console.log('saved', out);
})().catch(e => { console.error(e.message); process.exit(1); });
