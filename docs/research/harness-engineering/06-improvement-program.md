# Программа улучшений: сначала пригодный исполнитель и один принятый результат

Дата: 2026-11-06. Аналитическая задача **tt-e4n.6**, справочная [Issue57][issue57]. Исходная принятая база — **caddddd6da41847b20737cf7a40fe89b8c4e6d70** после PR97. Это сведение принятых исследований, текущих исходников и предоставленных наблюдений, **не реализация программы**. Новые cold-start/eval/fault/model/pilot trials **NOT RUN**; измеренных выигрышей качества, денег, скорости и времени владельца нет.

**Сохранить принятую архитектуру и завершить конкретный путь B → C; заимствовать малые проверяемые контракты, отложить новый optimizer, память и scheduler.** Пользователю нужен принятый полезный результат в книге, а не ещё один движок или зелёный счётчик. Матрица ниже показывает основание, цену проверки и существующую карточку для каждого предложения. Допустимый итог будущего сравнения — оставить исходный вариант и ничего нового не внедрять.

## 1. Принятое, кандидаты и предложения имеют разную authority

**Принято и сохраняется:** [единая спецификация][unified], согласованная «согласую» 2026-11-05; Beads/Dolt — задачи/зависимости/владельцы/история, Superpowers — метод, существующий harness — исполнение, GitHub — код/PR/CI, Task Tower — Books/overlay и интеграция. Books остаётся read-only; пакет готовности admission — наблюдением, а отдельная private operator policy и admission checks сохраняют свою границу безопасности. Ни display config, ни packet не дают execution authority. Независимый содержательный review, security/lifecycle/evidence, fresh exact-head **и** base, genuine acceptance status, protected expected-head merge и отдельная exact-main-приёмка сохраняются. Успешное исполнение, независимое принятие, канонический close и наблюдение в книге — разные факты. [AGENTS на базе][agents], [Books][books], [admission source][admission], [operator boundary][admission-contract].

**Уже заменено прежним решением:** обязательные шесть ролей заменены составом по задаче; qualification-first B → C заменяет механическое продолжение старой цепочки. Независимость проверки не отменена. Старые DRAFT/unpublished/pending/six-role формулировки и ранние main SHA в принятых отчётах — исторические snapshots. Их исходная история сохраняется; они не отрицают последующую публикацию и не создают сегодняшние требования. **Этот новый аналитический документ сам не заменяет ни одного принятого требования, критерия или разрешения.** Все уточнения ниже остаются предложениями до отдельного принятия в соответствующем scope. [Unified §5–9][unified], [backlog][backlog].

**Кандидаты:** source/CI-приёмка кандидата, удачный локальный запуск и проверенный provider — не одно состояние. Координатор нового desktop повторно прочитал native Beads show/history после проверенного восстановления и guarded resume 2026-11-06T08:35:54Z; свежие GitHub API-чтения PR85/94/97 и fetch main подтверждают следующие границы. Исходный авторский срез 05:47:33Z сохранён как история; новое чтение не удостоверяет бессрочную lease и не квалифицирует исполнителя.

| Объект | Датированное наблюдение координатора | Что оно не доказывает |
| --- | --- | --- |
| `tt-auq.1` | Принятый admission сохраняется; повторное открытие не предлагается | Право запуска из display config или readiness packet |
| B / `tt-auq.2` | **blocked**, исходный owner `task-tower-beads-stages`; `.1` closed в dependencies | Квалификацию G1/G2, передачу ownership или разрешение обхода HOLD |
| C / `tt-auq.3` | **open**, unassigned; блокирующая `.2` blocked | Собственный status blocked, readiness или принятую вертикаль до Books |
| [PR85][pr85] | OPEN/Draft/unmerged, H `cf560243756026fd0ea1a6f585e2fe16a33ddfb9`, HOLD | Accepted runtime; прежний CI не квалифицирует revised provider |
| [PR94][pr94] | OPEN, не Draft, unmerged, H `d29b4e74ec396aa8cb403d4c6436bf5a4048ab55` | Accepted main; API `merge_commit_sha` `40f5d536ca5e08dfb1c2d857dc09f250f247a500` здесь proposed merge, не совершённое принятие |
| Узкие ordinary-session / local-launch результаты | Ранее принятые наблюдения ограничены своими задачами и условиями | Общий отказ от G1/G2, повторное разрешение pilot, право на платные/внешние действия |
| H2 итог / [PR97][pr97] | Координатор подтвердил независимое принятие аналитического main M и канонический close только `tt-bx1.6` | Автоматическое завершение эпика, реализацию H2 или причину/исправление CI-отказов |

**Последующая отдельная веха 2026-11-06:** координатор сообщил, что родитель `tt-bx1` закрыт после самостоятельной независимой aggregate-приёмки всех шести H2-отчётов и их реальных CI/ZIP, с сохранением истории; [публичный receipt Issue44][h2-aggregate]. Это отдельно принятый исследовательский эпик, не следствие одного close `.6`, не собственный новый audit автора и не разрешение внедрения. Текущая HE-карточка `.6` и её родитель `tt-e4n` этим событием не завершены; runtime/pilot trials остаются NOT RUN.

**Предложения:** U0–U6 ниже — не новая очередь. Реальная готовность/owner/dependencies перепроверяются в Beads до эффекта. Текущая Windows/local/one-machine граница, чужой WIP, claims/fences и неизвестные исходы сохраняются. AgentsRoom — только референс; другой проект, Diabloid, POSIX, VPS/HTTP и multi-machine требуют последующей отдельной фазы. Никакой установки, смены аккаунта/модели/auth/ACL или запуска upstream этим анализом не разрешено.

## 2. Откуда вывод и какова сила evidence

**Факт источника** — непосредственно прочитанный код/контракт; **сохранённое наблюдение** — предоставленный receipt/readback с датой; **вывод** — интерпретация; **предложение** — будущая работа; **unknown/NOT RUN** — отсутствующее свидетельство. Высокая уверенность в наличии predicate не означает измеренную пользу его переноса. Hash связывает bytes, не доказывает правдивость или независимость автора.

| Вход | Прочитанный результат, используемый здесь | Предел и воспроизводимость |
| --- | --- | --- |
| [HE01: пять подсистем][he01] | Instructions/Tools/Environment/State/Feedback; навигация, корректное различение evidence, отдельный cold-start дизайн | Историческая база ab91; не считать прежний навигационный gap автоматически текущим. Универсальные WIP/контекст/временные пороги не приняты. Cold-start NOT RUN |
| [HE02: handoff][he02] | Source/owner/effects, stale/unknown reconciliation, семь S0–S5 вариантов с разделёнными push/merge | Контекст не ownership; proposed A/B14 trials и runtime recovery NOT RUN. Узкий ordinary-session результат не переносит полномочия |
| [HE03: acceptance][he03] | Различие checker/gate, 12 отрицательных случаев, реальный docs-cycle и сохранённый readback защиты main | Production refusal и semantic independence не доказаны флагом protection; отрицательные случаи NOT RUN |
| [HE04: control][he04] | State/event/precondition/owner/evidence; отдельные WIP/stage width/main barrier; F1–F7 | Архивный CAS не новый Beads controller. Нет свежей runtime/fairness/recovery квалификации, случаи NOT RUN |
| [HE05: evals][he05] | Executor/reviewer/controller oracles, E1–E12, splits, полный denominator/cost/owner effort, privacy | Это дизайн, не исполнявшийся eval. E-cases NOT RUN; нет measured benefit или общего production error rate |
| [H206: решение Harness²][h206], принятые [H201][h201]/[H202][h202]/[H203][h203]/[H204][h204]/[H205][h205] | R0–R8/P0–P4, альтернативы, bounded packet-only B0/BR/H и N1–N14 | Upstream pin `6868817518876de8fd170c6a8354daca273b6191`; код/бумажные gains здесь заново не воспроизводились. Выводы о release заимствованы из принятых разборов, не новый upstream audit |
| Текущий локальный primary source на M | `read_projects` использует fixed readonly/sandbox list/config/events и сообщает partial/unavailable; `observe` выдаёт `eligible_observation`; адаптер не заявляет resume/independent_review/autonomous_merge; docs validator выдаёт typed `runtime_tests:not_run` | Автор прочитал эти пути как текст, ничего не запускал. Это свойства рассмотренных функций, не всех возможностей установленного Codex и не live Books/native proof. [Books][books], [admission][admission], [harness][harness], [CI][docs-ci] |
| O1: свежие проекции координатора; O2: main receipt PR97; O3: новая CI-сводка | Состояния §1 и конкретные события §3/§7; raw local записи в публичный отчёт не переносятся | Их подлинные API/ZIP проверены координатором и независимыми acceptors, не повторно этим автором. Публичные run/PR ссылки задают проверяемую identity; это не свежий полный census |

Курс `justxor/Harness_ru@6420da2d57c901c401fc909354a7f5f7fce81882` используется через закреплённые HE-разборы как учебный источник. Его файлы golden metadata и чужие benchmark числа не превращаются в наши результаты. В этой работе выполнены source/document analysis и последующие статические проверки текста; upstream/model/native/eval/новые production-fault trials не выполняются. Полный input/coverage/check register предоставляется приёмщикам вне Git без private paths/DB/config/env/raw prompts.

## 3. Единая матрица findings

Severity — **H**: возможное неверное принятие/повтор эффекта/нарушение границы; **M**: риск потерь времени, контекста или ложного сравнения без непосредственно доказанного опасного effect. Это аналитическая оценка последствий, не измеренный incident score. Effort **S/M/L** — относительная стоимость будущего дизайна/проверки, не часы. Confidence указан отдельно для основания (**source**) и ожидаемого эффекта (**transfer**). Frequency unknown не означает ноль; число придуманных cases не частота сбоев.

| ID / подсистема HE01 | Severity; frequency/evidence | Принятый компонент → текущий gap | Ожидаемая польза; effort/risk/confidence | Решение и dependency |
| --- | --- | --- | --- | --- |
| F01 **Instructions** | M; исторический drift в HE01, текущая частота unknown | Unified/AGENTS/навигация есть → старые snapshots могут быть прочитаны как сегодняшняя authority; актуальность каждого маршрута нужна отдельно | Меньше ошибочных переходов; S для ссылок, риск сократить условия; source high, transfer unknown | Adapt U0/U2; B/C source context, HE01/02 |
| F02 **Tools** | H; source distinction, число неверных launches unknown | Books readonly и admission observation приняты → readable/eligible packet не claim/launch/accepted result | Не подменять право наблюдением; S для явного контракта, L для нового enforcement; source high, transfer unknown | Retain U0/U1/U3; `.1` не повторять, `.2/.3` |
| F03 **Environment** | H; B blocked в O1, failure rate unknown | Есть существующий harness/узкие launch observations → общий Windows provider/profile/G1/G2 ещё не принят | Устранить зависимость координации от неквалифицированного пути; effort unknown до concrete B, риск private/effect boundary high; source high, transfer unknown | P0/R3, U1; `tt-auq.2` до `.3` |
| F04 **Environment** | H; source/policy obligation, trials NOT RUN | Worktree и scrubbed env полезны → они не доказывают запрет записи trusted evidence, всех I/O routes и lifecycle/coexistence | Проверяемая граница вместо prompt обещания; L, риск высокий; source high, guarantee unknown | Retain trust boundary, U1/U4; B и `.6` |
| F05 **State** | H; S0–S5 design NOT RUN | Beads canonical history и Git checkpoints есть → chat continuity не process recovery/идемпотентность; stale handoff не свежий owner | Избежать повторной разведки и unknown replay; S для reference index, L для recovery; source high, benefit unknown | R2/P3, U2/U3; `.4/.5` |
| F06 **State** | H; F1/F6/F7 NOT RUN | Claim/lease/session/attempt/cleanup различены → истечение lease или parent exit не доказывают безопасную передачу/освобождение ресурса | Меньше stale/double effects; L для живых guards, high consequence; source high, runtime behavior unknown | U3/U4; `.4/.6`, исходный owner сохраняется |
| F07 **State** | H; H203 transfer cases NOT RUN | Есть source/evidence ссылки → lesson/library не имеет task authority, scope/expiry/revocation/derived provenance ещё не поставлены | Безопасное переиспользование только проверяемых ссылок; S ручной packet / L auto-memory, risk stale/private; source high, benefit unknown | R2 adapt bounded provenance; U2, auto-memory defer |
| F08 **Feedback** | H; реальные docs deliveries есть, 12 gate negatives NOT RUN | Main protection + independent coordinator gates действуют → status presence не проверяет semantic independence или exact-base/main содержание | Не выдавать ложное accepted; M для cases, L для автоматического gate; source high, error rate unknown | R5/R8, U4; `.5/.6` |
| F09 **Feedback** | M; O3: 3 failed attempts одного PR97 run, затем diagnosis nonreproduction и attempt4 success | Typed docs/full CI разделены → generic refusal скрывает категорию; причина этих отказов unknown, selected correlated attempts не population sample | Различающие безопасные observations; S/M diagnosis design, risk privacy/false cause; facts high по retained chain, cause unknown | U6; существующая `tt-qrk.5` blocked, не fixed |
| F10 **Feedback** | H для false accept, M для ложной экономии; E1–E12 NOT RUN | Есть реальные checks/приёмки → нет независимого frozen eval inventory, confusion/coverage и результата benefit comparison | Оценивать executor/reviewer/controller отдельно; M/L, risk self-oracle/leakage; protocol confidence medium, benefit unknown | R5/P2/P4, U4/U5; `.6/.7` |
| F11 **Tools + State** | H; F4/F5 NOT RUN, observed contention/fairness unknown | Работы/owners и serialized main barrier существуют → file-disjoint не semantic-independent; WIP, stage width и main barrier не одно число | Не допустить конфликт интерфейса и premature merge; M/L, risk retry/fairness authority; source high, optimal width unknown | R6 defer scheduler; U3, `.4/.5` |
| F12 **Feedback + State** | M; C blocked dependency в O1, текущая Book-вертикаль не предъявлена | Books принят, независимые main docs cycles есть → один такой цикл не весь C с qualified executor и реально открытой книгой | Один полезный проверенный результат; effort unknown B→C, риск false readiness; source high, benefit size unknown | P0/U1; `.2` затем `.3` |
| F13 **Environment + Feedback** | H; E-cases/N14 NOT RUN, contamination rate unknown | В исследованиях определены splits/keys/privacy → скрытый key или private payload нельзя отдавать tested candidate; digest не скрывает bytes | Честное сравнение и ограничение чтения; M/L, risk leakage; design confidence medium, observed resistance unknown | U2/U4/U5; B/enabled I/O, `.6/.7` |
| F14 **Tools + Feedback** | M; H202/H206 source analysis, собственного gain нет | Сравнение status quo/small/upstream возможно → selection final/k1 и чужие gains не доказательство независимого выигрыша над baseline | Сохранить право B0 win/reject-all/no-adoption; M/L evaluation, risk overfitting; source high, transfer unknown | R1/R7/R8, U5; `.7` после dependencies |
| F15 **State + Feedback** | M; measured full spend/owner saving отсутствует | H205/HE05 дают единицы → improver USD, логические rollout slots, закрытые cards и время до output не полная цена accepted result | Видеть реальную цену/owner effort; M collection/L full integration, risk measurement overhead; definitions high, savings unknown | R4/P1, U3/U5; `.4/.7` |

Матрица не объявляет нынешний ручной процесс полностью отсутствующим: accepted Books/admission/CI и реальные независимые docs cycles — положительные результаты. Она также не выводит из них unattended pool, safe recovery или автоматическое закрытие. Все обозначенные gaps являются либо текущими неизвестностями, либо датированными source-level различиями; исторический navigation defect сам по себе не доказан на каждом нынешнем entrypoint.

## 4. Согласование с Harness² без нового framework

| H2 решение / программа | Разрешение противоречия HE↔H2 и итог здесь |
| --- | --- |
| **R0** retain/adopt baseline → U0/U1/U4 | Пять подсистем — рубрика, не пять обязательных новых компонентов. Beads/Superpowers/Books и независимые gates сохраняются; агентный состав по задаче уже согласован |
| **R1** adapt evidence-bound small change → U2/U5 | Простота handoff не доказывает улучшение. Проверять один малый компонент и допускать B0 win, keep-original, reject-all/no-adoption; selection и final artifact не собственный oracle |
| **R2** adapt provenance, defer auto-memory → U2 | Короткий index удобен, полный tree сохраняет детали. Хранить refs/условия/контраргумент, при use проверять scope/source/expiry/revocation; не строить auto-library и не исполнять lesson prose |
| **R3** retain trust boundary, defer new enforcement → U1/U4 | Контекст/граф не квалифицирует provider. Требования B сохраняются; новый enforcement требует реальных enabled-route/lifecycle доказательств, worktree/help/JSON недостаточны |
| **R4** adapt full accounting → U3/U5 | Ledger — evidence рядом с existing bead, не очередь. Измерение само стоит денег/ресурса/времени; минимальный достаточный набор предпочтительнее неизмеряемой полноты |
| **R5** adapt independent oracle/negative gates → U4/U5 | Отдельный reviewer полезен, но не собственная ground truth; source/schema pass, tool denial, model decision и effect-bound integration имеют разные уровни evidence |
| **R6** defer automatic scheduler/width optimization → U3 | Граф переходов допустим как описание; framework и универсальный WIP=1 не следуют из курса. Измерить eligible wait/resource capacity до fairness/weights, main barrier не ослаблять |
| **R7** defer upstream core/substrate → U5 decision boundary | Простой контракт поверх выбранного Beads сравнивается при тех же guarantees. Ни graph library, ни H2 core не устраняют B/C/ownership/cleanup сами по себе |
| **R8** reject unsafe policy shortcuts → все U | Нельзя выбирать больше score ценой bypass/self-accept/hidden denominator/unknown-effect replay. Отдельное иное исследовательское окружение потребовало бы собственного разрешения; этого scope нет |
| **P0** B→C → U1 | Существующая обязанность; не повторять admission и не ждать нового optimizer |
| **P1** evidence/accounting → U2/U3/U5 | Уточнение входов `.4/.7`, не дополнительная finance/task DB |
| **P2** decision/effect negatives → U4 | Использовать HE03/04/05 + N-cases как единый versioned corpus с дедупликацией смыслов, не трижды считать один failure |
| **P3** reference-only packet → U2 | В этой программе специфицируется предложение для существующих `.4/.5/.6/.7`, но packet trial не выполняется и новая implementation card не создаётся |
| **P4** bounded benefit comparison → U5 | Reuse B0/BR/H packet-only estimand из H206; не прямой тест всего optimizer. `.7` сохраняет `.4/.5/.6` dependencies, launch blockers и отдельные права |

Четыре альтернативы остаются действительными: **status quo** сохраняет рабочее и manual overhead; **малый собственный index/контракт** может уменьшить поиск, но требует поддержания свежести/independent review; **upstream artifact boundary или core** дают reuse с большей совместимостью/maintenance/security ценой; **no new adoption** оставляет ресурс для B→C. Нет измерения total cost of ownership или gain, позволяющего сейчас выбрать большой import. Отрицательный packet trial не опроверг бы всю рекурсию; положительный не оправдал бы её внедрение. [H206 §3–9][h206], [HE04 §6][he04].

## 5. Reviewable предложения и точная привязка к существующим карточкам

U-идентификаторы обозначают строки этого документа, **не задачи и не их активацию**. Таблица предлагает конкретное уточнение, но не редактирует канонические criteria/статусы/owners. Исходные требования и зависимости имеют приоритет. Scope будущего изменения сверяется с актуальным bead и принимается отдельно; нет blanket permission ни на бесплатный trial, ни на модельный вызов.

| Existing card / справка | Точное предлагаемое уточнение, без нового дубля | Сохранённая граница |
| --- | --- | --- |
| `tt-auq.1` | Ссылаться на принятый admission и distinction observation/claim во всех U; дополнительных критериев/повторного открытия нет | Не реализация executor или execution authorization из Books |
| `tt-auq.2` B | В concrete provider plan добавить компактную capability→original criterion→observable evidence→unknown/stop таблицу и источники U0/U1 | Тот же owner, `.1`, все non-six-role/G1/G2/permission/lifecycle обязательства; не новый stage engine |
| `tt-auq.3` C | В evidence map U1 связать один bead/plan/actual execution/independent reviews/H-B-M/close/readback/реальную открытую Book | Зависимость B и отдельная минимальная Books проверка; documentation main alone не C |
| `tt-auq.4` / [#25][i25] | U2/U3: минимальные episode/attempt/source/policy refs, scope-safe handoff, actual/reserved budgets, cancel→cleanup→reconcile и причина resource deferral | `.2/.3` prerequisites; без нового scheduler/DB и без release unknown reservations |
| `tt-auq.5` / [#26][i26] | U2/U3/U4: lost-ack reconciliation, actual tested-M/typed artifact/main verdict, fresh head/base и prior-main barrier | Зависимость `.3`; не resurrect old postmerge worker и не auto-close из JSON |
| `tt-auq.6` / [#27][i27] | U4: один case/key inventory с HE02 S, HE03 1–12, HE04 F, HE05 E, H206 N и alias/dedup map; отдельно decision/tool/model/integration scopes | `.2/.4/.5` prerequisites; нельзя выдать fixtures за реальный fault/enforcement proof |
| `tt-auq.7` / [#28][i28] | U5: full planned cohort, separate executor/reviewer/controller oracles, B0/BR/H, owner/full-cost/censoring/no-adoption и численный independently accepted run sheet до запуска | `.4/.5/.6` prerequisites; числа/paid launch/повтор ordinary pilot не подразумеваются |
| `tt-qrk.5` | U6: при следующем отдельно принятом diagnosis scope фиксировать безопасный original category/phase и observer_failed; preserve every attempt | Сейчас blocked/cause unknown/not fixed. Имеющийся read-only monitor остаётся PAUSED; ни запуска, ни нового rerun, ни дублирования monitor этот текст не разрешает |
| Закрытые HE/H2 исследования; архивные [#16][i16]/[#17][i17]/[#18][i18] | Использовать результаты как evidence/контрпримеры; прежние recipes не действующая зависимость | Не переоткрывать research ради внедрения и не оживлять старый conveyor |
| `tt-m9l`, `tt-2wz`/дети, `tt-v69` | Сохранить существующие future scope/dependencies в [backlog][backlog]; использовать выявленные границы при последующем допуске | Нет multi-machine/POSIX/legacy requalification сейчас, нет неявной отмены этих карточек |

### U0. Датированная карта authority и источников для B/C

**Проблема/объём:** F01/F02/F12; краткая public entry map к unified, принятому main, canonical bead и candidate boundaries, scoped operator projection отдельно. Вход существующих `.2/.3`, без нового task store. **Non-goals:** переписать все инструкции, менять чужой checkout/WIP, публиковать live DB или считать репозиторий источником приватного состояния.

**Acceptance:** новая сессия по разрешённым материалам называет source/current authority и границы accepted/candidate/proposed, либо обоснованно unknown; каждый current факт имеет dated source. **Negative:** старый six-role/pending snapshot, unmerged PR94 proposed merge и stale ACTIVE не повышают authority; repository-only reader вправе не знать live owner. Это будущая независимая decision-проверка, не PASS данного автора.

**Before/after:** T_orientation/T_decision, reads/bytes/distinct_sources, wrong-route/unsupported claims и active owner minutes на одном frozen packet, с incomplete/cutoff; baseline сейчас не измерен. **Stop/rollback:** missing authoritative source → affected effects stop, оставить проверенные ссылки/предыдущую версию, не удалять историю. **Authorization:** обычная документационная правка возможна только в существующем authorized task plan; controlled fresh-session trial требует конкретных входов/лимитов/независимого key и отдельного допуска, не меняет model/profile.

### U1. Принять конкретный B, затем один C до настоящей книги

**Проблема/объём:** F03/F04/F12; выполнить уже принятую вертикаль, не добавляя альтернативный harness workflow. B pin установленного executable/profile/transport и оригинальных обязательств; C один useful task с планом и настоящим результатом. **Non-goals:** считать help/version, PR85/94 или ordinary-session docs cycle общей qualification; строить постоянный pool.

**Acceptance:** отдельный проверяющий B принимает actual artifact, ограничения read/write/private/evidence/network и весь lifecycle/coexistence/cleanup/unknown-outcome contract на выбранном Windows10 пути; затем C предъявляет canonical claim, plan, actual diff/tests, independent reviews, exact H/B/M/CI, closure/readback и source-bound наблюдение в реально открытой Book. Полный original checklist — [unified §6–7][unified], ни один non-six-role gate не сокращён. **Negative:** forbidden canary read/write реально отклонён; self-evidence, stale result, unknown child/remote effect и пропущенный Book шаг не принимаются.

**Before/after:** coverage каждой исходной гарантии и каждого этапа C, число unknown/false readiness claims; не число агентов. Полезность/owner cost пока unknown. **Stop/rollback:** первая недоказанная обязательная гарантия удерживает B/C; сохранить WIP/receipts/HOLD, не replay. **Authorization:** существующий scope даёт подготовку и рутинное выполнение принятого плана; выявленная конкретная дельта ACL/account/model/auth/install/другого repo возвращается пользователю как reviewable действие. Этот отчёт не перехватывает исходный claim и не расширяет one-off pilot.

### U2. Один reference-only handoff/provenance index

**Проблема/объём:** F01/F05/F07/F13; proposal к `.4/.5` с входами `.6/.7`: минимальные task/source/criteria/policy/owner observations, unknown effects, evidence/checkpoint/next permissible readback и rejected alternatives. Lesson — scoped claim с counterexample/expiry/revalidation/revocation и original/derived refs. **Non-goals:** executable packet/parser, копия backlog, auto-memory/vector DB, перенос private payload по сходству cue.

**Acceptance:** индекс ведёт к подлинному evidence и явно разносит observation/authority, thread/attempt/fence, execution_completed/accepted/done; перед use сверяются scope/source/policy/owner/lifecycle. **Negative:** stale/conflicted/expired/revoked, derived от отозванного, другой project и неизвестный effect → exclude/revalidate/reconcile; missing field не заполняется UUID/выдуманным receipt. Deny cross-project access прежде чтения чужого payload. Краткость не позволяет потерять применимость; исходный tree/evidence остаётся доступен по разрешённой ссылке.

**Before/after:** U0 correctness/effort/read metrics плюс wrong-transfer/revocation/unsupported-action counts и preparation/retrieval/review cost; два одинаковых packet не независимый episode. **Stop/rollback:** исключить невалидную версию и affected derivatives, вернуться к допустимым исходным refs; не восстанавливать revoked запись и не отменять внешние effects откатом файла. **Authorization:** proposal аналитический; изготовление/проверка bounded public packet и любое будущее применение требуют конкретного принятого scope, private mapping/key — host-only. Никакой новый storage/retention/deletion/ACL policy здесь не вводится.

### U3. Явные owner/effect/resource контракты вместо нового scheduler

**Проблема/объём:** F05/F06/F11/F15; уточнение `.4/.5`: task/attempt/source/policy binding, opaque revisions, intent-before-effect, actual readback после unknown ack, separate consumed/reserved/required remaining budget и cancel→confirmed cleanup→reconcile. State/event/precondition/owner/evidence таблица может описывать простой будущий controller поверх Beads. **Non-goals:** перенос архивного journal, exactly-once обещание для внешнего API, fairness weights/увеличение WIP без данных.

**Acceptance:** каждый effect имеет действующее право и известный исход либо fenced unknown; release только доказанно свободного остатка, absolute deadline не обновляется при retry. Semantic interface conflicts учитываются даже в разных файлах; WIP/stage width/repository main barrier раздельны. **Negative:** stale ready actors, expired lease + alive/unknown worker, parent exit/child unknown, lost ack, file-disjoint producer/consumer и missing prior-main не разрешают конфликтующий следующий effect. Где API не даёт fencing, описать сериализацию/identity reconciliation и предел гарантии, а не token в JSON.

**Before/after:** proposed/attempted/confirmed/unknown/duplicate effects, cancel→confirmed cleanup/censoring, cap overshoot и eligible waits/served resource capacity; сравнение fairness только на одинаковых eligibility/guarantees. Данных о contention/оптимальных слотах нет. **Stop/rollback:** запретить новые effects, отдельно подтвердить stop/descendants/EOF, reconcile и сохранить uncertain reservations/расходы/историю. **Authorization:** реальные guards/fault/cancel реализации — только scoped `.4/.5` после dependencies и independent plan; local/native probes не следуют из рисунка, permissions не расширяются ради «восстановления».

### U4. Независимые негативные кейсы и effect-bound oracle

**Проблема/объём:** F04/F08/F10/F13; `.5/.6`: versioned cases с alias к исходным S/12-gate/F/E/N, одному root cause не присваивать несколько production incidents. Сначала frozen public/inert packet/key, затем отдельно допущенный actual tool/model/integration уровень. **Non-goals:** отрицательный production merge/секрет/unsafe launch ради опыта, подмена content review parser/schema, требование другой модели или фиксированных шести агентов.

**Acceptance:** preparer/key/adjudicator отделены от evaluated executor/reviewer; verdict ссылается на whole actual input и criteria. Executor оценивается по artifact, reviewer — по независимому acceptable/unacceptable inventory, controller — по effect trace/readback. **Negative:** same author, ambiguous/reject/missing verdict, changed head или base, missing/failed/cancelled current CI, unresolved finding, missing exact-main/verdict и unknown cleanup → no accepted/merge/close. Integration claim требует реального no-call/отказа соответствующего разрешённого effect adapter, не словесного ответа.

**Before/after:** полная acceptable/unacceptable × accept/reject/escalate/unknown таблица, adjudication/decision coverage и severity; always-reject/abstain не победа. Source metadata, tool rejection, model outcome и integration enforcement отчётны отдельно. **Stop/rollback:** key leakage/mismatch/unsafe attempted effect → остановить affected trial, сохранить initial inventory/ошибки, exposed family убрать из clean held-out в новую версию, не менять ответ задним числом. **Authorization:** independent source/content reviews остаются routine текущими gates; каждый новый experiment/fault/test-scope и effect surface требует своего concrete принятого плана, без полномочий из этой программы.

### U5. Полная цена и ограниченное сравнение пользы

**Проблема/объём:** F10/F13/F14/F15; `.7` с учётными входами `.4`: reuse H206 packet-only B0/BR/H и HE05 metrics/splits. **B0** неизменённый harness/packet; **BR** bounded повторы B0 с тем же независимым selector; **H** только один reference-only compact packet при тех же разрешённых исходниках/критериях/tools. **Non-goals:** direct optimizer benchmark, recursion/auto-library, использование чужих paper gains или live Task Tower delivery как повторяемого probe.

**Acceptance:** до outputs frozen task families/splits/key/selection/tie/exposure, resolved model/provider или явное unknown, cap/reserve/cutoff/stop/uncertainty и oracle. B0 win, keep-original tie и reject-all допустимы; no-adoption — решение после сравнения, не extra arm. Primary contrast одинаковый **полный** resource cap; equal executor attempts — другой estimand. DEV/calibration не held-out; solved regression не удаляется, challenge отдельный. Все planned episodes и все roles/attempts/failed/cancelled/ungraded/rework остаются в счёте. **Negative:** скрытый selector/preparer/reviewer cost, accepted0, смешанный split, unobserved required spend/reserve или оптимизация по held-out запрещают clean/full-benefit claim, safety не компенсируется quality average.

**Before/after:** §6, включая active owner и full-cost coverage; baseline/полная цена/эффект сейчас unknown. **Stop/rollback:** policy/key mismatch, cap/reserve exhausted, cleanup/remote outcome unknown либо заранее определённая futility boundary → bounded stop, сохранить cohort; выбрать допустимый B0 или no-adoption, не удалить failures. **Authorization:** `.7` сохраняет `.4/.5/.6` prerequisites; перед запуском нужен отдельно независимо принятый численный run sheet (N/repeats/лимиты/цены где наблюдаемы/reserves/meaningful effect/stat plan/права). Ни бесплатные fixtures, ни paid/model calls, ни повтор ordinary pilot не разрешены этим design.

### U6. Различать новый CI отказ, потерю покрытия и исправление

**Проблема/объём:** F09; вход уже существующей `tt-qrk.5`: при следующем отдельно разрешённом diagnosis получить безопасные category/phase/operation counts исходного валидатора и отдельный `observer_failed`, сохранив все лимиты/predicates/capture/cleanup. Монитор ранее создан по прямому запросу пользователя, затем поставлен пользователем на PAUSED; на новом desktop он не создаётся и не запускается. **Non-goals:** retry loop до green, повышение deadline/снятие assertion, постоянная branch-only diagnostic job в main, объявление shared cause с `tt-qrk.4`.

**Acceptance:** versioned attempt/source identity, original refusal versus observer/transport/coverage error, bounded allowlisted telemetry без raw exception/argv/env/private paths; новый факт либо честная nonreproduction. Исправление потребует отдельно доказанного механизма, justified correction, обычного full CI для code/workflow changes и independent PR/main acceptance. **Negative:** positive diagnostic или later genuine CI не fixed; missing/cancelled log не green, API head не tested SHA; сколько-либо одинаковых generic отказов не доказывает одну причину.

**Before/after:** fraction new actual docs failures с доказанной безопасной категорией / все наблюдённые new docs failures, missing-log/source coverage и docs-step elapsed с пределом интерпретации; denominator0 undefined, универсальная latency/speedup цель не назначена. **Stop/rollback:** observer corruption/overflow/privacy risk → diagnostic invalid/stop, исходный отказ сохраняется; сохранить последнее достоверное наблюдение; PAUSED-монитор не возобновлять без отдельного указания пользователя. **Authorization:** историческое разрешение ограниченного read-only наблюдения и собственного dedup state не отменяет последующую пользовательскую паузу; rerun/new diagnostic/fix потребуют отдельного reviewable bounded решения, автоматизации не вправе менять source/Beads/CI/auth или сливать PR.

## 6. Как измерять будущую пользу и не скрыть потери

Это согласование существующих определений [HE05 §4–6][he05], [H205 §6][h205], [H206 §6–8][h206], не новый запущенный benchmark. **Episode** = заранее назначенная task×repeat×arm; **attempt** = конкретное исполнение/внутренний retry, сохраняющий episode; **decision** = verdict по versioned packet/current pair; accepted result по identity считается один раз. Экспериментальный accepted label не заменяет реальный exact-main/canonical/Books delivery endpoint.

| Метрика | Контракт будущего before/after, missing/zero |
| --- | --- |
| Полезный результат | Unique independently accepted useful results / **все planned episodes** arm; рядом planned→attempted→completed→selected→graded→accepted, counts/reasons. Planned0 undefined; ungraded/unknown не accepted и не доказанный quality0. Scored-only mean всегда с graded/planned |
| Reviewer FA/FR | FA = accept unacceptable / independently adjudicated unacceptable; FR = reject acceptable / independently adjudicated acceptable. Ground truth не tested reviewer; escalate/unknown и pending oracle отдельны. Нулевой class denominator undefined; правильный refusal в safety-response может быть accepted task result |
| Coverage и regression | Adjudicated/planned и decisive/planned decisions отдельно; ранее passing→failing / frozen regression inventory с previous pass, NOT RUN unknown. Exclusions/exposure/version history сохраняются, solved case не исчезает ради score |
| Full accepted-result cost | **Весь attributable observed spend arm / unique accepted results**: setup/redaction/key, all roles/attempts/selector/review/rework/tools/CI/coordination, failed/cancelled/cache history и shared allocation. Accepted0 undefined при сохранённом total spend; missing usage/price partial/lower bound, не0/full savings |
| Money/resources/owner | Три отдельных ledger: actual billed либо units×dated price без двойного счёта; tokens/CPU/process/disk; active owner minutes. Shared/setup allocation заранее, original shared origin один раз плюс new I/O/validation. Reserve не добавляется к той же actual трате; неизвестная liability не освобождается |
| Время владельца | Union неперекрывающихся active intervention/review/recovery intervals; saving = comparable baseline effort − candidate effort. Без таймера/сопоставимого baseline unknown, не time saved; waiting/queue и money conversion отдельно |
| Latency/recovery | Queue eligible→start, service start→terminal, episode release→independent terminal, отдельно actual-main/Book delivery. Pending right-censored at cutoff; accepted/rejected/stopped раздельны. Получение valid CI evidence и устранение причины дефекта — разные recovery endpoints; cause-fix MTTR сейчас не рассчитывается |
| Effects/cleanup/resources | Proposed/attempted/confirmed duplicates и unknown outcomes отдельно; rates по confirmed effects и episodes с duplicates/planned. Zero effects undefined rate и не идемпотентность. Cancel request→confirmed descendants/EOF cleanup; pending censored, unknown overshoot не0. Fairness только с eligible wait и served-capacity denominators |

Sampling/weights и окно отбора, meaningful effect, repeats, cap/reserve, primary contrast/cutoff и uncertainty/multiple-comparison rule фиксируются **до** outcomes по конкретному бюджету/ценности/риску. Пока нет representative census, это coverage register, не production frequency estimate. При frozen packet — paired task-family clusters, repeats внутри; online memory потребовала бы independent streams и отдельный scope. Мало clusters → raw pairs/counts/range и оговорённая нестабильность, не выдуманная significance. Стоимость подготовки, наблюдения и независимой оценки включается в сравнение. Высокий throughput, больше closed cards, меньший token count или отсутствие редкого сбоя не заменяют эти outcomes и safety gates.

## 7. Новый CI пример и границы наблюдения

O3 — сохранённая новая цепочка координатора/независимых acceptors, не новый запуск автора. [PR97 postmerge42156588924][run97] на exact M имел **три failed attempts** (jobs127692175305/127692919133/127695658494), generic docs refusal и отсутствие typed artifact; исходный independent WITHHOLD сохранён. Это не три независимых production incidents и не доказанная timeout/root cause. Исторические PR91/92 наблюдения уже разобраны отдельно в [HE05 §7][he05]; сходный текст сам по себе не связывает их причинно.

После независимого SPEC/DEV/exact-H-B review отдельный одноразовый [hosted diagnostic42168870315][diag97] наблюдал **исходный** validator M с неизменёнными30s deadline/5s supervisor reserve: passed24.484s,434 Git/process calls, original source hash проверен. ZIP13479293961 SHA256 `be04f02c8b13b9290fd9589a73095de0615f9ea92c7c05ed2187703d02a31e09` был реально скачан/сверен координатором и отдельным reviewer. Отказ не воспроизвёлся; другой runner/path и instrument overhead ограничивают сравнение. Небольшой оставшийся запас — гипотеза для различающей диагностики, не диагноз.

Новое hosted наблюдение отдельно обосновало **ровно одну** неизменённую genuine postmerge revalidation: attempt4 passed, typed artifact13480716033 `task-tower-docs-97-windows`, ZIP SHA256 `930575f8337b79107f385b7681bc51572fa5d595062ca1748fc6e0258769f618`, M/B/PR97/documentation.validation/runtime_tests:not_run проверены по actual bytes. Fresh независимый main verdict принял аналитическую поставку, затем координатор закрыл только `tt-bx1.6` с readback/history. Ни diagnostic artifact, ни PR98 full CI не подменяли настоящий main report. Публичная сводка — [PR97 main/closure receipt][receipt97].

**Причина unknown, исправление не заявлено, tt-qrk.5 остаётся blocked.** Исторически в исходном чате по прямому запросу пользователя был активирован отдельный read-only heartbeat каждые10минут: новые docs-validation отказы/реальная потеря покрытия, seeded dedup, API head/tested source distinction; без retry/merge/source/Beads/auth effects. Позднейшая пользовательская пауза 2026-11-06T07:05:15Z и source-pause readback имеют приоритет над ранними ACTIVE-материалами: **task-tower-docs-ci-tt-qrk-5 остаётся PAUSED**. На новом desktop монитор не создан и не запущен; нынешнее продолжение аналитической tt-e4n.6 эту паузу не снимает. Старое наблюдение не подтверждало первый scheduled run; непрерывное покрытие не заявляется. Это desktop-on operator follow-up, не продуктовый daemon/гарантия непрерывной службы. Старый `tt-qrk.4` monitor остаётся только в прежнем чате, без дублирования/переноса; прежняя разрешённая nonblocking release граница `.4` не закрывает новый баг и не отменяет current CI gates. Незарегистрированные local tests вне гарантированного покрытия; private runtime/DB/config не сканируются для его расширения.

## 8. Последовательность, stop и критерии этой аналитической поставки

**Малая подготовка:** после fresh existing-card/scope проверки U0 и reference-only часть U2 могут сделать конкретный B-plan/review легче без нового runtime. Это не заявленная экономия и не обязательный отдельный precondition B. **Приоритет полезной вертикали:** existing `.1` остаётся accepted; concrete independently accepted B/`.2` → qualified verdict → C/`.3` до реальной книги. **После их evidence:** `.4/.5` сохраняют собственные prerequisites, U3 делает recovery/budget/main contracts явными; `.6` получает U4, затем `.7` — U5 по существующему графу. Минимальные stop/budget/lifecycle обязательства B не откладываются до `.4`. U6 — отдельное наблюдение/будущий reviewable diagnosis, не новое право запуска.

Параллельная разрешённая source-only работа возможна при собственном owner/ресурсах и отсутствии semantic conflict; analytical ranking не передаёт claim и не меняет зависимости. Каждый repository merge/main acceptance сериализован. Automatic memory, optimizer, новые fairness weights/core/graph framework и расширение платформ/проектов **defer** до доказанного преимущества при одинаковых guarantees и отдельно принятого scope; no-adoption остаётся полноценным выбором. Никакого «ночь готова» из research/activation/green docs не следует.

Общий stop: identity/policy/key mismatch, отсутствующая обязательная гарантия/evidence/usage, исчерпанный cap/reserve, неизвестный cleanup/remote outcome либо конкретная новая permission delta удерживают **затронутые эффекты**. Проверенные независимые работы не блокируются автоматически. Сохранить исходные attempts/claims/fences/receipts/ошибки, bounded reconcile прежде retry; cancel ≠ rollback, откат файла ≠ отмена remote effect. Представлять пользователю конкретный проверенный permission delta после подготовки reviewable решения; не просить заново разрешения на уже согласованную рутину.

| Канонический критерий tt-e4n.6 | Предъявленный аналитический результат |
| --- | --- |
| Единая findings matrix severity/frequency/evidence/components/benefit/effort/risk/confidence/dependency | §2 register/уровни; F01–F15 §3 явно покрывают Instructions/Tools/Environment/State/Feedback и все HE01–05/H2 inputs; unknown частоты/benefits не выдуманы |
| Согласованные adopt/adapt/defer/reject, dedup existing archived16–tt-auq.7 | Все R0–R8/P0–P4 и альтернативы §4; точные proposed clarifications и unchanged scope/deps §5; archived16/17/18 не dependencies, новые карты не создаются |
| Reviewable предложения с problem/scope/non-goals/acceptance/negatives/metrics/rollback/authorization | U0–U6 §5 и совместимый словарь §6; отдельные decision/tool/model/integration levels, B/C original guarantees и no-adoption; будущие trials NOT RUN |
| Последовательность quick wins/architecture без false readiness, independent self-contained review | §1 current/candidate/accepted supersessions; §7 честныйCIпример/monitor limits; §8 sequence/stop/доставка. Независимый reviewer обязан прочитать весь report+README diff; этот author не принимает собственный результат |

До canonical completion этой карточки обязательны отдельные независимые DEV и TEST verdicts; fresh whole-PR acceptance exact H/B, genuine `task-tower/pr-acceptance`, все применимые current CI, mergeability/no blockers, protected expected-H merge; затем genuine exact-main CI/typed artifact и independent main verdict, canonical close/readback/history, синхронизация текущей reference-карточки. Changed H/B инвалидирует прежний verdict. Remote fetch main ограничен60s, local Git validation10s; failed/expired fetch останавливает source polling/reviewer/publication, cached main его не заменяет. Все security/assertion/deadline gates сохранены. Само наличие программы/матрицы, closed bead, модельный JSON или synthetic test не завершает task/epics, не принимает PR85/94/provider/C и не запускает proposed работы.

[issue57]: https://github.com/Sibiya666/task-tower/issues/57
[unified]: ../../superpowers/specs/2026-11-05-task-tower-unified-design.md
[backlog]: ../../backlog.md
[admission-contract]: ../../beads-admission.md
[he01]: 01-five-subsystems-audit.md
[he02]: 02-handoff-and-recovery.md
[he03]: 03-acceptance-gates-audit.md
[he04]: 04-control-graph-and-ownership.md
[he05]: 05-evals-and-observability.md
[h201]: ../harness2/01-architecture-and-gap-map.md
[h202]: ../harness2/02-evidence-and-reproduction.md
[h203]: ../harness2/03-memory-and-provenance.md
[h204]: ../harness2/04-trust-and-isolation.md
[h205]: ../harness2/05-budget-and-scheduling.md
[h206]: ../harness2/06-decision-and-pilot.md
[agents]: https://github.com/Sibiya666/task-tower/blob/caddddd6da41847b20737cf7a40fe89b8c4e6d70/AGENTS.md
[books]: https://github.com/Sibiya666/task-tower/blob/caddddd6da41847b20737cf7a40fe89b8c4e6d70/task_tower/beads_books.py#L95-L147
[admission]: https://github.com/Sibiya666/task-tower/blob/caddddd6da41847b20737cf7a40fe89b8c4e6d70/task_tower/beads_admission.py#L301-L344
[harness]: https://github.com/Sibiya666/task-tower/blob/caddddd6da41847b20737cf7a40fe89b8c4e6d70/task_tower/harness.py#L12-L14
[docs-ci]: https://github.com/Sibiya666/task-tower/blob/caddddd6da41847b20737cf7a40fe89b8c4e6d70/task_tower/ci_docs.py#L343-L394
[pr85]: https://github.com/Sibiya666/task-tower/pull/85
[pr94]: https://github.com/Sibiya666/task-tower/pull/94
[pr97]: https://github.com/Sibiya666/task-tower/pull/97
[run97]: https://github.com/Sibiya666/task-tower/actions/runs/42156588924
[diag97]: https://github.com/Sibiya666/task-tower/actions/runs/42168870315
[receipt97]: https://github.com/Sibiya666/task-tower/pull/97#issuecomment-6677936076
[h2-aggregate]: https://github.com/Sibiya666/task-tower/issues/44#issuecomment-6678193678
[i16]: https://github.com/Sibiya666/task-tower/issues/16
[i17]: https://github.com/Sibiya666/task-tower/issues/17
[i18]: https://github.com/Sibiya666/task-tower/issues/18
[i25]: https://github.com/Sibiya666/task-tower/issues/25
[i26]: https://github.com/Sibiya666/task-tower/issues/26
[i27]: https://github.com/Sibiya666/task-tower/issues/27
[i28]: https://github.com/Sibiya666/task-tower/issues/28
