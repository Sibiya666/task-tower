# Headless Task Tower Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Провести одну реальную согласованную задачу Beads через Codex, независимый review, merge и подтверждённое закрытие без ручной передачи этапов.

**Architecture:** Один Linux Docker service вокруг native Beads; внешний фоновый Python connector с собственным Codex app-server. SQLite хранит только попытки/доставку. HTTP polling заменяет брокер и UI в первой версии.

**Tech Stack:** Python 3.11+, unittest, sqlite3, HTTP JSON стандартной библиотеки, Git worktrees, установленный Codex app-server, закреплённый совместимый Linux bd/Dolt, существующие GitHub Actions.

**Spec:** [Согласованный минимальный релиз](../specs/2026-11-07-headless-release-design.md).

## Global Constraints
- Один оркестратор, max_active_tasks=2 на коннектор, значение настраивается.
- Первичная проверка плюс максимум 3 цикла исправления/повторной проверки; затем needs_input.
- Beads — единственная очередь задач и владелец dependency/ready/claim semantics.
- UI, Redis и расширенное восстановление исключены. Неизвестный внешний эффект требует ручной сверки, а не повтора.
- Автоматический merge сохраняет все действующие gates, независимость reviewer, exact head/base и exact-main приёмку.
- После подтверждённого needs_input слот освобождается; несвязавшийся коннектор/неизвестный запуск не освобождают владение автоматически.
- Не менять модели, авторизацию, branch protection и глобальные настройки. Новые зависимости/установки — отдельное конкретное действие, если реально потребуется.
- Переиспользовать текущий checkout/worktree по правилам проекта; исходный код и активные задачи чужих сессий не менять. Перед реализацией получить актуальный main и native ownership новой разрешённой карточки.

## Review Focus
1. Потерян ответ turn/start: Task 3 обязан доказать отсутствие повторной отправки.
2. HTTP claim принят, ответ потерян: Task 2 возвращает тот же attempt по request_id.
3. Base изменился после review: Task 5 отвергает старый verdict и сериализует новую проверку.
4. Ожидание пользователя при живом дочернем процессе: Task 4 не освобождает слот до подтверждения остановки.
5. Частично импортирован план или двойной писатель Beads: Task 2 скрывает незавершённый batch; Task 6 проверяет процедуру переключения.

## Проверенная карта переиспользования
Baseline: локально доступный принятый main 6f5afb95c76a14e3ea422ccdcd376ef78cbd66e8; перед реализацией сверить с fresh remote. PR105 не принимать за завершённую поставку.

| Код | Использование и ограничение |
|---|---|
| task_tower/beads_admission.py: observe(config_path, project, bead, runner, clock) | Готовое bounded read-only наблюдение ready/show; не выполняет claim. Конфиг ограничен Windows, environment содержит NUL: нельзя использовать неизменённым в Linux. Новый service adapter берёт проверенные правила, без расширения старого публичного контракта |
| task_tower/beads_books.py: project_rows/read_projects | Готовые проекции задач/связей/истории. UI-слой не трогать; не импортировать его display config как полномочие исполнения |
| task_tower/processes.py: run_command | Использовать для коротких bd/git команд после профильных тестов; stdin DEVNULL/ограниченный запуск не подходит для длительного двустороннего app-server |
| task_tower/github_tasks.py: GitHubTasks.request | Проверить возможность повторного использования bounded HTTP transport без GitHub Issues как второй очереди |
| task_tower/github_source.py, merge_events.py | Проверенные чтение/валидация источника и merge-event; адаптировать только необходимые чистые проверки, проверить поддержку typed docs artifacts |
| .github/workflows/cli.yml, postmerge.yml; ci_docs.py, ci_unittest.py | Сохранить действующие PR/main gates. Добавить минимальный Linux container smoke, не заменять Windows gate и не копировать 899 тестов в новый обязательный platform programme |
| github_publication.py, postmerge_worker.py, pipeline_*, executor_queue.py | Старый lifecycle/карточки/очередь: не запускать и не использовать как новый scheduler. Возможны точечные чистые валидаторы после проверки зависимостей |
| tests/test_beads_admission.py, test_beads_books.py, test_merge_events.py, test_postmerge_fetch_budget.py | Переиспользовать сценарии и fixtures; старые платформенные проверки не превращать в новую очередь работ |

## Общее представление данных
Все JSON-сообщения version=1. IDs — непрозрачные строки, repository/project берутся из allowlist. API errors: code, retryable, request_id; без приватных путей/секретов.
Attempt: attempt_id, project_id, bead_id, connector_id, phase, execution_state, connection_state, correction_count, thread_id, turn_id, worktree_ref, head_sha, base_sha, pr_number, main_sha.
Фазы: claim_pending, claimed, executing, reviewing, revising, awaiting_merge, postmerge, accepted, needs_input, needs_reconciliation. Отдельно queued/sent/acknowledged команды.
SQLite: attempts, commands, events, decisions, plan_imports; unique request_id/event_id, не более одной незавершённой попытки на project/bead. Время хранить UTC. Локальные ID не считать правом выполнить команду.

## Task 1: Проверить конкретный путь запуска и закрепить контракт
**Files:** create docs/runtime/headless-capabilities.md, tests/fixtures/app_server_protocol.json (только публичная схема); будущие deployment/headless/Dockerfile и compose.yaml относятся к Task 6.
**Interfaces:** зафиксировать supported RPC methods/fields и способ фонового запуска текущего бинарника; не создавать альтернативный executor.
- [ ] Прочитать fresh main AGENTS/current-direction; сверить активный tt-qrk.6 без его изменения. Применить новый согласованный scope как более позднее решение пользователя.
- [ ] Проверить docker executable/engine/Linux container mode. Если отсутствует — назвать конкретную требуемую установку; не исследовать остальные ОС.
- [ ] Получить схему через codex app-server generate-json-schema (сначала --help), закрепить версию 0.166.0-alpha.6 либо фактически используемую версию.
- [ ] В собственной тестовой сессии проверить initialize, thread/start/read, turn/start, завершение, независимый review thread и доступные методы чтения истории. Не подключаться к чужому desktop daemon; отсутствие метода не заменять чтением приватной БД.
- [ ] Одна маленькая harmless model-задача подтверждает используемую авторизацию и реальную возможность исполнения. Отдельно разорвать только HTTP связь с тестовым оркестратором: app-server продолжает работу. Падение самого app-server должно давать unknown/interrupted, а не фиктивное продолжение.
- [ ] Проверить Linux bd/Dolt на disposable database: ready, claim/readback, history, backup/restore. Закрепить версии и checksums реально совместимых бинарников.
- [ ] Зафиксировать результаты/неподдержанные методы. Неизвестная идемпотентность turn/start означает запрет повтора; это не blocker запуска happy path.
**Done:** подтверждён один конкретный транспорт и один Linux bd путь. Коммит документа/санитизированной схемы; private receipts вне Git.

## Task 2: Beads API и минимальный журнал попыток
**Files:** create task_tower/service/{__init__,beads,store,api,cli}.py; tests/test_service_beads.py, test_service_store.py, test_service_api.py.
**Interfaces:** Beads.ready(project_id)->list[dict]; claim(project_id,bead_id,actor)->dict; show(...)->dict; close(...)->dict. Store.claim_request(request_id,project_id,bead_id,connector_id)->dict; record_event(event:dict)->dict. CLI entry python -m task_tower.service.cli.
HTTP: GET /v1/ready?project_id=; POST /v1/claims {request_id,project_id,bead_id,connector_id}; POST /v1/events; GET /v1/attempts/{id}; POST /v1/plans/import; GET/POST /v1/decisions. Коннектор получает только назначения собственной identity.
- [ ] RED: два claims одной задачи дают одну попытку; повтор request_id возвращает тот же результат; foreign Beads owner не перезаписывается; зависимость блокирует ready; чужой project/connector и неверный token отклоняются до эффекта.
- [ ] Run: python -m unittest tests.test_service_beads tests.test_service_store tests.test_service_api -v; ожидаемый RED — конкретный отсутствующий контракт, не ошибка окружения.
- [ ] Реализовать bounded native argv, отдельный actor, owner/readiness readback, journal intent перед claim. Любой незавершённый claim после рестарта требует сверки, не нового запуска.
- [ ] Импорт только approved plan с immutable plan digest и request_id. Пока все карточки/связи не записаны и не сверены, держать новые карточки deferred и batch неисполняемым; service ready принимает только опубликованные approved batches. Сбой не запускает частичный граф.
- [ ] Для доступа: bind/publish loopback, private token file, bounded body/timeouts, allowlisted commands. HTTP polling default 2s, configurable; durable commands/events, никакого Redis/SSE.
- [ ] GREEN указанной команды; добавить потерю HTTP ответа после claim и повтор event_id. Коммит api/store/native adapter.
**Done:** disposable Beads обслуживается через API с реальным claim и без Codex.

## Task 3: Фоновый коннектор, worktree и app-server
**Files:** create task_tower/connector/{__init__,cli,client,store,app_server,worktrees}.py; tests/test_connector_rpc.py, test_connector_worktrees.py, test_connector_recovery.py.
**Interfaces:** AppServer.create_thread(cwd:Path)->str; start_turn(thread_id:str,command_id:str,input:dict)->dict; inspect(thread_id:str)->dict. ConnectorStore.receive(command:dict)->dict; pending_events()->list[dict]. Worktrees.prepare(project_id:str,attempt_id:str,base_sha:str)->dict.
- [ ] RED: повтор command_id создаёт один turn; thread_id сохранён до turn/start; потерянный ответ turn/start не вызывает второй start; чужой путь/dirty-existing worktree отвергается; restart не удаляет worktree.
- [ ] Run: python -m unittest tests.test_connector_rpc tests.test_connector_worktrees tests.test_connector_recovery -v.
- [ ] Реализовать выделенный app-server subprocess со stdio JSON-RPC по схеме Task 1. RPC request IDs только сопоставляют ответы. Собственный процесс и ограниченные очереди stdout/stderr; не использовать run_command для интерактивного RPC.
- [ ] Коннектор создаёт ветку/worktree через поддержанный Git/native механизм согласно AGENTS. Один writer worktree задачи; reviewer получает отдельный detached checkout точного head. Не передавать произвольный cwd из HTTP.
- [ ] В журнале до эффекта записывать команды. Неизвестный ответ → needs_reconciliation. Доставлять outbox повторно с тем же event_id. При потере API соединения продолжать текущий turn, не брать новые задачи.
- [ ] Фоновый запуск не зависит от UI: документированная команда connector run; при запуске через Start-Process использовать Hidden. Автозапуск при входе/системная служба не нужен первому релизу. Один процесс на connector_id, секреты GitHub удалены из env app-server.
- [ ] GREEN + один реальный app-server smoke по Task 1; коммит.
**Done:** реальная задача в worktree завершается и результат доходит до API; merge пока выключен.

## Task 4: Исполнение, независимый review и решения
**Files:** create task_tower/service/lifecycle.py, task_tower/connector/briefs.py; tests/test_service_lifecycle.py; docs/runtime/headless-operation.md.
**Interfaces:** advance(attempt:dict,event:dict,policy:dict)->list[dict] выдаёт durable commands; build_brief(task:dict,role:str,source:dict)->dict. Состояние меняется только после commit record_event.
- [ ] RED: первые review findings возвращают executor в ту же сессию; после 3 исправлений четвёртый отрицательный verdict даёт needs_input; каждый review использует новый thread_id; author thread не может принимать собственный результат.
- [ ] RED: max_active_tasks=2 допускает две задачи в отдельных worktrees, третья ждёт; уменьшение лимита не прерывает; needs_input освобождает слот только после quiescent acknowledgement; disconnect не освобождает слот.
- [ ] Run: python -m unittest tests.test_service_lifecycle -v.
- [ ] Реализовать фиксированные роли executor/reviewer для MVP, без динамического многоагентного scheduler. Brief включает согласованные criteria, полный actual diff, base/head, нужные Superpowers instructions. Самостоятельные помощники не включаются по умолчанию.
- [ ] Разделить model turn completed и task accepted. Валидация review JSON: verdict approve/changes_requested, findings, head_sha, base_sha, reviewer_thread_id; только доверенный коннектор связывает ответ с реальной сессией.
- [ ] Запросы разрешений app-server выводить в CLI decision list/respond; не выводить их из произвольного текста агента и не автоматически одобрять. Менеджер/пользователь отвечает через API CLI; новые задачи/расширение объёма остаются deferred до утверждения.
- [ ] GREEN; сценарий needs_input → следующая ready-задача. Возобновление по явной CLI команде, без приоритетной автоматики. Коммит.
**Done:** полный цикл работы/review/исправлений работает до merge boundary.

## Task 5: Доверенный GitHub delivery и закрытие Beads
**Files:** create task_tower/connector/delivery.py, task_tower/service/acceptance.py; tests/test_headless_delivery.py, test_headless_acceptance.py. Existing github_source.py/github_tasks.py использовать только через явно проверенные узкие адаптеры.
**Interfaces:** Delivery.prepare_pr(attempt:dict)->dict; verify_pr(repository:str,pr:int,head:str,base:str)->dict; merge_expected(...)->dict; verify_main(repository:str,pr:int,main_sha:str)->dict. accept(attempt:dict,evidence:dict)->dict.
- [ ] RED: stale head/base, missing/failed/cancelled CI, self-review и неподтверждённый статус запрещают merge; чужой PR/repo запрещён; docs artifact не считается runtime pass; потерянный ответ merge не вызывает повтор POST.
- [ ] Run: python -m unittest tests.test_headless_delivery tests.test_headless_acceptance -v.
- [ ] Реализовать фиксированные операции trusted host helper: push/PR, bounded reads, genuine task-tower/pr-acceptance после independent verdict, protected expected-head merge. Модельные процессы не получают GitHub credentials helper.
- [ ] По одному merge/main acceptance на repository. При изменении base обновить branch, повторить нужный CI/review. Конфликт исправляет executor в пределах 3 correction cycles либо needs_input.
- [ ] Проверить exact merge SHA, реальные CI artifacts и независимый postmerge verdict (свежая сессия). Сохранить различие documentation.validation и runtime. Сохранить fetch budget 60s/local Git 10s. Ошибка после merge оставляет задачу незакрытой; re-merge запрещён.
- [ ] Сохранить accepted evidence, затем native Beads close с owner/readback/history. Не создавать GitHub Issue как дубликат Beads. При lost close response сначала readback, неоднозначность → reconciliation.
- [ ] GREEN и профильные существующие тесты используемых валидаторов; коммит.
**Done:** автоматическая поставка соблюдает существующие gates без ручного переноса результатов.

## Task 6: Контейнеризация и один настоящий сквозной запуск
**Files:** create deployment/headless/Dockerfile, deployment/headless/compose.yaml, tests/test_headless_e2e.py; update README.md, AGENTS.md, docs/current-direction.md и docs/runtime/headless-operation.md в рамках текущего решения. UI-файлы не менять.
**Interfaces:** docker compose service orchestrator; persistent /data/beads и /data/runtime; host connector endpoint http://127.0.0.1:<configured-port>. Docker не получает репозитории/модельную auth и docker.sock.
- [ ] RED fake integration: approved import → ready/claim → execution → independent review → protected merge receipt → main acceptance → closed; restart в unknown phase не повторяет launch.
- [ ] Run: python -m unittest tests.test_headless_e2e -v; затем полный python -m unittest discover -s tests -v на применимом хосте.
- [ ] Собрать Docker с закреплёнными версиями из Task 1; не скачивать latest при каждом запуске. Запустить Linux container smoke для новых service-модулей с реальным disposable bd и persistent volume.
- [ ] Проверить два параллельных fixture задания и третье ожидающее; потерю HTTP связи с продолжающимся Codex и доставку накопленного результата; отдельный crash turn/start оставляет unknown.
- [ ] Подключить только явно одобренную небольшую полезную pilot-задачу. Исходный вариант: документация API и операций headless с проверяемыми CLI примерами; её карточку утвердить/создать через новый путь. Если такая работа уже выполнена, выбрать другой конкретный маленький результат, не фиктивный файл ради теста.
- [ ] Пилот выполняется коннектором от claim до verified main/close. Человек только согласует исходный scope и отвечает на реальные запросы разрешений; ручное создание reviewer/перенос verdict/merge не засчитываются автономным проходом.
- [ ] Артефакт приёмки: bead/attempt/connector/thread/turn IDs, branch, actual PR H/B/M, review identities, CI/artifact links, canonical close/history. Без токенов и private locators. UI не запускать.
- [ ] Перед переключением настоящего backlog: одна контролируемая native миграция из spec; проверить отсутствие чужих активных writers/claims. Не переключать базу пока другая сессия ведёт tt-qrk.6. Smoke не требует миграции всей канонической базы.
- [ ] Свежая whole-PR/head/base независимая приёмка реализации, действующий CI, protected merge и exact-main acceptance. Не утверждать готовность по одному fake E2E.
**Done:** реальный автономный happy path подтверждён; неисследованные recovery-кейсы честно остановлены, UI отсутствует.

## Порядок исполнения и остановки
Последовательно Task 1 → 2 → 3 → 4 → 5 → 6. Сначала один smoke attempt, затем проверка лимита 2. Не добавлять Kafka/Redis, платформенную матрицу, отдельный планировщик, UI, автоочистку worktrees или балансировку ресурсов.
Если Task 1 выявит несовместимость установленного app-server или Linux Beads, описать конкретный несовместимый метод/бинарник и минимальное исправление; не разрабатывать обходной движок.
План подготовлен как deliverable в projectless outputs. При начале репозиторной реализации перенести spec/plan в docs/superpowers/specs и docs/superpowers/plans с исправлением относительной ссылки; зафиксировать на изолированной ветке. Сейчас исходники, очередь Beads и установки не изменялись.

## Самопроверка плана
Каждое требование spec покрыто Tasks 1–6; неизвестные исходы имеют явную границу ручной сверки. Проверка UI исключена. Контракты между tasks приведены выше; новые файлы являются планируемыми, не существующими. Выполнение и runtime-приёмка этим документом не заявляются.

## Repository execution provenance (2026-11-07)

The user approved this design and its implementation plan in the Docker discussion
and requested separate
execution sessions for the six stages. The approved original design SHA256 is
`28a39f60d242fcc68b6e3eeb263dd359668c5b274839e15b7ed0b0a6bfc6d005`;
the original plan SHA256 is
`64b606d87b9cdb95e77c87bba3aa1d88ea90725e00bb990ca4a400fa6a0a6e9e`.
The repository copy preserves the approved text; the plan's Spec link is adjusted
to the repository location. This provenance section was added during execution.

The `6f5afb95c76a14e3ea422ccdcd376ef78cbd66e8` baseline above is historical
preparation evidence. Stage 1 fetched and locally verified accepted main
`b8f8598e869eef79f404a41f085bbfe3f777f5eb`; native readback confirmed
`tt-qrk.6` closed. That card was not changed. The later approved Docker scope
supersedes the prior platform restriction only for this bounded headless release.
No old qualification programme or historical worker is reactivated.
