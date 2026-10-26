# Live Monroe Site BOM editor

The live editor keeps the **editable master** in the private native Google Sheet
[Monroe Site BOM Live](https://docs.google.com/spreadsheets/d/1jzAxrOuChKzcCWCpYyI1FnN-D40pR_G1Pc30s1Cz46c/edit).
The static export package remains in `G:\My Drive\SiteBOM`; GitHub Pages is the
view and editing interface. The Sheet is in the private `SiteBOM Live Master
(private)` Drive folder, because the export folder grants anyone with its link
edit access. Do not move the live Sheet back to that public folder.

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

The website loads the latest Sheet revision on page open. The site does not
store the PIN or a Google credential. A six digit PIN is checked by the bound
Apps Script server, has a global five-failure/15-minute lockout, and is stored
there only as a salted hash. The editor name is a user-entered audit label; it
does not prove a person's identity. The public site still exposes BOM data to
any visitor, so do not put secrets in item fields.

## Deployment and verification

The public web app is deployed at
`https://script.google.com/macros/s/AKfycbwAFM2SkdjoHYeUa_cEXY9WplqhjNyk5qbE1AsjA-mKXjDF2j0IEOYgvTqFOvQxxCbB/exec`.
The GitHub Pages site reads its revision 1 successfully. A disposable local
server verified browser edits, adds, custom JSON fields, and the rendered
public page. A real PIN-gated website save and the scheduled G: refresh still
need end-to-end verification.

1. In the bound Apps Script project, open **Project Settings → Script
   properties**. Add `SITE_BOM_SETUP_PIN` with a new six digit PIN chosen by the
   owner. Run `configureEditorPin` once. It deletes the clear-text setup
   property and stores a salted hash. The owner must enter the PIN personally.
2. Run `testReadState` from the editor. Grant access only to this bound Sheet
   if Google's authorization screen shows that scope. The test should report
   revision 1, at least 300 items, and at least 100 categories.
3. Deploy as a **Web app**: execute as the owner; access **Anyone**. This
   exposes only the scripted public read and PIN-gated write methods, not the
   private Sheet itself. Review Google's requested permissions before granting.
4. Keep the deployment's `/exec` URL in `config/live-site-endpoint.json`.
   Rebuild with `node scripts/build-pages-snapshot.mjs`, review `site/`, then
   push to `main`. The GitHub Pages workflow publishes the updated site.
5. Open the published editor, save one reversible test change, and verify the
   public page and the Sheet revision both update. Restore the test revision.

The Apps Script URL is public configuration. Never commit the PIN, Script
Properties, OAuth tokens, or the local encrypted PIN file.

## Automatic NeoviOne / Drive export refresh

When NeoviOne produces a new `G:\My Drive\SiteBOM\NeoviBOM.html`, the local
sync compares its SHA-256 with `Meta` in the live Sheet. It merges new source
rows by permanent ID while preserving fields edited on the website. User-added
items remain. If a source item disappears, the live version is retained and
marked `sourceMissing` for review. A conflict or unreadable export stops the
sync; it never silently replaces editor changes.

After deployment, run `scripts/setup-live-sync.ps1` interactively as the
Windows user who has G: mounted. It asks the owner for the PIN, encrypts it
with Windows DPAPI under `%LOCALAPPDATA%\Neovi\SiteBomLive\pin.txt`, and
registers `Neovi-SiteBOM-Live-Sync` every five minutes while that user is
signed in. `scripts/run-live-sync.ps1` can be run manually for a check. If G:
is unavailable or the computer is off, the next successful run catches up.

The GitHub Pages files are a fallback snapshot. **Live edits do not create a
Git commit for each save**; the published page reads the Sheet every time it
opens. Changes to the website code still publish through GitHub Actions.
