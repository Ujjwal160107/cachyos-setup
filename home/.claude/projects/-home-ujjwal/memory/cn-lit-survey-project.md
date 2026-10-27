---
name: cn-lit-survey-project
description: "BACSE203 CN literature survey (AI network config generation) lives in ~/CN-Project (renamed from ~/Project); 98 verified journal papers, IDs fixed, Review 2 deck done, first manuscript draft written 2026-10-26"
metadata:
  node_type: memory
  type: project
  originSessionId: 34c01091-05da-4ab4-940b-179f64768f42
  modified: 2026-10-26T16:30:51.871Z
---

Ujjwal's VIT BACSE203 Computer Networks survey, "AI-Assisted Network Configuration Generation: Structured Outputs, Formal Validation, and Error Recovery" (team: Mannat Dhingra, T A Shreeram, Ujjwal Tiwari), is in `~/CN-Project/` (the user renamed it from `~/Project/` after 2026-10-15). `Guideline_Manuscript.PDF` and `Review_Workbook_Template.xlsx` were never found.

State:
- 98 Crossref-verified journal papers. Paper IDs 1–58 have PDFs in `Papers/`; 59–98 are abstract-only.
- Workbooks and gap/top-5/direction/methodology/progress reports are in `Analysis/`. Review 2 deck (33 slides) is in `Reviews/`.
- 2026-10-26: user asked for the manuscript draft to send to the professor. Written as a structured literature review in the professor's Step 9 section order, reference numbers = Paper IDs, American spelling, no em/en dashes (scripted lint). Output in `Manuscript/` (docx + pdf).
- 2026-10-26 later: v2 draft (`Manuscript/Review_Manuscript_Draft_v2.docx`) applies the user's supervisor-prep amendments (Table 1/2 detail, 3-level coverage scale, gaps and limitations structured, ranking basis, "References" instead of "Paper IDs", AI-declaration section removed). Scratchpad sources were lost between sessions, so further edits mean re-extracting the docx into blocks and rebuilding, or editing the docx directly.
- Open decisions: whether the professor counts PACM journals (IDs 17, 21, 35, 36, 40, 46, 51, 52, 98); which journal template; similarity check not run; the draft includes an AI-assistance declaration the authors must confirm.

**Why:** the user wants strict, evidence-based work: no conference papers, no invented data, honest abstract-only labelling, and prose free of AI markers.
**How to apply:** keep Paper IDs stable. Build scripts live only in session scratchpads (not kept in the project), so later fixes go into the docx/xlsx files or must be rebuilt. Statistics use only the 53 full-text primary papers. Check Progress_Report.md for pending tasks before continuing.
