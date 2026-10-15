// First-party, cookie-free load beacon. Reports page, load time, rough fps bucket and any script error.
(function () {
  var t0 = performance.now(), sent = false, errs = [];
  addEventListener('error', function (e) { errs.push(String(e.message || e).slice(0, 120)); });
  function send(l, f) { if (sent) return; sent = true; try { navigator.sendBeacon('/_t', JSON.stringify({ p: location.pathname, l: Math.round(l), f: f, e: errs.join(' | ') })); } catch (_) {} }
  function fpsThen(l) { var n = 0, s = performance.now(); (function tick(t) { n++; if (t - s < 1500) requestAnimationFrame(tick); else send(l, Math.round(n * 1000 / (t - s))); })(s); }
  var iv = setInterval(function () { if (document.body && document.body.dataset.loaded === '1') { clearInterval(iv); fpsThen(performance.now() - t0); } }, 250);
  setTimeout(function () { clearInterval(iv); send(0, 0); }, 90000);
  addEventListener('pagehide', function () { send(0, 0); });
})();
