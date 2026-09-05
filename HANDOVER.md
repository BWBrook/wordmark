# Wordmark Successor Handover

Last refreshed: 2026-09-05

Current stage: **awaiting Barry's Microsoft Word comparison of the 53 edits
that Wordmark deliberately refused in the first real-manuscript pilot**.

This note is a current-state bootstrap, not a project history. Verify live
repository and file state before acting. Do not revive the old Chief of Staff,
named action-agent, or four-file goal-packet workflow: those are historical
machinery, not current policy.

## Start here

1. Read `AGENTS.md`, then this file.
2. Check `git status --short --branch` and recent commits before changing
   anything. At this handover, `main` and `origin/main` both point to `8314e52`
   (`feat: localize tracked edits by target window`). The only inherited
   untracked file before this note was `.DS_Store`.
3. Read only the current surfaces needed for the task:
   - `README.md`
   - `docs/architecture.md`
   - `docs/fidelity-policy.md`
   - `docs/critical-reviewer-agent-brief.md`
   - `docs/critical-reviewer-playbook.md`
   - `docs/log/2026-08-14_target_window_real_manuscript_replay.md`
   - the latest relevant entries in `docs/decisions.md`
4. For the active pilot, use the exact evidence paths under "Human review in
   progress" below. The `artifacts/` tree is ignored by Git and contains real,
   private manuscript material; do not clean, stage, publish, or replace it.

## Product and user

Wordmark is Barry Brook's private, CLI-first toolkit for reviewing DOCX and
Markdown/Quarto manuscripts. Its active promise is to:

- inspect comments and tracked revisions;
- add comments authored as `Barry Brook`;
- apply precise tracked edits without damaging unrelated Word structure;
- accept or reject revisions;
- verify package, review-state, and rendered fidelity; and
- support an optional Markdown/Quarto collaboration round.

Barry is currently the only product user. Do not preserve obsolete interfaces
or add compatibility layers for hypothetical consumers. Preserve source data,
manuscript meaning, and Word document integrity instead.

The DOCX review path is the proven, current centre of gravity. The
Markdown/Quarto manuscript-round surface is implemented and documented but has
not yet earned further expansion through a real pilot. Leave it frozen unless
a concrete workflow demands it.

## Operating principles

Use `/Users/bwbrook/.codex/skills/twilight-laboratory/SKILL.md` for substantial
programme work. The collaboration contract is:

> Rigour at the scientific decision boundary; proportional engineering
> everywhere else.

Barry wants an assertive senior engineering and product collaborator, not an
approval-seeking assistant. Make reversible technical choices, challenge weak
design, and involve him when scientific/editorial judgment, strategy, public
release, or a material trade-off genuinely benefits from his attention. Work
to a coherent reporting horizon, then stop at the 80/20 point after one serious
self-review and any material repair.

Use `/Users/bwbrook/.codex/skills/kill-your-darlings/SKILL.md` whenever the
temptation is to add another fallback, mode, ledger, sidecar, test permutation,
or abstraction. Make each component earn its recurring cost. Git is the
archive. Protect meaningful fidelity and scientific safeguards, but do not
confuse more machinery with more confidence.

For DOCX work, also follow the available `documents` skill where visual or
artifact-level inspection is required. Wordmark itself is the product under
test, so do not silently substitute a generic DOCX editor for the behaviour
being evaluated.

Repository-specific non-negotiables:

- never overwrite original user documents;
- create clearly suffixed edited copies and report exact paths;
- tracked edits should contain the smallest possible character-level deletion
  and insertion, not whole-sentence revisions for one-word changes;
- fail closed when a target would risk fields, hyperlinks, comment anchors,
  existing revisions, or other protected markup;
- do not invent scientific facts or convert an issue requiring author judgment
  into an automatic edit;
- commit and push only when Barry explicitly authorizes it under the current
  `AGENTS.md`.

## What has been established

### Reviewer behaviour

The critical-reviewer guidance was strengthened to favour direct tracked edits
for high-confidence grammar, punctuation, British English, concision, clarity,
agreement, antecedents, and sentence flow. Comments are reserved for evidence,
methods, interpretation, design, and management judgment.

A synthetic dry run produced 15 targeted replacement operations, 22 revision
fragments, and 8 comments. The edit/comment split was judged consistent with
product intent. This was useful calibration, not a broad LLM evaluation.

### Lean audit and cleanup

The August simplification tranche removed an obsolete checkout-only UNO helper,
moved `python-docx` to development-only use, and removed duplicated render test
coverage. A subsequent audit declined to delete active safeguards without real
usage evidence. Sidecars, transcripts, policy modes, interop diagnostics, UNO
retry logic, and manuscript rounds were retained or frozen provisionally.

That is not a permanent endorsement. Use the real workflow to learn what Barry
actually consumes, then simplify narrowly. Do not refactor merely because a
file is long, but do not ignore the current concentration of complexity either:
`ooxml_engine.py` and `cli.py` are each over 1,000 lines, and the target-window
change added 1,330 lines while deleting 254, including a 610-line focused test
module. Any next addition should preferably replace or simplify machinery, not
just stack on top of it.

### Real-manuscript pilot (Goal 005)

The Ink NEE pilot used three real DOCX files plus Barry's critical comments and
suggested line edits. The latest implementation changed `replace_text_once`
from a paragraph-wide risk veto to an exact first review-visible target window.
Preflight now simulates ordered mutations using the same planner as apply, and
successful tracked editing enables Word's document-level track-revisions
setting directly.

Observed result:

- 65 of 120 proposed tracked-edit operations applied, up from 48;
- all 48 previously working edits remained working and 17 were recovered;
- every applied operation had the expected character-minimal delta;
- all 30 requested comments were added and 7 inherited comments preserved;
- all 26 targeted comment ranges were localized exactly;
- fields, instruction text, and hyperlink node sequences were preserved;
- 53 source/edited page pairs were visually inspected with no material damage;
- `make check`, pure coverage, external-tool tests, package checks, inspect,
  review-list, render, and `review-edit` verification passed.

Of the 55 withheld operations, 53 intersected genuinely unsafe markup or
incompatible run topology. Two more (`M-026b` and `M-048`) were classified safe
compatible multi-run edits but were outside the deliberately single-run pilot
executor. Treat those two as a small residual opportunity, not part of the 53.

## Human review in progress

Barry asked for the 53 refused edits in a manual checklist, then received two
working copies on `wsl-laptop` so he could apply them in Microsoft Word with
Track Changes enabled.

Checklist:

`artifacts/real_pilots/ink_nee_goal005/analysis/execution/remaining_unsafe_or_incompatible_edits.md`

The refusal classes are:

- 27 edits spanning differently formatted Word runs;
- 19 edits inside complex field results;
- 1 edit inside an existing comment range;
- 1 edit inside both a comment range and a complex field result;
- 4 edits sharing a run with `lastRenderedPageBreak`; and
- 1 edit combining that layout marker with an existing tracked revision.

Local starting copies for Barry's manual pass:

- `artifacts/real_pilots/ink_nee_goal005/human_review/Main text_NEE_v2_edited_fri14aug2026_goal005_humanreview.docx`
- `artifacts/real_pilots/ink_nee_goal005/human_review/Extended data_NEE_v1_edited_fri14aug2026_goal005_humanreview.docx`

Remote working copies sent byte-identically to WSL:

- `/mnt/c/Temp/ink_nee/Main text_NEE_v2_edited_fri14aug2026_goal005_humanreview.docx`
- `/mnt/c/Temp/ink_nee/Extended data_NEE_v1_edited_fri14aug2026_goal005_humanreview.docx`

The supplementary manuscript has no genuinely unsafe/incompatible operations
remaining. Accepted pilot evidence under `artifacts/.../edited/` must remain
untouched. Do not inspect, copy back, or alter Barry's remote working files
until he says his Word pass is complete.

## Recommended next reporting horizon

When Barry reports that the manual pass is complete, perform a bounded
human-reference differential before proposing more code:

1. Preserve the returned Word-edited files under a new suffix. Record their
   identity and keep the local pre-human copies unchanged.
2. Map the realized tracked changes to all 53 checklist IDs, plus the two safe
   residual operations `M-026b` and `M-048` if useful.
3. Inspect whether Word preserved formatting, fields, comment ranges, revision
   nesting, and page-layout markers after save/reopen. Distinguish edits Word
   can make safely from edits it merely allows but later regenerates or damages.
4. Classify each refusal as:
   - a Wordmark false negative worth supporting;
   - an intentional fail-closed boundary;
   - an operator-guidance issue; or
   - inconclusive evidence.
5. Recommend the smallest high-value engine tranche. The leading candidate is
   likely a narrowly characterized multi-run replacement path, but human
   evidence must decide. Complex field results and nested comment/revision
   structures should remain blocked unless the comparison demonstrates a
   deterministic, fidelity-preserving contract.
6. If implementation is authorized, cover only the earned topology classes,
   use focused characterization tests, replay the relevant real cases, then run
   one proportional full verification pass. Avoid another large framework or
   exhaustive permutation matrix.

The next gold stamp is not "support all 53." It is a defensible classification
of the human results and a lean recommendation about which refusals Wordmark
should learn to handle. Stop and report once further work would mainly polish
the analysis or speculate beyond the evidence.

## Useful evidence paths

- Pilot result: `docs/log/2026-08-14_target_window_real_manuscript_replay.md`
- Full acceptance report:
  `artifacts/real_pilots/ink_nee_goal005/analysis/execution/acceptance_report.md`
- Human checklist:
  `artifacts/real_pilots/ink_nee_goal005/analysis/execution/remaining_unsafe_or_incompatible_edits.md`
- Operation mapping and results:
  `artifacts/real_pilots/ink_nee_goal005/analysis/execution/`
- Focused implementation tests: `tests/test_ooxml_target_window.py`
- Fidelity-sensitive code: `src/wordmark/ooxml_replace.py` and
  `src/wordmark/ooxml_engine.py`
- Lean audit records: `docs/log/2026-08-04_lean_boundary_cleanup.md` and
  `docs/log/2026-08-04_fidelity_path_simplification.md`

Do not start by reading every old phase plan or goal packet. They are useful
only when tracing a specific decision. Start from the live product, the current
human evidence, and the smallest next scientific/editorial decision.
