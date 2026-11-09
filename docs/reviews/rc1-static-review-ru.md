# MOLE 1.0.0rc1 — глубокое статическое ревью

**Дата:** 8 ноября 2026  
**Объект:** `mole-1.0.0rc1.zip`, 31 файл, `mole/`  
**Эталон:** `MOLE-1.0.0-IMPLEMENTATION-PLAN.md` и `MOLE-1.0.0-PR-BACKLOG.md`  
**Метод:** выборочное и сквозное чтение исходников, анализ контрактов, графа зависимостей модулей и соответствия ТЗ. **Тесты, CLI, анализатор, HTML и приложение не запускались.** Поэтому выводы о фактическом runtime-поведении — логические следствия кода, а не наблюдения успешного или неуспешного исполнения.

## 1. Решение по релизу

**Вердикт: NO-GO для публичной стабильной 1.0.0.** Хороший прототип инженерного ядра и безопасности, но пока недостаточно доказательств готовности и не выполнен главный продуктовый контракт: реконструкция сквозных процессов, бизнес-семантики и многоуровневых объясняющих диаграмм. Текущий результат скорее «source-backed Python symbol explorer», чем «workflow intelligence engine».

### Сильные стороны

- Совпадает принятая схема публичного `mole` и внутреннего `molekit`; поставка самодостаточна, Python stdlib, без PyPI/MCP/API-ключей (`SKILL.md`, `scripts/mole.py`, `molekit/cli.py`).
- CLI имеет машинную оболочку ошибок, фиксированные команды, устойчивое состояние и версионирование (`cli.py:35–125`, `pipeline.py:12–90`, `workspace.py:61–122`).
- Попытка честно различать *static candidate* и *verified runtime*, отдельные evidence/claims, структурная валидация (`model.py:85–113`, `references/evidence-policy.md`).
- Отсутствие выполнения проектного кода при сканировании; безопасное чтение с запретом symlinks, ограничениями на размеры и секреты (`safety.py`, `scanner.py:18–21,104–171`).
- Автономный, data-driven HTML; текст добавляется через `textContent`, JSON экранируется при inline embedding (`html.py:12–30`, `explorer.js:23–27,181–184`).
- Preflight для защиты сгенерированных блоков от ручного редактирования, журнал `pendingExport`, блокировка workspace (`markdown.py:114–151`, `pipeline.py:178–235`).
- Честная документация ограничений Confluence и различие локальной XML-проверки и проверки на настоящем tenant (`references/confluence-export.md`).

## 2. Критические продуктовые блокеры (P0)

### P0-01. Сквозные процессы нельзя надёжно описать одним semantic patch

**Код:** `molekit/agent.py:12–43,114–150`; `molekit/scanner.py:338–347`.

Задачи создаются практически *по каждому символу*, а `accept_patch` разрешает `scenarios[].operationIds` только среди операций, чьи evidence пересекаются с evidence *одной* задачи (`allowed_operations`, строки 130–140). При типовом сценарии `api.py:route → service.py:execute → repository.py:save → worker.py:consume` доказательства разделены по модулям и задачам. К тому же scanner строит candidate calls только в том же файле и при точном совпадении имён. Один сценарий не может корректно собрать всё это посредством поддерживаемого LLM API.

**Влияние:** ограничение контрактного API, не просто низкое качество диаграммы. LLM не сможет исправить его более сильной моделью, не нарушая протокол.

**Исправление:** ввести первоклассные `workflow candidates` и `workflow_review` задачи с доказательствами нескольких symbols/operations; иметь явный `scope` задачи (`workflow`, `component`, `symbol`), allowlist операций для целого workflow, инкрементальное дополнение сценариев и ссылки на родственные задачи. Отдельно развести technical trace и authored business scenario. `scenarioIds`/`claimIds` можно привязывать к нескольким задачам без нарушения lineage. Добавить golden fixture cross-file HTTP→DB→event→consumer.

### P0-02. Текущий компилятор не строит системные бизнес-workflows

**Код:** `molekit/knowledge.py:8–50,51–86`; `molekit/markdown.py:28–66`; `molekit/layout.py:7–39`.

`compose()` создаёт `Static trace` для *каждой функции* и кладёт в overview отдельный узел на каждую функцию; `overview.edgeIds` остаётся пустым, связей между верхнеуровневыми процессами нет. В `scenario.operationIds` входят исходная operation и связанные *operation* IDs, но scanner-отношения соединяют в основном *symbol* IDs. При просмотре Markdown операция-источник может оказаться единственным техническим шагом сценария, хотя SVG покажет ещё symbol nodes. Авторские сценарии добавляются после автоматических, а не становятся основными организующими сущностями.

**Влияние:** на обычном сервисе обзор превращается в каталог символов и разрозненные call traces, а не объяснение «что делает система». Не выполняет ключевые требования ТЗ: actors/triggers/preconditions, ordered happy path, decisions, branch outcomes, failures/retries, side effects, business mapping.

**Исправление:** компилятор строит `System → Business workflows → Technical subprocesses → Low-level trace`; краткий overview только из агрегированных workflow-компонентов, не всех функций. Для каждого этапа есть порядок/варианты/ошибки и переходы с источниками. Markdown генерируется с нумерованными шагами, data flow, альтернативными ветвями и разделами неизвестного. Пустая бизнес-семантика явно маркируется, а не заполняется списком методов.

### P0-03. В предоставленном RC нет доказательной основы для маркировки 1.0.0

**Архив:** 31 файл, не содержит `tests/`, fixture repos, браузерных тестов, CI workflows, README для первого запуска/примера результата. Это описание **конкретного архива**; тесты могут находиться вне него, поэтому мы не утверждаем, что в GitHub их нет.

**Влияние:** невозможно подтвердить требования PR-13/14, совместимость с чистой установкой, crash/resume, безопасность, реальные `.drawio` и UX. Отдельно пользователь попросил **не запускать тесты**, и мы их не запускали.

**Исправление:** собрать воспроизводимый repo/CI с unit+integration+browser+security fixtures и evals, документировать фактически исполненные проверки; без положительных результатов release sign-off запрещён.

## 3. Существенные инженерные замечания (P1)

### P1-01. Call graph почти не работает между модулями и методами

**Код:** `scanner.py:174–180,209–229,338–347`.

Резолвинг смотрит только `p == path` и `name == call["target"]`; `self.method`, `Class.method`, алиасы импортов, `from module import helper`, dependency injection и вызовы из соседних файлов не превращаются в отношения. `unresolved` собираются, но не превращаются в отдельные высокоприоритетные межмодульные workflow-задачи. Решение: module/symbol table, alias resolution, methods/self/cls, re-exports, adapters, явно типизированные unresolved edges.

### P1-02. Branch/failure analysis почти не моделирует альтернативные пути

**Код:** `scanner.py:225–229,348–349`; `adapters.py:77–81`; `knowledge.py:34–39`.

Для `If/Try/Raise/Await` фиксируются лишь границы; нет условия, true/false, исключения→catch, rollback, retry, finally, side effect order, wait/cancel. `trace()` возвращает связный граф символов, не control-flow graph. Для серьёзной workflow-документации необходимо первое приближение CFG и структурированных side-effect/failure edges с explicit uncertainty.

### P1-03. Слишком грубые framework-adapters и false positives

**Код:** `adapters.py:19–23,43–81`.

Наличие `sqlalchemy`/`django` в imports файла приводит к трактовке любой функции `.add()`, `.save()`, `.create()` как `db_write` кандидата; `.execute()` — `db_read`, хотя это может быть write. FastAPI decorators определяются по хвостовому имени, без подтверждения владельца/router include graph. Async/Rabbit/Kafka также основаны на именах. Формально статическая неопределённость обозначена, но семантические названия вида `db_write` остаются слишком уверенными. Нужны typed confidence/source patterns и adapters с ограниченными alias/type-aware эвристиками.

### P1-04. LLM-task queue ориентирована на объём кода, не на значимость поведения

**Код:** `agent.py:12–43`; `references/agent-protocol.md:38–42`.

До 20/100/500 задач по символам, сортировка только `critical` и hash ID. Не видно отбора entrypoint-centric workflows, группировки повторов, critical unknowns, зависимостей между задачами или покрытия выбранного scope. В большой кодовой базе лимит просто отрезает остальное. Нужны workflow-level приоритизация, clustering, explicit coverage metrics и task budget на *сценарии*, а не отдельные функции.

### P1-05. `COMPLETED` не гарантирует семантическую готовность

**Код:** `pipeline.py:158–168,229–234`; `agent.py:114–117`; `model.py:85–95`.

Статус полной готовности зависит от `pending` и `scan.limitations`, но не от полноты подтверждённых success/failure paths, meaningful business mapping, unknown/contradicted claims или критичных unresolved dependencies. Патч с одной `unknown` claim удовлетворит задачу, даже если ключевые бизнес-сценарии не восстановлены. Лучше separate `technical_analysis_complete`, `semantic_coverage`, `export_success` + release thresholds и PARTIAL при критических неизвестных.

### P1-06. Проверка evidence не доказывает семантическую истинность claim

**Код:** `agent.py:119–156`; `model.py:85–95`.

Проверяются ID, формат, категория источника и наличие ограничений; не проверяется, подтверждает ли указанный фрагмент именно statement. Это нормальное фундаментальное ограничение скриптов, но его надо компенсировать механизмом contradiction/review, особенно для заявлений о транзакциях и гарантиях доставки, и не представлять structural validator как semantic verifier.

### P1-07. При изменении любого участка файла инвалидируются все его source/evidence IDs

**Код:** `scanner.py:259,265–275`; `update.py:143–177`.

`source_id` содержит `record["hash"]` (хэш **всего файла**). Даже добавление не связанного комментария делает хэш других spans новым, из-за чего claims, привязанные к ним, признаются устаревшими. Это безопасно с точки зрения ложного reuse, но сильно снижает обещанную экономию токенов и инкрементальность.

**Исправление:** отделить стабильную identity source span от content hash, хранить content fingerprints и структурные anchors, делать exact-match/span-aware reconciliation с консервативной инвалидацией только затронутых утверждений.

### P1-08. `diff/update` может принять неполную инвентаризацию за реальное удаление

**Код:** `scanner.py:118–120,131–157`; `update.py:14–33,133–158`.

`inventory()` возвращает `limitations` (включая time/size/file budget), но `changes()` игнорирует второй элемент `(records, _)`. Поэтому если повторная инвентаризация прервалась по бюджету/доступности, отсутствующие records могут быть классифицированы как `removed`, а их claims инвалидированы. Должен быть fail-closed: completeness marker, неполная diff помечается `UNKNOWN`/`PARTIAL`, destructive invalidation при incomplete inventory запрещена.

### P1-09. Некоммитный multi-file export и неоднозначность stale outputs

**Код:** `pipeline.py:178–235`; `markdown.py:99–151`.

Есть preflight, атомарная замена *каждого* файла и журнал восстановления — это хороший старт. Но публикация **всего пакета** не атомарна: после сбоя часть файлов может относиться к новой ревизии, другая к старой. Параллельные независимые workspaces могут экспортировать в один `output` без output-level lock. Файлы, не входящие в новый набор форматов (`explorer.html`, drawio, glossary), могут остаться на диске как устаревшие без отдельного manifest/retirement отчёта. Нужен stage directory + manifest + atomic publish стратегии, output lock и явная invalidation/retirement политика.

### P1-10. Layout не отражает причинно-следственную топологию

**Код:** `layout.py:13–39`, `explorer.js:134–156`.

Сетка из максимум четырёх колонок и одна отдельная горизонтальная lane для *каждой* связи означает значительное пустое поле сверху (`top = 40 + E*24`), много crossing/backtracking, плохое масштабирование. Нет иерархического раскладывания по зависимости, группировки, edge routing с обходом узлов. Лучше bundled DAG layout с SCC/cycles и отдельными failure lanes; для сложных графов предварительная кластеризация и ограничение числа элементов в view.

### P1-11. `draw.io` валидация структурная, а не совместимость с viewer

**Код:** `drawio.py:9–46,49–78`; `references/confluence-export.md`.

Экспортирует multipage XML и internal `data:page/id` ссылки, но проверяет их собственным ElementTree validator; реальные импорт, click navigation, tooltip и edit в diagrams.net/Confluence не доказаны. Отсутствуют необязательные, но запланированные слои. Релизу нужен diagrams.net editor round-trip и реальная проверка Confluence (либо честный NOT_RUN и ограниченное заявление совместимости).

### P1-12. Контекстные бюджеты и объем workspace

**Код:** `agent.py:56–111`; `workspace.py:12,61–67`; `scanner.py:21,104–171,252–354`.

Хотя `inspect` paginated и bounded, операция `operations` передаётся только на первой странице и при обрезании нельзя получить оставшиеся через cursor; `operationsTruncated` не имеет отдельной пагинации. Полный scan/model/cache сериализуются внутри `state.json` с лимитом 16 MiB; типичный крупный монорепозиторий может упереться в этот предел несмотря на лимит input 64 MiB. Нужны отдельные файлы/index tables и paging для всех коллекций.

### P1-13. Квадратичная стоимость построения задач и представлений

**Код:** `agent.py:16–23`; `knowledge.py:19–49`; `adapters.py:88–108`; `pipeline.py:184–205`.

Для каждого symbol генератор задач снова обходит **всю** evidence collection и relationships. Компилятор для каждой функции запускает `trace()`, а внутри `trace` для каждого посещённого узла заново фильтрует все relationships. Это может вести к росту затрат порядка `O(S × E)` или хуже на реальных репозиториях, а также к тысячам отдельных view в итоговом HTML. Бюджеты scanner по исходным файлам не гарантируют бюджет по количеству symbols/edges/tasks/views. Нужны индекс `evidenceBySource`, `adjacencyMap`, `operationsByName`, отдельный лимит generated views и измерения скорости на fixtures 10K/50K symbols.

## 4. Улучшения второго приоритета (P2)

1. **Готовность для пользователя.** В представленном архиве нет README/quickstart/guide с реальным примером вывода, `.gitignore`, CI или release provenance. Проверить за пределами архива, если они живут только в корне репозитория.
2. **`file://` и localStorage.** `assets/explorer/overrides.js:17–29,51–65` корректно переживает storage error, но между браузерами persistence для локальных файлов не гарантируется; нужен экспорт/импорт JSON пользовательских правок или отдельная опция переносимых заметок.
3. **Конфликты browser edits.** `overrides.js:31–38` сохраняет старое значение и выводит предупреждение, но интерфейса просмотра `old/new`, решения конфликта, переноса заметки в canonical MD нет.
4. **UX navigation.** `explorer.js:29–34,86–103` основан на первой схеме и её `childRefs`; типовой `compose()` строит только обзор и один уровень дочерних видов; план требовал неограниченную вложенность и shared subprocess routes.
5. **Нет явной архитектуры компонентов.** `markdown.py:70–73` выводит список объявлений, а не систему сервисов/хранилищ/интеграций, отсутствуют ссылки между source/diagram/Markdown на уровне узла/операции.
6. **Неполное поведение ошибок.** `cli.py:26–32` помечает все ошибки `recoverable: true`, включая неподдерживаемый runtime и логически неисправимые запросы; общая ошибка `INTERNAL_ERROR` скрывает диагностический ID. Безопасно не раскрывать traceback агенту, но нужен локальный диагностический log/trace ID.
7. **Масштабирование и доступность Explorer.** По коду есть keyboard/ARIA/ResizeObserver и DOM-safe strings, но нет гарантированной WCAG проверки, сценариев touch и screenshot/geometry CI. `zoom-label` показывает относительный коэффициент, а реальный fit может быть значительно меньше 100%.
8. **Нет отчёта о потере семантики экспортом.** Mermaid явно объявлен lossy; для draw.io тоже стоит формировать machine-readable loss manifest (например, browser notes, claim provenance, details drawer).
9. **Мультиязычность.** Python 3.11+ parser не разбирает Python 2.7/Django legacy и синтаксис новее текущего хоста; регистрирует limitation, что честно, но полезен opt-in fallback parser или tree-sitter optional.
10. **Версионирование/обратная совместимость.** Нужны migration tests для `schemaVersion` и CLI/format versions, прежде чем обеспечивать cross-release reuse старого workspace.

## 5. Предлагаемые обязательные правки до RC2

### PR-RC-01 — Flow graph foundation (P0)
- Разделить `AST symbol inventory`, `call graph candidates`, `control/data-flow evidence`, `workflow candidates`.
- Разрешить межфайловые ссылки, `self/cls`, imports, FastAPI routers/Django URLs и broker producer/consumer boundaries, с маркировкой confidence/unknown.
- Добавить workflow-review task, который может ссылаться на evidence/operations из нескольких модулей.
- **Acceptance:** fixture `HTTP → service → transaction → publish → consumer` даёт один связный workflow с подтверждёнными и неизвестными границами; ни один static edge не назван runtime verified.

### PR-RC-02 — Семантика и качественные документы (P0)
- Workflow-first overview; nested technical views; outcomes, branches, alternative paths, failures, actors, triggers, state changes.
- Отдельные разделы business vs technical; source evidence per step, допущения и coverage.
- Удалить «одна схема на каждую функцию» из дефолтного overview, оставить `symbol view` как drill-down/debug.
- **Acceptance:** независимый читатель может объяснить основные end-to-end сценарии по одному Markdown, не открывая код.

### PR-RC-03 — Integrity, update, release semantics (P1)
- `COMPLETED` зависит от явных coverage/critical unknown gates; иначе `PARTIAL`.
- Diff/update fail closed при incomplete inventory; span-granular identity/reuse.
- Манифест поколений output, output lock, stage/publish и удаление/retirement старых managed outputs.
- **Acceptance:** безопасная повторная генерация, crash/recovery, invalidation и пользовательские блоки проходят fixture checks.

### PR-RC-04 — Diagram UX + Confluence acceptance (P1)
- Hierarchical semantic layout, кластеризация по сценариям, edge routing, labels, навигация уровнями; browser keyboard/touch/resize.
- diagrams.net roundtrip и internal page link tests; Confluence tenant — `PASS` или `NOT_RUN`.
- Browser notes export/import; collision/conflict resolution.
- **Acceptance:** 390px–1920px, 30–80 nodes fixture, shared subprocess, graph cycles, leaf navigation; никакого overflow страницы или блокирующей потери содержимого.

### PR-RC-05 — Engineering evidence and release packaging (P0)
- Tests/fixtures/CI, security eval, portability, clean-skill install, documented dependency/version policy.
- README, quickstart, example output, troubleshooting, CONTRIBUTING, SECURITY, CHANGELOG, LICENSE, release manifest.
- Blind eval лёгкой/сильной LLM и сравнение с baseline по качеству (а не только токенам).
- **Acceptance:** результаты проверок записаны, P0/P1 закрыты, стабильная 1.0.0 не зависит от несуществующих заявленных тестов.

## 6. Конкретные критерии Go / No-Go

**GO на RC2:** P0-01/P0-02 устранены, есть исполняемые fixtures и тестовая инфраструктура; протокол сохраняет backwards-compatible migration либо явно versioned schema.

**GO на stable 1.0.0:** минимум один полностью связный реальный Python backend workflow, правильная failure/unknown модель, проверяемая Markdown-документация, пригодная для работы HTML-диаграмма, структурный draw.io и задокументированный статус Confluence, успешные повторный анализ и сохранение заметок; все заявленные тесты фактически прогнаны и их результаты опубликованы.

**NO-GO:** ложные существенные claims, структурная невозможность cross-file workflow, silent data loss/update, известная критическая проблема с безопасностью, отсутствие тестовых подтверждений и внешних пользовательских инструкций.

## 7. Позиция по продукту

В release candidate действительно видна собственная инженерная работа, а не одноразовый промпт: стабильная модель сущностей, API, локальный offline runtime и вложенный renderer. Главный риск сейчас — **перекос в инфраструктурную добротность при недостаточной глубине workflow intelligence**. Не следует добавлять ещё один framework или новый экспортный формат, пока не исправлена цепочка `source → flow → business meaning → connected diagram → Markdown`.

**Стратегический вывод:** не переписывать проект заново. Оставить CLI/workspace/security/serialization, переработать workflow reconstruction/semantic task scope/knowledge compilation, затем закрыть тесты и release gates. Это относительно управляемое изменение архитектуры, но оно критично для соответствия изначальной идее MOLE.
