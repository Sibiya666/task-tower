# Harness² предлагает улучшать доказательства, прежде чем интеграцию

> **Исторический исследовательский вход; текущая authority — [согласованная единая спецификация](../../superpowers/specs/2026-11-05-task-tower-unified-design.md), решение «согласую» от 2026-11-05.** Она заменяет прежнюю обязательную шестёрку составом по задаче и задаёт qualification-first B → C. Все исходные формулировки ниже, включая DRAFT/pending, прежние six-role gates и предложения backlog, сохранены как датированный snapshot и не задают следующий шаг. Admission `.1` accepted; `.2` blocked у исходного владельца `task-tower-beads-stages`, PR85 Draft/HOLD. Независимые security/CI/exact-head-base/exact-main gates и исходные обязательства сохраняются. Этот исследовательский пакет не опубликован и не принят в main; направление одобрено, исследования не объявляются завершёнными.

> Черновой вход расширенного пересмотра архитектуры, 2026-11-05. Публикация, merge и каноническое закрытие сейчас не выполняются. Новый бэклог будет совместно составлен после оценки текущей и целевой архитектуры. Beads и Superpowers остаются обязательными основами; AgentsRoom используется только как feature/UX-референс, его внедрение исключено решением пользователя.

**Переносить Harness² целиком в Task Tower сейчас не обосновано; первым полезным заимствованием являются требования к доказательствам и чёткие интерфейсы исполнения.** Исследовательский цикл повторно исполняет задачу с изменённым окружением модели, но не предоставляет независимую PR/main-приёмку или каноническое владение Beads. Его опубликованные launchers используют политики, несовместимые с текущей обязательной изоляцией Task Tower. Принятые Books и admission сохраняют ценность; незавершённая квалификация конкретного исполнителя PR85 остаётся отдельным интеграционным риском. Дополнительный optimizer этот риск не снимает. Ни upstream, ни модели, ни native probes в рамках исследования не запускались.

Дата: 2026-11-05. Объём: `tt-bx1.1` / [#46](https://github.com/Sibiya666/task-tower/issues/46), первый результат эпика [#44](https://github.com/Sibiya666/task-tower/issues/44). Upstream закреплён на **`6868817518876de8fd170c6a8354daca273b6191`**; Task Tower accepted main — **`ab91f551fb10e18622e2251e7d4709a2f2c380fb`**. Непринятый candidate PR85 — **`cf560243756026fd0ea1a6f585e2fe16a33ddfb9`**. Ссылки на исходники закреплены на соответствующем SHA; Issues/PR — изменяемые справочные страницы, не каноническая очередь. ([Upstream][h-root], [main][tt-agents], [candidate][tt-candidate-stages])

## Рекурсия улучшает harness, но не заменяет приёмку

Harness² оптимизирует окружение исполнения модели на одной задаче и сохраняет опыт для следующих задач домена. Это исследовательский цикл изменения harness, а не готовый Beads task engine или независимая PR/main-приёмка. Архитектурно полезно отделение method / substrate / benchmark adapter; перенос всей системы не следует из полезности этого разделения. [README][h-readme]; [spec.py:177–249][h-spec]; [schedule.py:619–734][h-schedule].

**Документированная идея и фактическая трасса.** README описывает две рекурсии: task-level Propose–Probe–Compose и перенос принятого harness/lessons между задачами. В коде это разделено на `core.recursion`, `core.schedule`, `core.selection` и `core.library`. Веса модели не являются изменяемой поверхностью метода; меняются инструкции, skills, helper scripts и другие файлы harness. [README, Harness components / Experiments][h-readme]; [SurfaceSpec и validate][h-tree].

| Переход | Реальная функция / данные | Проверенное поведение |
| --- | --- | --- |
| CLI → запуск sweep | `cli.run_sweep._main`, строки131–173 | Проверяет параметры, adapter/preflight, run identity; создаёт proposer; передаёт `pool_policy="finals"` |
| Определение задач/домена | `schedule.run_domain`,737–801; `run_task`,619–680 | В домене задачи идут в порядке потока; библиотека сохраняет только предшествующие задачи. Task inputs вычисляются отдельно; `k` reference runs обозначаются base1…basek |
| Base | `schedule._roll_bases`,473–520 | Запускает unmodified harness через `adapter.execute(task,None,run_id)` либо optional batch. Исключения записываются dead-run facts; если ни одного `b.ok`, `base-failed` прекращает refinement |
| Evidence | `context.build`,105–188 | Создаёт task/source/rollouts/deliverables/harness/pool/decisions/library; применяет leak-path/verdict checks; невозможность отрендерить любую траекторию даёт отказ stage |
| Propose INV/DOM | `recursion.run_parallel`,354–413; `prompts.propose`,824–890 | Из общего base evidence создаются `k` invariant/general и `k` domain-specific предложений. Proposer редактирует tree; выбор dimension влияет на prompt, не выбирает другую модель автоматически |
| Probe | `_roll_many`,314–350; `_roll`,271–311 | Материализует предложенный harness и повторно исполняет **ту же задачу** через benchmark adapter; ledger записывает результаты в фиксированном caller order |
| Compose parallel | `run_parallel`,415–460 | `k` отдельных AGG-композиций используют общее base и evidence всех INV/DOM probes; каждая композиция затем исполняется; finals = agg1…aggk |
| Compose sequential | `run_sequential`,463–576 | Каждый раунд создаёт INV+DOM относительно current harness, probes и composition c_t; история включает предыдущие кандидаты/композиции. Следующий раунд начинает с c_t; finals = **все** c1…ck, не только последний |
| Selection | `schedule._run_one_mode`,561–576; `selection.selection_pool`,93–111 | Pool содержит только `k` finals. Base специально исключён. При k=1 используется `trivial_selection`, без selector session; иначе выбирается один анонимизированный final |
| Reflection | `selection.reflect_adoption`,402–450; `_distil`,454–505 | После `sel.ok` читает выбранный и исходный harness, trajectories, decisions и pool; отдельный вызов extracts cue/lesson/evidence/confidence. Отсутствующий/неполный experience не превращается в lesson |
| Library → следующая задача | `Library.add`,106–152; `schedule.run_domain`,753–782 | Хранит полный выбранный tree и `EXPERIENCE.md` только при пригодном experience; domain/mode library передаётся последующим задачам как context |

Источники таблицы: [run_sweep.py][h-cli], [schedule.py][h-schedule], [recursion.py][h-recursion], [context.py][h-context], [prompts.py][h-prompts], [selection.py][h-selection], [library.py][h-library].

**Failure semantics не равны «всё успешно».** `_run_stage` разрешает два proposal attempts (`STAGE_ATTEMPTS=2`), передаёт ограниченный transport-attempt budget. Не удалось построить evidence — возвращается fallback tree и причина. Invalid/empty/off-surface предложение исправляется в следующей попытке; после исчерпания возвращается исходный/current tree с `fell_back`. `ProposerError` дополнительно ставит `execution_failed`, из-за чего `ModeResult.ok` становится false. `kept_base` — валидное решение оставить дерево, `fell_back` — сбой получения пригодного изменения; смешивать их нельзя. [recursion.py:36–38,73–82,141–261][h-recursion].

**Selection имеет существенную границу.** `selection_pool` исключает base не по качеству, а по конструкции опубликованного метода. `_render_pool` отбрасывает отсутствующие/пустые deliverables; state-deliverable benchmark при пустом pool может использовать trajectory. `assign_ids` применяет стабильную permutation по task/k/mode. При selector error `_fallback` выбирает delivered base, если он есть, иначе первый final для finals-pool; но **не выставляет `sel.ok=True`**. В нормальном release base в pool нет. Поэтому fallback сохраняет выбранную ссылку и ошибку, но scheduler считает selection failed и не добавляет такой результат в library. Это важнее вводящего в заблуждение обобщения docstring про «falls back to a delivered base». [selection.py:47–76,93–153,237–252,268–357][h-selection]; [schedule.py:603–615][h-schedule].

**k=1 не содержит независимого сравнительного selector.** Единственный пригодный final получает `ok=True` и `trivial=True`; пустой pool отказывает. Reflection при включённой library всё ещё отдельная операция, но она не превращает trivial selection в независимую приёмку качества. [selection.py:360–399][h-selection]; [schedule.py:561–590][h-schedule].

**Границы feedback.** `RunView` явно не несёт score; adapter `score` предназначен для judge после committed selection. Evidence builder и validators запрещают grader verdicts в context/tree. Это реализация anti-contamination checks в файлах, а не доказательство отсутствия leakage через сеть. README прямо сообщает unrestricted network и disabled Codex sandbox; experiments документирует наблюдённую загрузку публичной rubric. Детальная проверка benchmark claims относится к #47, здесь только контрактная граница. [spec.py:177–187,247–249][h-spec]; [context.py:153–175][h-context]; [EXPERIMENTS.md:93–109][h-experiments].

### Выводы из исходников

Для Task Tower можно заимствовать правило «предложение связывается с конкретным наблюдённым провалом» из `prompts.propose` и явное различение no-change/fallback/failure. Сам рекурсивный бюджет не следует считать лекарством от текущего неопределённого backend-контракта. Основание: [prompts.py:858–868][h-prompts]; [Task Tower candidate status][tt-status].
Повторное исполнение задачи — фундамент метода, поэтому production effects нельзя просто передать `BenchmarkAdapter.execute`; нужен отдельный безопасный экспериментальный substrate. Это вывод из repeated `_roll` и adapter-owned execution, а не утверждение о готовом production safety у upstream. [recursion.py:271–311,403–455][h-recursion]; [spec.py:219–225][h-spec].

### Ограничения доказательств

Ничего здесь не воспроизведено: нет собственных наблюдений runtime, качества/стоимости моделей или улучшения Task Tower. Публичные проценты README не экстраполируются.
Не исследованы полностью paper, статистика benchmark, adversarial memory transfer и экономика recursion; это зависимые #47–50, а не отсутствие выполнения #46.

## Контракты запуска и кеша требуют другой границы доверия

Core отделён от способа запуска, но `Substrate` сам не предоставляет готовую безопасность: launcher поставляет benchmark adapter. Cache/resume рассчитаны на research namespace и повторное исполнение, а не на восстановление production claims. Нативная Windows-совместимость upstream не подтверждена; исходники содержат явные POSIX runners. [base.py:26–80][h-substrate]; [codex.py:187–198][h-codex]; [runmark.py:132–159][h-runmark]; [JobBench runner:55–64,840–855][h-jobbench].

**Interfaces.** `BenchmarkAdapter` задаёт task list/domain/prompt/files, execute→run_dir, delivered, trajectory, deliverable text/files, base_harness, validate_tree и score. `execute` декларирует idempotency по run_id, но реализацию кеширования/запуска обеспечивает конкретный adapter. `Substrate` задаёт surface/materialise/execute/read_trajectory/preflight. `Install` содержит staging_dir, fingerprint исходного дерева и extras; `RunRequest` — task_ref/run_ids/timeout; `Launcher` — callable, возвращающий run directories. [spec.py:201–249][h-spec]; [base.py:26–80][h-substrate].

**Editable surface и validators.** Для Codex это `AGENTS.md`, `.agents/skills`, scripts и hooks; OpenCode использует отдельные systemprompt/guardrails/memory/tool-guidance, skills и plugin. `tree.validate` проверяет размер always-on context, skills/subagents, компиляцию Python helper, hook structure и ссылки на scripts. Это content validation, не изолированный process/credential boundary. [codex.py:39–106][h-codex]; [opencode.py:42–93][h-opencode]; [tree.py:336–390][h-tree].

**Codex materialise/launch.** `materialise` копирует source-tree entries в временное staging; `execute` без supplied launcher падает. Reference argv использует `--dangerously-bypass-approvals-and-sandbox` и `--dangerously-bypass-hook-trust`, `--ephemeral`, `--json`. Это не только reference sample: реальные JobBench shell runner строки331–341 и LAB runner строки294–304 содержат те же bypass flags. Поэтому перенос upstream launchers в текущую Task Tower policy несовместим с требованием сохранения native isolation. [codex.py:120–198][h-codex]; [actual JB launcher][h-jb-runner]; [actual LAB launcher][h-lab-runner].

**OpenCode/Proposer не равны текущему установленному Codex.** Reference OpenCode argv запускает source checkout через Bun, `run_env` добавляет `external_directory` permission map. Proposer имеет channels `claude_cli`/OpenCode; Claude path содержит `--dangerously-skip-permissions`, temporary context и retry. Shared `scrub_env` удаляет перечисленные exact-name ключи с возможным keep-list, не превращает процесс в OS sandbox. Это описанная реализация, не разрешение применять её к локальным credentials. [opencode.py:226–299][h-opencode]; [proposer.py:95–115,145–181,201–242][h-proposer]; [config.py:220–246][h-config].

**Три разных уровня reuse.**

| Уровень | Проверяемая идентичность | Ограничение |
| --- | --- | --- |
| Proposer `_cached` | Fingerprint label/mission/system/resolved context path и его файлов; непустой response; при harvest нужен workspace | Model identity не входит в сам `_call_fingerprint`; normal CLI отдельно защищает namespace. Не объявлять кеш универсально model-safe при произвольном прямом API вызове |
| Adapter `.adapt_complete` | Версия marker, harness fingerprint; inputs, когда доступны; у JB/LAB дополнительный output fingerprint | Старые markers без inputs специально остаются reusable; `harness_dir=None` fingerprint равен строке `base`, не байтам наследуемого base |
| Task `_resume` / CLI identity | Requested modes/selections, существующий output/harness; optional artifact integrity/input/harness digest. CLI config проверяет method/models/endpoints/task stream/split/seed | Missing input fingerprints не означают отказ: comparisons происходят, когда обе стороны присутствуют; resume может восстановить library из сохранённого выбранного tree |

Источники: [proposer.py:117–138,333–353,500–527][h-proposer]; [runmark.py:42–62,93–159][h-runmark]; [schedule.py:201–235,267–279,380–464][h-schedule]; [cli.run_sweep.py:209–235][h-cli]; [JobBenchAdapter.execute:722–764][h-jobbench].

**Это не production recovery.** Если JB run не reusable или output изменён, adapter удаляет старые out/mark и запускает заново; library `retain/forget` удаляет entries вне предыдущего stream. Такие операции относятся к экспериментальному workspace. Их нельзя переносить на Task Tower claims/fences или неизвестный исход публикации. [jobbench.py:730–756][h-jobbench]; [library.py:90–104][h-library]; [Task Tower AGENTS:9,23–24][tt-agents].

**Платформа.** README требует Linux/Python3.12; pyproject поддерживает Python>=3.12,<3.14 и имеет POSIX classifier. JB/LAB используют `start_new_session=True`, `os.killpg(...SIGKILL)`; JB вызывает bash для `.sh`. WorkBuddy использует process groups и Docker-oriented benchmark runner. Core abstractions могут быть переносимыми, но это не подтверждение Win10 compatibility benchmark launchers. [README Install][h-readme]; [pyproject][h-pyproject]; [jobbench.py:55–64,840–855][h-jobbench]; [lab.py:423–437][h-lab]; [workbuddy.py:458–470,581–642][h-wb].

### Выводы из исходников

Самое безопасное заимствование — интерфейсная граница и описание evidence, а не конкретные launcher flags, retry/resume или автоматическое adoption.
Task Tower должен считать old/missing identity **unknown**, если это input для исполнения/приёмки. Upstream допускает backward-compatible reuse для исследовательских markers; требования доменов различаются. Основание: [runmark.py:142–159][h-runmark]; [TT AGENTS:17,23–24][tt-agents].
Linux experiment service может изолировать upstream lifecycle от Windows продукта, но это отдельная будущая инфраструктура/авторизация. Текущий анализ не разрешает запускать VPS/Linux/Docker. [TT backlog:7–19][tt-backlog].

### Ограничения доказательств

Не проверены native Windows, Linux, Docker, модельные endpoints и фактическая очистка процессов. Source-only comparison не является platform qualification.
Нет гарантий, что current installed Codex alpha6 полностью соответствует ожидаемым upstream pinned runners/hooks. Это отдельная интеграционная проверка, не следствие одинакового имени CLI.
Не заявляется исчерпывающий security audit всех transitive dependencies; #49 остаётся отдельной задачей.

## Принятый main ограничивает разумную область заимствования

Accepted main уже содержит полезные Books, admission и CI-механизмы; их нельзя переобъявлять незавершёнными ради нового framework. PR85 — отдельный непоставленный stage-controller с незакрытой native qualification. Harness² не устраняет этот blocker: его Codex-launch contract сознательно другой. Предварительный вариант для обсуждения — **идеи без runtime-зависимости**; service/full integration только после отдельных критериев и исследований. [TT accepted receipt][tt-accepted]; [TT README:15–36][tt-readme]; [PR85][tt-pr85]; [upstream Codex launcher][h-codex].

**Fresh capability snapshot.** База анализа — main ab91; локальный snapshot зафиксировал clean branch `docs/harness-research` и known cleanup. Приёмка PR84 отдельно подтверждает .1, `task2_stage_execution:false`, `unattended_ready:false`. Это coordinator-supplied actual receipt, не новый тест исследователя. Main docs/backlog всё ещё говорит «.1 взята в работу» — это устаревшая документация, а не отрицание более поздней приёмки. [snapshot][tt-snapshot]; [PR84 receipt][tt-accepted]; [main backlog:31][tt-backlog]; [PR84][tt-pr84].

| Возможность | Статус относительно нового Beads пути | Код / evidence / план |
| --- | --- | --- |
| Локальные Beads Books: tasks/history/deps/assignee | **implemented**, read-only | `beads_books.read_projects` фиксирует readonly/sandbox commands; принята PR74. [main source:111–132][tt-books]; [PR74][tt-pr74] |
| Admission и input identity | **implemented**, только observation, не claim/launch | `beads_admission.observe`: 30s, readonly native calls; PR84 accepted. [main source:232–338][tt-admission]; [receipt][tt-accepted] |
| Интерактивная preparation harness | **partial** как executor platform | `harness.CAPABILITIES`: callbacks/structured_events/resume/independent_review/autonomous_merge false; prepare строит argv/context. [main harness:12–14,102–157][tt-harness] |
| Новые Beads stages/шесть ролей | **partial candidate**, не accepted main | PR85 CF, ordinary CI successful, mandatory native qualification HOLD; default CLI отказывает без concrete runner. [PR85][tt-pr85]; [candidate stages:559–564,1183–1196][tt-candidate-stages]; [public status][tt-status] |
| Старый pipeline/executor/PR worker/groups | **implemented historical / inactive for new path**, не «отсутствующий код» | Source remains, README/AGENTS explicitly archive scope; #16 historical completed, #17/#18/#20/#21 cancelled not_planned. [main README:34–36][tt-readme]; [#16][i16]; [#17][i17]; [#18][i18]; [#20][i20]; [#21][i21] |
| Новая PR/main/Beads-close автоматизация | **planned**, текущий coordinator выполняет gates | `tt-auq.3`; каноническое close координатором не shipped daemon. [backlog:19,43][tt-backlog] |
| Конфигурируемые бюджеты/health/recovery | **planned** `.4/.5`; промежуточные лимиты в draft `.2` не весь результат | [backlog:36–37][tt-backlog]; [candidate spec:108–128][tt-candidate-spec] |
| Системные fault tests / benefit pilot | **planned** `.6/.7`; обычный CI не доказательство полезности агентов | [backlog:38–39][tt-backlog] |
| Распределённое владение / много машин | **planned**, не принят локальным embedded режимом | tt-m9l/#19, отдельный future boundary. [#19][i19]; [backlog:59–63][tt-backlog] |
| Новый engine, уже решающий native isolation | **unknown / not established** | Нет такого результата в .1 receipt; PR85 explicitly blocked. [receipt][tt-accepted]; [status][tt-status] |

**Пересечения без восстановления старой очереди.**

| Historical requirement / текущая задача | Что пересекается с Harness² | Что не заменяется |
| --- | --- | --- |
| #16 stages, текущая `.2` | Роли/feedback/ограниченные corrections, evidence-context assembly | SPEC/DEV/TEST независимая приёмка и шесть настоящих процессов; upstream selector не тот gate |
| #17, текущая `.3/.5` | Provenance/fingerprints/выбор результата | Exact head/base review, current CI, main barrier, canonical closure; H2 не PR merger |
| #18, текущая `.4` | Thread pools/domain streams/лимиты | Beads canonical claims/semantic ownership/lease/fencing; domain ordering не dependency engine |
| #19, tt-m9l | Разделение independent experiments | Multi-machine durable ownership/unknown effects; H2 filesystem marker не distributed lock |
| #20/#21, будущие adapters | Substrate/Launcher interface | Сохранение текущих user auth/policy/Windows supervision; upstream Claudе/OpenCode launch policies не подходят автоматически |
| `.4` | Budget accounting/phase width | Task Tower абсолютные deadlines и stop semantics |
| `.5` | Resume identity checks как идея | Примирение внешнего main/PR эффекта без replay |
| `.6` | Negative-case corpus/cache invalidation cases | Реальная fault qualification продукта |
| `.7` | Baseline/variant/evidence structure | Контрольная оценка пользы и стоимости именно Task Tower |

Источники пересечений: [#16][i16], [#17][i17], [#18][i18], [#19][i19], [#20][i20], [#21][i21], [current backlog][tt-backlog], [H2 schedule][h-schedule], [H2 interfaces][h-spec], [H2 runmark][h-runmark]. Таблица — сопоставление требований, не утверждение, что H2 уже исполняет их.

### Выводы из исходников

| Вариант | Реальная цена и польза | Предварительная оценка |
| --- | --- | --- |
| **Идеи без зависимости** | Использовать evidence-bound changes, явный no-change/fallback, source/model/policy identity и ограниченный context. Не переносить auto-adoption, hooks или launcher | Наименьший интеграционный риск; обсуждать первым. Принятые Books/admission/CI сохранить |
| **Отдельный experiment service** | Собственный Task Tower benchmark adapter; безопасные копии задач без effects; импорт только reviewed рекомендаций. Нужны ОС, credentials boundary, cost budget и no-adoption gate | Потенциально полезно после #47–50; сейчас нет разрешения на сервис/VPS/POSIX/платные запуски |
| **Полная интеграция core+substrates** | Придётся адаптировать POSIX launch/cleanup, заменить bypass policy, сформировать Beads mapping, acceptance bridge и provenance/replay boundary; сопровождать upstream/third-party версии | Наиболее дорогой путь; не решает ближайший Win10 qualification gap сам по себе. Данных для выбора adopt нет |

Основание оценок: [H2 substrate][h-substrate], [actual JB/LAB runners][h-jb-runner], [LAB runner][h-lab-runner], [TT AGENTS][tt-agents], [candidate qualification][tt-candidate-spec]. Это рекомендации по направлению, не одобренный design или выполненный pilot.

Для текущего «много ошибок, идём не туда» наиболее применима исходная мысль H2: каждое изменение должно быть привязано к наблюдаемому моменту ошибки, а повторение ясных инструкций лишь расходует контекст. Практическое предложение — сначала проверить concrete Task Tower launch contract, а не оборачивать недоказанный контракт ещё одним optimizer. [prompts.py:858–868][h-prompts]; [candidate default refusal][tt-candidate-stages]; [architecture audit][tt-audit].

**Сравнение протоколов и сопровождения.** Вариант «идеи без зависимости» не вводит runtime-протокол: меняются только требования к доказательствам и предложенные схемы документов. Для отдельного experiment service предлагаемая граница — версионированные входные/выходные артефакты с task/source/model/policy identity, bounded budgets, digest и явным статусом; transport ещё не выбран и никакого HTTP/server сейчас нет. Потребуются отдельное сопровождение сервиса, обновление schema и контроль несовместимости версий. Полная интеграция связывает Task Tower с Python API, файловой структурой harness/staging/run markers и launcher lifecycle upstream; это более тесная зависимость и необходимость сопровождать изменения Python/CLI/hooks/benchmark adapters. Ни artifact protocol, ни перенос POSIX lifecycle на Windows здесь не реализованы или квалифицированы. Основание сравнения: [интерфейсы][h-spec], [substrate][h-substrate], [markers][h-runmark].

[Дополнительное сравнение AgentsRoom и инженерной статьи OpenAI](../2026-11-05-agent-environment-comparison.md) даёт feature/UX-референс для собственного workflow; использование AgentsRoom исключено пользователем, а его документация не заменяет действующие gates.

### Ограничения доказательств

Свежие GitHub Issue состояния проверены read-only для #16–21; они не заменяют Beads execution state и не дают прав на reopening/claim. #16 действительно historical completed; остальные cancelled/future не объявляются новым недоделанным delivery.
Parent #44 не завершён этой работой. Оценка paper/эффекта (#47), memory (#48), trust (#49), budgets (#50) и итоговое adopt/adapt/defer/reject (#56) остаются dependency-following исследованиями.
Этот отчёт требует независимой проверки артефакта, применимого docs CI, приёмки точных PR head/base и main до канонического завершения. Написание документа само по себе не закрывает задачу.

## Доказательства ограничивают следующий шаг

<a id="observations"></a>

**Санитизированные наблюдения координатора, 2026-11-05.** Предоставленный свежий main-снимок и сводки приёмки подтверждают принятую `.1` после PR84 и состояние PR85: source/ordinary CI accepted, native six-role qualification HOLD, реальных ролей не запускали, merge/closure не выполнены. Полные receipts не опубликованы: читатель может проверить код и требования по GitHub, но не должен считать краткую сводку независимо воспроизводимой проверкой фактического исполнения. Локальные приватные пути и журналы сюда не переносятся. Изменение main или кандидата требует нового сопоставления. ([PR84][tt-pr84], [PR85][tt-pr85], [обязательная квалификация][tt-candidate-spec])

| Claim | Первичный источник / вид evidence | Уверенность и предел |
| --- | --- | --- |
| Base исключён из normal selection pool; k=1 trivial | `selection_pool`, `trivial_selection` ([код][h-selection]) | Высокая для закреплённого кода; не измерение качества |
| Reference runners отключают sandbox/approval gates | Codex substrate и JB/LAB launchers ([substrate][h-codex], [JB][h-jb-runner], [LAB][h-lab-runner]) | Высокая для исходников; запуск не выполнен |
| Старые markers допускают reuse без input fingerprint | `runmark` и scheduler resume ([marker][h-runmark], [scheduler][h-schedule]) | Высокая для ветвей кода; эффект на Task Tower не измерен |
| Books/admission реализованы в accepted main | Закреплённые модули и предоставленная сводка приёмки ([Books][tt-books], [admission][tt-admission]) | Исходники проверяемы; фактическая приёмка здесь вторичная сводка |
| PR85 не поставляет квалифицированную шестиролевую вертикаль | Отказ CLI, обязательная спецификация и предоставленная статусная сводка ([код][tt-candidate-stages], [спека][tt-candidate-spec]) | Основание для HOLD; отсутствие любого возможного backend не доказано |
| Идеи без зависимости предпочтительнее полной интеграции | Сопоставление перечисленных интерфейсов и ограничений | Аналитическая рекомендация; не измеренный экономический эффект и не финальный adopt/reject |

Следующее решение должно уменьшать конкретную неизвестность: какой установленный исполнитель соблюдает утверждённый transport/privacy/cleanup контракт. Для обсуждения идей Harness² не требуется новый engine. Для experiment service сначала нужны отдельные исследования эффекта, памяти, угроз и бюджета (#47–50), а затем разрешённый протокол. Переход к реализации, платные вызовы, POSIX/VPS, установка, ACL и изменение модели/авторизации этим отчётом не разрешены. Шесть настоящих ролей, независимые приёмщики, exact head/base и exact-main gates сохраняются. ([Действующие границы][tt-agents], [квалификация][tt-candidate-spec])

[h-root]: https://github.com/google-research/harness2/tree/6868817518876de8fd170c6a8354daca273b6191
[h-readme]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/README.md
[h-pyproject]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/pyproject.toml
[h-spec]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/spec.py
[h-cli]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/run_sweep.py
[h-schedule]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/schedule.py
[h-recursion]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/recursion.py
[h-context]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/context.py
[h-prompts]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/prompts.py
[h-selection]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/selection.py
[h-library]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/library.py
[h-substrate]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/substrate/base.py
[h-codex]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/substrate/codex.py
[h-opencode]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/substrate/opencode.py
[h-tree]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/tree.py
[h-proposer]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/proposer.py
[h-config]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/config.py
[h-runmark]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/runmark.py
[h-jobbench]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/jobbench.py
[h-lab]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/lab.py
[h-wb]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/workbuddy.py
[h-jb-runner]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/third_party/jb_runner/run_benchmark_codex_cli_adapt.sh
[h-lab-runner]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/third_party/lab_runner/adapt_runs_cx/run_codex_lab.py
[h-experiments]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/docs/EXPERIMENTS.md
[tt-snapshot]: #observations
[tt-accepted]: #observations
[tt-status]: #observations
[tt-audit]: ../2026-11-05-direction-review.md
[tt-readme]: https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/README.md
[tt-agents]: https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/AGENTS.md
[tt-backlog]: https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/docs/backlog.md
[tt-books]: https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/task_tower/beads_books.py
[tt-admission]: https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/task_tower/beads_admission.py
[tt-harness]: https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/task_tower/harness.py
[tt-candidate-stages]: https://github.com/Sibiya666/task-tower/blob/cf560243756026fd0ea1a6f585e2fe16a33ddfb9/task_tower/beads_stages.py
[tt-candidate-spec]: https://github.com/Sibiya666/task-tower/blob/cf560243756026fd0ea1a6f585e2fe16a33ddfb9/docs/superpowers/specs/2026-11-05-beads-superpowers-stages-design.md
[tt-pr74]: https://github.com/Sibiya666/task-tower/pull/74
[tt-pr84]: https://github.com/Sibiya666/task-tower/pull/84
[tt-pr85]: https://github.com/Sibiya666/task-tower/pull/85
[i16]: https://github.com/Sibiya666/task-tower/issues/16
[i17]: https://github.com/Sibiya666/task-tower/issues/17
[i18]: https://github.com/Sibiya666/task-tower/issues/18
[i19]: https://github.com/Sibiya666/task-tower/issues/19
[i20]: https://github.com/Sibiya666/task-tower/issues/20
[i21]: https://github.com/Sibiya666/task-tower/issues/21
