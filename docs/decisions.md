# Architecture Decisions

## 2026-02-23 - ADR-001: Python-first CLI stack
- Status: accepted
- Context: We need a Linux-native, agent-friendly `.docx` workflow with tight control over side effects.
- Decision: Implement v1 as a Python package with a CLI (`wordmark`) using `lxml` for OOXML mutation, optional LibreOffice UNO fallback, and JSON sidecars for review.
- Consequences: Fast iteration and testability in WSL; revision semantics remain constrained to safe operations in v1.

## 2026-02-23 - ADR-002: UNO bridge runs on system Python
- Status: accepted
- Context: `uv` virtual environments do not include LibreOffice `uno` bindings; direct import fails in venv.
- Decision: Execute UNO fallback through `/usr/bin/python3` helper script (`scripts/uno_replace.py`) and keep CLI runtime in uv-managed env.
- Consequences: Reliable UNO access without polluting project env; fallback behavior depends on system LibreOffice/pyuno availability.

## 2026-02-23 - ADR-003: Safe OOXML operation boundary
- Status: accepted
- Context: Full run-level OOXML revision surgery is error-prone and high-risk for unintended formatting drift.
- Decision: Restrict OOXML v1 mutations to deterministic, paragraph-level transforms and explicit comment insertion; route unsupported operations to UNO fallback.
- Consequences: Higher safety for common operations, but narrower direct OOXML feature surface in phase 1.

## 2026-02-23 - ADR-004: Word desktop validation is manual release gate
- Status: accepted
- Context: Native Microsoft Word cannot run in this Ubuntu workspace, but Word round-trip confidence is still required.
- Decision: Automate Linux integrity/render checks and treat Word desktop spot-check as explicit manual gate for release-critical documents.
- Consequences: CI remains Linux-native; final high-risk sign-off still requires human Word validation.

## 2026-02-23 - ADR-005: Localized run-level revisions for replace_text_once
- Status: accepted
- Context: Paragraph-rewrite tracked edits caused whole-sentence redlines for single-word changes, reducing review fidelity.
- Decision: For `replace_text_once`, attempt localized run-level split first and emit word-level `w:del`/`w:ins` when match is contained in a safe run shape. Fall back to paragraph rewrite only when localized split is unsafe/unsupported.
- Consequences: Common single-word corrections now produce precise revisions in Word; complex multi-run cases still degrade to paragraph-level rewrites until richer run-diff logic is implemented.

## 2026-02-23 - ADR-006: Strict fidelity policy with explicit fallback routing
- Status: accepted
- Context: Even with localized run-level edits, complex patterns can still trigger fidelity-degrading rewrites.
- Decision: Introduce explicit policy controls (`fidelity_mode`, `on_unsupported`, `on_uno_fail`, `allow_paragraph_rewrite_tracked`) with default chain:
  1. OOXML strict localized attempt
  2. UNO fallback
  3. Comment-only fallback
- Consequences: No silent tracked paragraph rewrites in strict mode; behavior is deterministic and auditable via preflight/strategy metadata.

## 2026-02-23 - ADR-007: Canonical vs edited fixture separation
- Status: accepted
- Context: Mounted-drive test files are ephemeral and unsafe as long-term baselines.
- Decision: Store immutable fixture baselines under `examples/canonical/` and generated edited outputs under `examples/edited/`.
- Consequences: Reproducible local test corpus and reduced risk of mutating canonical examples.

## 2026-02-23 - ADR-008: Artifact cleanup command defaults to preview mode
- Status: accepted
- Context: Sidecar and render outputs in `artifacts/` are intentionally disposable, but accidental deletion of useful audit logs is a risk.
- Decision: Add `wordmark artifacts clean` with safe preview default, explicit `--apply` for deletion, optional `--older-than-days` retention filter, and `--keep-transcripts` to preserve operation logs.
- Consequences: Routine cleanup is one command and scriptable; destructive actions require explicit intent and are auditable via structured command output.

## 2026-02-23 - ADR-009: Paragraph+context anchor model with backward selector compatibility
- Status: accepted
- Context: `p:<index>` and `text:<snippet>` selectors are simple but can be ambiguous in repeated-content documents.
- Decision: Standardize richer anchor semantics (`paragraph_index`, `expected_text`, `context_before`, `context_after`, `occurrence`) while preserving legacy selector compatibility.
- Consequences: Safer disambiguation for comments and edits; unresolved/ambiguous anchors now surface explicit error codes.

## 2026-02-23 - ADR-010: Risky-markup-first preflight routing
- Status: accepted
- Context: Some paragraphs can appear localizable but still include fragile OOXML structures (hyperlinks, field codes, content controls, break/tab constructs).
- Decision: Preflight and apply layers treat risky markup as high risk and route to fallback policy rather than attempting localized tracked mutation in strict workflows.
- Consequences: Reduced chance of formatting/review-fidelity drift on complex constructs; more operations route through UNO/comment fallback.

## 2026-02-23 - ADR-011: Word desktop compare/combine remains explicit human merge gate
- Status: accepted
- Context: Team requirement is no direct automated write-back to shared online files without human review.
- Decision: Add explicit desktop merge-back SOP and a non-mutating CLI handoff helper (`review prepare-merge`) that prepares checklist/report metadata.
- Consequences: Shared-doc updates remain human-approved; merge process is repeatable and documented.

## 2026-02-24 - ADR-012: Split verify gates into strict and review-oriented profiles
- Status: accepted
- Context: Advanced mixed-content review passes can legitimately increase page count and produce broader visual diffs, while release-quality checks still require strict invariance.
- Decision: Keep `business-docs` strict (`threshold=0.02`, no page growth) and add `review-edit` (`threshold=0.12`, page growth up to 2) with explicit `profile_reasoning` in verify output.
- Consequences: Iterative supervisory review can proceed with bounded tolerance while preserving a strict release gate for final sign-off.

## 2026-02-24 - ADR-013: Deterministic UNO low-hit retry with explicit diagnostics
- Status: accepted
- Context: Long literal global replacements in complex documents can under-hit in LibreOffice UNO, reducing edit throughput and requiring manual rework.
- Decision: Extend UNO diagnostics to per-operation results and add one deterministic retry pass that converts missed `replace_text_global` operations into `replace_text_once` operations; record retry metadata in operation details.
- Consequences: Better automatic recovery for partial misses without hidden heuristics; operators can audit retry behavior and outcomes in JSON sidecars/transcripts.

## 2026-02-24 - ADR-014: Normalize newly introduced `Unknown Author` UNO revisions
- Status: accepted
- Context: LibreOffice UNO may emit tracked revisions with `Unknown Author`, reducing attribution fidelity in review workflows.
- Decision: After UNO tracked-change writes, detect newly introduced revisions and rewrite unresolved author fields to the requested actor label.
- Consequences: Improved attribution consistency for downstream review/accept-reject operations while preserving pre-existing revision history.

## 2026-02-24 - ADR-015: Serialize mutating DOCX commands with per-file lock
- Status: accepted
- Context: Parallel edit operations targeting the same `.docx` can trigger LibreOffice UNO write collisions (`SfxBaseModel::impl_store ... Write Code:12`) and degrade to comment fallback unexpectedly.
- Decision: Add an exclusive per-document lock (`<file>.docx.wordmark.lock`) around mutating CLI commands (`comment add`, `edit apply`, `review accept`, `review reject`) so concurrent processes queue instead of racing writes.
- Consequences: Eliminates a reproducible concurrency failure mode while preserving current fallback behavior for genuine UNO failures.

## 2026-02-24 - ADR-016: Minimal tracked-change delta for localized replacements
- Status: accepted
- Context: Replacing a phrase for tiny edits (for example `73% studies` -> `73% of studies`, `bird specific` -> `bird-specific`) previously produced full-span delete/insert revisions, reducing review fidelity.
- Decision: For localized tracked replacements, compute common prefix/suffix and emit only middle-segment `w:del`/`w:ins` deltas; for `replace_paragraph_text`, attempt localized full-string replacement before paragraph rewrite fallback.
- Consequences: Word review view now shows concise, intent-aligned edits (insertions/hyphen swaps/tail appends) in many cases, with paragraph rewrite still available as fallback when localization is unsafe.

## 2026-02-25 - ADR-017: UNO fallback rewrites replace_text_once to minimal spans when safe
- Status: accepted
- Context: Complex documents that route to UNO fallback (for example field-code/risky-markup paragraphs) were still producing broad clause-level tracked replacements even for tiny wording/punctuation edits.
- Decision: Before UNO apply, rewrite eligible `replace_text_once` operations to `replace_span_once` operations anchored on the original matched text plus a precise in-match span (`span_start`, `span_length`, `replacement`) computed from prefix/suffix deltas.
- Consequences: Fallback edits in risky-markup documents can express insertion-only, deletion-only, and punctuation-only tracked changes without replacing untouched surrounding text; rewrite diagnostics are recorded under `operation.details.uno_precision_rewrite` for auditability.

## 2026-02-25 - ADR-018: Add interop drift diagnostics and compact risk summary to edit apply
- Status: accepted
- Context: Advanced review passes can succeed technically while still introducing subtle cross-reference drift risk (for example Figure/Table/Eq/Appx renumbering shifts), and operators need a fast machine-readable signal for when manual Word desktop validation should be prioritised.
- Decision: Add a deterministic text-snapshot drift analyzer (`interop_drift`) for reference families (Figure/Table/Equation/Appendix), enable it by default in `edit apply` with explicit threshold control (`--drift-warning-threshold low|moderate|high`), and emit a compact `operation.details.risk_summary` block (fallback usage, risky preflight count, rewrite count, drift status/severity).
- Consequences: Handoffs become more auditable and triage-friendly without changing mutation semantics; drift warnings remain advisory and trigger validation workflow, not automatic mutation strategy changes.

## 2026-02-26 - ADR-019: Token-island split rewrite for separated UNO fallback edits
- Status: accepted
- Context: Even with minimal span rewrite, some `replace_text_once` operations in UNO fallback still surfaced as broad clause replacements when the intended change set contained two separated micro-edits (for example dropping an article near the start and inserting one word near the end).
- Decision: Add a conservative token-level split rewrite path before the existing minimal-span rewrite:
  1. Tokenize `find`/`replace` into whitespace, word, and punctuation tokens.
  2. Identify non-equal token islands via `SequenceMatcher`.
  3. For operations with 2-3 separated islands (`occurrence=1`), emit a sequence of deterministic `replace_span_once` steps, each anchored to the evolving intermediate phrase.
  4. Fall back to the existing single-span rewrite for all other shapes.
- Consequences: Multi-point edits now preserve unchanged middle text in tracked changes more often; aggressive splitting is avoided for dense transformations (for example many case/hyphen/token shifts), preserving prior stable behavior.

## 2026-02-26 - ADR-020: Promote move revisions to first-class review semantics and schema v2
- Status: accepted
- Context: Advanced manuscript runs exposed two fidelity gaps:
  1. UNO fallback could leave `Unknown Author` on `w:moveTo`/`w:moveFrom` revisions.
  2. Text extraction used for inspect/drift could over-report by concatenating both move-source and move-destination text.
- Decision:
  1. Treat move revisions as first-class tracked changes across inspect/review/verify outputs (`insert`, `delete`, `move_to`, `move_from`).
  2. Make `review-visible` text extraction the default for inspect/review/diff snapshots, with explicit `raw` mode for diagnostics.
  3. Expand UNO unknown-author postprocessing to cover `w:moveTo` and `w:moveFrom`.
  4. Extend review accept/reject transforms to handle move revisions and clean orphan move range markers.
  5. Roll CLI JSON outputs (`inspect`, `review list`, `verify`) to schema v2 with explicit `schema_version: 2`.
- Consequences: Reviewer-facing extraction now aligns with Word review behavior; move-revision attribution is consistent; machine-readable outputs are cleaner but intentionally break compatibility with pre-v2 revision field naming/counters.

## 2026-02-26 - ADR-021: Add verify-time OOXML compatibility namespace guard
- Status: accepted
- Context: Word can show “unreadable content” recovery prompts even when comments/revisions are present if `word/document.xml` contains compatibility attributes (for example `mc:Ignorable`) that reference undeclared prefixes.
- Decision: Add a verify gate (`compatibility_namespace_integrity`) that parses `word/document.xml`, inspects `mc:Ignorable` tokens, and fails verification when any referenced prefix is missing from namespace declarations.
- Consequences: Corrupt-but-partially-readable outputs are caught before handoff; operators get explicit diagnostics (`missing_prefixes`) and a deterministic fail condition in both strict and review-edit profiles.

## 2026-03-02 - ADR-022: Hybrid manuscript collaboration rounds keep `.md/.qmd` canonical
- Status: accepted
- Context: Teams author manuscripts in Markdown/Quarto but still need high-quality collaborative review workflows, including optional Word-style review ergonomics, without sacrificing source-of-truth discipline.
- Decision: Add a `manuscript` command suite (`prepare`, `collect`, `synthesize`, `status`) that:
  1. keeps `.md/.qmd` as canonical source,
  2. supports optional DOCX/PDF review artifacts for collaborator comfort,
  3. ingests feedback from PR comments/suggestions, markdown notes, and reviewed DOCX states into structured sidecars,
  4. synthesizes deterministic safe edit proposals with explicit opt-in apply (`--apply-safe`),
  5. treats DOCX backport automation as out-of-scope for this phase.
- Consequences: Wordmark now supports mixed collaboration styles with auditable artifacts and low-risk source mutation semantics, while avoiding brittle auto-translation of arbitrary DOCX tracked revisions into Markdown.

## 2026-03-08 - ADR-023: Use a local-first environment contract with marked external-tool tests
- Status: accepted
- Context: The repo depends on host-installed tools (`soffice`, `pdftoppm`, system UNO, `quarto`, `gh`) for important workflows, but not every development environment will provide all of them.
- Decision: Keep the default local workflow as the source of truth for now, add explicit pytest markers (`external_tools`, `rendering`, `uno`, `manuscript_build`, `github_integration`), add local `make test-pure` / `make test-external` lanes, and improve runtime/tool-missing diagnostics.
- Consequences: Developers can separate pure-Python validation from host-tool integration checks without changing default behavior, and missing dependencies fail more clearly.

## 2026-03-08 - ADR-024: Make `AppConfig` dataclass defaults the code source of truth
- Status: accepted
- Context: Config defaults were duplicated across dataclass field defaults, a hard-coded merge dictionary, and the repo `wordmark.yaml`, creating drift risk.
- Decision: Derive loader defaults from `AppConfig` dataclass defaults, align the dataclass with the effective default profiles, and add tests that compare repo `wordmark.yaml` against code defaults.
- Consequences: Effective defaults are centralized in code, and the sample repo config can no longer silently drift from the runtime baseline.

## 2026-03-08 - ADR-025: Hosted CI uses a required pure lane and a separate external-tools lane
- Status: accepted
- Context: The repo now has explicit pure-Python and external-tool validation lanes, but without hosted CI there is no always-on signal for contributors or pull requests.
- Decision: Add a required/default GitHub Actions workflow that runs `make test-pure` on Ubuntu across Python `3.11` and `3.12`, plus a separate hosted `external-tools` workflow (manual + nightly) that installs LibreOffice/UNO/rendering tools and runs `make test-external`.
- Consequences: Pull requests get a stable fast signal without forcing every contribution through heavyweight host-tool setup, while the integration lane remains visible and reproducible.

## 2026-03-08 - ADR-026: First `ooxml_engine` split is limited to review transforms
- Status: accepted
- Context: `ooxml_engine.py` is large enough to merit decomposition, but most of its text-localization and anchor logic is fidelity-sensitive and should not move until characterization coverage is stronger.
- Decision: Extract only the review-transform cluster (`accept`/`reject`, author filtering, unwrap logic, move-range cleanup) into an internal `ooxml_review` module while keeping `wordmark.ooxml_engine.review_action(...)` as the integration point used by the CLI.
- Consequences: The codebase gets a safer first decomposition slice with minimal behavior risk, and broader OOXML-engine breakup remains explicitly deferred.

## 2026-03-08 - ADR-027: External-tools CI should include one real Quarto-backed manuscript smoke build
- Status: accepted
- Context: The manuscript workflow had good characterization around mocked/default build behavior, but the hosted external-tools lane still did not exercise a real `.qmd` build path.
- Decision: Extend the external-tools CI lane to install Quarto and run at least one real `.qmd` smoke test through the `manuscript prepare` default build path.
- Consequences: The repo now validates one true end-to-end Quarto manuscript build in hosted CI without expanding the required pure-Python PR gate.

## 2026-03-08 - ADR-028: Second `ooxml_engine` split is limited to anchor resolution
- Status: accepted
- Context: After review transforms were extracted, the next safest concentration to reduce was anchor normalization/resolution because it is heavily used but more bounded than localized replacement logic.
- Decision: Extract anchor normalization and anchor resolution into an internal `ooxml_anchor` module, while keeping `AnchorResolutionError` and anchor-driven behavior accessible through `ooxml_engine`.
- Consequences: `ooxml_engine.py` shrinks further with limited behavior risk, while localized replacement and rewrite policy stay in place for later, more heavily characterized phases.

## 2026-03-08 - ADR-029: Add Ruff as the default lightweight lint gate
- Status: accepted
- Context: The repo had strong tests and CI but no fast static hygiene check for unused imports and similar maintenance issues.
- Decision: Add `ruff` as a dev dependency, expose `make lint`, and run it in hosted CI as part of the default PR signal.
- Consequences: Contributors get a fast, low-friction quality gate without introducing a heavy formatting or type-checking burden.

## 2026-03-08 - ADR-030: Make manuscript safe-apply source-aware when anchors are available
- Status: accepted
- Context: The manuscript workflow previously relied mostly on exact-match replacement, which was safe but underused available source context from GitHub line anchors and anchored review notes.
- Decision: When file/line anchors match the current source file, synthesize proposals against the anchored line slice rather than against global text only; keep exact-match fallback for unanchored inputs and continue marking unresolved duplicates as ambiguous.
- Consequences: Safe apply is more source-aware without pretending DOCX feedback can be losslessly mapped back to source; ambiguous global replacements remain conservative.

## 2026-03-08 - ADR-031: Third `ooxml_engine` split is limited to localized replacement logic
- Status: accepted
- Context: After review transforms and anchor resolution were extracted, the largest remaining concentration inside `ooxml_engine.py` was the localized replacement/rewrite subsystem.
- Decision: Extract localized replacement helpers and paragraph rewrite logic into an internal `ooxml_replace` module, while keeping `ooxml_engine` as the public integration point used by CLI callers.
- Consequences: `ooxml_engine.py` is further reduced without changing user-facing contracts, but localized replacement remains the highest-fidelity-risk OOXML area and still requires characterization-first changes.

## 2026-03-08 - ADR-032: Add a conservative pure-lane coverage floor in CI
- Status: accepted
- Context: The repo had coverage reporting but no automated floor, leaving room for unnoticed regressions in test breadth.
- Decision: Add `make test-pure-cov` with `pytest-cov` fail-under `80`, and use that in the hosted pure-Python CI lane.
- Consequences: Coverage regressions in the required PR lane are now bounded, while the floor remains conservative enough not to create frequent noise during ongoing hardening work.
