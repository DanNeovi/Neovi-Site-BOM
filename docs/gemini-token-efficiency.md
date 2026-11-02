# Gemini token efficiency for SiteBOM

## What the saved Monroe run actually used

The 135 saved page responses used 360,169 prompt tokens and 116,761 output
tokens, for 476,930 total. Prompt usage breaks down to 304,310 image tokens
and 55,859 text tokens. Images account for about 84% of input usage. These
are measured values from `usageMetadata`, not a price estimate.

The original 20-pass plan covers 133 pages per pass (2,660 requests). The
first pass is already complete, plus two targeted extra reads. Routine
extraction now stops after pass one, so rerunning the command against the
stored plan does not continue the remaining repeats. The daily request cap
still applies across all configured keys.

## What changes the token load

1. **Reuse saved responses.** The extractor identifies a page by its source
   SHA-256, page number, pass, and model. An unchanged completed page is not
   sent again.
2. **Read each page once by default.** Extra passes are for a named page with
   a discrepancy, not every page. For example:

   ```powershell
   python scripts/monroe_ai_extract.py --only-page "Monroe SE sheets.pdf:3" --repeat-limit 2 --max-requests 1
   ```

3. **Keep high-resolution crops where the drawing needs them.** A full-sheet
   pilot misread the helical schedule as 51 piles; the crop-based pass read
   the 48-pile table. The SE PDF also has a broken native text layer. Removing
   crops from these pages would save tokens but risks wrong quantities.
4. **Use a shorter extraction instruction.** The request still requires
   source evidence, exact sizes and units, site/factory classification, and
   no inferred whole-project totals. This change has not been benchmarked
   against the previous prompt, so no token saving is claimed yet. New
   responses carry `promptVersion: 2`; older saved responses are version 1
   in the review report.
5. **Track real usage.** `python scripts/monroe_ai_review.py` adds a
   `tokenUsage` section to the private `review-report.json` using saved
   responses. It sends no API requests.

## Open source tools worth testing

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) is already used to read and
  render pages locally. It can avoid sending duplicate source pages but cannot
  recover the Monroe SE schedule's corrupt text layer by itself.
- [Docling](https://github.com/docling-project/docling) supports local PDF
  layout, table structure, and OCR engines. A pilot should compare every pile
  row, diameter, and count against the known 48-pile schedule before its text
  replaces any Gemini image input.
- [LLMLingua](https://github.com/microsoft/LLMLingua) compresses text prompts.
  It does not compress drawing images. Lossy text compression is a poor default
  for dimension and quantity tables where one missing digit changes a BOM.

For future projects, index files locally first, hash duplicate revisions,
send only current authoritative drawing pages, and keep source/page evidence
in every AI finding. Gemini candidates remain review data; they never update
the shared BOM automatically.
