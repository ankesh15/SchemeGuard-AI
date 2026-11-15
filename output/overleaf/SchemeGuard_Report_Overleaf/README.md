# SchemeGuard thesis project

This folder is a complete, editable Overleaf project for the SchemeGuard report. It follows the supplied report folder's useful structure—main LaTeX source, bibliography, images and LaTeX support files—while replacing the unrelated HireMate content, NIT-specific class and logos with SchemeGuard material.

## Open and compile

Upload the extracted `SchemeGuard_Report_Overleaf` folder to Overleaf and select `Final_Thesis_All.tex` as the main document. Compile with pdfLaTeX. The source keeps inline TikZ fallbacks for the main illustrations, so the report remains readable if an image is moved; the supplied images are used when present. References are embedded in the main source for a simple one-file compile, and `bib/mybib.bib` is provided as an editable bibliography source for future citation-key migration.

The built-in Codex LaTeX preview is opened on the existing `Final_Thesis_All.tex`; it may not resolve sibling project assets. Overleaf should receive this entire folder, not only the `.tex` file.

## Update the report and artwork

The narrative and structure are in `source/report_content.py`; `submission.json` contains editable front-matter metadata. After changing either, regenerate the existing main file in place:

```bash
python3 build_overleaf.py
```

To recreate the original SchemeGuard diagrams and wordmark PNG/SVG assets:

```bash
python3 -m pip install Pillow
python3 source/create_assets.py
```

`images/recommendation-cards-desktop.png` is a cropped application capture. `images/recommendation-card-mobile.png` is an explicitly illustrative mobile layout. Neither carries over the reference product's branding or screenshots.

## Project boundaries

The project is named **SchemeGuard** throughout the report. No institution, guide, roll number, team roster or approval signature was inferred. Confirm the unfilled academic details before submission. The recorded dataset contains 282 government discovery records; that count is not the number of executable government policies. The recorded database snapshot contains no approved government eligibility rule sets. The report distinguishes verified implementation evidence, small synthetic tests and unverified production/model behavior.

## Complete folder contents

```text
SchemeGuard_Report_Overleaf/
├── Final_Thesis_All.tex
├── README.md
├── README_SCHEMEGUARD_THESIS_LATEX
├── build_overleaf.py
├── format-notes.md
├── submission.json
├── algorithmwh.sty
├── enumitem.sty
├── fancyhdr.sty
├── fncychap.sty
├── myfancy.sty
├── pdfpages.sty
├── rotating.sty
├── schemeguardthesis.cls
├── watermark.sty
├── pic1.png
├── bib/
│   └── mybib.bib
├── images/
│   ├── README.md
│   ├── SchemeGuard_logo.png
│   ├── SchemeGuard_logo.svg
│   ├── document-processing-workflow.png
│   ├── policy-monitoring-workflow.png
│   ├── profile-first-journey.png
│   ├── recommendation-card-mobile.png
│   ├── recommendation-cards-desktop.png
│   └── schemeguard-architecture.png
└── source/
    ├── create_assets.py
    └── report_content.py
```

## File guide

- `Final_Thesis_All.tex` is the main Overleaf document. It contains the complete report and vector fallbacks.
- `source/report_content.py` and `build_overleaf.py` keep the narrative and generated LaTeX reproducible.
- `submission.json` is the source for the known author display name, department and report date; unknown academic details stay blank.
- `bib/mybib.bib` contains the external and repository references in BibTeX format.
- `images/` contains SchemeGuard diagrams, a wordmark, a desktop app capture and a mobile illustration.
- `pic1.png` is the document-to-policy workflow figure in the same convenient root-level location as the reference bundle.
- `schemeguardthesis.cls` is a neutral optional base class. The main document uses the standard `report` class so its source remains portable.
- `algorithmwh.sty`, `enumitem.sty`, `fancyhdr.sty`, `fncychap.sty`, `myfancy.sty`, `pdfpages.sty`, `rotating.sty` and `watermark.sty` are reusable LaTeX support packages. The copied package files retain their upstream headers and notices.
- `README_SCHEMEGUARD_THESIS_LATEX` is the concise companion inventory for users familiar with the original template folder.

## Verification note

The report's repository measurements refer to the dated evidence identified in its references. Editing this folder does not rerun the SchemeGuard application test suites. The current document was opened in the editor and its existing source is updated in place; the built-in compiler result is reported separately after the requested compilation check.
