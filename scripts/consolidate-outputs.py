"""One-time, hash-verified migration of the pre-consolidation generated files.

Copies the canonical files first and records an explicit cleanup plan. Deletion
is performed separately only after the new delivery has passed verification.
"""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'outputs/NeoviBOM'
OLD=ROOT/'outputs/NeoviBOM-Updated-2026-09-14'

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()

def project_target(name):
 key=name.lower()
 project='Franklin' if key.startswith('franklin') else 'Santa-Rita' if key.startswith('santa-rita') else None
 if not project:return None
 return DEST/'02-Projects'/project/('' if 'all-items-calculations' in key else 'Evidence')/name

def migrate():
 if DEST.exists():raise FileExistsError('Destination already exists; migration will not merge unknown files.')
 copied=[]
 def copy(src,dst):
  dst=dst.resolve()
  if not dst.is_relative_to(DEST.resolve()):raise ValueError(dst)
  dst.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(src,dst)
  digest=sha(src)
  assert sha(dst)==digest,(src,dst)
  copied.append({'source':str(src.relative_to(ROOT)),'destination':str(dst.relative_to(ROOT)),'bytes':src.stat().st_size,'sha256':digest})
 for src in (ROOT/'outputs/everything-tests').iterdir():
  if src.suffix in ('.json','.txt'):target=DEST/'_Internal/Model-Data'/src.name
  elif 'TEST-ONLY' in src.name:target=DEST/'04-Audits/Synthetic-Tests'/src.name
  elif src.suffix=='.md':target=DEST/'04-Audits'/src.name
  else:target=project_target(src.name)
  if target is None:raise ValueError(f'Unclassified data file: {src}')
  copy(src,target)
 for src in (ROOT/'outputs/all-model-audit').iterdir():copy(src,DEST/'04-Audits/All-Models'/src.name)
 for src in (OLD/'Category-Catalog').rglob('*'):
  if src.is_file():copy(src,DEST/'03-Categories'/src.relative_to(OLD/'Category-Catalog'))
 for src in OLD.iterdir():
  if not src.is_file():continue
  name=src.name
  if name in ('START-HERE.txt','planning-allowances.json','Delivery-Verification.json'):continue
  target=project_target(name)
  if target:copy(src,target)
  elif name.startswith(('Catalog-Changes','Source-List-Completeness')):copy(src,DEST/'04-Audits'/name)
  elif name.startswith('New-Items-by-Category'):copy(src,DEST/'04-Audits/History'/name)
  else:copy(src,DEST/'01-Catalog'/name)
 for src in (OLD/'Google-Sheet').iterdir():copy(src,DEST/'05-Google-Sheet'/src.name)
 copy(ROOT/'tmp/annotations.json',DEST/'_Internal/Provenance/Annotated-PDF-Notes.json')
 # Every file in the redundant packaged source tree has an original in the repo.
 for src in (OLD/'Source').rglob('*'):
  if src.is_file():assert (ROOT/src.relative_to(OLD/'Source')).is_file(),src
 targets=['output','tmp','outputs/all-model-audit','outputs/everything-tests','outputs/NeoviBOM-Updated-2026-09-14','outputs/NeoviBOM-Updated-2026-09-14.zip','outputs/site-bom-v0.2','outputs/site-bom-v0.4.0','scripts/__pycache__','test/__pycache__']
 old_files=[]
 for name in targets:
  path=ROOT/name
  for file in ([path] if path.is_file() else path.rglob('*')):
   if file.is_file():old_files.append({'path':str(file.relative_to(ROOT)),'bytes':file.stat().st_size})
 manifest={'workspace':str(ROOT),'destination':str(DEST),'status':'COPIED_AND_HASH_VERIFIED; cleanup pending delivery validation','copies':copied,'cleanupTargets':targets,'oldFiles':old_files,'oldBytes':sum(f['bytes'] for f in old_files),'notes':'Current deliverables and unique model evidence retained once. Old source copies, older layouts/releases, the redundant ZIP, scratch scripts/logs, rendered previews and Python bytecode are superseded/generated. Repository sources and original Downloads models are outside cleanup targets.'}
 out=DEST/'_Internal/Cleanup-Manifest.json';out.write_text(json.dumps(manifest,indent=2)+'\n')
 print(f'Copied and SHA-256 verified {len(copied)} files. Cleanup plan covers {len(old_files)} generated files.')
if __name__=='__main__':migrate()
