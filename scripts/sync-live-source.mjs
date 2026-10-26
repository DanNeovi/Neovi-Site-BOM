import fs from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
const url=JSON.parse(await fs.readFile(path.join(root,'config/live-site-endpoint.json'),'utf8')).url;
if(!/^https:\/\/script\.google\.com\/macros\/s\/[^/]+\/exec$/.test(url||''))throw new Error('Deploy and configure the live Google Apps Script endpoint first.');
const pin=process.env.SITE_BOM_PIN;
if(!/^\d{6}$/.test(pin||''))throw new Error('SITE_BOM_PIN is not configured for this user.');
const sourcePath=process.env.SITE_BOM_DRIVE_HTML||'G:\\My Drive\\SiteBOM\\NeoviBOM.html';
const html=await fs.readFile(sourcePath,'utf8');
const hash=createHash('sha256').update(html).digest('hex');
const match=html.match(/<script id="snapshot" type="application\/json">([\s\S]*?)<\/script>/);
if(!match)throw new Error('The Drive HTML has no Site BOM snapshot.');
const snapshot=JSON.parse(match[1]);
if(!Array.isArray(snapshot.items)||snapshot.items.length<250)throw new Error('Source export has an unexpected item count. Review before publishing.');
const read=async()=>{const endpoint=new URL(url);endpoint.searchParams.set('mode','read');endpoint.searchParams.set('_',Date.now());const response=await fetch(endpoint);if(!response.ok)throw new Error('Google Sheet read failed: '+response.status);return response.json()};
const current=await read();
if(current.sourceHash===hash){console.log('Google Sheet already matches the Drive export.');process.exit(0)}
const nonce=randomUUID().replaceAll('-','');
const body=new URLSearchParams({action:'source',pin,revision:String(current.revision),sourceHash:hash,nonce,payload:JSON.stringify({items:snapshot.items})});
const result=await fetch(url,{method:'POST',body,redirect:'follow'});
if(!result.ok)throw new Error('Google Sheet source update failed: '+result.status);
for(let attempt=0;attempt<5;attempt++){
  const next=await read();
  if(next.sourceHash===hash&&next.nonce===nonce){console.log(`Imported Drive export as live revision ${next.revision}: ${next.items.length} items.`);process.exit(0)}
  if(next.revision!==current.revision)throw new Error('Another edit was saved first. Retry after reviewing the live revision.');
  await new Promise(resolve=>setTimeout(resolve,1500));
}
throw new Error('The source update was not confirmed. Check the PIN and the Apps Script execution log.');
