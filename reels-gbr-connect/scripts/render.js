// Renderiza um HTML quadro a quadro com Playwright.
// uso: node render.js <arquivo.html> <largura> <altura> <fps> <duracao> <pasta-saida> [dados.json] [transparente]
// O HTML precisa expor setTime(t) e, se receber dados, montar(dados).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [html, W, H, FPS, DUR, OUT, DADOS, TRANSP] = process.argv.slice(2);
const largura = +W, altura = +H, fps = +FPS, dur = +DUR;
const total = Math.round(dur * fps);
const dados = DADOS && DADOS !== '-' ? JSON.parse(fs.readFileSync(DADOS, 'utf8')) : null;
const transparente = TRANSP === 'transparente';
const WORKERS = Math.max(1, Math.min(4, require('os').cpus().length));

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files', '--font-render-hinting=none'] });
  const url = 'file://' + path.resolve(html);
  let feitos = 0;
  await Promise.all([...Array(WORKERS).keys()].map(async w => {
    const page = await browser.newPage({ viewport: { width: largura, height: altura }, deviceScaleFactor: 1 });
    await page.goto(url);
    if (dados) await page.evaluate(d => montar(d), dados);
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; })));
    });
    for (let f = w; f < total; f += WORKERS) {
      await page.evaluate(t => setTime(t), f / fps);
      await page.screenshot({ path: path.join(OUT, String(f).padStart(5, '0') + '.png'), omitBackground: transparente });
      if (++feitos % 60 === 0) process.stdout.write(`  ${feitos}/${total} quadros\n`);
    }
    await page.close();
  }));
  await browser.close();
  console.log(`Renderizados ${total} quadros em ${OUT}`);
})().catch(e => { console.error(e); process.exit(1); });
