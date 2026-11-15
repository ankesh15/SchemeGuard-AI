% Neutral thesis base class for the SchemeGuard report bundle.
% The main report remains self-contained and uses the standard report class;
% this class is supplied for authors who want a reusable SchemeGuard layout.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{schemeguardthesis}[2026/11/15 SchemeGuard neutral thesis base]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{report}}
\ProcessOptions\relax
\LoadClass[12pt,a4paper,twoside]{report}
\renewcommand{\bibname}{References}
