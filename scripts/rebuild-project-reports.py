"""Rebuild project takeoffs, CSVs and separate PDFs using saved source rules."""
import subprocess
import sys
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
def run(*args):
    subprocess.run(args, cwd=root, check=True)

# Reuse full element scans unless explicitly refreshing the original exports.
def cache_current(slug):
    try:
        manifest=json.loads((root/f'outputs/NeoviBOM/_Internal/Model-Data/{slug}-scan-manifest.json').read_text())
        stat=Path(manifest['source']).stat()
        return manifest['schema']=='mapping-scan-2' and manifest['sourceBytes']==stat.st_size and manifest['sourceMtimeNs']==stat.st_mtime_ns and (root/f'outputs/NeoviBOM/_Internal/Model-Data/{slug}-takeoff-elements.json').exists()
    except (FileNotFoundError,KeyError): return False

if '--rescan' in sys.argv or not all(cache_current(slug) for slug in ('franklin','santa-rita')):
    for slug in ('franklin','santa-rita'):
        evidence=root/f'outputs/NeoviBOM/_Internal/Model-Data/{slug}-evidence.json'
        source=json.loads(evidence.read_text())['source']
        run(sys.executable,'scripts/inspect-everything-export.py',source,str(evidence))
    run(sys.executable, 'scripts/scan-project-takeoffs.py')
run('node', 'scripts/sync-catalog-identities.mjs')
run('node', 'scripts/build-google-sheet-script.mjs')
run('node', 'scripts/build-no-quantity-inputs.mjs')
run('node', 'scripts/export-project-catalog.mjs')
run(sys.executable, 'scripts/build-mapping-register.py')
if '--all-models' in sys.argv:
    run(sys.executable,'scripts/audit-all-download-models.py')
    run(sys.executable,'scripts/verify-all-model-audit.py')
    run(sys.executable,'scripts/build-all-model-audit-pdf.py')
run(sys.executable, 'scripts/map-project-takeoffs.py')
run(sys.executable, 'scripts/audit-all-item-mappings.py')
run('node', 'scripts/build-full-project-reports.mjs')
run(sys.executable, 'scripts/verify-mapped-takeoffs.py')
run(sys.executable, 'scripts/build-project-test-pdf.py')
run(sys.executable, 'scripts/build-formula-guide.py')
if '--package' in sys.argv:
    run(sys.executable, 'scripts/build-delivery-package.py', '--refresh')
