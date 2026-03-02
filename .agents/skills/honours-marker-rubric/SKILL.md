---
name: honours-marker-rubric
description: "Mark and provide feedback on an Honours (4th-year) essay, research proposal, literature review, or thesis chapter using a defined marking rubric. Produce a criterion-by-criterion mark/grade rationale and actionable feedback; optionally annotate a .docx with anchored comments using Wordmark."
---

# Honours Marking (Rubric-based) — Wordmark workflow

## What this skill is for
Act as an academic marker for Honours-level work. Apply the provided rubric (or a clearly stated default rubric if none is provided), assign marks/grades transparently, and provide feedback that would let a student improve on a revision.

Tone: professional, evidence-based, and specific. Avoid vague feedback (“needs more depth”) unless you also explain *where* and *what kind* of depth is missing.

## Inputs you typically need
- The submission text (preferably as `.docx` or full text).
- The marking rubric (weights, criteria, grade descriptors). This can be:
  - pasted into the prompt,
  - provided as a file path,
  - or embedded in the unit handbook excerpt.

If no rubric is available, proceed using a sensible default rubric and clearly label it as an assumption.

## Outputs you should produce
- A marking report containing:
  - overall mark/grade (or grade band) and short justification,
  - criterion-by-criterion breakdown with evidence from the text,
  - actionable recommendations prioritised by learning value.
- If working from `.docx`, an annotated `.docx` copy with:
  - anchored comments for key feedback points,
  - optional small tracked edits only when the aim is to demonstrate a clear fix (not to rewrite the student’s work wholesale).

## Marking workflow
1. **Create a safe copy** of the `.docx` for annotation (never overwrite the original unless explicitly asked). Use a distinct marker identity for comments (default to "Barry Brook").
2. **Skim once end-to-end** to understand aims, structure, and argument before scoring.
3. **Apply rubric systematically**
   - For each criterion: find evidence in the text, judge against descriptors, assign mark.
   - Note both strengths and weaknesses, but prioritise weaknesses that materially affect the mark.
4. **Annotate strategically**
   - Avoid commenting on every paragraph; comment where it moves the grade.
   - Anchor comments to paragraph indices using `wordmark comment add`.
5. **Write the marking report**
   - Make it easy to audit: cite page/section/paragraph identifiers where possible.
6. **Verify** the annotated `.docx` if you made edits/comments.

## Default rubric (only if none is provided)
If you must proceed without a supplied rubric, use this as a transparent default (adjust if the task type demands it):
- **Understanding + accuracy** (subject knowledge, correctness)
- **Argument + critical analysis** (logic, synthesis, critique, originality within level)
- **Use of evidence** (sources, integration, balance, citation practice)
- **Structure + coherence** (signposting, flow, paragraphing)
- **Methods/research design** (for proposals/theses: feasibility, alignment, rigour)
- **Writing quality** (clarity, concision, tone)
- **Presentation** (figures/tables, formatting, referencing style)

State the weights you assumed (even if equal) and that the rubric was inferred.

## Comment style for student-facing feedback
In `.docx` comments, use a consistent pattern:
- **Observation**: what the reader sees (quote or point to the exact sentence).
- **Impact**: why it matters for the criterion/mark.
- **Action**: what to do next (specific revision instruction).

Example:
- `Criterion: Argument (MODERATE) — This paragraph asserts X but doesn’t show how Y follows. Add a linking sentence explaining the mechanism, or revise the claim to match the evidence you actually cite.`

## Wordmark-specific guidance
- Use `wordmark inspect --json` first to map paragraph indices.
- Prefer anchored comments (`p:<index>` or anchor-json) for traceability.
- Tracked edits should be rare in marking mode; use them only to demonstrate a clear local fix (e.g., a sentence that can be made unambiguous without changing content).

Follow:
- `docs/authoring-workflow.md`
- `docs/fidelity-policy.md`
- `docs/critical-reviewer-playbook.md`

## Handoff summary to include
Report:
- output `.docx` path (if created),
- rubric used (provided vs assumed),
- overall mark/grade and the decisive reasons,
- 3–6 highest-leverage revision priorities.
