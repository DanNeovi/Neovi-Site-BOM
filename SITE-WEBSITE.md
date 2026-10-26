# Site BOM website

The public, interactive Monroe catalog is published from `site/` with GitHub Pages.
The public page reads the latest revision from the private Monroe Google Sheet.
Its editor supports shared item, category, quantity, and progress changes behind
a six digit PIN. See `docs/live-site-bom.md` for the deployment and sync design.
It starts with all items across Site Setup, Foundation, Panels, and Finishing.
The checked-in HTML is a fallback snapshot of the generated HTML in
`G:\My Drive\SiteBOM`; the Drive folder remains the source for complete exports.
Franklin and Santa Rita project exports
are excluded from this Monroe page. Search, phase views, item details, and
printing work on the website. Shared edits save to the private Google Sheet and
appear for other visitors when they load the page. The progress CSV remains an
export option.

The local `scripts/sync-live-source.mjs` refreshes the Sheet from a new Drive
HTML export while preserving website edits. Register its scheduled task with
`scripts/setup-live-sync.ps1` on the machine where G: is mounted. To update the
checked-in fallback snapshot, run `node scripts/build-pages-snapshot.mjs`,
review `site/`, and push to `main`. GitHub Actions publishes that fallback.
