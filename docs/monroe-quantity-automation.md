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

`rod_lengths_by_diameter` in `scripts/monroe_structural_schedule.py` accepts
only verified site-installed **physical rod paths**. Each path needs an
interface, physical fastener ID, axis, source reference, endpoints and diameter. Repeated observations
of one rod from the wall, cassette and HSS/RHS count once; separate rods above
and below the cassette count separately. Hole symbols and modeled hold-downs
or angles are not rod pieces. The helper rejects incomplete or conflicting
paths. For each diameter, `totalIn = distinct confirmed rods x 21` and
`totalFt = totalIn / 12`; a detail-specific bolt length is a separate class.
The export does not yet supply a verified physical-fastener ledger, so no
diameter-specific rod purchase total is published.

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
python scripts/monroe_ai_sources.py plan --daily-cap 20
python scripts/monroe_ai_extract.py --max-requests 20
python scripts/monroe_ai_review.py
```

`--daily-cap` is a local throttle, **not** Google's actual quota. Check the
project/model's active RPM, TPM, and RPD in Google AI Studio. The default
The new plan default is one pass over 133 pages. The existing Monroe audit
plan still records the earlier 20-pass proposal (2,660 requests), but the
extractor now stops after pass one by default even when reading that plan.
For a disputed page, use `--only-page 'Monroe SE sheets.pdf:3' --repeat-limit 2
--max-requests 1` to request one additional pass. Use `--include-prior` only
when older revisions are needed for an explicit comparison. Each run resumes
from saved results and records every
attempt before contacting Gemini. A source hash mismatch stops extraction.
Use `--only-page 'Monroe SE sheets.pdf:3' --max-requests 1` for a page pilot.
Keys are read from the local `GEMINI_API_KEY` or `GEMINI_API_KEYS` settings and
are never written to the report. The daily cap applies to all keys together.

The extractor renders engineering sheets as a full-page preview plus four
higher-resolution quadrants. This is necessary because the structural PDF's
text layer has broken font encoding and large-sheet text is unreadable when
shrunk to one image. Gemini returns source-linked candidate items, including
unknown quantities. The review script emits `candidate-findings.csv` and
`review-report.json` under `G:\My Drive\SiteBOM\04-Audits\Monroe-AI`.
The report checks each pile-schedule pass against the 12 stored source rows;
it also flags different results across passes. No candidate writes to the
live Google Sheet or GitHub Pages.

As of 2026-11-01, the first pass covers all 133 current PDF pages. It saved
135 successful page responses (including two extra schedule/wall checks),
yielding 905 raw findings: 768 with a number and 137 without. Many numbered
findings describe factory work or typical details, so this is a review queue,
not 905 distinct purchase items. One malformed response was retried and
succeeded; the request ledger records both attempts.

The review report includes saved Gemini token usage by image input, text input,
output, and total. Run `python scripts/monroe_ai_review.py` to refresh it
without calling Gemini. See [Gemini token efficiency](gemini-token-efficiency.md)
for the measured usage and open source extraction options.

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

## Full live quantity audit and instructions

Run `python scripts/audit-monroe-values.py` to independently recompute the
catalog formulas from the current Export Everything cache. Then run
`python scripts/monroe_full_quantity_audit.py`. The second command fetches
the current live Google Sheet revision and writes a read-only audit to
`G:\My Drive\SiteBOM\04-Audits\Monroe-Full-Quantity-Audit`.

`audit-summary.md` has distinct **How each value was obtained**, **AI
instructions**, and **Math instructions** sections. `per-item-audit.csv` has
those same three explanations for every live row, plus its listed quantity,
planning quantity, formula, driver values, rounding, spares, source-reference
sample, drawing evidence and unresolved review note. `per-item-audit.json`
contains the full model or schedule reference list. `panel-device-ledger.csv`
and `opening-schedule-ledger.csv` record the E4.1 device circuits and A7.1
opening marks used for direct checks.

The AI instructions require a source file/revision/page or element key, exact
unit and size, installation scope, and a visible evidence snippet. Missing
values stay unknown. The math instructions recompute net demand from the
reviewed driver and rate, then calculate spares, minimum kit and vendor packs
separately. A correct formula does not prove that its driver, rate or product
scope is approved. The audit does not publish changed quantities to the live
Sheet.

The A7.1 review found 19 tilt-and-turn and five fixed windows in 24 rows.
Model window mark 204 is classified as operable by a family name containing
`Hung`, while A7.1 calls it fixed. A7.1 also calls door mark 110 interior,
although the model's host-wall selector includes it among exterior doors.
These differences affect screen/handle and door sill/flashing estimates and
remain review items until the relevant drawing revision and installation
scope are confirmed.

## Publishing path

The generated report and viewer live under `G:\My Drive\SiteBOM`. The public
GitHub site includes a fallback built from the Drive HTML and reads the live
Google Sheet when available. The Sheet receives source changes only when the
local export sync runs with its private writer token after the Apps Script
writer migration is deployed. A successful local build is not proof that the
live Sheet or GitHub Pages has received these changes.
