---
name: study-guide-pdfs
description: "When turning lecture PDFs into study material, user wants detailed first-time-learning guides, not cheat sheets"
metadata:
  node_type: memory
  type: feedback
  originSessionId: dc58b342-f84d-4648-8134-68b1361edd27
  modified: 2026-11-13T23:44:39.153Z
---

When the user asks to turn a course PDF (e.g. DBMS modules) into an "easy to understand" PDF, make a **detailed study guide**: intuition first, full theory, diagrams, step-by-step methods for numericals, worked examples, practice questions per section, and an answer key at the end.

**Why:** On 2026-11-11 a condensed 11-page version of DBMS Module 4 was rejected: "im not asking for cheat sheet or revision im learning for the first time so ofc i need to learn theory aswell also give example questions aswell". The 39-page guide that replaced it was the accepted shape.

**Also (2026-11-12, CN Module 5):** a 131-page guide was rejected: "remove contents which isnt in the syllabus ... i need imedeiate ans not ans at the end ... do not makw this long pdf try to include everyhting though". Use the official syllabus as the filter (faculty decks contain extras), put practice answers directly under each question, and set a page budget per chapter (~55-60 pages for a whole module).

**How to apply:** "Not bloated" from this user means no filler or repetition. It does not mean short. Pipeline that worked: pdfimages + tesseract OCR, then Python-generated HTML with inline SVG diagrams, printed with headless Chrome to ~/Downloads/<Subject>_<Module>_Study_Guide.pdf.

**Also (2026-11-13, CN Module 2):** the user asked for "crisp and to the point which explains well in one read", with the question bank answered at the end, each question followed by its answer.

**Also (2026-11-13, CN Module 2 redo):** the textbook-style notes (idea/analogy/key-fact boxes) were rejected as "very complicated ... very hard to understand". The user wants the notes to copy the faculty PPT style: one box per slide, the slide's title, short bullets in the deck's own wording, its tables and simple diagrams, and nothing beyond the syllabus. Default to this slide-by-slide style when faculty decks are given.

**PYQ pages (2026-11-14):** for CN the user wanted EVERY question from both course codes' papers (BCSE308L + BACSE203), one tabbed HTML page per module, topic-wise, each with a full 10-mark answer (not top-5). Sources and generators are backed up in ~/.cache/cn-restore/pyq-answers.tgz.

**Working files:** a reboot at 18:59 on 2026-11-13 wiped the scratchpad, because /tmp is tmpfs. The files were rebuilt by replaying the Write/Edit/Bash calls from the session transcripts (scripts in ~/.cache/cn-restore/). For multi-session guide work, keep the generator sources somewhere persistent, e.g. ~/dev/study-guides, not only in the scratchpad.
