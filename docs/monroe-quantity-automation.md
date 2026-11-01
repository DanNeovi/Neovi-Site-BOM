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

### Monroe source index and repeatable page review

The Monroe AI pipeline inventories all 59 collected files in
`Downloads/Data for SiteBOM`, including 34 PDFs (751 pages), ZIP member lists,
STEP headers, and the Export Everything model identity. The four current
`AI Core` PDFs contain 133 pages. Their fifth companion is the 1.97 GB model,
which is processed locally by `scan-monroe-model.py`; it is not sent to Gemini.
The existing scan cache matches the AI Core model SHA-256 and records 184,682
elements scanned and 7,903 retained.
Older revisions and duplicate PDF copies stay in the index for conflict review.

```powershell
python scripts/monroe_ai_sources.py index
python scripts/monroe_ai_sources.py plan --repeats 20 --daily-cap 20
python scripts/monroe_ai_extract.py --max-requests 20
python scripts/monroe_ai_review.py
```

`--daily-cap` is a local throttle, **not** Google's actual quota. Check the
project/model's active RPM, TPM, and RPD in Google AI Studio. The default
20-pass core plan is 133 x 20 = 2,660 requests; use `--include-prior` to plan
all 751 PDF pages (15,020 requests) only when older revisions are needed for
an explicit comparison. Each run resumes from saved results and records every
attempt before contacting Gemini. A source hash mismatch stops extraction.
Use `--only-page 'Monroe SE sheets.pdf:3' --max-requests 1` for a page pilot.
The key is read from `GEMINI_API_KEY` in the process or Windows User
environment and is never written to the report.

The extractor renders engineering sheets as a full-page preview plus four
higher-resolution quadrants. This is necessary because the structural PDF's
text layer has broken font encoding and large-sheet text is unreadable when
shrunk to one image. Gemini returns source-linked candidate items, including
unknown quantities. The review script emits `candidate-findings.csv` and
`review-report.json` under `G:\My Drive\SiteBOM\04-Audits\Monroe-AI`.
The report checks each pile-schedule pass against the 12 stored source rows;
it also flags different results across passes. No candidate writes to the
live Google Sheet or GitHub Pages.

In the first pilot, a single full-page image misread HP-2a and HP-2d and
totaled 51 piles; the cropped-page second pass read 48. A wall sheet first
returned zero findings and then nine connection notes with the higher-resolution
tiles. These results show why a successful API response is not a verified
quantity. Review drawing revisions, repeated views, site/factory scope, and
each item's basis before publishing. The 21-inch rod rule must still be
applied only after each hold-down or L-angle has a verified type and diameter.

The collected drawings are sent to Google's free-tier Gemini service when
this extractor runs. Google states free-tier content may be used to improve
its products. Keep the AI outputs in the private Drive audit folder and do
not commit the key or raw customer drawings.

### Earlier whole-PDF experiment

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
