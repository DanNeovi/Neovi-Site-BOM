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
uses the signed-in session; its backend derives the audit actor and sends a
private 64-character writer token to Apps Script after the writer is enabled.
No writer token belongs in browser code or the public GitHub repository. Apps
Script stores only a salted hash of the token and rejects anonymous writes.
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
2026-11-09, the WorkNeovi TEST viewer loaded revision 11 with 300 items, and
the GitHub Pages update removed the public PIN form. The Apps Script `/exec`
deployment now runs version 2 with token-only write authorization; a read
returned revision 11, 300 items, and 167 categories, and a legacy PIN-only
request was rejected. The writer token hash is not configured yet, so writes
remain disabled. Saving through WorkNeovi has not been verified. Source rows
reach the Sheet only after the writer token is configured on Apps Script and
the processor host and a reversible save and restore pass.

For migration to WorkNeovi-authenticated editing, the PIN-free public page and
Apps Script version 2 deployment are complete. The following credential and
write checks remain:

The deployed `Code.gs` retains the JSONP `doGet(e)`/`output_(value, e)` path
used by the current viewer and its strict
`siteBomCallback_[A-Za-z0-9]{8,64}` callback validation. Its token migration
was applied as a narrow patch to the live script.

1. A fresh 32-byte random writer token is already stored privately for the
   WorkNeovi TEST server and export sync. In the bound Apps Script project,
   open **Project Settings → Script
   properties**. Add `SITE_BOM_SETUP_WRITER_TOKEN` with this value, then run
   `configureWriterToken` once. It deletes the clear-text setup property and
   stores a salted hash. Do not put the value in chat, browser code, or Git.
2. Run `testReadState` from the editor. Grant access only to this bound Sheet
   if Google's authorization screen shows that scope. The test should report
   the current revision, at least 300 items, and at least 100 categories.
3. The existing **Web app** deployment runs version 2: execute as the owner;
   access **Anyone** for public reads. The same `/exec` URL remains in
   `config/live-site-endpoint.json`. The old six-digit PIN was rejected by the
   deployed version. The GitHub Pages editor now redirects to WorkNeovi.
4. Set `SITE_BOM_WRITER_READY=1` only after the Apps Script hash exists. Open
   the WorkNeovi TEST editor as an authorized account,
   save one reversible test change, and verify the public page and the Sheet
   revision both update. Restore the test revision. Verify an anonymous user
   and a signed-in user without SiteBOM edit permission both receive a denial.
5. In Apps Script run `retireLegacyPin` to delete old PIN properties. Check for
   and disable any older public web-app deployments that still accept a PIN.
6. Release the WorkNeovi editor to production only after the TEST write and
   restore checks and the separate production release checks pass.

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

After the writer credential is configured, run `scripts/setup-live-sync.ps1` interactively as the
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
