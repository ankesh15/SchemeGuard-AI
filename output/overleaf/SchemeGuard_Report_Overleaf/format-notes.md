# Format adaptation notes

The report adopts the reference folder's practical Overleaf organization while keeping SchemeGuard's content, evidence and academic identity separate from the sample project.

| Reference element | SchemeGuard adaptation |
| --- | --- |
| Main `Final_Thesis_All.tex` report | Kept as the existing SchemeGuard source and edited in place. |
| `bib/` directory and `mybib.bib` | Recreated with the report's official-source, research and repository references. The main source retains inline references for one-file portability. |
| `images/` directory and `pic1.png` | Recreated with SchemeGuard wordmark, architecture, document workflow, monitoring workflow, citizen journey and recommendation visuals. |
| `nitathesis.cls` | Replaced by `schemeguardthesis.cls`, a neutral optional base class. The main report uses standard `report` formatting so it does not require a new institution's identity. |
| Support `.sty` files | Reused as general LaTeX support packages with their upstream notices intact; no package was given NIT or SchemeGuard-specific behavior. |
| NIT logo, sample authors and HireMate WhatsApp images | Not copied. They do not describe this project or its authors. |
| HireMate workflow image | Replaced with SchemeGuard's source-document, extraction, evidence review and controlled publication workflow. |
| Report illustrations | Project-specific diagrams are generated assets; the LaTeX source keeps TikZ fallbacks. The desktop recommendation image is a cropped application capture, and the mobile image is clearly illustrative. |

No institute, guide, roll number, signatory or author roster is guessed. The report distinguishes implementation evidence, synthetic evaluation and current limits, especially the difference between government scheme metadata and approved executable eligibility policies.
