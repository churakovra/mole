# MOLE 1.0.0 — окончательный план реализации

> **MOLE** — **M**apping **O**perations, **L**ogic & **E**vidence  
> **Tagline:** *Follow the code. Find the why.*  
> **Релиз:** `1.0.0` (проектное ТЗ, не выпущенная версия)  
> **Дата согласования:** 2026-11-08  
> **Статус:** *Implementation-ready architecture & backlog*  
> **Исходные материалы:** `workflow-diagram-explorer(1).zip`, планы `Workflow Diagram Explorer 2.0 / 2.1`, согласования в беседе.  
> **Назначение документа:** единый нормативный источник для реализации, ревью и приёмки MOLE 1.0.0.

---

## 0. Executive decision: что строим

**MOLE** — устанавливаемый целиком **Agent Skill** с `name: mole`. Пользователь обращается к нему через `$mole` в Codex или соответствующий механизм другого совместимого агента. **MoleKit** (`molekit`) — входящий в состав скилла **локальный Python-движок**, а не обязательный пакет из PyPI, постоянно работающий сервис или MCP-сервер.

**Архитектурная формула: `script-first · LLM-guided · evidence-driven`.**

- **Движок** делает всё, что можно выполнять механически и воспроизводимо: обнаруживает структуру репозитория, индексирует исходники, извлекает потенциальные зависимости и события, организует поисковые задачи, хранит доказательства и состояние, проверяет модель знаний, строит документацию и диаграммы, отслеживает обновления.
- **LLM** отвечает за смысл и сложные неоднозначности: определяет реальные сценарии, бизнес-назначение, важные границы процессов, смысл ветвлений, объяснения и ограничения; добавляет строго структурированные **semantic patches**, а не переписывает найденные факты и не генерирует HTML вручную.
- **Skill** содержит короткий протокол для агента: запуск Engine, последовательное получение задач, прицельный анализ, отправка результатов, завершение; не дублирует логику Engine.
- **Единый System Knowledge Model (SKM)** служит источником для Markdown, интерактивного HTML, `.drawio`, Mermaid и отчёта о качестве.
- **Никакого отдельного Engine Setup**: пользователь устанавливает только каталог скилла; для базовой версии на машине должен быть совместимый `python3`, а все пользовательские артефакты открываются без MoleKit.

### 0.1 Критически важные разграничения

1. **Установка скилла ≠ установка Python-пакета**: исходники Engine поставляются в каталоге скилла, не требуется `pip install`, `uv sync`, отдельный CLI в PATH, Node.js, API-key, Docker или MCP.
2. **Скрипты не заменяют модель полностью**: Python AST обнаруживает возможные вызовы, но не доказывает runtime-поведение и не умеет сам достоверно интерпретировать бизнес-смысл.
3. **Структурная проверка ≠ доказательство истинности**: наличие file/line и корректного JSON не означает, что семантический вывод верен. Надёжность обеспечивается evidence lineage, моделированием неопределённостей и целевыми evals.
4. **Документация — обязательный продукт**, а не пояснение к картинке; HTML — интерактивный навигатор по тому же знанию.
5. **Конкретная модель не является зависимостью продукта**: качество LLM-рассуждений различается, но Engine, CLI, schema, экспорт и проверки должны быть одинаковыми для всех агентов с shell-доступом.
6. **Confluence не является обязательной инфраструктурой**: `.drawio` экспортируется локально; публикация или Forge-интеграция не запускаются без разрешения пользователя.
7. **1.0.0 означает стабильно работающий заявленный scope**, а не поддержку всех языков и доказательство каждого runtime-пути любого репозитория.

---

## 1. Зафиксированные продуктовые решения (ADR)

| ID | Решение | Обоснование |
|---|---|---|
| D-01 | User-facing skill: **`mole`**; `SKILL.md` содержит `name: mole` | Короткая, узнаваемая команда вызова |
| D-02 | Bundled Engine: Python namespace **`molekit`** | Независимый тестируемый код, спрятанный от пользователя |
| D-03 | GitHub-repo: **`mole`**, рабочий кандидат | Совпадает с брендом; перед созданием проверить доступность и конфликтность имени |
| D-04 | Project/workspace state: **`.mole/`** | Прозрачное, предсказуемое расположение индексов и ревизий |
| D-05 | License: **Apache-2.0**, проверить лицензии включённых assets | Permissive OSS с явно оговорённым патентным предоставлением |
| D-06 | Distribution: один **self-contained Agent Skill** | Установка одним действием; не нужно отдельно ставить Engine |
| D-07 | Runtime core: **Python 3.11+**, stdlib-only | Практичный минимум зависимостей для первой версии |
| D-08 | Shell + CLI + JSON + files | Работает в Codex без MCP и без прямого LLM API |
| D-09 | Engine owns state machine and validation | LLM не определяет порядок пайплайна и готовность по памяти |
| D-10 | Engine создаёт raw facts, agent — bounded semantic patches | Экономия контекста, стабильная evidence-модель |
| D-11 | Versioned **SKM** с provenance, types и stable IDs | Одинаковый смысл в документации и во всех визуализациях |
| D-12 | Markdown **всегда** в базовом результате | Работает как самостоятельная документация |
| D-13 | Автономный **single-file HTML** по умолчанию | Portable, открывается через `file://`, без сервера/CDN |
| D-14 | `.drawio` exporter для Confluence | Интерактивные страницы и ссылки при наличии draw.io app |
| D-15 | Mermaid — дополнительный, явно lossy export | Git-friendly представление, не полная замена HTML |
| D-16 | Редактирование HTML через field-level overrides | Сохранение совместимых ручных правок при регенерации |
| D-17 | `quick` / `standard` / `deep` | Управление стоимостью анализа и уровнем полноты |
| D-18 | Static analysis by default; no target-code execution | Безопасное исследование незнакомого исходного кода |
| D-19 | Confluence Forge и SaaS/MCP — **после 1.0.0** | Не усложнять распространение скилла |
| D-20 | PyPI **не требуется** для 1.0.0 | Отдельный канал распространения не даёт пользы основному сценарию |
| D-21 | Model neutral: no vendor-specific structured output requirement | CLI/JSON работает через разные shell-enabled агенты |
| D-22 | Поддержка non-code domain без AST через agent-assisted evidence | Сохранить полезное назначение исходного skill; явно обозначить меньшую автоматизацию |

**Релизный компромисс:** делаем глубокий Python-first анализ, а не иллюзию универсальной статической точности на всех языках. Framework adapters активны только при распознавании соответствующей технологии. Для неподдерживаемого языка Engine строит inventory/textual references, возвращает `reduced_coverage`, а агент исследует релевантные места отдельно.

---

## 2. Требования к пользователю и пользовательский опыт

### 2.1 Основные сценарии

**UC-01. Объяснить систему целиком.**  
`$mole Исследуй репозиторий, расскажи как он работает и нарисуй основные процессы.`  
Результат: карта архитектуры, glossary, отдельные Markdown-документы по существенным процессам, HTML explorer, quality summary.

**UC-02. Объяснить конкретный путь.**  
`$mole Как проходит POST /notifications от HTTP до доставки, включая ошибки и ретраи?`  
Результат: ограниченный scope, сквозной trace, failure paths, источники и детали.

**UC-03. Бизнес-объяснение для команды.**  
`$mole Объясни процесс оплаты нетехнической аудитории, приложи технические доказательства.`  
Результат: бизнес-слой и технический слой одной модели, без придуманных ролей/SLA.

**UC-04. Обновить документацию после изменений.**  
`$mole Обнови существующие схемы и заметки после последних изменений в коде.`  
Результат: инкрементальный анализ, изменённые claims/flows, обновлённые материалы, сохранение ручных правок и конфликтный отчёт.

**UC-05. Для Confluence.**  
`$mole Подготовь интерактивную диаграмму для страницы Confluence.`  
Результат: `.drawio`, инструкция импорта/макроса и перечень функций, которые не переносимы из HTML; публикация только по отдельному запросу.

**UC-06. Отдельный технический документ.**  
`$mole Составь Markdown-разбор сервиса без диаграммы.`  
MOLE уважает явный запрос на формат; внутренняя SKM может строиться, HTML не навязывается.

**UC-07. Не-кодовый источник.**  
По предоставленным design docs, ADR или текстовому описанию agent-assisted evidence pipeline строит процессы/диаграммы, но не претендует на source-code call graph.

### 2.2 Набор режимов

| Режим | Что делает Engine | Что делает LLM | Ограничение |
|---|---|---|---|
| `quick` | Inventory + основные entry points + короткий trace | Понятные краткие выводы | Частичные branches помечены |
| `standard` (**default**) | Python AST + framework adapters + critical branches + validation | Business/technical interpretation; критические неоднозначности | Баланс качества и контекста |
| `deep` | Расширенные forward/backward traces, failure modes, state transitions, dependency review | Дополнительные проверки, противоречия, варианты, evidence boundaries | Больший расход контекста; не гарантирует runtime truth |

### 2.3 Принцип *no surprise*

- Не выполнять `pip install`, `npm install`, `uv`, код исследуемого проекта, тесты и миграции автоматически.
- Не отправлять исходники за пределы агента/локального окружения и не публиковать страницу в Confluence без авторизации пользователя.
- Не изменять исследуемые исходники: допустимо создать документацию и `.mole/` при явном запросе на генерацию; для read-only анализа указывать внешний `--workspace`.
- Не задавать вопросы, на которые можно разумно ответить через код и scope; когда граница неясна, выбрать минимально безопасный scope и сообщить допущение.
- Если не удалось выполнить проверку, показывать `NOT_RUN`, не `PASS`.

---

## 3. Целевая структура репозитория и поставки

Каноническая структура **monorepo**, в которой **весь runtime-необходимый payload находится внутри `skills/mole/`**. Установщик, копирующий только эту директорию, не ломает скилл.

```text
mole/                                  # GitHub repository
├── README.md
├── LICENSE                            # Apache-2.0
├── NOTICE                             # при необходимости: third-party license notices
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── .github/
│   └── workflows/
│       ├── quality.yml
│       └── release.yml
├── skills/
│   └── mole/                           # = installable Agent Skill, self-contained
│       ├── SKILL.md                    # name: mole
│       ├── agents/
│       │   └── openai.yaml
│       ├── scripts/
│       │   └── mole.py                 # thin executable stdlib wrapper
│       ├── molekit/                    # bundled Python Engine
│       │   ├── __init__.py
│       │   ├── cli.py                  # argument parsing, JSON output, errors
│       │   ├── config.py
│       │   ├── workspace.py
│       │   ├── pipeline.py             # persistent state machine
│       │   ├── index/
│       │   │   ├── repository.py
│       │   │   ├── python_ast.py
│       │   │   ├── symbols.py
│       │   │   └── cache.py
│       │   ├── adapters/
│       │   │   ├── fastapi.py
│       │   │   ├── django.py
│       │   │   ├── sqlalchemy.py
│       │   │   ├── messaging.py
│       │   │   └── async_python.py
│       │   ├── graph/
│       │   │   ├── model.py
│       │   │   ├── trace.py
│       │   │   ├── normalize.py
│       │   │   └── layout_fallback.py
│       │   ├── knowledge/
│       │   │   ├── schema.py
│       │   │   ├── claims.py
│       │   │   ├── evidence.py
│       │   │   ├── semantic_patch.py
│       │   │   └── migrations.py
│       │   ├── validation/
│       │   │   ├── structural.py
│       │   │   ├── provenance.py
│       │   │   ├── coverage.py
│       │   │   └── security.py
│       │   ├── exporters/
│       │   │   ├── markdown.py
│       │   │   ├── html.py
│       │   │   ├── drawio.py
│       │   │   └── mermaid.py
│       │   └── report.py
│       ├── schemas/
│       │   ├── knowledge-model.v1.schema.json
│       │   ├── task.v1.schema.json
│       │   ├── semantic-patch.v1.schema.json
│       │   └── cli-envelope.v1.schema.json
│       ├── references/
│       │   ├── agent-protocol.md
│       │   ├── investigation-protocol.md
│       │   ├── evidence-policy.md
│       │   ├── explorer-contract.md
│       │   └── confluence-export.md
│       └── assets/
│           ├── explorer/              # prebuilt offline JS/CSS + notices
│           └── templates/             # Markdown templates
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── browser/
│   ├── exporters/
│   ├── security/
│   ├── evals/
│   └── fixtures/
│       ├── fastapi-db-events/
│       ├── consumer-retry-idempotency/
│       ├── django-transactions/
│       ├── dynamic-dispatch/
│       └── changed-revision/
└── docs/
    ├── architecture/
    ├── installation.md
    ├── cli-reference.md
    └── examples/
```

**Никаких runtime-imports из корня репозитория** внутри `skills/mole/`. `scripts/mole.py` добавляет собственную родительскую директорию в `sys.path` и вызывает `molekit.cli.main()`. Тестировать копированием *только* `skills/mole` в чистый temp directory.

**`SKILL.md`** содержит краткую frontmatter, карту режимов, правила безопасности, запуск команд, разрешение ошибок, условия остановки, ссылки на references. Никаких гигантских описаний схем и парсеров в контексте модели; сложная логика остаётся в Python.

**Минимальная frontmatter (пример):**

```yaml
---
name: mole
description: Investigate codebases and domain workflows, reconstruct evidence-backed processes, and produce Markdown documentation and interactive diagrams. Use for architecture exploration, code-to-process explanation, workflow tracing, failure-path analysis, documentation updates, and Confluence-ready diagrams.
license: Apache-2.0
compatibility: Requires a shell and Python 3.11+ for bundled engine; no network for core operation.
metadata:
  version: "1.0.0"
---
```

Путь `skills/mole/` совместим с форматом Agent Skills; наличие shell и локального Python **не гарантируется во всех чат-интерфейсах**. Требуемая среда для 1.0.0 — Codex или другой агент, действительно способный запускать локальные команды.

---

## 4. Разделение ответственности между Skill, LLM и Engine

| Операция | Engine | Skill / LLM |
|---|---|---|
| Определение цели и аудитории | Создаёт/проверяет scope | Интерпретирует запрос и устанавливает границу |
| Индексация файлов | **Основной исполнитель** | Не просматривает весь репозиторий без необходимости |
| Извлечение AST, imports, routes, decorators | **Основной исполнитель** | При необходимости проверяет нестандартный код |
| Кандидаты call/event/data graphs | **Основной исполнитель** | Не принимает heuristics за runtime truth |
| Критические ветви и неизвестные | Вычисляет и приоритизирует | Разбирает конкретные pending tasks |
| Бизнес-смысл и объяснения | Даёт компактные evidence packs | **Основной исполнитель** |
| Проверка реальности ссылок и типов | **Основной исполнитель** | Пересматривает спорные выводы |
| Семантическая корректность выводов | Проверяет формальные ограничения | Вторичная проверка по коду/тестам и ограничениям |
| Создание SKM | Сборка и нормализация | Ограниченные semantic patches |
| Markdown, HTML, `.drawio`, Mermaid | **Единственный компилятор** | Контроль смысла и выбор форматов |
| Сохранение cache/revisions/overrides | **Основной исполнитель** | Читает summary, разрешает конфликты |
| QA и readiness gates | **Основной исполнитель** | Оценивает failures и сообщает пользователю |

**Строго запрещено в нормальном потоке:** просить модель вручную вычислять координаты SVG, писать JS-обработчики для каждой диаграммы, строить большой JSON Knowledge Model без base index или копировать весь репозиторий в один prompt.

### 4.1 Экономия токенов — механизм, а не маркетинговое обещание

Engine возвращает в stdout **только машинно-читаемую оболочку с короткой сводкой** (целевой лимит 8–12 KiB на команду, кроме явно запрошенного `inspect`). Большие индексы и материалы лежат на диске; LLM запрашивает доказательства точечно по `task_id`, `evidence_id`, `scenario_id` с ограничением контекста и пагинацией. В качестве задач на ревью отбираются наиболее влиятельные неопределённости. Все derived-факты кешируются по revision + content hash + adapter/parser version.

**Не заявлять «80–90% экономии токенов» до измерения.** Можно ставить цель автоматизировать большую часть повторяемых операций; реальные tokens/cost/latency измерить на одинаковых репозиториях и одинаковом качестве результата.

---

## 5. Протокол взаимодействия LLM ↔ Engine

### 5.1 Принципы

- **Stateless CLI processes, persistent workspace**: один shell call запускает Python, читает state, выполняет операцию, атомарно сохраняет state и выходит.
- **No direct LLM API inside Engine** в 1.0.0. Все reasoning tasks исполняются текущим агентом по инструкциям `SKILL.md`.
- **Engine-driven workflow**: модель не решает по памяти, что осталось сделать; `next` и `status` управляются состоянием.
- **Idempotent operations**: повторный `next` безопасен; повторный `submit` с тем же `task_id` и digest не дублирует изменения.
- **Machine output contract**: stdout — один JSON document; progress/logs/errors для человека — stderr; корректные exit codes.
- **Task context bounded**: `next` возвращает вопрос и указатели; `inspect` — релевантные фрагменты с бюджетом.

### 5.2 Команды, обязательные для 1.0.0

```bash
# Агент вызывает локальный entrypoint внутри установленного skill.
python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py doctor --json

python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py start \
  --repo <ABSOLUTE_TARGET_REPO> \
  --workspace <ABSOLUTE_WORKSPACE> \
  --mode standard \
  --scope repository --json

python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py next \
  --workspace <ABSOLUTE_WORKSPACE> --json

python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py inspect \
  --workspace <ABSOLUTE_WORKSPACE> \
  --task <TASK_ID> --budget-chars 12000 --json

python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py submit \
  --workspace <ABSOLUTE_WORKSPACE> \
  --input <SEMANTIC_PATCH_JSON> --json

python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py status \
  --workspace <ABSOLUTE_WORKSPACE> --json

python3 <ABSOLUTE_SKILL_DIR>/scripts/mole.py finish \
  --workspace <ABSOLUTE_WORKSPACE> \
  --output <DOCS_WORKFLOWS_DIR> --json
```

`export` для переэкспорта существующей SKM и `diff` для обновления — тоже обязательные внешние команды; конкретные флаги проектируются на PR-этапе с сохранением обратной совместимости. `--help` у каждой команды обязателен. Выдавать удобные ошибки вида `PYTHON_UNSUPPORTED`, `WORKSPACE_BUSY`, `SCHEMA_MISMATCH`, `TASK_STALE`, `INSUFFICIENT_EVIDENCE`, `OUTPUT_PERMISSION_DENIED`, `PARSER_UNSUPPORTED_SYNTAX`.

**Не путать `start` и самостоятельный агентный `dig`:** `start` запускает *автоматизируемую* фазу и создаёт очередь задач. Сам Python процесс **не сможет заставить Codex рассуждать** между этапами без отдельной API/MCP-интеграции; это делает workflow внутри skill.

### 5.3 Пример короткого JSON-ответа

```json
{
  "protocolVersion": "1.0",
  "ok": true,
  "status": "NEEDS_ANALYSIS",
  "runId": "r-20261108-001",
  "workspace": "/workspace/project/.mole",
  "summary": {
    "scenariosDiscovered": 8,
    "criticalUnknowns": 2,
    "pendingTasks": 4
  },
  "nextAction": "next"
}
```

`next`:

```json
{
  "protocolVersion": "1.0",
  "ok": true,
  "status": "NEEDS_ANALYSIS",
  "task": {
    "id": "task-0017",
    "kind": "delivery_guarantee_review",
    "priority": "critical",
    "question": "Which delivery guarantee is actually supported?",
    "scopeId": "scenario-notification-delivery",
    "evidenceIds": ["ev-012", "ev-013"],
    "contextAvailable": true,
    "responseSchema": "semantic-patch.v1"
  }
}
```

Пример `submit` (иллюстративно, не полная schema):

```json
{
  "protocolVersion": "1.0",
  "taskId": "task-0017",
  "baseRevision": "sha256:example",
  "claims": [{
    "claimId": "claim-delivery-guarantee",
    "statement": "The code schedules retries when the handler raises.",
    "status": "inferred",
    "evidenceIds": ["ev-012", "ev-013"],
    "limitations": ["Broker acknowledgement semantics not proven"]
  }]
}
```

Важно: пример вывода не доказывает никаких свойств реального кода. `submit` сверяет `baseRevision`, `task_id`, поля и evidence lineage. Семантически спорные claims могут быть возвращены в очередь на уточнение.

### 5.4 Pipeline state machine

```text
NEW
  │ start
  ▼
SCANNING → EXTRACTING → TRACING → NEEDS_ANALYSIS
                                │       ▲
                                │ submit│ next/inspect
                                ▼       │
                             VALIDATING ─┘
                                │
                      ready or explicit partial
                                ▼
                             EXPORTING
                                │
                ┌───────────────┴──────────────┐
                ▼                              ▼
            COMPLETED                       PARTIAL

Additional states: BLOCKED, FAILED, STALE.
```

- `NEEDS_ANALYSIS` — Engine ждёт structured response агента.
- `BLOCKED` — отсутствует необходимое право/доказательство или нужно решение пользователя; не зацикливаться.
- `PARTIAL` — разрешён явный частичный экспорт с quality warnings и отметкой ограничения во всех артефактах.
- `STALE` — изменилась основа (`repo revision`, evidence, schema или task base) во время агентного ответа; patch отклонить, пересчитать затронутую задачу.
- `COMPLETED` — достигнуты все заявленные release quality gates, а не «агент сказал готово».
- Recover: атомарные JSON-файлы (temp + rename), workspace lock с обработкой crash, инварианты при resume; никакой зависимости от состояния беседы.
- Ограничить число повторных попыток review; при исчерпании отметить нерешённость, не открывать бесконечные циклы.

### 5.5 Ошибки и exit codes

Минимальный контракт: `0` — операция выполнена (возможно `NEEDS_ANALYSIS` или `PARTIAL`, смотреть JSON), `2` — invalid request/schema, `3` — environment/dependency, `4` — workspace lock/permissions, `5` — task conflict/stale state, `6` — quality gate failed, `10` — internal engine error. Ошибки всегда возвращают JSON envelope с `error.code`, `message`, `recoverable`, `suggestedAction`.

---

## 6. System Knowledge Model (SKM v1)

**Главный инвариант:** одна нормализованная модель, из которой выводятся все форматы и все объяснения. Разделять: факты исходников, потенциальные связи, интеллектуальные claims, представления, пользовательские дополнения.

### 6.1 Сущности

| Сущность | Минимальные поля | Важная семантика |
|---|---|---|
| `System` | id, title, scope, source snapshot, generatedAt, mode | Не смешивать разные репозитории/ревизии |
| `Source` | id, URI, repository, commit/snapshot, path, lineStart/End, kind | Source reference живёт дольше HTML-ссылки |
| `Evidence` | id, sourceId, observation, extractor, parserVersion, excerptHash, classification | Факт из источника, а не обещание runtime |
| `Claim` | id, statement, status, evidenceIds, limitations, reviewer | Статус достоверности обязательный |
| `Symbol` | id, kind, qualifiedName, signatures, sourceRefs | AST-факт; не утверждение о достижимости |
| `Operation` | id, kind, owner, dataEffects, input/output, evidence | Функциональная операция или действие |
| `Relationship` | id, source/target, kind, resolution, evidenceIds, condition | `calls` ≠ `publishes` ≠ `depends_on` |
| `Scenario` | id, title, actor, trigger, preconditions, operations, outcomes, alternatePaths, unknowns | У сценария есть границы и проверяемые исходы |
| `BusinessStep` | id, what, why, audience, relatedOperations, claimIds | Только доказуемая доменная интерпретация |
| `DiagramView` | id, scenarioIds, type, audience, nodes, edges, childRefs, labels | Представление не источник фактов |
| `GlossaryTerm` | id, term, definition, evidence/claim refs | Технический и бизнес-лексикон |
| `Revision` | modelSchema, engineVersion, snapshotHash, previousRevision | Поддержка diff/merge |
| `Override` | targetId, fieldPath, baseHash, value, changedAt, origin | Ручные правки отдельно от авто-данных |
| `QualityFinding` | id, severity, affectedIds, evidence, resolution | Машинно-читаемый отчёт |

### 6.2 Provenance и статусы

Отдельно хранить:

- **Evidence kind:** `source_code`, `test_source`, `config`, `documentation`, `runtime_trace`, `user_supplied`.
- **Claim status:** `source_observed`, `runtime_verified`, `documented_intent`, `inferred`, `unknown`, `contradicted`.
- **Relationship resolution:** `resolved_static`, `possible`, `unresolved`, `observed_runtime`.
- **Quality severity:** `blocker`, `major`, `minor`, `info`.

Не называть статический call graph «проверенным runtime flow». Не считать имеющийся unit-test доказательством production-гарантий. Не придумывать проценты уверенности (confidence) без калиброванного измерения.

### 6.3 IDs и ревизии

- `systemId` и semantic IDs стабильны между изменениями имён файлов, где возможно.
- Для code symbols первичная identity строится из language + qualified name + owner + signature, затем relocation matching по source fingerprint; fuzzy relocation не применяется без conflict report.
- `sourceId` включает snapshot context, а не только `file:line` (номера строк меняются).
- `diagramId` и `scenarioId` не зависят от координат и от пользовательских подписей.
- У каждой ссылки есть проверка реального target; unresolved refs остаются явными unknown, не «заглушками».
- JSON Schema `v1`, golden fixtures, round-trip decode/encode и миграционный контракт при изменении.

### 6.4 Инварианты модели

1. Нет dangling IDs и невалидных source refs внутри текущего snapshot.
2. Все существенные утверждения — с evidence или явным `inferred/unknown` и ограничениями.
3. В графах разрешены циклы выполнения; в дереве навигации циклические child refs не порождают бесконечное дерево.
4. Временная последовательность и causal links не создаются автоматически по одному import.
5. Контрольные/данные/событийные/ошибочные рёбра имеют разные типы и проверяются отдельно.
6. Каждая важная ветвь заканчивается outcome, явно неполным путём или evidence boundary.
7. Source content и source labels считаются **недоверенными строками**.
8. Элементы BusinessStep должны ссылаться на операции/claims; самостоятельные доменные предположения помечаются.
9. Экспортируемые форматы используют одинаковые идентификаторы и semantics.
10. В отчёте нельзя писать «полное покрытие», если неизвестен denominator реальных достижимых ветвей.

---

## 7. Движок: scanner, adapters, traces, uncertainty

### 7.1 Базовый offline scanner (Python stdlib)

**Вход:** `repo`, `scope`, `mode`, ignore configuration, optional baseline snapshot.  
**Выход:** `source-index`, `symbols`, `candidate-edges`, `evidence`, `unresolved`, `agent-brief`.

Этапы:

1. **Workspace discovery:** оценить git root/revision или fallback snapshot hash, язык, manifests, топологию директорий, README, ADR, `AGENTS.md`, тесты, config. Чтение untrusted инструкций из репозитория не должно переопределять правила безопасности MOLE.
2. **File inventory:** корректно учитывать `.gitignore`, бинарные файлы, symlinks, большие файлы; по умолчанию исключить `.git`, `node_modules`, `.venv`, `venv`, `dist`, `build`, `__pycache__`, `.mole`, `.env*`, private keys, credential stores; вести список excluded evidence classes.
3. **Python syntax parse:** `ast` для совместимой версии Python; symbols, calls, imports, decorators, if/else/try/except/finally, await, background task patterns, possible SQL operations, exceptions.
4. **Static relationship graph:** call sites, imports, ownership, cfg branches, async/event edges; каждый edge с resolution status.
5. **Trace candidate discovery:** forward по entry points и backward от side effects (DB write, publish, HTTP outward, response, scheduled task), ограниченный глубиной/ветвлением и scope.
6. **Uncertainty queue:** prioritize dynamic DI, decorators, dispatch, config/feature flags, publish/commit/ack order, retries and timeouts, runtime guarantees.
7. **Context bundles:** создать компактный `agent-brief` и задачи `next` с ссылками на фрагменты, не выводить весь индекс в stdout.

**Python version nuance:** `ast` запущенного Python не обязательно парсит синтаксис более новых версий и не подходит для Python 2.7. При несовместимом синтаксисе возвращать `PARSER_UNSUPPORTED_SYNTAX` или reduced-coverage lexical mode, а не терять файл без отчёта. Дополнительный parser можно подключить позже без изменения SKM.

### 7.2 Framework adapters, обязательные для 1.0.0

- **FastAPI / Starlette:** routers, endpoints, dependencies (как кандидаты), middleware chain, background tasks, lifespan hooks.
- **Django:** URL patterns, views, ORM access, middleware, management commands; не обещать полную поддержку старых версий без fixtures.
- **SQLAlchemy / DB:** transaction boundaries, commit/rollback locations, session usage, reads/writes (эвристики с provenance).
- **Python async:** `async def`, `await`, task creation, cancellation paths, timeout contexts.
- **Messaging:** общие patterns publishers/consumers (например aio-pika/RabbitMQ и aiokafka/Kafka), но без неоснованных гарантий доставки.
- **Tests:** find caller/test references, test names, explicit assertions; различать тестовую семантику и production behavior.

Адаптеры должны быть **small and opt-in by detection**, а не платформой с обязательным plugin manager. Сначала production paths в известных версиях, затем расширение поддержки по фикстурам.

### 7.3 Исследовательский процесс по этапам

1. **Scope:** цель, пользовательская аудитория, actor/trigger/outcome, границы и exclusions.
2. **Discover:** repo index и entry points.
3. **Collect evidence:** AST, config, tests, docs, source spans, hashes.
4. **Trace technical paths:** success/error/timeout/retry, data/event/state effects, boundaries.
5. **Resolve semantic uncertainties:** Engine выпускает задачи, агент читает компактные evidence packs и пишет patch.
6. **Build domain explanation:** `what`, `why`, `trigger`, `rules`, `inputs`, `outputs`, `data/state effects`, `failure/recovery`, `implementation`, `evidence`, `limitations`.
7. **Compose SKM:** стабильные процессы, cross-links, business/technical layers.
8. **Validate & cover:** проверка orphan refs, contradictions, missing outcomes, ungrounded material claims.
9. **Compile:** Markdown, HTML, `.drawio` при заданном формате, Mermaid опционально.
10. **Review & deliver:** Engine возвращает quality/report, агент объясняет границы, выдаёт ссылки.

**Уровни диаграмм не фиксировать искусственно.** L0 — контекст/бизнес-обзор, L1 — взаимодействия и существенные решения, L2+ — детали API/DB/events/states/transactions при объяснительной ценности. Остановиться на полезном листе или честной границе доказательств.

---

## 8. Генерация документации Markdown — обязательная подсистема

### 8.1 Конкретный результат

```text
docs/workflows/
├── README.md                 # карта системы, summary, каталог процессов
├── architecture.md           # компоненты, data/event flows, внешние зависимости
├── glossary.md               # важные термины, если есть содержимое
├── processes/
│   ├── notification-creation.md
│   ├── notification-delivery.md
│   └── retry-and-recovery.md
├── explorer.html             # offline interactive
├── confluence/
│   └── workflows.drawio      # если запросили Confluence/drawio
└── quality-report.md         # ограничения, evidence status, неизвестные
```

Дополнительно в `.mole/` остаются `model.json`, `sources.json`, `evidence.json`, `tasks.json`, `overrides.json`, `history/`, `quality-report.json`, cache; эти файлы — рабочие данные, не основная человекочитаемая документация.

**Не генерировать пустые страницы** и папки «на всякий случай»: если scope маленький, достаточно `README.md` и одного процесса. Имя каждого файла стабильно относительно scenario IDs, а не случайного wording LLM.

### 8.2 Обязательное содержание документа процесса

1. Название, короткое описание, аудитория и scope.
2. Business purpose и ожидаемый outcome (отделить intended от observed).
3. Actors, triggers, preconditions.
4. Нумерованный основной путь выполнения.
5. Decisions, альтернативные ветви, failures/retries/compensation.
6. Data reads/writes, persistent state, integration/events.
7. Technical mapping: компоненты, функции, модули, calls/handlers.
8. Гарантии/инварианты и **доказательные ограничения**.
9. Связанные процессы, glossary, ссылки на HTML diagram ID / другие MD.
10. Evidence section: repo revision, relative path, line range, status и основание.
11. Unknowns, contradictions, excluded scope.
12. Служебная отметка autogenerated/manual sections и дата snapshot.

**Не путать source citations с красивой ссылкой:** локальный `src/foo.py:L10-L22` должен быть полезен в repo; permalink можно сделать при наличии корректного URL и commit SHA без утечки internal repo links.

### 8.3 Защита ручных заметок

Использовать **явные generated sections + manual sections** и version-aware three-way merge:

```markdown
<!-- mole:generated:start id=scenario-delivery-overview -->
... текст, полученный из SKM ...
<!-- mole:generated:end id=scenario-delivery-overview -->

<!-- mole:manual:start id=scenario-delivery-notes -->
Заметки команды. Mole Kit не перезаписывает этот блок.
<!-- mole:manual:end id=scenario-delivery-notes -->
```

- Generated blocks могут пересобираться из SKM, manual blocks сохраняются побайтово насколько возможно.
- Если вручную изменён generated block, **нельзя молча перезаписывать**: detect changed-base, создать conflict report и предложить перенос изменений в manual section или patch.
- Для разделов, которые исчезли/переименованы, сохранять архив/отчёт, не удалять user text без предупреждения.
- Изменения Markdown и HTML-localStorage — **разные хранилища**: browser edits не попадают автоматически в Git/Markdown; никогда не обещать обратное.

---

## 9. Интерактивный HTML Explorer — production contract

Исходный файл `assets/request-workflow-example.html` служит **только референсом**, но не Engine. Новый exporter использует **один проверенный data-driven renderer** и модель диаграммы с stable IDs; не должен заново генерировать JSX/JS/HTML per workflow.

### 9.1 Product UX (унаследовать из explorer-contract)

- Слева дерево Overview → processes → descendants + Glossary. Содержимое и выбранные элементы в дереве, диаграмме и details panel синхронизированы.
- Справа ограниченный SVG diagram viewport; ниже — объяснение выбранного узла/ребра/термина с источниками, notes, limitations.
- **Single click** выбирает и раскрывает описание; **double click** по узлу с child открывает дочернюю диаграмму; **leaf double click** не создаёт пустую диаграмму.
- **Double click text** запускает редактирование текстового поля, не вызывает drilldown. Перевести все важные операции на keyboard equivalents с ARIA labels.
- **Back** — один уровень реального route of containment, а не история произвольных clicks. Shared child diagrams используют контекст родителя; process loops допустимы, navigation recursion — защищена.
- Zoom: fitted view показывает **100%** (относительно fit), +/- кнопки, Fit только при отклонении от baseline; wheel всегда scroll, не zoom. Drag background pan при overflow, pointer capture/cancel; touch-native.
- Длинные подписи переносятся; edge labels привязаны к собственному path; условия ветвления различаются; не писать одинаковое «Next» на всех рёбрах.
- Небольшой viewport **не расширяет ширину всей страницы**. Проверять 390, 600, 768, 1280, 1920 px; graph scroll остаётся локальным.
- Внешняя сеть **не нужна** для `file://` открытия; все CSS, JS и model встроены в один HTML. No external fonts, CDNs, APIs.
- User-controlled strings через `textContent`, URL validation; HTML/JS injection запрещён.

### 9.2 Layout strategy

Цель — хороший результат без Node.js и без сторонних библиотек у пользователя. Предложение:

- В каталоге скилла поставлять **prebuilt/offline renderer**. Для сложных графов допустим **vendored ELK.js** (с фиксированной версией, licence audit, инлайн в финальный HTML); JS исполняется **в браузере при открытии артефакта**, а не требует Node.js/PyPI во время запуска Python Engine.
- Для `.drawio` и headless preview использовать детерминированный layout fallback, реализованный на Python stdlib, либо предрасчитанные layout hints в SKM. Не обещать pixel-perfect parity разных экспортёров.
- Исходные build-средства для renderer могут использовать Node.js **в CI для разработки**, но установленный скилл не требует Node.js.
- Layout должен учитывать wrapping, node dimensions, ports, edge labels, branch spacing, cycles, bounds, nested views. Большие процессы разумно декомпозировать на отдельные meaningful diagrams вместо масштабирования всех 200+ узлов в один экран.
- Тесты должны выявлять clipping/overlap; fallback при сложном графе — предупреждение и readable scroll, а не бесконечная попытка авто-укладки.

**Отдельная инженерная задача:** сделать reproducible asset build с version pinning, SPDX/NOTICE и проверкой того, что итоговый HTML действительно не делает сетевых запросов. Если bundled ELK оказывается слишком тяжёлым или несовместимым с лицензионной политикой, использовать свой ограниченный renderer/layout с явными пределами, а не безмолвную runtime-загрузку CDN.

### 9.3 Редактирование и persistence

- Поля: node title/description/notes, glossary term definition, meaningful connector label, пользовательские добавления в notes.
- Автосохранение в `localStorage` с ключом `mole:<artifactId>:v1`; хранить **только field-level overrides**, `baseFieldHash`, `baseRevision`, schema version, timestamps — не копию всей автосгенерированной SKM.
- При обновлении source text: если пользователь не редактировал поле, брать новую generated value; если редактировал — сохранять override; если обе стороны изменились — конфликтная индикация.
- Malformed/blocked/quota-exceeded localStorage не ломает viewer; показывать ясную ошибку, не врать об успешном сохранении.
- **Local edits не являются shared editing**: не синхронизируются с коллегами или Confluence. CLI `apply-overrides` / sidecar migration можно добавить при реальной потребности, но не добавлять навязчивых UI import/export кнопок по умолчанию.

### 9.4 Visual identity

Отдельный ресурс branding, но функциональность важнее: MOLE — тёмный forest green, moss, amber, ivory; лёгкая ассоциация с кротом/туннелями. UI diagram должен быть **нейтрально читаемым и доступным** даже в светлой теме и для пользователей с нарушением цветовосприятия. Юмор остаётся в CLI/README, не в предупреждениях о фактических ошибках.

---

## 10. Confluence, draw.io, Mermaid

### 10.1 Приоритетная архитектура экспорта

`SKM → diagram IR → exporters {HTML, .drawio, .mmd}`.

**Для Confluence основной результат — `.drawio`**, потому что у него есть multipage diagrams, custom links, layers и редактирование в draw.io app. Однако это **не означает**, что произвольный HTML можно прикрепить к странице и он станет работающим интерактивным макросом. Требуется подходящий draw.io/диаграммный app и корректный viewer mode.

### 10.2 Draw.io exporter, обязательный для 1.0.0

- Генерировать `mxfile`/`mxGraphModel` XML c каждой meaningful subdiagram отдельной `<diagram>` page.
- Каждому shape и edge назначать стабильный deterministic `mxCell id` из semantic IDs; явно делать source/target.
- Поддержать decisions, process nodes, actor/swimlane style по необходимости, labelled connectors, basic layers для success/error/technical (если реально полезно).
- В пределах `.drawio` использовать **внутренние custom links на дочерние страницы**, а не ссылки на несуществующие URL; external code links — только безопасные и доступные ссылки.
- Tooltip содержит concise explanation/status; полноценное доказательное описание находится в Markdown/HTML sidecar — не обещать 100% UX parity.
- Проверять XML escaping/DTD forbidden, валидность схемы, ссылочную целостность, открытие и повторное сохранение. Draw.io предоставляет reference/XSD для XML-формата.
- Документировать необходимость включённых links и выключенного **Simple Viewer**, поскольку в упрощённом режиме ссылки могут не работать.
- Если доступен тестовый Confluence, провести реальный manual PoC и отметить результаты; если нет — выпустить validated `.drawio` c пометкой, что проверка в целевом инстансе **not run**. **Не заявлять full Confluence certified без реального теста**.

### 10.3 Hosted HTML + Confluence iFrame — документированный альтернативный путь

- Отдельная инструкция: защищённый HTTPS-хостинг с access controls, `frame-ancestors`/X-Frame-Options, correct content type, corporate DLP review.
- Confluence Cloud iFrame macro может показывать внешние страницы, но browser/HTTP policies могут блокировать вставку; отсутствие публичного хостинга не мешает локальной работе MOLE.
- Локальные browser edits не станут общими автоматически.
- MOLE **не публикует/не хостит** код, диаграммы и документы без явного разрешения.

### 10.4 Mermaid — дополнительный формат

- Экспортировать `.mmd` для flow/state/sequence, если тип диаграммы представим корректно. Сохранять source IDs в комментариях/sidecar manifest, когда возможно.
- Явно указывать потери: нет полного интерактивного explorer, details drawer, field-level editing и единых guarantees для click handlers во всех viewer'ах.
- Невозможность отразить сложный граф → честный warning, а не искажённая диаграмма.

### 10.5 Не включать в 1.0.0

Forge Custom UI macro, Confluence OAuth/API публикация, общий collaborative editing storage, серверная синхронизация и собственный SaaS. Это **отдельные будущие плагины** к тому же SKM/renderer. Не включать небезопасный HTML macro как рекомендуемую установку.

---

## 11. Инкрементальная работа, кэш и обновления

**Цель:** не перечитывать неизменённые файлы и не переобъяснять неизменённые сценарии при обновлении.

### 11.1 Workspace

```text
.mole/
├── manifest.json          # repo identity, run config, engine & schema versions
├── state.json             # pipeline state and checkpoints
├── index.json             # compact file/symbol inventory
├── evidence.json          # normalized evidence with source hashes
├── knowledge-model.json   # canonical SKM
├── tasks.json             # unresolved/completed semantic tasks
├── overrides.json         # file-level manual overrides (if present)
├── cache/                 # hashes and derived index fragments
├── history/               # prior snapshot model and change ledger
├── quality-report.json    # machine report
└── run.log                # redacted local logs (size-limited)
```

`--workspace` может указывать путь вне target repo. Добавить шаблон `.gitignore` или рекомендацию не коммитить кэши и potentially sensitive snippets; `docs/workflows/` можно коммитить по пользовательскому решению.

### 11.2 Update algorithm

1. Извлечь repo snapshot и сравнить file hashes / dependency indices с baseline.
2. Пересканировать changed/added/removed files; пересчитать зависимые edge candidates/affected scenarios.
3. Сохранить существующие semantic annotations, **только если** их evidence hash/status всё ещё действуют.
4. Выдать новые `needs_analysis` tasks для затронутых ambiguous claims; пометить stale evidence.
5. Мигрировать semantic IDs и overrides; конфликты не перетирать.
6. Переэкспортировать изменившиеся документы/представления (или весь bundle, если так надёжнее при небольшом проекте).
7. Сгенерировать `change-report.md`: added/removed/changed processes, claims, source evidence, user edit conflicts и неразрешённые вопросы.

### 11.3 Базовые требования к diff

- Любые удалённые файлы/символы вызывают проверку impacted claims.
- Renames не должны массово сбрасывать пользовательские правки при сохранённой семантической identity; ambiguous renames → conflict.
- Ревизии схемы и Engine сериализованы и проверяются на загрузке; непонятная версия → `SCHEMA_MISMATCH`, безопасный выход.
- После ошибки или interrupt прежняя валидная SKM остаётся доступной (atomic writes, checkpoints).
- Нельзя молча заменять ранее доказанный claim новым `inferred` без предупреждения.

---

## 12. Безопасность, конфиденциальность, устойчивость

### 12.1 Threat model

**Акторы/риски:** недоверенные файлы анализируемого репозитория, prompt injection в README/комментариях, sensitive secrets, symlink escape, output XSS, runaway recursion, path traversal, повреждение workspace, HTML публикация в открытом интернете, supply-chain assets.

**MUST:**

- Read-only анализ исходников, не импортировать и не исполнять модули target repo для «разведки».
- Не выполнять `pytest`, alembic migrations, docker compose, shell scripts, network requests без отдельного согласования.
- Path allowlist, ignore settings, `realpath` bounds, sym-link safe traversal, max filesize, max graph size, max recursion, max runtime, cancellation.
- Секреты и PII по умолчанию исключать или маскировать в stdout, MD, diagrams, logs, cache; никогда не показывать сырые `.env`, tokens, private keys.
- Исходный код, комментарии, README и result text считать **data**, не инструкциями управления агентом. Скилл не должен выполнять «команды», найденные в текстовом репозитории.
- HTML: text nodes, safe URL allowlist, no eval/dynamic import/remote script; escapings on draw.io XML и Markdown.
- JSON: ограничивать глубину/размер/тип, валидировать все IDs и поля, не принимать arbitrary filesystem paths из LLM без проверки.
- Не делать upload/commit/push/deploy automatically; ясно отделять локальную генерацию от публикации.
- Учитывать license/NOTICE для third-party JS assets в поставке и встраиваемых артефактах.

### 12.2 Разграничение offline и optional dependencies

- `doctor` проверяет Python/runtime, sandbox paths, доступные optional analyzers, не устанавливает их.
- В базовом режиме **ни один сценарий установки скилла не вызывает pip/uv/npm**.
- Advanced integrations реализуются feature-gated и по явному запросу, с проверкой лицензии и версии; их отсутствие — reduced coverage, не ошибка установки.
- Предсобранный JS входит в skill payload и в итоговый HTML, поэтому runtime не загружает зависимости из сети.
- Под Windows/macOS/Linux тестировать пути, кодировки, path separators, case sensitivity и shell quoting.

---

## 13. Quality gates, тесты, измерения

### 13.1 Quality checks Engine

| Gate | Условие для статуса PASS |
|---|---|
| `SCHEMA` | Все выходные JSON соответствуют Schema v1 и не содержат dangling refs |
| `PROVENANCE` | Материальные claims имеют источники или явно обозначенную inferred/unknown границу |
| `REACHABILITY` | Каждая охваченная критическая ветвь ведёт к outcome либо explicit evidence boundary |
| `CONTRADICTIONS` | Все найденные противоречия отражены в quality findings |
| `NAVIGATION` | Child refs, Back paths, shared subprocess, process loops работают без бесконечного дерева |
| `OFFLINE_HTML` | Файл открывается с диска и не делает network requests |
| `HTML_UX` | Редактирование/zoom/pan/focus/narrow viewport проходят автотесты |
| `MARKDOWN` | Нет сломанных локальных ссылок; manual sections не теряются |
| `DRAWIO` | XML валиден; pages/shape IDs/page links сохраняются |
| `SECURITY` | Injection snippets остаются inert, secrets не экспортируются |
| `UPDATES` | Кеш инвалидация и 3-way merges сохраняют правки; конфликты видимы |

`PASS / FAIL / NOT_RUN / PARTIAL` — разные состояния. **Отсутствие браузера или Confluence инстанса нельзя маскировать статусом PASS.**

### 13.2 Набор обязательных fixtures

1. `fastapi-db-events`: API → validation → service → transaction → event → consumer.
2. `consumer-retry-idempotency`: retry, ack/nack, timeout, DLQ, duplicate, partial failure.
3. `django-transactions`: route/view → ORM → transaction boundary → rollback.
4. `dynamic-dispatch`: decorators, DI, reflection, feature flags → неизвестные runtime edges.
5. `shared-subprocess`: один child на двух путях; Back route сохраняет реальный ancestor.
6. `graph-cycles`: process loop с конечной иерархией навигации.
7. `dense-graph`: 30–80 узлов, длинные labels, crossings, 390px narrow viewport.
8. `malicious-input`: `<script>`, `onerror`, `javascript:`, weird Markdown/XML, prompt injection в комментариях.
9. `changed-revision`: правки кода, rename, manual overrides, конфликт обновления.
10. `unsupported-syntax`: Python newer-than-host и legacy syntax; degradation без пропуска файлов.
11. `non-code-doc`: процесс из документов с явно неопределёнными местами.
12. `untrusted-secret`: `.env`, ключи, path traversal/symlinks без утечек.

### 13.3 Тестовая матрица

- **Unit:** parsers, resolvers, graph types, relation statuses, source spans, schema migrations, localStorage override merge, XML/Markdown encoding.
- **Integration:** CLI start→next→inspect→submit→finish и resume; реальные fixtures/archives; parser fallback.
- **Browser:** Chromium + Firefox + WebKit в CI где возможно; resolutions 390/600/768/1280/1920; select, drill, leaf, back, search, edit, reload, fit, zoom, pan, scrolling, no overflow; touch smoke where possible.
- **Export:** draw.io XML round-trip/schema, .mmd parsing, deterministic render and file-size budget.
- **Security:** no target-code execution, no outgoing network, no script injection, safe filesystem.
- **Packaging:** скопировать `skills/mole/` в новый temp dir, удалить доступ к repo root, запустить `doctor` и smoke workflow.
- **Agent eval:** минимум 3 класса моделей (light/medium/strong, если доступны), одинаковые tasks/fixtures, фиксация tokens, semantic errors, evidence coverage и blind review.
- **Manual Confluence acceptance:** реальный Cloud tenant + draw.io app при доступности; viewer interactions, multipage, custom links, reload and edit. Если доступа нет — фиксировать `NOT_RUN`.

### 13.4 Количественные release thresholds

- 0 **known** fabricated material claims на golden fixtures; любой найденный blocker → release stop.
- 100% структурных references внутри SKM валидны; orphan refs = 0.
- 100% material claims в экспортируемой документации имеют evidence или явный статус inferred/unknown с причиной.
- 0 известных критических security regression failures.
- 0 регрессий базовых interaction contract scenarios.
- 0 горизонтального overflow на уровне `document.body` при контрольных ширинах от диаграммы.
- Все форматы генерируются из одного snapshot/идентификатора ревизии, а не независимо LLM.
- Кэш: повторный запуск без изменений не пересчитывает неизменённые файлы; инструмент сообщает reuse stats.
- CLI workflows resume после искусственного interruption, idempotent submit tested.
- Стандартные smoke fixtures завершаются без внешней сети после установки скилла.

**Контекст/скорость:** измерять, но не задавать произвольных «магических» процентных целей до baseline. Для 1.0.0 обязательно сохранить benchmark и показать delta относительно первоначального LLM-led подхода при равном качестве.

### 13.5 Token/quality eval метод

- Одинаковые фикстуры, prompt задачи, модели, условия доступа к инструментам и оценки правильности.
- Сравнить `baseline agent reads code and drafts HTML manually` и `MOLE engine-assisted`.
- Собирать input/output tokens при наличии telemetry; иначе помечать `unavailable`, измерять calls/context bytes/duration.
- Quality eval независимо от потребления: completeness of known critical branches, false-positive edges, hallucinated guarantees, factual inaccuracies, artifact usability.
- Статистику кэш-выигрыша считать отдельно от single first-run; не усреднять случаи, где качество стало хуже.

---

## 14. План реализации — последовательность PR

Ниже **один основной delivery path**, а не «всё сразу». Каждая PR включает код, тесты, обновление документации и короткий architectural decision note. Все команды — proposals until implemented.

### Фаза A — фундамент и доказательства

**PR-01 · Repository / Skill skeleton / Packaging**  
Создать self-contained `skills/mole`, корневой repo layout, `SKILL.md` frontmatter, `agents/openai.yaml`, Python entrypoint, versioning, `doctor`, `--help`, license, packaging test.  
**DoD:** скопированная директория skills/mole работает без repo-root; `doctor` работает на чистом Python 3.11+, не вызывает pip/npm/network.

**PR-02 · Workspace + CLI contract + persistent state**  
JSON envelopes/errors/exit codes, atomic write, state machine, workspace manifest, locks/resume, `start/next/status/inspect/submit/finish` mock stage.  
**DoD:** interrupt/restart, duplicate submission и invalid transitions корректно обрабатываются без потери данных.

**PR-03 · Knowledge schema + evidence/provenance validators**  
Versioned SKM v1, source/evidence/claim/scenario/graph types, migrations v1 basics, JSON Schemas, source line references, structural validators.  
**DoD:** 100% golden invalid models отвергаются; known valid models accepted; no orphan refs.

**PR-04 · Python stdlib scanner + cache**  
Inventory, ignores, AST symbols/imports/calls, source spans, basic control-flow, content hashes, version fallback, stable IDs.  
**DoD:** fixtures detect symbols and candidate call relationships with source spans; code target never runs; no-network smoke.

**PR-05 · Python backend adapters + candidate traces**  
FastAPI/Django/SQLAlchemy/async/messaging patterns; forward/backward candidate paths, branching/error edges, uncertainty priority.  
**DoD:** на трёх основных Python backend fixtures найдены expected entry points и candidate paths; динамические связи не выдаются как runtime-verified.

**PR-06 · Agent research protocol + semantic patch loop**  
Настоящие `next/inspect/submit`, contextual budget, task kinds, task priority, schema + evidence checking, `BLOCKED/PARTIAL`; минимальный SKILL.md orchestrator.  
**DoD:** при ограниченном контексте модель завершает несколько задач, повторный submit idempotent, stale revision rejected.

### Фаза B — знания и визуализация

**PR-07 · Business / Technical knowledge + Markdown compiler**  
Scenario decomposition, glossary, documentation sections, evidence footnotes/links, manual blocks, generated section merges; quality report.  
**DoD:** по fixtures формируется осмысленный самостоятельный `README.md` + process docs, все существенные claims traceable, manual notes сохраняются.

**PR-08 · Universal offline HTML renderer**  
Перенести референсный UX в data-driven renderer, explorer navigation, source drawer, glossary, search, nested/shared views, generic SVG nodes/edges.  
**DoD:** один неизменный renderer работает на разных SKM, не содержит hardcoded views или диаграммных IDs; `file://` offline работает.

**PR-09 · Layout, accessibility and responsive QA**  
Bundled layout + fallback, edge labels, fit baseline, zoom/pan, narrow viewport, keyboard/ARIA, browser tests.  
**DoD:** контрольная viewport matrix и navigation/accessibility сценарии проходят, old mobile horizontal overflow исправлен.

**PR-10 · Editing, overrides, migration / regen**  
Editable texts, field-level localStorage, conflict resolution, model & Markdown 3-way update, graceful storage failure.  
**DoD:** reload сохраняет правки; source regeneration обновляет нетронутые fields; конфликт не затирается.

### Фаза C — Confluence и обновления

**PR-11 · `.drawio` + Mermaid export**  
Multipage XML, links/layers/tooltips, XML tests, Mermaid simple flow/state/sequence fallback, export manifest and loss report, Confluence guide.  
**DoD:** `.drawio` импортируется в diagrams.net; все внутренние IDs/links валидны; доступный Confluence PoC проверен и задокументирован либо NOT_RUN.

**PR-12 · Incremental diff / update**  
Changed-files invalidation, impacted scenarios, semantic patch reuse/stale invalidation, stable IDs, conflict report, `diff` CLI.  
**DoD:** changed-revision fixtures обнаруживают impacted docs/flows, ручные тексты остаются, caches hit on unchanged files.

### Фаза D — релизное качество

**PR-13 · Evals, threat model, portability**  
Полный benchmark, path/security tests, packaging in isolated skill dir, cross-OS CI, browser suite, documentation and examples.  
**DoD:** все release gates из §13, сравнение low/medium/strong по доступности, известных P0/P1 дефектов нет.

**PR-14 · Release 1.0.0**  
Version bump/changelog, Git tag, clean release archive, README, install one-liner or GitHub install guide, sample outputs, license attribution, `SECURITY.md`, support/limitations.  
**DoD:** независимый пользователь устанавливает один `mole` skill, выполняет end-to-end на sample repo, получает Markdown + offline HTML + Confluence-ready `.drawio` без установки отдельного Engine.

**Стоп-условия:** PR-01–06 должны доказать техническую целесообразность до вложений в UI; PR-07–10 должны пройти end-to-end acceptance до расширения форматов; PR-13 не маскирует `NOT_RUN` как `PASS`.

---

## 15. Release checklist 1.0.0

### Must have / функциональность

- [ ] `name: mole`, invoke `$mole`, в комплекте локальный `molekit`.
- [ ] Установка **только** `skills/mole/`, Engine не устанавливается отдельно.
- [ ] Python 3.11+ stdlib core: `doctor`, scan, inventory, AST, cache.
- [ ] Состояние pipeline и CLI JSON contract, resume, bounded review tasks.
- [ ] Evidenced SKM, provenance, explicit unknowns, semantic patches.
- [ ] Python backend adapters + failures/async/data/events trace.
- [ ] Обязательная Markdown-документация в `docs/workflows`.
- [ ] Single-file autonomous HTML с arbitrary meaningful depth.
- [ ] Дерево, glossary, selection/explanations, sources, edit, storage.
- [ ] Zoom/fit/pan/mobile/keyboard/accessibility checks.
- [ ] Confluence-oriented `.drawio`; Mermaid optional; limitations documented.
- [ ] Update/diff и сохранение совместимых manual edits.
- [ ] Quality report и clear partial/unknown statuses.

### Must have / инженерное качество

- [ ] Нет скрытых network calls, installs и target-code execution.
- [ ] Лицензия Apache-2.0 и notices third-party.
- [ ] JSON schema, deterministic tests, fixtures, browser suite, evals.
- [ ] No known blocker security/performance/data-loss defects.
- [ ] Install smoke в **чистой копии** каталога скилла.
- [ ] Поддержка macOS/Linux/Windows в заявленном scope.
- [ ] Fresh-install guide, README, usage examples, limitations, changelog.
- [ ] Не заявлена Confluence-функция, не подтверждённая собственным test evidence.
- [ ] Source code release tag и стабильная совместимость schema/protocol 1.x.

### Explicitly **not** required for 1.0.0

- [ ] Публикация PyPI/отдельного Engine binary.
- [ ] MCP server, SaaS, web backend или API-key к LLM.
- [ ] Forge macro, Confluence auto-publish, collaborative cloud edits.
- [ ] Полная поддержка всех языков, эквивалентная Python backend.
- [ ] Автоматическая установка advanced parsing/debugging tools.
- [ ] Выполнение runtime трассировок или тестов исследуемого проекта по умолчанию.
- [ ] 100%-ная доказуемость динамических веток и внешних интеграций.

---

## 16. Риски, trade-offs и решения

| Риск | Вероятность/эффект | Стратегия |
|---|---|---|
| Слабая LLM выдумывает бизнес-процессы | Высокий эффект | Evidence tasks, semantic review, unknown status, evals разных моделей |
| Python AST недостаточен для dynamic dispatch | Высокий эффект | Candidate edges, explicit unresolved, optional deeper analysis |
| Python 3.11 не парсит Python 3.14-синтаксис | Средняя/высокая | `unsupported syntax` + fallback, optional parser без silent success |
| Skills install копирует только `SKILL.md` | Высокий | Package/test full `skills/mole` dir, документировать совместимые installers |
| Bundle JS/ELK слишком тяжёлый | Средний | Size budget, prebuild assets, simpler fallback, no CDN |
| Недоступен Confluence draw.io app | Высокий для отдельного пользователя | Local `.drawio` + import instructions, HTML iFrame альтернативный PoC |
| Устаревшие локальные edits затирают модель | Высокий | field-level overrides, base hashes, conflict UX |
| HTML может раскрыть sensitive code snippets | Высокий | secret suppression, provenance links instead of full snippets, output audit |
| Нет доступного shell/Python у агента | Средний | `compatibility` в frontmatter, `doctor`, чёткий unsupported-environment message |
| Скорость и токены хуже первоначального baseline | Средний | profiling, caching, selective context, quality-constrained benchmark |
| Слишком разросшийся универсальный Engine | Высокий | Python-first stable scope, no premature MCP/plugin architecture |
| Название `mole` уже пересекается с проектами | Средний | проверить конфликтующие skills/CLI при установке, документировать product identity; юридический trademark review перед масштабным продвижением |

---

## 17. Критерии готовности конкретной реализации для Codex

Для **каждой** PR исполнитель обязан:

1. Дать короткую схему изменений: что создано, что изменено, почему решение соответствует ADR.
2. Описать фактические команды тестирования и их результат, включая `NOT_RUN`.
3. Подтвердить отсутствие установки зависимостей или выполнения target-code в default path.
4. Добавить/обновить fixtures и negative tests для нового поведения.
5. Убедиться, что ни один PR не делает `SKILL.md` зависимым от чужих файлов вне `skills/mole/`.
6. Сохранять совместимость SKM / CLI или явно версионировать миграцию.
7. Не добавлять пустые методы, бесконечные «заглушки», mock-only feature implementations и мёртвый код под видом готовой возможности.
8. Проверять новые авто-объяснения на источниках и сравнивать с golden expected findings.
9. Не «улучшать» demo HTML вместо универсального renderer, кроме извлечения референсных interaction tests.
10. При документировании не обещать features, пока не прошли implementation + test gates.

**Ключевое правило архитектуры:** любая новая функция должна жить в соответствующем слое: extractor → graph/SKM → validator → exporter → interaction, без дублирования бизнес-логики в Markdown/HTML/draw.io.

---

## 18. Готовый стартовый prompt для Codex-исполнителя

> Implement the **MOLE 1.0.0** open-source Agent Skill from `MOLE-1.0.0-IMPLEMENTATION-PLAN.md`. Use the uploaded legacy `workflow-diagram-explorer` as a source for product behavior and historical constraints, **not** as a generic renderer.  
> Build a self-contained skill in `skills/mole` with `name: mole` and bundled Python `molekit` engine.  
> Follow the PR sequence and stop at each PR boundary with a reviewable summary and actual test output.  
> Enforce script-first, LLM-guided, evidence-driven architecture. Keep the base runtime stdlib-only with Python 3.11+; never require PyPI installation, remote services, or an MCP server.  
> The Python CLI must own workflow state and validation, provide compact JSON tasks, and accept bounded semantic patches from the agent.  
> Build a versioned SKM, source evidence, Markdown, offline HTML explorer, `.drawio` and optional Mermaid exports from the same semantic data.  
> Preserve the original navigation/editing/zoom/pan requirements; support nested/reused subdiagrams and safe updates.  
> Never execute target repo code, install its dependencies, fetch external resources, or publish anything without authorization.  
> Every nontrivial assertion must have provenance or be explicitly marked inferred/unknown.  
> Do not claim a test or Confluence integration passed unless it was actually executed.  
> Start with **PR-01** and **PR-02**; do not implement all phases in a single unreviewable change.

---

## 19. Источники, на которых основаны внешние решения

Проверено по официальной документации; источники не являются гарантией прохождения PoC в конкретном окружении:

1. [Agent Skills specification](https://agentskills.io/specification) — `SKILL.md`, `scripts`, `references`, `assets`, frontmatter, portability.
2. [OpenAI skill creator](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md) — progressive disclosure, скрипты для детерминированных задач, skill packaging.
3. [OpenAI Codex skills documentation](https://learn.chatgpt.com/docs/build-skills) — skill discovery, local skills, `agents/openai.yaml`.
4. [draw.io XML generation & validation](https://www.drawio.com/docs/reference/diagram-generation/) — `.drawio` XML, `mxfile`, XSD.
5. [draw.io interactive links/layers](https://www.drawio.com/docs/tutorials/interactive-diagram-layers/) — multipage, custom links, layer interactions.
6. [draw.io Confluence viewer settings](https://www.drawio.com/docs/integrations/atlassian/confluence/confluence-cloud-viewer-settings/) — Simple Viewer limitations, link mode, pages/layers.
7. [Confluence Cloud iFrame macro](https://support.atlassian.com/confluence-cloud/docs/insert-the-iframe-macro/) — HTTPS embedding, browser/frame policy restrictions.
8. [Atlassian Forge macro](https://developer.atlassian.com/platform/forge/manifest-reference/modules/macro/) — возможный будущий нативный macro, не scope 1.0.0.
9. [ELK.js](https://github.com/kieler/elkjs) — возможный офлайн layout-компонент, требующий pinning и license audit.

---

## 20. Краткое заключение

**MOLE 1.0.0 = самостоятельный, устанавливаемый одним действием Agent Skill с предустановленным исходным кодом MoleKit, который локально извлекает факты из Python-систем, поручает модели только сложное осмысление, хранит evidence-backed знания и создаёт поддерживаемую Markdown-документацию, интерактивный HTML и Confluence-ready диаграммы.**

Оптимальный порядок реализации: **(1) packaging/protocol → (2) evidence/scanning → (3) research loop → (4) Markdown/SKM → (5) HTML UX → (6) Confluence exports → (7) incremental/update → (8) security/evals/release.**

Всё, что не улучшает точность, надёжность, экономию токенов или пользовательский опыт в этих рамках, не должно попадать в 1.0.0 только ради потенциального будущего расширения.
