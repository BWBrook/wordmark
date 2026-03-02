---
name: grant-proposal-reviewer
description: "Critical review and scoring of a competitive research grant proposal (e.g., ARC Discovery-style), focusing on fit-to-criteria, feasibility, and persuasive case. Produce a scorecard, prioritised risks, and concrete rewrites while respecting page/word limits; optionally annotate a .docx using Wordmark."
---

# Grant Proposal Review (Competitive) — Wordmark workflow

## What this skill is for
Act as a grant reviewer. Your job is to assess whether the proposal, as written, would win in a competitive round, and to produce feedback that improves its competitiveness.

Default stance: sceptical, criterion-driven, and practical. Highlight both fatal flaws and easy wins.

## Inputs you typically need
- Proposal `.docx` (preferred) or full text.
- Funder and scheme (ARC Discovery, NSF, ERC, internal, etc.).
- Assessment criteria + weights + scoring scale (if provided).
- Any hard constraints: page limit, word limit, track record format, budget rules, “no new aims”, etc.

If the scheme is unknown, use a general competitive-grant rubric and clearly label your assumptions.

## Outputs you should produce
- A reviewer report with:
  - overall competitiveness verdict,
  - a criterion-by-criterion scorecard (with brief justification),
  - prioritised issues (with fixes),
  - concrete rewrite suggestions for the highest-leverage passages.
- If working from `.docx`, optionally an annotated `.docx` copy:
  - comments for strategic/content issues,
  - tracked edits for wording improvements where the fix is clear and low-risk.

## Default criterion lens (adapt to the scheme)
If criteria are provided, follow them. Otherwise default to:
- **Significance / importance of the problem**
- **Innovation / novelty**
- **Approach / feasibility / rigour**
- **Team capability**
- **Environment / resources / partnerships**
- **Impact pathway / outcomes** (as appropriate)
- **Clarity / presentation** (structure, readability, compliance)

For ARC Discovery-style proposals, it’s often helpful to explicitly map issues to:
- Investigator(s)
- Project Quality and Innovation
- Feasibility and Benefit
…but only do this if it matches the supplied rubric or scheme.

## Review workflow with Wordmark
1. **Create an edited output copy** (never overwrite the original unless explicitly asked). Use a distinct reviewer identity for comments/edits (default to "Barry Brook").
2. **Skim end-to-end first** to understand aims, claims, and logic before scoring.
3. **Score against criteria** (even if provisional) and note the 2–5 decisive weaknesses.
4. **Identify “killer” issues**
   - unclear aims/hypotheses,
   - mismatch between methods and aims,
   - overambitious timeline,
   - missing preliminary support where needed,
   - weak novelty claim or poor positioning vs literature/competition,
   - weak track record-to-task alignment.
5. **Propose fixes that respect constraints**
   - If at a page/word limit, suggest swaps: add X only if you cut Y.
6. **Annotate the `.docx` (optional)**
   - comments for strategic issues,
   - targeted tracked edits for clarity and persuasion.
7. **Verify** the edited `.docx` if you changed it (`verify --profile review-edit`).

## Comment style (grant reviewer mode)
Use tags to help triage:
- `FATAL:` would likely sink the proposal unless fixed.
- `MAJOR:` strongly reduces score; must address.
- `MODERATE:` score drag; fix if possible.
- `MINOR:` polish/compliance.

Make every comment actionable: observation → why it matters (criterion) → fix.

## Rewrite guidance
- Prefer **small, surgical rewrites** to make claims specific and defensible.
- Replace generic claims (“novel”, “world-leading”) with concrete differentiators.
- Ensure each aim has: rationale → method → feasibility → expected outcome → risk mitigation.
- Where you recommend adding text, also recommend where to cut to keep within limits.

## “No invention” rule
Do not invent:
- prior work, preliminary results, citations, partners, budgets, or infrastructure.
If something seems missing, flag it as a request (e.g., `[NEEDED] preliminary data demonstrating …`).

## Wordmark-specific safety + fidelity
- Follow `docs/authoring-workflow.md` for patch/comment workflow.
- Follow `docs/fidelity-policy.md` for verification profiles.
- For tracked edits, prefer minimal operations (`replace_text_once`) and avoid broad paragraph rewrites unless the user wants heavy rewriting.
- If risky markup is detected or UNO fallback is recommended, narrow the edit or convert it to a comment unless higher-risk edits are explicitly desired.

## Handoff summary to include
Report:
- output `.docx` path (if created),
- scoring assumptions (scheme, rubric, scale) if not provided,
- the 3–7 changes most likely to move the score,
- any compliance risks you noticed (page/format, missing sections, unclear eligibility, etc.).
