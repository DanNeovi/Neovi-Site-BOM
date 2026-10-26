import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = process.argv[2] || 'G:\\My Drive\\SiteBOM';
const destination = path.join(root, 'site');
const html = await fs.readFile(path.join(source, 'NeoviBOM.html'), 'utf8');
const match = html.match(/(<script id="snapshot" type="application\/json">)([\s\S]*?)(<\/script>)/);
if (!match) throw new Error('The Site BOM HTML has no embedded data snapshot.');
const snapshot = JSON.parse(match[2]);
if (!Array.isArray(snapshot.items) || snapshot.items.length === 0) throw new Error('The Site BOM snapshot has no items.');
if (!snapshot.items.some(item => item.monroeEstimate)) throw new Error('The snapshot has no Monroe estimates.');
snapshot.siteProject = 'Monroe';
snapshot.projects = []; // Franklin and Santa Rita are separate project exports.

// The public site includes only the linked formula report. The Drive folder
// remains the source for the complete export package and project documents.
const report = '05-Monroe/Monroe-Item-Formulas.md';
snapshot.documents = snapshot.documents.filter(document => document.path === report);
if (snapshot.documents.length !== 1) throw new Error(`Missing linked report: ${report}`);
const safeJson = JSON.stringify(snapshot).replaceAll('<', '\\u003c');
function replaceOnce(input, from, to) {
  if (!input.includes(from)) throw new Error(`Viewer template changed; missing: ${from.slice(0, 70)}`);
  return input.replace(from, to);
}
let page = replaceOnce(html, match[0], match[1] + safeJson + match[3]);
page = replaceOnce(page, '<title>Site Bill of Material</title>', '<title>Monroe Site BOM · All items</title>');
page = replaceOnce(page, '<span class="tag">Local snapshot</span>', '<span class="tag">Monroe · planning snapshot</span>');
page = replaceOnce(page, '<br>Offline catalog</footer>', '<br>Monroe public catalog</footer>');
page = replaceOnce(page, "const state={presentation:'phase',view:'catalog',path:[],phase:'Foundation',query:'',docPath:[],docQuery:''};",
  "const state={presentation:'phase',view:'catalog',path:[],phase:'',query:'',docPath:[],docQuery:''};");
page = replaceOnce(page, "if(!state.phase&&state.presentation!=='ordering')return;", "if(!state.phase&&state.presentation!=='ordering'&&data.siteProject!=='Monroe')return;");
page = replaceOnce(page, "state.phase||'Combined ordering list'", "state.phase||(state.presentation==='ordering'?'Combined ordering list':'Monroe · all items')");
page = replaceOnce(page, "document.title='Site Bill of Material - '+(state.phase||'Combined ordering list');", "document.title='Monroe Site BOM - '+(state.phase||'All items');");
page = replaceOnce(page, "state.path.at(-1)||state.phase||'Material catalog'", "state.path.at(-1)||state.phase||'Monroe · all items'");
page = replaceOnce(page, "'Browse category folders or select a phase to see all its materials.'", "'All Monroe Site BOM items across Site Setup, Foundation, Panels, and Finishing. Quantities are labeled by source and are planning values until reviewed.'");
page = replaceOnce(page, "else if(state.query||state.phase){", "else if(state.query||state.phase||data.siteProject==='Monroe'){");
page = replaceOnce(page, "else if(!state.phase)state.phase='Foundation';", "else if(data.siteProject!=='Monroe'&&!state.phase)state.phase='Foundation';");
page = replaceOnce(page, '</script></body></html>', '</script><script src="live-config.js"></script><script src="live-site.js?v=3"></script></body></html>');

await fs.mkdir(path.join(destination, '05-Monroe'), { recursive: true });
await fs.writeFile(path.join(destination, 'index.html'), page);
await fs.copyFile(path.join(source, report), path.join(destination, report));
for (const file of ['live-site.js', 'editor.html', 'editor.js']) {
  await fs.copyFile(path.join(root, 'web', file), path.join(destination, file));
}
const liveConfig = JSON.parse(await fs.readFile(path.join(root, 'config', 'live-site-endpoint.json'), 'utf8'));
if (liveConfig.url && !/^https:\/\/script\.google\.com\/macros\/s\/[^/]+\/exec$/.test(liveConfig.url))
  throw new Error('Live Site BOM endpoint must be a deployed Google Apps Script web app URL.');
await fs.writeFile(path.join(destination, 'live-config.js'), 'window.SITE_BOM_LIVE_URL = ' + JSON.stringify(liveConfig.url) + ';\n');
await fs.writeFile(path.join(destination, '.nojekyll'), '');
console.log(`Prepared Monroe GitHub Pages snapshot: ${snapshot.items.length} items across ${new Set(snapshot.items.map(item => item.phase)).size} phases.`);
