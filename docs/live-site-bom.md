# Live Monroe Site BOM editor

The live editor keeps the **editable master** in the native Google Sheet
[Monroe Site BOM Live](https://docs.google.com/spreadsheets/d/1jzAxrOuChKzcCWCpYyI1FnN-D40pR_G1Pc30s1Cz46c/edit).
The Sheet and static export package are together in `G:\My Drive\SiteBOM`;
GitHub Pages is a read-only view. Shared editing is moving to the signed-in
WorkNeovi editor. The Sheet moved into that folder on 2026-11-05. Raw model
and drawing files remain outside the public GitHub repository.
The SiteBOM Drive folder is owner-only. The live Sheet has an unlisted
anyone-with-link viewer permission; it is not discoverable in Drive search.
Folder access is not granted across the company by default.

The Sheet starts with 301 Monroe items and 167 category paths from the October
25 Drive HTML export. Each save creates a new hidden `State_vN` tab; the visible
`Read Me` sheet explains the storage. `Meta` points at the current revision.
The bound Apps Script project is named **Monroe Site BOM Live API**. Its source
is versioned in `apps-script/LiveSiteBom.gs`.

## What editors can change

- Rename, add, remove, and drag items; change phases, work areas, groups,
  categories, units, listed and site quantities, checkoffs, specification,
  vendor, part number, owner, procurement method, and notes. Type category
  levels with ` > `; a slash inside a category name is ordinary text.
- Add, rename, and remove category paths; drag an item onto a category or
  another item. An empty category is stored but appears publicly after it
  contains an item. Category names display alphabetically.
- Edit additional item fields through the advanced JSON editor. These fields
  appear in **All item fields** on the public page. The permanent `lineId`
  cannot change because it joins source exports and revision history. Formula
  and evidence edits need review before purchasing.
- Form changes are applied automatically on Save or when selecting another
  item. If both the form and JSON have pending edits, apply one first so no
  edits are silently discarded.
- Restore a prior revision. Saves use the current revision number to reject
  conflicting edits; refresh and reconcile rather than overwriting another
  person's work.

The website loads the latest Sheet revision on page open. The WorkNeovi editor
uses the signed-in session; its backend derives the audit actor and is prepared
to send a private 64-character writer token to Apps Script. No writer token
belongs in browser code or the public GitHub repository. Once deployed, Apps
Script will store only a salted hash of the token and reject anonymous writes.
The public site still exposes BOM data to any visitor, so do not put secrets
in item fields.

## Deployment and verification

The public web app is deployed at
`https://script.google.com/macros/s/AKfycbwAFM2SkdjoHYeUa_cEXY9WplqhjNyk5qbE1AsjA-mKXjDF2j0IEOYgvTqFOvQxxCbB/exec`.
On 2026-11-01, a direct public API read returned revision 6 with 301 items
and 167 categories. At that time, the Drive HTML and live Sheet had the same
301 item IDs and planning estimates, with two Sheet item descriptions or
specifications changed through the editor. On 2026-11-05, the live API returned
revision 8 with 300 items and 167 categories. The `site/index.html` fallback
has the same 300 item IDs; three live items have field differences from that
fallback (SHEET-001, SHEET-002, and SHEET-036).
`Meta.sourceHash` still uses the prior whole-HTML method, so its difference
from the current Drive file does not by itself prove a BOM item change. A
live website save has not been verified in that historical audit. On
2026-11-09, the WorkNeovi TEST viewer and editor loaded revision 11 with 300
items, and the GitHub Pages update removed the public PIN form. Saving through
WorkNeovi has not been verified. The Apps Script editor draft contains the
writer-token change, but the deployed `/exec` version still uses the old PIN.
Source rows reach the Sheet only after the writer token is configured on Apps
Script and the processor host and the new version is deployed. These source
changes alone do not complete that cutover.

For migration to WorkNeovi-authenticated editing:

The deployed `Code.gs` has a JSONP `doGet(e)`/`output_(value, e)` path used by
the current viewer. Keep that path and its strict
`siteBomCallback_[A-Za-z0-9]{8,64}` callback validation. Compare the live
script with this repository and apply the writer migration as a narrow patch:
the `doPost` authorization line, `validWriterToken_`,
`configureWriterToken`, `retireLegacyPin`, and the editor actor defaults.
Do not overwrite the entire live script merely to apply the credential change.

1. Generate a fresh 32-byte random value as 64 lowercase hex characters on a
   trusted machine. Store it securely for the WorkNeovi server and export sync.
   In the bound Apps Script project, open **Project Settings → Script
   properties**. Add `SITE_BOM_SETUP_WRITER_TOKEN` with this value, then run
   `configureWriterToken` once. It deletes the clear-text setup property and
   stores a salted hash. The old PIN hash remains during redeployment so the
   current live editor does not lose write access midway through migration.
2. Run `testReadState` from the editor. Grant access only to this bound Sheet
   if Google's authorization screen shows that scope. The test should report
   the current revision, at least 300 items, and at least 100 categories.
3. Redeploy as a **Web app**: execute as the owner; access **Anyone**. The
   `/exec` URL remains public for reads, but writes require the private token.
   Review Google's requested permissions before granting. Confirm the old
   six-digit PIN is rejected by the new deployment before enabling the editor.
4. Keep the deployment's `/exec` URL in `config/live-site-endpoint.json`.
   Rebuild with `node scripts/build-pages-snapshot.mjs`, review `site/`, then
   push to `main`. The GitHub Pages workflow publishes the updated site.
5. Set `SITE_BOM_LIVE_URL` and `SITE_BOM_WRITER_TOKEN` in the private WorkNeovi
   backend configuration. Open the WorkNeovi editor as an authorized account,
   save one reversible test change, and verify the public page and the Sheet
   revision both update. Restore the test revision. Verify an anonymous user
   and a signed-in user without SiteBOM edit permission both receive a denial.
6. In Apps Script run `retireLegacyPin` to delete old PIN properties. Check for
   and disable any older public web-app deployments that still accept a PIN.

The Apps Script URL is public configuration. Never commit the writer token,
Script Properties, OAuth tokens, or the local encrypted token file.

## Automatic NeoviOne / Drive export refresh

When NeoviOne produces a new `G:\My Drive\SiteBOM\NeoviBOM.html`, the local
sync hashes the canonical `snapshot.items` payload and compares that SHA-256
with `Meta` in the live Sheet. HTML timestamps and document-list changes alone
do not create new Sheet revisions. The first run after this hash-method change
will create one migration revision because older `Meta` values used the entire
HTML file hash. The sync merges new source
rows by permanent ID while preserving fields edited on the website. User-added
items remain. If a source item disappears, the live version is retained and
marked `sourceMissing` for review. A conflict or unreadable export stops the
sync; it never silently replaces editor changes.

After deployment, run `scripts/setup-live-sync.ps1` interactively as the
Windows user who has G: mounted. It asks for the same private writer token and
encrypts it with Windows DPAPI under
`%LOCALAPPDATA%\Neovi\SiteBomLive\token.txt`. A changed
Monroe export then triggers the Sheet sync in the same processing run. There
is no timed sync task. `scripts/run-live-sync.ps1` can also be run manually.
On a separate processor host, store the token in a root-protected file and set
`SITE_BOM_WRITER_TOKEN_FILE`; the token is never passed on a command line.
If G: is unavailable or the computer is off, upload or connect the source
again, or use **Check sources now** after it becomes available.

The GitHub Pages files are a fallback snapshot. **Live edits do not create a
Git commit for each save**; the published page reads the Sheet every time it
opens. Changes to the website code still publish through GitHub Actions.
