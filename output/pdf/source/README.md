# SchemeGuard report source

This package rebuilds the 70-page academic PDF with the supplied reference's
preliminary sequence, six chapters, references and two appendices. The project
name in the report is **SchemeGuard**.

## Edit and rebuild

1. Confirm the author roster, roll numbers, institute, guide, HOD and date in
   `submission.json`. No sample authors, college logo or certification is copied.
2. Edit technical prose in `report_content.py`. Layout and diagram definitions
   are in `build_report.py`. Counts, metrics and citations refer to the existing
   repository evidence, not to fresh application tests during report authoring.
3. Install the small authoring dependencies in a private virtual environment:

   ```bash
   python3 -m venv .venv-report
   .venv-report/bin/pip install -r requirements.txt
   .venv-report/bin/python build_report.py
   ```

The generator writes `../SchemeGuard_Project_Report.pdf` and
`../report_inventory.json`. It prefers Times New Roman when installed, then
Liberation Serif, then ReportLab's standard Times faces. No application service,
database or external AI request is required. No repository secrets are included.

The source format was visually inspected: A4 pages, approximately 30 mm left and
20 mm right margins, Times-style 12-point body, ruled chapter openings, roman
preliminary numbering and Arabic body numbering. Page contents are explicitly
bounded; the build fails rather than silently overflowing a page. After changing
text, render the rebuilt PDF and review all pages again.

## Academic and verification status

The supplied development context identifies Ankesh, but no full author roster,
roll numbers, institute or supervisor details were confirmed. The report does
not invent these facts. Its approval, declaration and certificate pages are
unsigned submission records, not issued institutional endorsements. Appendix A
states that no plagiarism/similarity or guide-issued AI-content report was
provided; no score is fabricated. Append the real institutional reports before
submission and have the authors and supervisor approve the final wording.

The PDF includes 8 figures, 22 tables and 19 numbered references. Two UI figures
are crops from archived, synthetic-input browser verification images; no fresh
browser test is claimed. Model extraction is distinguished from fixture
validation, and the government catalog is distinguished from approved policy.

This is an editable Python/ReportLab source package, not a compiled Overleaf
project. All content can be reviewed as ordinary text in `report_content.py`.
