# Monroe quantity automation

## Current structural pile evidence

`config/monroe-helical-pile-schedule.json` is the extracted table from PDF page 3
of the Monroe structural sheets. The build checks its 12 row IDs, diameter
subtotals, 48-pile total and source PDF SHA-256 when the PDF is available in
`Downloads/Data for SiteBOM/AI Core`. The model's 50 linked U saddles remain a
separate position proxy.

Run `python scripts/build-monroe-estimates.py` followed by
`python scripts/audit-monroe-values.py`. Pile count now uses 48. The dependent
planning rates yield 12 extensions, 48 brackets, 96 nuts, 96 bolts and 960
washers. Only the pile count and diameter distribution come from the schedule;
the extension and hardware multipliers still require connection review.

The supplied Site BOM also contains legacy 6-inch and 4-inch pile rows with
listed quantities 50 and 25. They do not match the structural schedule's
3-1/2-inch, 4-1/2-inch and 2-7/8-inch shaft diameters. They are retained as
historical user entries with a review note. The website no longer copies a
shared catalog estimate into each size-specific row. The same protection
applies to repeated annular-cutter and cutting-fluid entries; the GAL/EA unit
conversion remains explicit instead of displaying 16 bottles as 16 gallons.

## Rod by diameter

`rod_lengths_by_diameter` in `scripts/monroe_structural_schedule.py` calculates
one 21-inch cut for each evidenced hold-down or L-angle connection, grouped by
rod diameter. For each diameter, `totalIn = connections x 21` and
`totalFt = totalIn / 12`. The current model count of 65 hold-downs has no
verified diameter grouping, and the wall-angle estimate comes from wall length
rather than counted connections. No diameter-specific rod purchase quantity is
published until those identities and diameters are extracted and reviewed.

## Optional Gemini drawing pass

After setting `GEMINI_API_KEY` locally, install the optional official SDK with
`python -m pip install google-genai`. Extract one PDF and scope at a time:

```powershell
python scripts/extract-drawing-quantities-gemini.py --pdf "C:\Users\danie\Downloads\Data for SiteBOM\AI Core\Neovi - Monroe_Fabrication Shop Drawing Package - Wall Panels 2026-08-26.pdf" --scope "hold-down and L-angle connection counts and rod diameters" --output "G:\My Drive\SiteBOM\04-Audits\Monroe-Wall-Gemini-Candidates.json"
```

This writes source-page candidates for review. It never overwrites the live
Google Sheet or converts an AI response directly to an order. Check each
candidate against its drawing page, revision, site/factory scope and model
location. The Export Everything JSON is parsed locally; it is not uploaded as
a 1.97 GB Gemini prompt.

## Publishing path

The generated report and viewer live under `G:\My Drive\SiteBOM`. The GitHub
site is built from the Drive HTML. The private live Google Sheet only updates
from that export when the separate sync task runs with the owner's PIN. A
successful local build is not proof that the live Sheet or GitHub Pages has
received these changes.
