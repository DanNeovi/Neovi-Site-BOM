# Local SiteBOM project workspace

## Project menu

Open http://127.0.0.1:8765/dashboard to choose Monroe, Franklin, or Santa Rita,
or to create another project. Creating a project writes its registry record to
`G:\My Drive\SiteBOM\_Internal\project-registry.json` and creates private
`00-Raw/<project>/Model`, `00-Raw/<project>/AI Core`, `02-Projects/<project>`,
and `04-Audits/<project>` folders. Choose an existing NeoviOne model export at
creation, or connect/upload it from the new project page. Current PDFs can be
uploaded there too. The model must match the workspace's Revit identity.

For new projects, the first automatic result is a source census: element
counts by Revit category. These are not material purchase quantities. Each
project still needs reviewed item mappings and calculation rules. Creating a
project does not create a Google Sheet or publish it on GitHub Pages.

## Monroe processing

The standalone SiteBOM website is running on this computer at
http://127.0.0.1:8765/dashboard. The current processed G: preview is at
http://127.0.0.1:8765/preview/NeoviBOM.html. The Google Sheet catalog is at
http://127.0.0.1:8765/bom/index.html and the shared editor is at
http://127.0.0.1:8765/bom/editor.html. The server binds to 127.0.0.1, so
other computers cannot reach this trial instance.

The Windows task `Neovi-SiteBOM-Local` starts the server at sign-in.
`scripts/setup-local-sitebom.ps1` installs that task and allows it to run while
the laptop is on battery. Creating a project with a selected model, connecting
an export, or uploading a model or PDF through SiteBOM starts processing as
soon as the file is accepted. The server does not scan files on a timer.
The menu's **Check all projects now** and each project's **Check sources now**
button handle files placed directly in Drive or Downloads outside the website.

The raw source of truth is the owner-only Google Drive folder
[SiteBOM / 00-Raw / Monroe](https://drive.google.com/drive/folders/16THLj6mzXs2A1D3Ioq3GBkQN5ML6bQgz),
mounted locally at `G:\My Drive\SiteBOM\00-Raw\Monroe`. The processor looks
for the newest verified Monroe model in `%LOCALAPPDATA%\Neovi\One\Models\Exports`
(NeoviOne's Autodesk download location), `%LOCALAPPDATA%\Neovi\SiteBOM\Raw\Monroe`,
and the existing Downloads copies. It copies that model and the four current
AI Core PDFs into the private Drive folder, verifies the copy, then reads the
Drive model. A changed model or calculation rule triggers a Monroe rescan,
quantity rebuild, value audit, and verified JSON/XLSX/HTML export to
`G:\My Drive\SiteBOM`. The first run checks all sources; unchanged runs do no
heavy work.

NeoviOne's cloud gateway uses temporary Autodesk APS object storage and a
time-limited download URL; it does not write to Google Drive. SiteBOM's local
bridge starts after NeoviOne has downloaded the export. It cannot trigger a
new Autodesk export or read the temporary APS bucket by itself. The local
website links to the private Drive folder; Google requires access as
`danielb@neovi.co` to open it. GitHub Pages does not receive these raw files.

The four PDFs in the private Drive `AI Core` folder are the current retained
extraction set. The local Downloads set remains the input to the older-file
revision/conflict index. Source indexing creates a review-only page plan for 20 passes
over the four current PDFs, capped locally at 20 planned Gemini requests per
day. This local server **does not call Gemini**. AI extraction can be enabled
later after the local file and quantity path is accepted.

The processed preview reads the newly built G: HTML, while the shared catalog
and editor still read the existing live Google Sheet. When Monroe processing
produces a changed export, SiteBOM can sync the new source rows to that
Sheet immediately if the local encrypted live-sync PIN has been configured.
This computer does not currently have that PIN file, so its local exports do
not yet change the shared Sheet. GitHub Pages receives no raw files. No local
processing output is approved as a purchase order.

Revit's exporter still requires a manual **Export Model** in this trial stage,
or **Refresh Neovi model** for an authorized NeoviOne cloud model. An automatic
export after a successful Revit save is a separate integration step. The local
processor selects the right project and handles the 1.97 GB model, but it does
not replace website edits in the shared Sheet.

The processor state and log are under
`%LOCALAPPDATA%/Neovi/SiteBOM/automation-state.json` and `automation.log`.
The server runs only while the signed-in computer is on. To inspect the task,
use `Get-ScheduledTask -TaskName Neovi-SiteBOM-Local`.
