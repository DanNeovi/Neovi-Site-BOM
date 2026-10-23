# Site BOM website

The public, interactive catalog is published from `site/` with GitHub Pages.
It is a snapshot of the generated HTML in `G:\My Drive\SiteBOM`; the Drive folder
remains the source for complete exports. Search, phase views, item details, and
printing work on the website. Site progress edits are stored in each visitor's
browser and can be downloaded as CSV; they do not update Google Drive or other
visitors' copies.

To refresh the published data after generating a new Site BOM HTML export, run
`node scripts/build-pages-snapshot.mjs`, review the changes in `site/`, and commit
and push those files to `main`. GitHub Actions then publishes the new snapshot.
Only the Monroe formula report is copied with the HTML; the rest of the export
package stays in Google Drive.
