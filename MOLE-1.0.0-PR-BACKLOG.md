# MOLE 1.0.0 — Implementation Backlog

> **Рабочий список для Codex / GitHub PR.** Нормативный источник подробных требований — [MOLE-1.0.0-IMPLEMENTATION-PLAN.md](MOLE-1.0.0-IMPLEMENTATION-PLAN.md). Не реализовывать все пункты одним PR. Каждая задача считается выполненной только после тестов, ревью и проверки Definition of Done.

## Неподвижные договорённости

- Public skill: `mole`; internal Python engine: `molekit`; рабочие данные: `.mole/`.
- Self-contained payload: `skills/mole/{SKILL.md,scripts/,molekit/,schemas/,references/,assets/}`.
- `python3` 3.11+, stdlib-only core; **без установки Engine через PyPI/uv и без MCP**.
- Engine владеет state machine, schema, evidence, validation, exports; агент делает bounded semantic reasoning.
- Markdown — обязательный вывод; HTML — offline single-file, `.drawio` — Confluence-ready; Mermaid — optional.
- No target-code execution, no runtime network, no auto publication/installation.
- Все material claims — с evidence или явной inferred/unknown границей.

## Delivery waves

| Wave | PRs | Контрольная демонстрация |
|---|---|---|
| A. Foundation | 01–06 | Skill запускает Engine и обрабатывает source-backed LLM task loop |
| B. Knowledge & Explorer | 07–10 | Документы + HTML из одной SKM; изменения и editing стабильны |
| C. Interop & updates | 11–12 | `.drawio`, Mermaid, changes/diff, сохранение заметок |
| D. Release quality | 13–14 | Изолированная установка и full end-to-end, release tag `1.0.0` |

## PR-01 — Packaging / self-contained skill

**Зависимости:** нет.

- [ ] Создать `skills/mole/SKILL.md`, `agents/openai.yaml`, `scripts/mole.py`.
- [ ] Добавить stdlib Python package `skills/mole/molekit/` с CLI skeleton.
- [ ] Реализовать `doctor --json`, version, `--help`.
- [ ] Поставить license, project README, `.gitignore`, first CI.
- [ ] Тест: скопировать **только** `skills/mole/` во временный каталог и выполнить `doctor` без сети.

**Acceptance:** установка одного скилла работает без отдельного Engine/PyPI/Node/MCP.

## PR-02 — CLI protocol / workspace / state

**Зависимости:** PR-01.

- [ ] Оболочка JSON: version, ok, status, errors, next action.
- [ ] Команды `start`, `next`, `inspect`, `submit`, `status`, `finish` с настоящим state storage.
- [ ] Workspace manifest, atomic writes, locks, resume and idempotency.
- [ ] Enum `NEW`, `SCANNING`, `EXTRACTING`, `TRACING`, `NEEDS_ANALYSIS`, `VALIDATING`, `EXPORTING`, `COMPLETED`, `PARTIAL`, `BLOCKED`, `FAILED`, `STALE`.
- [ ] Тесты invalid transitions, interruption, duplicate submit, corrupt state, permissions.

**Acceptance:** повторяемое управление сессией без участия LLM/запуска сервиса.

## PR-03 — SKM / evidence / JSON Schema

**Зависимости:** PR-02.

- [ ] `Source`, `Evidence`, `Claim`, `Symbol`, `Operation`, `Relationship`, `Scenario`, `BusinessStep`, `DiagramView`, `Override`, `Revision`, `QualityFinding`.
- [ ] Separate `source_observed`, `runtime_verified`, `documented_intent`, `inferred`, `unknown`, `contradicted`.
- [ ] Versioned JSON Schemas для knowledge model, tasks, patches, CLI.
- [ ] Validators: dangling IDs, missing provenance, wrong status, invalid type, inconsistent revision.
- [ ] Valid/invalid golden models.

**Acceptance:** raw static edge никогда автоматически не становится proven runtime edge.

## PR-04 — Python scanner / index / cache

**Зависимости:** PR-03.

- [ ] Safe directory traversal; ignored secrets, binary, symlinks, huge files.
- [ ] Repo revision/hash; source lines; symbol index; AST parser.
- [ ] Imports, call sites, decorators, async/branches/exceptions; candidate relationships.
- [ ] Incremental cache по hash и версии parser.
- [ ] Unsupported Python grammar → structured limitation, not silent data loss.
- [ ] Tests no target-code execution/no network.

**Acceptance:** реальные code refs, branch candidates и повторное сканирование без анализа неизменённых файлов.

## PR-05 — Framework adapters / traces

**Зависимости:** PR-04.

- [ ] FastAPI/Starlette routers + dependencies + middleware candidates.
- [ ] Django URL/view/ORM/transactions.
- [ ] SQLAlchemy DB writes/reads and transaction boundaries.
- [ ] Async background tasks, cancellation/timeouts.
- [ ] RabbitMQ/Kafka publish/consume patterns; never invent delivery guarantees.
- [ ] Forward/backward traversal and failure paths, `unresolved` queue.

**Acceptance:** representative FastAPI/Django/consumer fixtures pass; `possible` edge != `observed_runtime`.

## PR-06 — Bounded agent protocol

**Зависимости:** PR-05.

- [ ] `next` prioritizes meaningful unknowns; compact JSON output.
- [ ] `inspect` returns paginated, source-located evidence within budget.
- [ ] `submit` validates patch schema, task linkage, revision, evidence IDs; merges safely.
- [ ] Agent protocol references and concise `SKILL.md` workflow.
- [ ] Tests small/large context, double submit, stale evidence, blocked, partial.

**Acceptance:** agent can complete one real task loop by shell + JSON, without manually reading entire repository.

## PR-07 — Semantic knowledge / Markdown

**Зависимости:** PR-06.

- [ ] Scenario grouping, business mapping, glossary, unknowns.
- [ ] Markdown compiler: root README, architecture, process docs, quality report.
- [ ] Source-backed links with revision and status.
- [ ] Manual sections + merge conflict reporting.
- [ ] Cross-reference validation docs↔SKM↔diagram IDs.

**Acceptance:** output docs independently explain success/failure paths and preserve manual notes on second run.

## PR-08 — HTML Explorer renderer

**Зависимости:** PR-07.

- [ ] One data-driven SVG/DOM renderer; inlined CSS/JS/model, fully offline.
- [ ] Tree, selected explanation, glossary, source evidence, nested/shared diagrams.
- [ ] Single-click selects, double-click drills, leaf inert, Back follows actual route.
- [ ] Shortcuts/ARIA, safe user strings, no hardcoded scenario names/layout IDs.
- [ ] Test three different SKM fixtures with unchanged renderer.

**Acceptance:** one self-contained HTML opens via `file://` without CDN/API/server.

## PR-09 — Layout / zoom / responsiveness

**Зависимости:** PR-08.

- [ ] Bundled offline layout or proven fallback; labels and connector geometry.
- [ ] Fit=100%, +/- zoom, local scroll, drag-pan, touch behavior.
- [ ] 390/600/768/1280/1920 px screenshots and geometry assertions.
- [ ] Keyboard navigation and focus states.
- [ ] No `document.body` horizontal overflow from diagram.

**Acceptance:** original example's narrow-viewport issue absent; no known critical clipping/overlap failures in golden fixtures.

## PR-10 — Text editing / overrides / regeneration

**Зависимости:** PR-08, PR-09.

- [ ] Node/edge/glossary labels, descriptions and notes editable via double click.
- [ ] Field-level localStorage override format with base hash, schema, artifact ID.
- [ ] Compatible revisions retain edits; conflicts visible.
- [ ] Malformed/blocked storage graceful handling.
- [ ] XSS and safe-link injection tests.

**Acceptance:** editing/reload/regen works and doesn't corrupt generated model.

## PR-11 — draw.io / Mermaid / Confluence guide

**Зависимости:** PR-07; preferably PR-08/09 done.

- [ ] `.drawio` multipage XML; stable shape IDs, arrow labels, internal links, layers when useful.
- [ ] XML/XSD validation and diagrams.net editor round-trip.
- [ ] Mermaid optional and documented loss report.
- [ ] iFrame guide + Confluence Cloud draw.io settings/requirements.
- [ ] Actual Confluence app smoke if test tenant exists, otherwise **NOT_RUN**.

**Acceptance:** local `.drawio` opens and navigates, no false claims of Confluence deployment.

## PR-12 — Change detection / incremental regeneration

**Зависимости:** PR-07, PR-10, PR-11.

- [ ] `diff` / `update` CLI, changed-file invalidation, affected scenario detection.
- [ ] Reuse unaffected semantic patches; reject stale evidence.
- [ ] Preserve or report conflicts on generated and manual sections.
- [ ] Change-report: added/removed/changed flows, sources and unknowns.
- [ ] Resume and crash recovery after diff.

**Acceptance:** fixture v1→v2 changes correct docs and diagrams while preserving manual text.

## PR-13 — Security, evals, portability

**Зависимости:** PR-01–12.

- [ ] End-to-end benchmark vs LLM-led baseline on same quality criteria.
- [ ] Agent eval on light/medium/strong models when available.
- [ ] Secret/redaction, symlink, injection, path traversal, network denial tests.
- [ ] Clean-install test on macOS/Linux/Windows support matrix.
- [ ] Browser automated regression and offline tests.
- [ ] Third-party assets notices/licensing audit; usability and CLI docs.

**Acceptance:** all release gates pass; unknown or not-run items are accurately reported.

## PR-14 — Release 1.0.0

**Зависимости:** PR-13.

- [ ] Freeze schema v1 and CLI v1 contract.
- [ ] README, installation, quickstart, example outputs, known limitations.
- [ ] Apache-2.0, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md.
- [ ] Reproducible skill archive, version tag and release notes.
- [ ] Fresh-user E2E: install `mole` only, run, inspect Markdown + HTML + draw.io.

**Acceptance:** no P0/P1 blockers, release artifacts independently verifiable.

## Повторяемый шаблон отчёта исполнителя по каждому PR

```markdown
### PR-XX — <topic>
- Scope completed:
- Files changed:
- Design decisions / ADR alignment:
- Tests executed (commands + actual results):
- Tests not run (with reason):
- Risks / unsupported cases:
- Compatibility / data migration:
- Screenshot/artifact proof (where relevant):
- Follow-ups / blockers:
```

## Короткий prompt для запуска реализации

> Read `MOLE-1.0.0-IMPLEMENTATION-PLAN.md` and `MOLE-1.0.0-PR-BACKLOG.md`. Implement **PR-01 only**. Preserve all architectural decisions: public `mole` skill, bundled stdlib-only `molekit`, zero separate engine install, evidence-driven analysis, CLI JSON. Add tests, run them, and report actual outcomes. Do not proceed to PR-02 without review. Avoid placeholder features and hidden network/target execution.
