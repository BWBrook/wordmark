---
name: coauthor-manuscript-edit
description: "Collaborative co-author editing for a scientific manuscript draft, delivered as tracked changes + anchored comments in a .docx using Wordmark. Use when you are acting as a colleague/co-author (not an anonymous peer reviewer) to improve clarity, logic, framing, and readiness for submission."
---

# Co-author Manuscript Edit — Wordmark workflow

## What this skill is for
Act as a scientific colleague and co-author. Your job is to improve the manuscript in ways that make the *senior author’s* life easier: cleaner prose, clearer argument, fewer reviewer attack surfaces, and explicit open decisions/questions.

Use tracked edits for clear, low-risk improvements. Use comments for things that need author consensus (interpretation, claims, structure, additional analyses, repositioning, journal strategy).

## Inputs you typically need
- The manuscript `.docx` (preferred) or full text.
- Any target journal, word limit, and section constraints.
- Any author preferences (house style, terminology, “don’t rewrite voice”, etc.).
- Optional: figure/table source files, if revisions likely require figure changes.

If the journal isn’t specified, edit for general scientific readability and restraint.

## Outputs you should produce
- An edited `.docx` copy with tracked changes and comments (never overwrite the original unless explicitly asked).
- A short co-author note to the senior author covering:
  - what you changed directly,
  - the most consequential issues you flagged in comments,
  - a short list of questions/decisions the author team needs to resolve.

## Co-author workflow with Wordmark
1. **Create an edited output copy** (prefer `examples/edited/` with dated suffix). When you apply patches, use track changes and a clear co-author identity (default to "Barry Brook").
2. **Inspect + skim end-to-end first** (`wordmark inspect --json`) to understand the narrative spine.
3. **Do a “safe edit pass”**
   - tighten sentences, fix ambiguity, remove hedges/hype where inappropriate,
   - standardise terminology,
   - ensure claims are supported and scoped.
4. **Do a “reviewer-proofing pass”**
   - look for missing citations, overclaiming, unclear methods, missing limitations,
   - check Results ↔ Methods alignment (what was promised vs what was done),
   - check Discussion ↔ Results alignment (interpretation doesn’t outrun evidence).
5. **Add co-author comments for bigger issues**
   - keep them crisp: observation → why it matters → proposed fix / question.
6. **Verify** (`wordmark verify` with `review-edit` profile) and render if layout-sensitive.

## Intervention policy (tracked edits vs comments)
Use **tracked edits** when:
- the intended meaning is clear and you are not changing scientific content,
- you can materially improve clarity/flow with minimal risk,
- the change is local (wording, syntax, signposting).

Use **comments** when:
- a claim may be wrong, overstated, or missing evidence,
- an analysis might be required,
- a restructure could improve coherence,
- there’s a strategic decision (journal fit, framing emphasis, what to cut).

When in doubt, comment rather than rewrite.

## Style defaults
- Prefer British spelling unless the target journal clearly uses US spelling.
- Keep the author’s voice; do not homogenise idiosyncratic phrasing unless it harms clarity.
- Replace vague intensifiers (“very”, “highly”, “significant” as rhetoric) with specifics or delete.
- Prefer concrete nouns and verbs over abstract nominalisations where it improves readability.

## Wordmark-specific safety + fidelity
- Follow `docs/authoring-workflow.md` for commands and patch operations.
- Follow `docs/fidelity-policy.md` (default strict tracked-edit safety; use `review-edit` verify profile for iterative passes).
- Use preflight (`edit apply --preflight-only`) before running large patches.
- If edits would trigger broad paragraph rewrites or risky markup, narrow them or convert to comments.

## Handoff summary to include
Report:
- output `.docx` path,
- whether you focused on (a) prose, (b) argument/framing, (c) methods/reviewer-proofing, or a mix,
- the top issues the senior author should tackle first,
- any limitations (missing figures, incomplete references, sections absent).
