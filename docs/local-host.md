# Local SiteBOM trial

The standalone SiteBOM website is running on this computer at
http://127.0.0.1:8765/dashboard. The current processed G: preview is at
http://127.0.0.1:8765/preview/NeoviBOM.html. The Google Sheet catalog is at
http://127.0.0.1:8765/bom/index.html and the shared editor is at
http://127.0.0.1:8765/bom/editor.html. The server binds to 127.0.0.1, so
other computers cannot reach this trial instance.

The Windows task `Neovi-SiteBOM-Local` starts the server at sign-in.
`scripts/setup-local-sitebom.ps1` installs that task. While it is running,
the server checks raw files every five minutes. The dashboard's **Check and
process now** button runs the same check immediately.

The current raw model is the published
`Downloads/Neovi_206 Monroe Dr_00004_ShopDrawing.neovi-model.json`. If
`%LOCALAPPDATA%/Neovi/SiteBOM/Raw/Monroe/` contains a newer model file with
that name, the processor uses that path instead. A changed model or calculation
rule triggers a Monroe rescan, quantity rebuild, value audit, and verified
JSON/XLSX/HTML export to `G:\My Drive\SiteBOM`. The first run checks all
sources; unchanged runs do no heavy work.

The four PDFs under `Downloads/Data for SiteBOM/AI Core` are the current
extraction set. Other collected Monroe files are indexed for revision and
conflict checks. Source indexing creates a review-only page plan for 20 passes
over the four current PDFs, capped locally at 20 planned Gemini requests per
day. This local server **does not call Gemini**. AI extraction can be enabled
later after the local file and quantity path is accepted.

The processed preview reads the newly built G: HTML, while the shared catalog
and editor still read the existing live Google Sheet. Rebuilding G: files does
not update that Sheet or GitHub Pages automatically; the current
live sync deployment and PIN setup remain separate. No local processing output
is approved as a purchase order.

Revit's exporter still requires a manual **Export Model** in this trial stage.
An automatic export after a successful Revit save is the next integration
step. Keeping that hook separate lets us confirm that the local processor
selects the right project, handles a 1.97 GB model, and preserves the current
Sheet edits before changing Revit behavior.

The processor state and log are under
`%LOCALAPPDATA%/Neovi/SiteBOM/automation-state.json` and `automation.log`.
The server runs only while the signed-in computer is on. To inspect the task,
use `Get-ScheduledTask -TaskName Neovi-SiteBOM-Local`.
