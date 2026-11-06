# Этап A: контракт локального исполнения и навигация

> **ИСТОРИЯ / ЗАМЕНЕНО решением 2026-11-06.** Действующий маршрут: [Beads + Superpowers + готовый Codex](../../current-direction.md). Прежние Windows-квалификация, план B и порядок этапов ниже не действуют. Весь последующий текст, включая старые approvals, слова «текущая authority» и «следующий шаг», сохранён как датированный материал; не возобновлять по нему исполнение или claims. Независимые проверки, безопасность и PR/main gates сохраняются в актуальном AGENTS.md.

Статус: спецификация для независимого review после согласия пользователя с архитектурным направлением. Основание: [архитектура](../../research/2026-11-05-task-tower-architecture-reset.md) и [последовательность A–E](../../research/2026-11-05-task-tower-proposed-backlog.md). Одобрение направления разрешает подготовить и выполнить ограниченную документационную работу A; оно не отменяет обязательную живую квалификацию шести ролей `.2` и не разрешает ACL/auth/model changes. Приёмка данной спецификации и docs-поставка не равны квалификации исполнителя.

## Цель и первый полезный результат

Новый исполнитель, открыв README, должен найти один действующий контракт: что принято, что ещё candidate, откуда берутся задачи, что можно исполнять и что блокирует B. Он не должен принимать исторический shared-worker за текущий путь или угадывать границу между Beads, Superpowers и harness.

Первый результат A — небольшой reviewable документ `docs/execution-contract.md` и согласованные ссылки README/AGENTS/bootstrap/backlog. Он описывает минимальный сквозной сценарий и evidence gaps существующего installed harness. Он не содержит программы запуска, новой очереди, готовых фиктивных receipts или инструкций изменения системных разрешений.

## Global Constraints

- Windows 10, одна машина; macOS/Linux/WSL/VPS/HTTP/multi-machine execution не входит в A.
- Beads — единственный канонический источник задач, dependencies, owner и history; GitHub — код/PR/CI.
- Superpowers остаётся методом анализа, планирования, разработки и независимого review.
- Модель, аккаунт, авторизация, scopes, ACL и приватная конфигурация не меняются и не читаются.
- A не запускает модели, native probes, тесты продукта, installed CLI commands, Beads mutations или PR85 runtime.
- Обязательная живая шестиролевая квалификация tt-auq.2 сохраняется; ordinary CI не заменяет её.
- Существующие независимые exact-head/base PR, актуальный CI и exact-main gates сохраняются; docs-only имеет runtime_tests:not_run.
- Старые claims, receipts, branches и пользовательский WIP сохраняются; executable ownership из JSON не восстанавливается.

## Источники и текущая граница

Исходная база исследования — main `ab91f551fb10e18622e2251e7d4709a2f2c380fb`, отдельный PR85 head `cf560243756026fd0ea1a6f585e2fe16a33ddfb9`. При реализации docs сверить актуальную базу и не выдавать эти SHA за вечный latest. Принятый `task_tower/harness.py` объявляет только interactive_launch; callbacks, structured_events, resume, independent_review и autonomous_merge false. Это факт адаптера Task Tower, а не доказательство отсутствия соответствующего интерфейса у самого Codex. ([Закреплённый источник](https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/task_tower/harness.py#L12-L14)).

Публичные OpenAI Docs описывают `codex exec`, App Server и SDK, но текущий сайт не устанавливает поддерживаемые флаги конкретного installed build. В A допускается только source/document inspection и ранее разрешённые санитизированные receipts. Не запускать бинарник даже для `--help`/`--version` в рамках этого плана. Если точная версия, digest или локальная схема не подтверждены доступным публичным артефактом, записать unknown и требование к B; не обращаться к приватным настройкам и не устанавливать SDK. ([CLI](https://learn.chatgpt.com/docs/non-interactive-mode), [App Server](https://learn.chatgpt.com/docs/app-server), [SDK](https://learn.chatgpt.com/docs/codex-sdk)).

**Уже известная привязка, не blanket unknown:** санитизированный протокол `backend-prerequisites-alpha6.json` сообщает установленный `0.166.0-alpha.6`, executable SHA256 `925c7d0665ffa49b0dcf748e034a805a04da984164ac92301432073b47789b99`. Он фиксирует command-only MXC refusal с EOF/cleanup и отсутствие model qualification; public-schema assessment не установил полного запрета всех builtin IO. Это prior observation, не проверка, что бинарник не обновился сегодня. Более поздний `win10-current-status.json` отдельно сохраняет успешные legacy primitives, парный error267 и неквалифицированную cancellation/coexistence. Ни первый отказ, ни отсутствие найденного интерфейса не доказывают невозможность всех вариантов Windows10. Перед B требуется подтверждение соответствия выбранного provider этой точной версии, а не новый поиск имени CLI с нуля.

## Выбранный сценарий и границы A/B/C

Пользователь задаёт одну небольшую цель в уже разрешённом Task Tower. После уточнения критериев Superpowers готовит spec/plan; каноническая задача Beads связана с ними. Квалифицированный driver позднее делает fresh admission/claim, запускает исполнителя в выделенной копии, получает независимые review и проверенные тесты. Только настоящий PR/main цикл разрешает каноническое завершение; книга показывает task, attempt и acceptance раздельно.

**Решение реализации:** начать контракт с одного разрешённого work item и одного исполняемого шага за раз. Это ограничивает первый эксперимент, не устанавливает универсальный WIP=1 и не отменяет два независимых разрешённых task slots. Конкретная тестовая задача для B выбирается по существующему обязательному контракту `.2`: лёгкая docs-задача сама по себе не заменяет требуемую runtime/TEST квалификацию.

Первый промежуточный slice для B: публичный brief → существующий harness → проверяемый artifact → честный execution receipt → независимая содержательная проверка. Accepted bootstrap пока даёт запуск/exit code без этой привязки; PR85 ожидает связанный RoleResult, но обычный entrypoint не создаёт qualified provider. Поэтому сначала документируется недостающий binding; новая очередь, transport и ACL не являются первым deliverable. Одна сессия не закрывает `.2`; exit0 не доказывает EOF/cleanup. ([Bootstrap](https://github.com/Sibiya666/task-tower/blob/ab91f551fb10e18622e2251e7d4709a2f2c380fb/task_tower/bootstrap.py), [candidate roles](https://github.com/Sibiya666/task-tower/blob/cf560243756026fd0ea1a6f585e2fe16a33ddfb9/task_tower/beads_stage_roles.py), [candidate entrypoint](https://github.com/Sibiya666/task-tower/blob/cf560243756026fd0ea1a6f585e2fe16a33ddfb9/task_tower/beads_stages.py)).

| Граница | Необходимый результат | Чего результат не означает |
| --- | --- | --- |
| A — этот план | Полный документационный контракт, navigation, source-level interface matrix и независимый docs review | Нет runtime qualification и автоматического допуска B |
| B — отдельная спецификация/исполнение | Точный installed provider и входы, реальный six-role run по действующему mandate, negative cases, EOF/cleanup, независимый квалификационный вердикт | Зелёный primitive, shell exit0 или schema JSON не достаточны; PR85 не принимается автоматически |
| C — отдельная интеграция | Native Beads claim/readback, цепочка работы и проверок, fresh PR head/base, actual CI, expected-head merge, exact-main acceptance, реальная history closure | Закрытая исходная карточка без evidence не доказывает delivery |

Для B заранее фиксируются границы времени/числа попыток и ожидаемые различители отказа в отдельном утверждённом протоколе. A не придумывает численные таймауты и не ослабляет существующие. Нужен один отчёт по каждому запланированному случаю с exact inputs, actual result и qualification verdict; повтор без нового основания не разрешён. Для C все перечисленные доказательства обязательны, число отсутствующих обязательных evidence должно быть нулевым. Полезность измеряется отдельно: ручные вмешательства, rework, время готовой задачи до принятия; ускорение заранее не обещается.

## Матрица данных, доверия и интерфейса

`docs/execution-contract.md` должен содержать следующую таблицу как документационный интерфейс. Имена колонок: `Capability`, `Required behavior`, `Source/version`, `Evidence kind`, `Observed result`, `Unknown / next gate`. Evidence kind допускает только `source_inspected`, `vendor_documented`, `prior_observation`, `not_checked`; `qualified` не выводится из этих меток.

Обязательные строки: executable identity/version; launch input transport; model/account preservation; independent role context; workspace writes; private-data denial; host evidence integrity; network/credential exposure; structured result; cancellation; descendant EOF/cleanup; permission lifecycle/external-client coexistence; resume/unknown effects. Путь к installed executable и секретные настройки не публикуются. Для каждой строки указывается точная ссылка/публичный protocol ID с digest либо явное unknown. Копирование флагов из vendor docs как установленного API запрещено.

| Объект | Кто имеет authority | Требование к будущему исполнению / ограничение A |
| --- | --- | --- |
| Beads DB, policy, credentials | Доверенный оператор/ограниченный coordinator interface | Модель не получает DB/config/секреты; A их не читает |
| Задача/spec/plan | Beads identity + Git revision | Sanitized packet связывается с task/source; prose не выдаёт новые полномочия |
| Working source | Implementer в назначенной рабочей копии | Отдельная копия не считается OS sandbox |
| Review inputs | Независимый acceptor | Исходные требования и whole diff, не только пересказ implementer |
| Host evidence | Доверенный verifier | Модельный результат не может переписать фактические process/test receipts |
| GitHub effect | Ограниченный integration helper | Неизвестный исход требует сверки, не повтора по старому JSON |
| Обычный внешний sandbox client | Отдельный субъект | Сосуществование не квалифицируется внутренним mutex автоматически |
| Отдельно разрешённый full-access host | Вне гарантии противодействия этому доверенному host | Нельзя обещать защиту от полномочного администратора; это не ослабляет private-data границы модели |

**Решение реализации:** контракт фиксирует требуемое поведение, а не навязывает deny-root/file-exception, новый ACL-helper или universal filesystem policy. Выбор transport/provider — предмет B после independent feasibility assessment. Успешный предыдущий primitive сохраняется как prior observation, не повторяется ради документации.

## Навигация и файлы

Создать `docs/execution-contract.md` с разделами: `Current scope`, `Authority and data boundaries`, `Installed interface assessment`, `Qualification gates`, `Existing task crosswalk`, `Next permitted action`. README получает один короткий вход в контракт; AGENTS — ссылку и актуальную границу A без дублирования всего исследования. `docs/bootstrap.md` сохраняет действительный interactive launch, а historical shared-conveyor/file-task рецепты явно маркирует historical и убирает из «первой текущей задачи». `docs/backlog.md` получает crosswalk и разделение accepted/candidate/planned по проверенным источникам; не переписывать реальную Beads authority из stale markdown. Корневой workspace AGENTS и все файлы вне этого repository scope не редактируются данным планом; конфликт входа фиксируется как операторское наблюдение, а не скрытая замена чужого checkout.

## Crosswalk: reuse существующих идентичностей

Карта ID основана на `docs/backlog.md`. Свежий санитизированный readback координатора `current-auq-crosswalk.json` от 2026-11-05 (SHA256 `3CDD496AD18FFF5F0BEE1C2BC9AC3364CF62F1AADC230A7F270DEAAE5475FCFD`) отдельно сообщает: `tt-auq` open; `.1` closed; `.2` blocked, assignee `task-tower-beads-stages`; `.3–.7` open/unassigned с исходными зависимостями. Это прочитанное наблюдение, не запуск Beads данным автором и не перенос ownership. Более раннее «.1 взята в работу» в Markdown не переопределяет readback. Карта ничего не создаёт, не claims и не закрывает.

| Область A–E | Существующие ID | Обращение с существующей работой |
| --- | --- | --- |
| A: контракт/навигация | `tt-e4n.1` (#51), `tt-bx1.1` (#46); пересечение с `tt-e4n.2` (#52) | Использовать завершённый source audit как вход; не объявлять #52 полностью исследованным по исправлению ссылок |
| B: исполнитель | `tt-auq.2`; вопросы независимости `tt-e4n.3` (#53) | Сохранить обязательные шесть ролей и PR85/HOLD; reuse port/evidence после оценки; не создавать параллельную замену карточки |
| C: доставка | `tt-auq.1`, `tt-auq.3`; graph/ownership `tt-e4n.4` (#54) | `.1` — принятый вход, `.3` — будущая интеграция; не повторять `.1` и не обходить dependency `.2` |
| D: продолжение | `tt-auq.4` (#25), `.5` (#26), `.6` (#27) | Сохранить budgets/recovery/fault criteria для отдельной работы |
| E: польза | `tt-auq.7` (#28), `tt-e4n.5` (#55) | Не считать source audit измерением пользы или game qualification |
| Исследования/синтез | `tt-bx1.2–.6` (#47–50/#56), `tt-e4n.6` (#57) | Не закрывать зависимые исследования общим одобрением архитектуры; bounded A не реализует recursion/memory/benchmark economics |

Координатор отдельно сверяет canonical Beads состояние перед назначением реализации. Документ не выделяет себе искусственный новый Bead ID и не меняет зависимости. Другие проекты, `tt-m9l` и `tt-2wz` остаются вне A.

## Приёмка A и условия остановки

Независимый reviewer должен по одному входу README найти текущую authority, различить main/candidate, перечислить unknown interface facts и следующий разрешённый шаг. Проверяется полный охват 13 capability rows, отсутствие неподтверждённого qualified/pass, отсутствие машинных приватных путей, корректность относительных ссылок, отсутствие runtime изменений и неизменность six-role/PR/main gates. Это проверка документа, не тест продукта и не выдуманный fresh-session benchmark.

Если обязательная гарантия не подтверждена, A всё ещё может честно поставить контракт с `unknown`; B остаётся закрыт до отдельного разрешённого протокола/доказательства. Если появился новый scope прав, остановить затронутое действие и показать конкретную дельту, не расширять трактовку «погнали». При source/base change обновить факты и аннулировать устаревшую приёмку. Публикация docs следует существующим whole-diff/CI/main gates координатора; this spec не даёт исполнителю отдельного разрешения commit/merge.
