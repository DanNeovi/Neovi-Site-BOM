# Site BOM website

The public Monroe catalog is published from `site/` with GitHub Pages.
It reads the latest revision from the Monroe Google Sheet and is read-only.
Shared editing belongs in the signed-in WorkNeovi SiteBOM editor, with access
for the owner and named editors. See `docs/live-site-bom.md` for the current
deployment status and sync design.
It starts with all items across Site Setup, Foundation, Panels, and Finishing.
The checked-in HTML is a fallback snapshot of the generated HTML in
`G:\My Drive\SiteBOM`; the Drive folder remains the source for complete exports.
Franklin and Santa Rita project exports are excluded from this Monroe page.
Search, phase views, item details, printing, and the progress CSV work on the
public page. Once the WorkNeovi writer credential is deployed and verified,
shared edits will save to the Sheet and appear on the public page when reloaded.

The local `scripts/sync-live-source.mjs` can refresh the Sheet from a changed
Drive HTML export while preserving website edits after its writer credential
is configured. `scripts/setup-live-sync.ps1` stores that credential for the
processor; it does not install a timed task. To update the checked-in fallback
snapshot, run `node scripts/build-pages-snapshot.mjs`, review `site/`, and push
to `main`. GitHub Actions publishes that fallback.
