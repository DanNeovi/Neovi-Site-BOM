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
for (const project of snapshot.projects || []) {
  if (typeof project.source === 'string') project.source = path.win32.basename(project.source);
}

// The public site includes only the linked formula report. The Drive folder
// remains the source for the complete export package and project documents.
const report = '05-Monroe/Monroe-Item-Formulas.md';
snapshot.documents = snapshot.documents.filter(document => document.path === report);
if (snapshot.documents.length !== 1) throw new Error(`Missing linked report: ${report}`);
const safeJson = JSON.stringify(snapshot).replaceAll('<', '\\u003c');
const page = html.replace(match[0], match[1] + safeJson + match[3])
  .replace('<span class="tag">Local snapshot</span>', '<span class="tag">Published Site BOM snapshot</span>')
  .replace('<br>Offline catalog</footer>', '<br>Public catalog snapshot</footer>');

await fs.mkdir(path.join(destination, '05-Monroe'), { recursive: true });
await fs.writeFile(path.join(destination, 'index.html'), page);
await fs.copyFile(path.join(source, report), path.join(destination, report));
await fs.writeFile(path.join(destination, '.nojekyll'), '');
console.log(`Prepared GitHub Pages snapshot: ${snapshot.items.length} items, ${snapshot.projects.length} projects.`);
