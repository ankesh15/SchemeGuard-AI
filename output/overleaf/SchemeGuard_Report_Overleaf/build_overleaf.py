#!/usr/bin/env python3
"""Build the self-contained SchemeGuard Overleaf source from report content."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "source" / "report_content.py"
OUTPUT = ROOT / "Final_Thesis_All.tex"
METADATA = json.loads((ROOT / "submission.json").read_text(encoding="utf-8"))


class Page:
    def __init__(self, chapter: str = "", number: str = "") -> None:
        self.chapter = chapter
        self.number = number


events: list[tuple] = []
pages: list[Page] = []
headings: list[tuple] = []
current_chapter = ""
current_number = ""


def new(chapter: tuple[str, str] | None = None) -> Page:
    global current_chapter, current_number
    if chapter:
        current_number, current_chapter = chapter
        events.append(("chapter", current_number, current_chapter))
    page = Page(current_chapter, current_number)
    pages.append(page)
    return page


def h(number: str, title: str) -> None:
    events.append(("heading", number, title))
    headings.append((1, (number + " " + title).strip(), len(pages)))


def sub(title: str) -> None:
    events.append(("subheading", title))


def add(text: str, style: str = "body") -> None:
    events.append(("paragraph", text, style))


def tbl(number: str, title: str, headers: list[str], rows: list[list[str]], widths=None) -> None:
    events.append(("table", number, title, headers, rows, widths))


def fig(number: str, title: str, kind: str, height: int = 285) -> None:
    events.append(("figure", number, title, kind))


def imagefig(number: str, title: str, filename: str, width=None) -> None:
    events.append(("figure", number, title, "ui"))


def code(text: str) -> None:
    events.append(("code", text))


def esc(value: str) -> str:
    return html.escape(value, quote=False)


exec(compile(CONTENT.read_text(encoding="utf-8"), str(CONTENT), "exec"), globals())


def tex_escape(value: str) -> str:
    value = value.replace("\u2011", "-").replace("\u2013", "--").replace("\u2014", "---")
    value = value.replace("\u2018", "`").replace("\u2019", "'")
    value = value.replace("\u201c", "``").replace("\u201d", "''")
    value = value.replace("\u00a0", " ")
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    return "".join(replacements.get(char, char) for char in value)


class HTMLToTeX(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.suppress_link_text = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("b", "strong"):
            self.parts.append(r"\textbf{")
        elif tag in ("i", "em"):
            self.parts.append(r"\textit{")
        elif tag == "br":
            self.parts.append(r"\\")
        elif tag == "link":
            url = dict(attrs).get("href", "") or ""
            self.parts.append(r"\url{" + url + "}")
            self.suppress_link_text = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("b", "strong", "i", "em"):
            self.parts.append("}")
        elif tag == "link":
            self.suppress_link_text = False

    def handle_data(self, data: str) -> None:
        if not self.suppress_link_text:
            self.parts.append(tex_escape(data))


def convert_markup(value: str) -> str:
    parser = HTMLToTeX()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts)


def label_for(prefix: str, number: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", number).strip("-").lower()
    return f"{prefix}:{slug or 'item'}"


def make_table(title: str, headers: list[str], rows: list[list[str]], widths=None) -> str:
    count = len(headers)
    ratios = widths if widths and len(widths) == count else [1.0] * count
    total = float(sum(ratios)) or float(count)
    available = 0.96
    columns = "|".join(
        r">{\RaggedRight\arraybackslash}p{"
        + f"{available * float(ratio) / total:.4f}"
        + r"\textwidth}"
        for ratio in ratios
    )
    header = " & ".join(r"\textbf{" + convert_markup(value) + "}" for value in headers) + r" \\ \hline"
    body = []
    for row in rows:
        cells = [convert_markup(str(value)) for value in row]
        if len(cells) < count:
            cells.extend([""] * (count - len(cells)))
        body.append(" & ".join(cells[:count]) + r" \\ \hline")
    continued = " & ".join([r"\textbf{" + convert_markup(value) + "}" for value in headers]) + r" \\ \hline"
    caption = convert_markup(title)
    return "\n".join(
        [
            r"\begingroup\small\renewcommand{\arraystretch}{1.18}",
            rf"\begin{{longtable}}{{|{columns}|}}",
            rf"\caption{{{caption}}}\label{{{label_for('tab', title)}}}\\",
            r"\hline\rowcolor{sglight}" + header,
            r"\endfirsthead",
            rf"\caption[]{{{caption} (continued)}}\\",
            r"\hline\rowcolor{sglight}" + continued,
            r"\endhead",
            r"\hline\multicolumn{" + str(count) + r"}{r}{Continued on next page}\\\endfoot",
            r"\hline\endlastfoot",
            *body,
            r"\end{longtable}",
            r"\endgroup\vspace{0.3em}",
        ]
    )


def box(node: str, title: str, detail: str, *, options: str = "") -> str:
    return rf"\node[sgbox{',' + options if options else ''}] ({node}) {{\textbf{{{title}}}\\{detail}}};"


def make_diagram(kind: str) -> str:
    start = [
        r"\begin{figure}[htbp]\centering",
        r"\resizebox{0.98\textwidth}{!}{%",
        r"\begin{tikzpicture}[sgbox/.style={draw=sggreen,fill=sglight,rounded corners=3pt,align=center,text width=10.8cm,inner sep=7pt,font=\small},sgarrow/.style={-{Latex[length=2.5mm]},thick,draw=sggreen},node distance=6mm]",
    ]
    end = [r"\end{tikzpicture}%", r"}"]
    if kind == "architecture":
        nodes = [
            ("people", "Citizens, guests and administrators", "Profile-first discovery, assessments, document review and monitoring"),
            ("web", "Next.js application", "Responsive citizen and protected administrator workspaces"),
            ("api", "FastAPI modular monolith", "Versioned APIs, recommendations, deterministic rules, ingestion, review and RAG"),
            ("db", "PostgreSQL with pgvector", "Scheme metadata, policy history, private records, evidence and durable jobs"),
            ("jobs", "Celery workers and one scheduler", "Document processing, source checks and consent-aware reassessment"),
            ("infra", "Redis and persistent document storage", "Redis carries task delivery; original files remain checksummed and durable"),
        ]
    elif kind == "journey":
        nodes = [
            ("n1", "1. Tell us about yourself", "Optional age, state, education, work and interests"),
            ("n2", "2. Discover relevant schemes", "Catalog-backed results with plain reasons and unknown fields"),
            ("n3", "3. Explore scheme details", "Verified metadata, source links and assessment support status"),
            ("n4", "4. Check supported requirements", "Only an applicable approved rule set can support a strict result"),
            ("n5", "5. Understand the report", "Evidence, rule version, missing information and informational notice"),
        ]
    elif kind == "pipeline":
        nodes = [
            ("n1", "Authorized source or administrator upload", "Validate PDF bytes, size, page count, URL and checksum"),
            ("n2", "PyMuPDF page-aware extraction", "Preserve original pages, text blocks, chunks and extraction issues"),
            ("n3", "Gemini structured candidate rules", "Pydantic validation, supported operators and located evidence"),
            ("n4", "LangGraph verification and human review", "Reviewer decides on an exact saved revision; uncertainty stays pending"),
            ("n5", "Transactional rule publication", "Only approved, evidenced rules can become executable"),
        ]
    elif kind == "monitor":
        nodes = [
            ("n1", "Opt-in source schedule", "Celery Beat enqueues bounded, idempotent checks"),
            ("n2", "Secure conditional fetch", "Timeouts, safe redirects, ETag, Last-Modified and SHA-256"),
            ("n3", "New immutable document version", "Unchanged content is skipped; changed bytes do not imply a policy change"),
            ("n4", "Reuse extraction and review workflow", "Candidate rules retain document, page and excerpt evidence"),
            ("n5", "Structured policy comparison", "Normalize old approved rules and new pending candidates"),
            ("n6", "Human approval and reassessment", "Publish a new version, retain old reports and deduplicate user impact"),
        ]
    elif kind == "deploy":
        nodes = [
            ("n1", "HTTPS browser entry", "Next.js client; server-only API proxy configuration"),
            ("n2", "Application services", "API, bounded workers and a single Celery Beat scheduler"),
            ("n3", "Private PostgreSQL and Redis", "Database owns durable state; broker remains internal"),
            ("n4", "Persistent document storage", "Local Docker volume in development; private object storage in deployment"),
            ("n5", "Operations", "Readiness checks, structured logs, backup and restore procedures"),
        ]
    elif kind == "erd":
        start = [r"\begin{figure}[htbp]\centering", r"\resizebox{0.98\textwidth}{!}{%", r"\begin{tikzpicture}[sgbox/.style={draw=sggreen,fill=sglight,rounded corners=3pt,align=center,text width=3.5cm,inner sep=7pt,font=\small},sgarrow/.style={-{Latex[length=2.5mm]},thick,draw=sggreen}] "]
        nodes = []
        nodes.extend([
            r"\node[sgbox] (s) at (0,0) {\textbf{schemes}\\UUID and stable slug};",
            r"\node[sgbox] (src) at (5,0) {\textbf{scheme\_sources}\\official source URL};",
            r"\node[sgbox] (doc) at (10,0) {\textbf{document\_versions}\\checksum and provenance};",
            r"\node[sgbox] (chunks) at (10,-2.2) {\textbf{document chunks}\\page, section and text};",
            r"\node[sgbox] (rules) at (5,-2.2) {\textbf{rule\_sets}\\immutable version and status};",
            r"\node[sgbox] (conds) at (0,-2.2) {\textbf{rule\_conditions}\\typed deterministic logic};",
            r"\node[sgbox] (evid) at (0,-4.4) {\textbf{rule\_evidence}\\document and page excerpt};",
            r"\node[sgbox] (assess) at (5,-4.4) {\textbf{assessments}\\original rule version and trace};",
            r"\node[sgbox] (profiles) at (10,-4.4) {\textbf{users and profiles}\\owner-scoped encrypted data};",
            r"\draw[sgarrow] (s) -- (src);\draw[sgarrow] (src) -- (doc);\draw[sgarrow] (doc) -- (chunks);",
            r"\draw[sgarrow] (doc) -- (rules);\draw[sgarrow] (rules) -- (conds);\draw[sgarrow] (conds) -- (evid);",
            r"\draw[sgarrow] (rules) -- (assess);\draw[sgarrow] (profiles) -- (assess);",
        ])
        return "\n".join(start + nodes + end)
    elif kind == "ui":
        start = [r"\begin{figure}[htbp]\centering", r"\resizebox{0.9\textwidth}{!}{%", r"\begin{tikzpicture}[sgbox/.style={draw=sggreen,fill=white,rounded corners=4pt,align=left,text width=5.4cm,minimum height=3.5cm,inner sep=10pt,font=\small},sgtag/.style={fill=sglight,rounded corners=8pt,inner sep=4pt,font=\footnotesize\bfseries}] "]
        nodes = [
            r"\node[sgbox] (card1) at (0,0) {\textcolor{sggreen}{\textbf{SCHOLARSHIPS AND EDUCATION}}\\[4pt]\textbf{Ishan Uday Special Scholarship}\\Based on the selected education interest and student details.\\[4pt]\textcolor{sggreen}{Matches your interest in education}\\Scheme-specific criteria: more information required\\[5pt]\textcolor{sggreen}{View details $\rightarrow$}};",
            r"\node[sgbox] (card2) at (7,0) {\textcolor{sggreen}{\textbf{AGRICULTURE}}\\[4pt]\textbf{Agri Clinics and Agri Business Centres}\\Suggested because agriculture was selected as an interest.\\[4pt]\textcolor{sggreen}{Category match}\\State coverage is not verified for this record\\[5pt]\textcolor{sggreen}{View details $\rightarrow$}};",
            r"\node[sgtag] at (0,1.45) {HIGHLY RELEVANT};\node[sgtag] at (7,1.45) {POTENTIALLY RELEVANT};",
        ]
        return "\n".join(start + nodes + end)
    else:
        nodes = [("n1", "Source", "Verified document and evidence"), ("n2", "Decision", "Typed result and version trace")]
    lines = list(start)
    for index, (name, title, detail) in enumerate(nodes):
        options = "below=of " + nodes[index - 1][0] if index else ""
        lines.append(box(name, title, detail, options=options))
        if index:
            lines.append(rf"\draw[sgarrow] ({nodes[index - 1][0]}.south) -- ({name}.north);")
    lines.extend(end)
    return "\n".join(lines)


PREAMBLE = r"""\documentclass[12pt,a4paper,twoside]{report}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[a4paper,inner=30mm,outer=22mm,top=25mm,bottom=25mm,headheight=15pt]{geometry}
\usepackage{setspace}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage[table]{xcolor}
\usepackage{array,longtable,booktabs,tabularx}
\usepackage{caption}
\usepackage{fancyhdr}
\usepackage{enumitem}
\usepackage{listings}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning,shapes.geometric}
\usepackage{xurl}
\usepackage{hyperref}
\usepackage{titlesec}
\usepackage{chngcntr}
\usepackage{ragged2e}
\usepackage{float}
\definecolor{sggreen}{HTML}{176B4D}
\definecolor{sglight}{HTML}{E9F3EE}
\definecolor{sggray}{HTML}{515B55}
\hypersetup{colorlinks=true,linkcolor=sggreen,citecolor=sggreen,urlcolor=sggreen,pdftitle={SchemeGuard Project Report},pdfauthor={AUTHOR}}
\setstretch{1.22}
\setlength{\parskip}{0.45em}
\setlength{\parindent}{1.25em}
\setcounter{secnumdepth}{3}
\setcounter{tocdepth}{2}
\counterwithin{figure}{chapter}
\counterwithin{table}{chapter}
\titleformat{\chapter}[display]{\normalfont\bfseries\Huge\filright}{\chaptertitlename\ \thechapter}{1ex}{\titlerule\vspace{1ex}}
\titlespacing*{\chapter}{0pt}{-15pt}{22pt}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[LE]{\small\nouppercase{\leftmark}}
\fancyhead[RO]{\small\nouppercase{\rightmark}}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\captionsetup{font=small,labelfont=bf}
\lstset{basicstyle=\ttfamily\small,breaklines=true,frame=single,backgroundcolor=\color{sglight},rulecolor=\color{sggreen},columns=fullflexible,keepspaces=true}
\newcommand{\SchemeGuard}{\textsc{SchemeGuard}}
\newcommand{\Unknown}{\textsc{Unknown}}
\newcommand{\StatusNotice}{\textit{SchemeGuard provides informational discovery and assessment demonstrations. It does not make government eligibility decisions or issue official approval.}}
\begin{document}
"""


def front_matter() -> str:
    author = tex_escape(METADATA.get("author_display") or "Project team")
    report_date = tex_escape(METADATA.get("submission_date") or "Date to be confirmed")
    department = tex_escape(METADATA.get("department") or "")
    institute = tex_escape(METADATA.get("institute") or "")
    roll = tex_escape(METADATA.get("roll_number") or "")
    guide = tex_escape(METADATA.get("project_guide") or "")
    guide_designation = tex_escape(METADATA.get("guide_designation") or "Project Guide")
    institute_block = rf"{{\large {institute}\par}}" if institute else ""
    roll_block = rf"{{\large Roll number: {roll}\par}}" if roll else ""
    guide_block = (
        rf"{{\large Under the guidance of {guide} ({guide_designation})\par}}"
        if guide
        else ""
    )
    return r"""\begin{titlepage}
\thispagestyle{empty}
\centering
\vspace*{1.3cm}
{\Huge\bfseries\color{sggreen} SCHEMEGUARD\par}
\vspace{0.8cm}
{\Large Personalized Government Scheme Discovery, Evidence-backed Eligibility and Policy Change Monitoring\par}
\vspace{1.2cm}
\IfFileExists{images/SchemeGuard_logo.png}{\includegraphics[width=0.54\textwidth]{images/SchemeGuard_logo.png}}{%
\begin{tikzpicture}
\draw[sggreen,line width=2pt,rounded corners=10pt] (0,0) -- (0,1.8) -- (1.2,2.2) -- (2.4,1.8) -- (2.4,0.5) -- (1.2,-0.1) -- cycle;
\draw[sggreen,line width=3pt] (0.55,1.05) -- (1.0,0.62) -- (1.85,1.45);
\end{tikzpicture}}
\vspace{1.1cm}

{\Large Project Report\par}
\vspace{0.55cm}
{\large Prepared by\par}
{\Large\bfseries AUTHOR\par}
\vspace{0.8cm}
{\large Bachelor of Technology Project\par}
{\large DEPARTMENT\par}
INSTITUTE_BLOCK
\vfill
{\large REPORT_DATE\par}
\end{titlepage}

\begin{titlepage}
\thispagestyle{empty}
\centering
\vspace*{1.5cm}
{\Large\bfseries SCHEMEGUARD\par}
\vspace{0.8cm}
{\large Personalized Government Scheme Discovery, Evidence-backed Eligibility and Policy Change Monitoring\par}
\vspace{1.3cm}
{\large A project report submitted in partial fulfilment of the requirements for the degree of\par}
\vspace{0.35cm}
{\Large Bachelor of Technology\par}
{\large in DEPARTMENT\par}
\vspace{0.9cm}
{\large by\par}
{\Large\bfseries AUTHOR\par}
ROLL_BLOCK
GUIDE_BLOCK
INSTITUTE_BLOCK
\vfill
{\large REPORT_DATE\par}
\end{titlepage}

\pagenumbering{roman}
\chapter*{Acknowledgement}
\addcontentsline{toc}{chapter}{Acknowledgement}
This project took shape through many rounds of building, testing and reconsidering what the system should claim. I am grateful to the people who tried the application, questioned unclear results and shared feedback that helped make the citizen and administrator journeys easier to understand. I also acknowledge the public departments that maintain the official scheme information used as discovery provenance, and the open-source communities whose tools support the implementation.

The most useful feedback was often a reminder to show uncertainty plainly. That principle shaped the recommendation explanations, the deterministic assessment engine and the document review workflow.

\chapter*{Abstract}
\addcontentsline{toc}{chapter}{Abstract}
\SchemeGuard is a full-stack academic project for personalized discovery of Indian government schemes and traceable assessment of supported requirements. A citizen can share optional profile details and interests to receive explainable, catalog-backed recommendations. The system keeps this relevance ranking separate from eligibility: strict assessments use only applicable, human-approved deterministic rules, preserve source evidence and return \textsc{Pass}, \textsc{Fail} or \textsc{Unknown}. Missing information remains unknown.

The application combines a Next.js interface, FastAPI services, PostgreSQL, immutable document and policy history, PyMuPDF extraction, structured Gemini candidates, a bounded LangGraph review workflow, Celery monitoring and user reassessment. AI output remains pending until an administrator reviews and approves the exact proposed rule revision. Policy updates preserve prior versions and evidence so historical assessments remain reproducible.

The recorded project catalog contains 282 government scheme discovery records, while no government eligibility rule set is approved in the recorded database snapshot. Automated and synthetic integration checks exercise the end-to-end design, but they do not establish current eligibility coverage, real-model accuracy or production deployment. \SchemeGuard is an informational demonstration and does not issue government decisions.

\noindent\textbf{Keywords:} Government schemes, eligibility assessment, evidence provenance, deterministic rules, document processing, policy monitoring, human review.

\tableofcontents
\listoffigures
\listoftables
\clearpage
\pagenumbering{arabic}
""".replace("AUTHOR", author).replace("REPORT_DATE", report_date).replace(
        "DEPARTMENT", department
    ).replace("INSTITUTE_BLOCK", institute_block).replace("ROLL_BLOCK", roll_block).replace(
        "GUIDE_BLOCK", guide_block
    )


def render() -> str:
    out = [PREAMBLE.replace("AUTHOR", tex_escape(METADATA.get("author_display") or "Project team")), front_matter()]
    in_bibliography = False
    appendix_started = False
    for event in events:
        kind = event[0]
        if kind == "chapter":
            _, number, title = event
            if in_bibliography:
                out.append(r"\end{thebibliography}\clearpage")
                in_bibliography = False
            if number == "A" and not appendix_started:
                out.append(r"\appendix")
                appendix_started = True
            out.append(r"\clearpage\chapter{" + tex_escape(title) + "}")
        elif kind == "heading":
            _, number, title = event
            if title == "References":
                if not in_bibliography:
                    out.append(r"\clearpage\chapter*{References}\addcontentsline{toc}{chapter}{References}\begin{thebibliography}{99}")
                    in_bibliography = True
            elif in_bibliography and not number:
                out.append(r"\section*{" + tex_escape(title) + "}")
            else:
                out.append(r"\section{" + tex_escape(title) + "}")
        elif kind == "subheading":
            out.append(r"\subsection*{" + tex_escape(event[1]) + "}")
        elif kind == "paragraph":
            _, text, style = event
            if in_bibliography and style == "ref":
                plain = re.match(r"^\[(\d+)\]\s*(.*)$", text, re.S)
                if plain:
                    number, body = plain.groups()
                    out.append(r"\bibitem{sgref" + number + "}" + convert_markup(body))
                else:
                    out.append(convert_markup(text))
            elif style == "code":
                out.append(r"\begin{lstlisting}" + "\n" + text + "\n" + r"\end{lstlisting}")
            elif style == "small":
                out.append(r"{\small " + convert_markup(text) + "}")
            elif style == "ref":
                out.append(r"\noindent " + convert_markup(text) + r"\par")
            else:
                out.append(convert_markup(text))
        elif kind == "table":
            _, number, title, headers, rows, widths = event
            out.append(make_table(title, headers, rows, widths))
        elif kind == "figure":
            _, number, title, diagram = event
            image_paths = {
                "architecture": "images/schemeguard-architecture.png",
                "pipeline": "images/document-processing-workflow.png",
                "monitor": "images/policy-monitoring-workflow.png",
                "journey": "images/profile-first-journey.png",
                "ui": "images/recommendation-cards-desktop.png" if number == "4.2" else "images/recommendation-card-mobile.png",
            }
            caption = r"\caption{" + tex_escape(title) + "}\\label{" + label_for("fig", number) + r"}"
            if diagram in image_paths:
                asset = image_paths[diagram]
                image_figure = (
                    r"\begin{figure}[htbp]\centering\includegraphics[width=0.94\textwidth,height=0.68\textheight,keepaspectratio]{"
                    + asset
                    + "}"
                    + caption
                    + r"\end{figure}"
                )
                fallback_figure = make_diagram(diagram) + caption + r"\end{figure}"
                out.append(r"\IfFileExists{" + asset + "}{" + image_figure + "}{" + fallback_figure + "}")
            else:
                out.append(make_diagram(diagram))
                out.append(caption + r"\end{figure}")
    if in_bibliography:
        out.append(r"\end{thebibliography}")
    out.append(r"\end{document}")
    return "\n\n".join(out) + "\n"


OUTPUT.write_text(render(), encoding="utf-8")
print(f"Wrote {OUTPUT} ({len(events)} report elements)")
