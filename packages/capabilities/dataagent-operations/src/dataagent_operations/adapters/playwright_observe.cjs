const fs = require('node:fs');

async function observe() {
  const {modulePath, channel, url, lookup, readResources} = JSON.parse(fs.readFileSync(0, 'utf8'));
  const {chromium} = require(modulePath);
  const browser = await chromium.launch({channel: channel || undefined, headless: true});
  try {
    const context = await browser.newContext({serviceWorkers: 'block', acceptDownloads: false});
    const page = await context.newPage();
    const target = new URL(url).href;
    const resources = new Set(readResources.map(value => new URL(value).href));
    await context.route('**/*', async route => {
      const request = route.request();
      const navigation = request.isNavigationRequest();
      const allowed = navigation ? request.frame() === page.mainFrame() && request.url() === target :
        resources.has(request.url());
      if (!allowed || !['GET', 'HEAD'].includes(request.method())) {
        return route.abort();
      }
      try {
        const response = await route.fetch({maxRedirects: 0, timeout: 6000});
        if (response.status() >= 300 && response.status() < 400) return route.abort();
        return route.fulfill({response});
      } catch {
        return route.abort();
      }
    });
    if (context.routeWebSocket) await context.routeWebSocket('**/*', socket => socket.close());
    const response = await page.goto(url, {waitUntil: 'domcontentloaded', timeout: 8000});
    if (!response?.ok() || page.url() !== target) {
      return {state: 'unavailable', controls: [], status_text: null};
    }
    if (await page.locator('input[type=password]:visible').count()) {
      return {state: 'login_required', controls: [], status_text: null};
    }
    const result = await page.evaluate(() => {
      const entries = [...document.querySelectorAll('input:not([type=hidden]),select,textarea,button,a[href],[role=button]')]
        .filter(element => element.getClientRects().length && getComputedStyle(element).visibility === 'visible')
        .slice(0, 100);
      const controls = entries.map(element => {
        const label = [...(element.labels || [])].map(node => node.textContent).join(' ');
        const role = element.getAttribute('role') ||
          (element.tagName === 'A' ? 'link' : element.tagName === 'BUTTON' ? 'button' :
            element.tagName === 'SELECT' ? 'select' : element.getAttribute('type') || 'textbox');
        const name = element.getAttribute('aria-label') || label || element.innerText || element.name || '';
        return {role, name: name.trim().slice(0, 160), required: element.required || element.getAttribute('aria-required') === 'true',
          enabled: !element.disabled && element.getAttribute('aria-disabled') !== 'true'};
      }).filter(control => control.name);
      return {controls, status_text: document.querySelector('[role=status]')?.textContent.trim().slice(0, 300) || null};
    });
    let record_evidence = null;
    if (lookup) {
      record_evidence = await page.evaluate(config => {
        const visible = element => element.checkVisibility({checkOpacity: true, checkVisibilityCSS: true});
        function text(row, selector) {
          const nodes = [...row.querySelectorAll(selector)].filter(visible);
          return nodes.length === 1 ? nodes[0].innerText.trim() : '';
        }
        const matches = [...document.querySelectorAll(config.row)].filter(
          row => visible(row) && text(row, config.key) === config.business_key,
        );
        const status = matches.length === 1 ? text(matches[0], config.status) : '';
        return status ? {business_key: config.business_key, status: status.slice(0, 120)} : null;
      }, lookup);
    }
    const png = await page.screenshot({timeout: 8000, animations: 'disabled'});
    return {state: 'observed', ...result, record_evidence, screenshot: png.toString('base64')};
  } finally {
    await browser.close();
  }
}

observe().then(result => process.stdout.write(JSON.stringify(result))).catch(() => {
  process.stderr.write('Browser observation failed\n');
  process.exitCode = 1;
});
