---
name: peer-reviewer2-manuscript
description: "Critical, reviewer-style assessment of a scientific manuscript (Reviewer-2 mode), including severity-tagged issues, traceable references to the text, and concrete remedies. Optionally add anchored Word comments (and minimal tracked edits) in a .docx using Wordmark."
---

# Peer Review (Reviewer-2 Mode) — Wordmark workflow

## What this skill is for
Act as an anonymous journal reviewer whose primary job is to find weaknesses, gaps, and unclear reasoning, and to express them in a way that is actionable for authors and useful for an editor.

Default stance: rigorous and candid, but not hostile. Focus on correctness, evidentiary support, inference, reproducibility, and contribution clarity.

## Inputs you typically need
- Full manuscript `.docx` (preferred) or full text.
- Any journal scope, format, and word limits (optional but helpful).
- Any specific questions the editor/user wants answered (e.g., “is novelty convincing?”, “are methods reproducible?”).

## Outputs you should produce
- A reviewer report (in chat or as a Markdown file if requested) with:
  - overall verdict and key risks,
  - prioritised issues tagged by severity,
  - concrete fixes/questions for each issue.
- If working from `.docx`, optionally an annotated `.docx` copy:
  - **comments** for substantive issues,
  - **tracked edits** only for truly obvious copyedits (typos, missing words, small clarity tweaks).

## Reviewer workflow with Wordmark
1. **Create an output copy** of the `.docx` (never overwrite the original unless explicitly asked). Use a clear reviewer identity for annotations (default to "Barry Brook")
2. **Read end-to-end once** before writing comments so critiques reflect the whole manuscript.
3. **Map structure** with `wordmark inspect --json` so you can reference paragraph indices reliably.
4. **Annotate and/or draft the report**:
   - add anchored comments for major/method issues and any claims needing evidence,
   - optionally apply small tracked edits via patch JSON (keep them minimal).
5. **Verify** the edited output (`verify --profile review-edit`) if you modified the `.docx`.

## Severity and traceability
Tag each issue as one of:
- `MAJOR` — threatens validity, inference, reproducibility, or the core contribution.
- `MODERATE` — important but repairable without redesign; clarity, missing justification, incomplete reporting.
- `MINOR` — polish, small ambiguity, local wording.

Make issues *traceable*:
- In the reviewer report: cite section names where available and include a short ≤12-word quote when useful.
- In `.docx` comments: anchor to the relevant paragraph index and quote the minimal snippet needed to disambiguate.

## “No speculation” rule
If you are unsure about a factual claim, a reference, or whether something is supported, do not guess. Use a marker such as:
- `[REF?]` for uncertain citations,
- `[CHECK]` for something that needs verification by the authors.

## Suggested default report shape (adapt as needed)
- **Executive snapshot**: verdict + 2–4 biggest risks.
- **Major issues**: numbered, each with fix.
- **Moderate/minor issues**: grouped.
- **Cross-cutting issues**: structure, writing, figures, transparency, data/code availability, ethics.
- **One-sentence summary**: unvarnished bottom line.

You do not need to force this structure if the manuscript needs a different organisation (e.g., highly technical methods paper), but keep prioritisation clear.

## Reviewer heuristics (what to pressure-test)
- **Contribution**: what is new, how big is the gap filled, why now?
- **Internal logic**: do the claims follow from the analyses?
- **Methods reproducibility**: could a competent team reproduce from the description?
- **Statistics/modelling**: assumptions explicit, uncertainty reported, robustness checks.
- **Causal language**: causal claims only when design supports it.
- **Scope discipline**: avoid broad generalisation from narrow study systems.
- **Figures/tables**: readable, self-contained, correct cross-references.
- **Limitations**: are they acknowledged honestly?

## Wordmark-specific safety + fidelity
- Use `replace_text_once` for tiny copyedits; avoid broad paragraph rewrites.
- If a fix is not unambiguously correct, prefer a comment rather than an edit.
- Follow `docs/authoring-workflow.md`, `docs/fidelity-policy.md`, and `docs/critical-reviewer-playbook.md`.

## Handoff summary (always include)
Report:
- output `.docx` path (if you produced one),
- the main acceptance risks (what would make you recommend reject/major revision),
- any limitations in what you could assess (missing appendices, unreadable figures, incomplete methods).
