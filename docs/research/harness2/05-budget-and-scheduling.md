# Harness²: полная стоимость рекурсии и границы планирования

Дата: 2026-11-06. Задача `tt-bx1.5`. Upstream: `google-research/harness2@6868817518876de8fd170c6a8354daca273b6191`; принятая база Task Tower: `e5347b9cbfb7e36fad0d0cf1c1f02b6d5bbb0caf` после PR95. Исследованы исходники; модели, upstream, native, продукт и предлагаемые эксперименты **НЕ ЗАПУСКАЛИСЬ**. Политики ниже **НЕ РЕАЛИЗОВАНЫ**. Все числовые сценарии стоимости и времени — **ГИПОТЕЗЫ / НЕ ИЗМЕРЕНО**.

**4k/3k описывают структуру работы, но не полный счёт.** Для решения о рекурсии нужны стоимость всех попыток и ролей, ограничения ресурсов и независимо принятые полезные результаты. В проверенном core ledger rollout записывается без фактической цены executor; равные структурные бюджеты не доказывают равенство денег, времени или качества. Предлагаемый первый шаг — полный измерительный контракт и сравнение с неизменённым harness; внедрение optimizer или нового scheduler сейчас не обосновано.

## 1. Что действительно считает закреплённый код

| Наблюдение и первичный источник | Вывод и предел |
| --- | --- |
| `expected_rollouts`, `expected_sessions`, `Ledger.assert_identity`: R=4k, P=3k, проверяются количества и повторные labels. [ledger:15–125][ledger] | Это логические записи на mode/task, включая неудачные слоты; проверка identity не доказывает успешное исполнение или оплату. |
| `run_task` создаёт k base IDs, один раз вызывает `_roll_bases`, затем передаёт **тот же base list** в каждый mode; modes обходятся последовательно. Полный отказ всех bases завершает задачу раньше рекурсии. [schedule:634–714][schedule-task] | Shared base действительно есть в этом caller. Нормальная полная схема не описывает ранний выход, частичное выполнение или fresh spend при resume. |
| Parallel: 2k INV/DOM stages/probes, затем k independent compositions/finals; sequential: k раундов INV+DOM+composition с переходом current harness/history. [recursion:354–576][modes] | Оба mode имеют те же R/P, но разные зависимости и объём evidence; «parallel» не означает одновременные независимые задачи Task Tower. |
| `_roll`, `_roll_many` вызывают adapter и записывают `ledger.rollout(label)` без usd; `RunView.cost_usd/wall_s` имеют defaults0 и здесь не заполняются. Shared bases также заносятся без цены. [recursion:271–350][roll]; [spec:177–187][runview]; [modes][modes] | `ledger.usd` в этих путях не содержит фактический executor spend. Нулевое поле не является доказательством бесплатного rollout. Полный cost из одной этой суммы получить нельзя. |
| `_run_stage` ограничивает invalid-proposal попытки, передаёт transport limit, на transport exhaustion прекращает stage, на invalid tree может повторить и затем fallback. [recursion:141–268][stage] | P считает stage один раз; `session_attempts` суммирует учтённые транспортные session attempts, не API requests и не весь run. Fallback не исчезает из затрат. |
| `Proposer.call` проверяет cache до запуска; на cache miss создаёт session workspace, повторяет helper с задержкой, учитывает полученный cost. Cached Reply возвращает cost0; timeout/exception может не вернуть фактический billed cost. [proposer:117–199][call]; [333–379][cache] | Fresh reported cost, историческая цена cache и неизвестный billed spend — разные величины. Один helper/session способен выполнить много API requests. |
| k=1 использует `trivial_selection`; при library и `sel.ok` вызывается reflection; `_distil` делает дополнительный `prop.call`. [schedule:550–600][select-call]; [selection:360–399,402–486][reflection] | Selector может отсутствовать, reflection — остаться. Они не входят в3k. Ни trivial selection, ни reflection не заменяют независимую приёмку Task Tower. |
| WorkBuddy `execute` может вернуть reusable trial; `execute_many` обслуживает k replicates одним batch и при нехватке запускает substrate. [workbuddy:753–857][adapter] | k логических rollouts не равно k новых ОС-процессов. Внутренний runner может иметь свою работу/повторы; R не ограничивает их число. Это конкретный adapter, не универсальная гарантия остальных. |
| Judge вызывает `adapter.score`; WorkBuddy читает verifier score, а report исключает ungraded из средних. [judge:67–159][judge]; [workbuddy:986–1004][score]; [report:80–110][report] | Grading не всегда новый model call в core. Стоимость verifier может возникать раньше; учитывать по реальным receipts ровно один раз. Нельзя считать только graded outcomes и забыть остальные затраты. |
| CLI report суммирует `stages[].usd + selections[mode].usd`; `_distil` добавляет reflection cost в selection usd. Вывод явно называется improver spend. [cli/report:37–55,104–108][report-spend]; [selection:481–486][reflection] | Здесь учтены reported editor/composer/selection/reflection суммы, но не полный executor/judge/CI/review/coordination bill. Утверждение «reflection вообще потеряна» тоже было бы неверным. |

Уверенность в этих source facts высокая для указанной ревизии; перенос на runtime/оплату Task Tower не проверен. Результаты [evidence-аудита](02-evidence-and-reproduction.md), [memory-аудита](03-memory-and-provenance.md) и [trust-аудита](04-trust-and-isolation.md) остаются контекстом. Отсутствуют исходные provider usage/billing receipts, измерения времени/процессов/диска и сопоставимые принятые результаты Task Tower; неизвестное не достраивается из приватных DB/config или старых pipeline logs.

### Структурная арифметика с правильным знаменателем

Для **одного полностью дошедшего до ledger identity mode**: `R=k base+2k probes+k finals=4k`; `P=k INV+k DOM+k compositions=3k`. Для m modes одного `run_task`, использующих те же k bases: сумма per-mode ledger R равна `4km`, но уникальных запланированных rollout-слотов `U=k+3km`. При двух modes U=7k, а сумма R=8k. P суммарно3km. Дедупликация относится только к shared bases; разные modes имеют отдельные namespaces/работу. Это вывод из [caller][schedule-task] и [mode functions][modes], не число успешных попыток или новых API запросов.

| k — пояснительный параметр | Один mode: R / P | Два modes: сумма R / уникальные U / сумма P |
| --- | --- | --- |
| 1 | 4 / 3 | 8 / 7 / 6 |
| 2 | 8 / 6 | 16 / 14 / 12 |
| 5 | 20 / 15 | 40 / 35 / 30 |

При cold run без reuse U — число запланированных executor slots; свежие физические запуски могут отличаться из-за adapter batching/internal trials, cache, ошибок и раннего выхода. При полном resume scheduler может вернуть `status=skipped` с сохранёнными modes, не выполняя эту схему заново. [schedule:433–464,665–668][resume]. Старые receipts сохраняют происхождение и исходную цену.

В данном config `STAGE_ATTEMPTS=2`, `TRANSPORT_ATTEMPTS=2`: один stage может дойти до четырёх helper invocations, если обе validation attempts потребовали по две transport attempts. Exhausted transport обрывает stage; cache или ошибка сборки context могут дать ноль новых вызовов. Это локальная граница `_run_stage`/`Proposer.call` при этих константах, **не** верхняя граница provider API requests, rollouts или всего run. Selector/reflection используют собственный `prop.call` путь. [stage][stage], [call][call], [config:175–179][config].

## 2. Полная стоимость — вектор, а не одно поле usd

Единица сравнения — заранее заданный **episode = task × repeat × arm**. Attempt — связанная с ним попытка; stage, executor rollout, provider request и процесс считаются отдельно. Для каждой записи нужны project/repository/bead, episode/run/attempt/parent, role/stage, source/harness/model/provider/policy/input identity, start/end/outcome, cache origin и coverage `observed/partial/unknown`. Unknown отличается от not_applicable. Это предлагаемый ledger доказательств, не новая очередь или ownership store. [Принятый словарь evals](../harness-engineering/05-evals-and-observability.md).

| Компонент | Единица и агрегирование | Недостающие данные и защита от двойного счёта |
| --- | --- | --- |
| Tokens/API | Input, output, provider-cache-read/write tokens; actual request count; money по provider/model/валюте/дате тарифа и billing unit | Если категории cache входят в input, разделить их на непересекающиеся billable buckets. Pricing/usage unknown остаются параметрами; session count не заменяет requests. |
| Executor/editor/selector/reflection/judge/tools | Все роли, attempts/retries и tool/compute charges; отдельно actual billed и оценка | Если total session price уже включает tokens/tools, компонентный расчёт служит расшифровкой, не добавляется повторно. Встроенный verifier не оплачивается второй раз как гипотетический новый judge call. |
| Процессы/compute | Starts, peak concurrent processes, process-seconds, CPU-seconds, peak memory при доступном измерении | Сумма длительностей — работа; peak и elapsed — другие метрики. Tree ребёнка и launcher не считать одной абстрактной «моделью». Unobserved children отмечаются как gap. |
| Диск | Peak bytes, сохранённые bytes × время, artifact count, copy/read/write при необходимости | Parallel peak и retention — разные расходы. Copies/library/harvest/cache занимают место даже при нулевом новом model spend; deletion/retention policy этим отчётом не меняется. |
| CI | Billed runner-minutes по типу runner, actual job durations и queue отдельно; все попытки PR/main | Matrix wall time не равен сумме billed job time. Docs validation и full runtime route имеют разные покрытия; отсутствие runtime тестов не означает их прохождение. |
| Review/coordination/owner | Active independent review, rework, orchestration и owner minutes, отдельно queue/wait | Цена человеческой минуты — необязательный заранее согласованный параметр, не скрытый0. Разные агенты расходуют и tokens/API, и effort; нельзя дважды монетизировать один расход. |
| End-to-end | Authorized release→independent terminal decision; отдельно accepted-main delivery endpoint, queue/service/wait spans | Использовать actual UTC identities и локальные monotonic durations; missing endpoint — censored, не0. Parallel wall time определяется critical path, не суммой. |

Для непересекающихся billable token buckets b: `M_tokens=Σ_b N_b × price_b / billing_unit_b`. Затем `M_total=M_tokens+не включённые request/tool/compute/CI charges`; либо actual billed totals с компонентной сверкой. Цены неизвестны, поэтому здесь нет актуального денежного прайса и запроса к аккаунтам. Money, resource work и active owner time публикуются отдельными ledgers; объединить их можно лишь с явными conversion и без double counting.

**Cache не означает бесплатную историю.** Provider prompt-cache discount применяется к части tokens; whole-session/rollout reuse может не запускать модель вообще. В последнем случае публикуются incremental new spend, validation/I/O и исходный receipt/cost отдельно. Для cohort историческая работа распределяется по объявленному правилу либо показывается отдельной fixed setup cost; shared receipt учитывается один раз. `_call_fingerprint` включает mission/system/label/context path/files, но не model/effort; внешний CLI identity guard отдельно сверяет models/tasks. Cache hit сам по себе не доказывает пригодность или acceptance. [proposer:500–527][fingerprint], [CLI:209–235][cli-identity]; подробные ограничения — [memory](03-memory-and-provenance.md).

## 3. Breadth, depth, retries и задача без оптимизации

Три arm сохраняют одинаковые task/source/model/provider/policy/oracle и неизменные security/acceptance gates: **B0** неизменённый harness, **BR** bounded retries того же harness с сопоставимым независимым выбором, **H** bounded recursion. Основное сравнение — при одинаковом **полном resource cap**; вторичное — при равном числе executor attempts. Эти нормировки не взаимозаменяемы. Все planned episodes, failed/cancelled/ungraded/unknown attempts и причитающийся review включаются. Release selection исключает base и не предусматривает abstention; возможность baseline win / keep-original / reject-all — наше предложение, не существующий flag. [selection:93–111][pool], [evidence](02-evidence-and-reproduction.md).

При условных постоянных временах p для improvement stage и e для rollout и ширинах wp/wr, без retries/cache/queue:

- Parallel: `Tpar≈ceil(k/wr)e + ceil(2k/wp)p + ceil(2k/wr)e + ceil(k/wp)p + ceil(k/wr)e + O`.
- Sequential: `Tseq≈ceil(k/wr)e + k[ceil(2/wp)p + ceil(2/wr)e + p + e] + O`.
- Суммарная работа одного mode: `W≈4ke+3kp+Wextra`; O — elapsed дополнительного critical path, Wextra — дополнительная работа. Они не обязаны совпадать.

Это учебная модель фаз, не оценка runtime. В actual functions default phase width2, proposer semaphore2; domain streams могут конкурировать за него, а adapter запускает свою работу. Context/history растёт в sequential; p/e не обязаны быть постоянными. `--workers` ограничивает domains, задачи внутри domain идут по порядку. **k — рекурсия внутри task; task WIP, domain workers, stage width и предел процессов — разные оси.** [modes][modes], [proposer:41–42,140–155][call], [config][config], [schedule:752–780,848–903][streams], [guide:6–28][guide].

### Sensitivity: расчётные примеры, НЕ ИЗМЕРЕНО

Пусть условная единица затрат CU: executor slot e=1 CU, editor invocation p=0,2 CU, совокупный дополнительный расход g=2 CU/episode. Нет reuse/retries; один mode. Тогда `C(k)=4ke+3kp+g`. Это не доллар, token или quality score; g лишь показывает, что overhead нельзя выбросить. Реальный g зависит от k и workflow.

| Изменённое условие | Расчёт | Что меняется в решении |
| --- | --- | --- |
| k=1 / 2 / 5 | 6,6 / 11,2 / 25 CU | Цена растёт; quality improvement здесь неизвестен. Числа k не являются operational cap. |
| k=5, editor дороже: p=1 вместо0,2 | 20+15+2=37 CU | Отношение editor/executor price и длина context могут сделать оптимизацию доминирующим расходом. |
| k=5, на25% больше editor invocations | 20+15×1,25×0,2+2=25,75 CU | Условная частота retry — параметр; не выведена из константы attempts. |
| k=5, половина rollout slots reused | 10+3+2=15 CU **incremental** | Историческая цена reused outputs и I/O остаются отдельно; это не amortized total и не доказанная cache-hit rate. |
| k=5, overhead g=6 вместо2 | 20+3+6=29 CU | Selector/judge/CI/review/coordination могут изменить вывод даже при том жеR/P. |
| k=5, p=2/e=10 условных единиц времени; ширины1→2 | Parallel elapsed230→126, работа230 в обоих; sequential при ширине2:150 | В этой модели ширина снижает latency, сохраняя работу и увеличивая peak demand. Дополнительные I/O/process overhead способны увеличить total cost; реального speedup не измерено. O=0 только в примере. |

Контрпример «дешевле значит лучше»: два **синтетических** cohort по10episodes: A тратит100CU и имеет5accepted →20CU/accepted; B тратит60CU, но2accepted →30CU/accepted. Снижение spend не гарантирует эффективность. Эти числа объясняют знаменатель, не являются результатом модели или выбором качества.

**Break-even с фиксированным качеством.** Для cohort общей стоимостью C и independently accepted useful results A, дополнительная рекурсия с ΔC/ΔA улучшает отношение только если `A>0`, `ΔA>0` и `ΔC/ΔA<C/A`. Это алгебра, не прогноз ΔA. До будущего опыта нужны фиксированные oracle/rubric, held-out split, comparable tasks, predeclared caps/retries и uncertainty rule; paired/clustered analysis и coverage следуют [evals](../harness-engineering/05-evals-and-observability.md). При неизвестном или неустойчивом ΔA вывод «выгодна» недоступен. В equal-cap опыте сравнивается accepted yield при cap, а не объявляется равенство actual spend. Safety violation не компенсируется средним quality.

| Решение о следующем increment — предложение | Условие и действие |
| --- | --- |
| Не допускать / остановить новое optional refinement | `observed consumption + outstanding reservations + bounded next increment + required reserve > cap` хотя бы по одному ресурсу; либо не хватает времени до абсолютного deadline. Сохранить review/CI/cleanup reserve; не ослаблять gates. |
| Остановить по evidence/safety | Identity/policy mismatch, contamination, запрещённый эффект, missing required evidence, неизвестный внешний исход/cleanup. Сохранить unknown; сначала bounded readback/reconcile, не replay. |
| Остановить по отсутствию доказанной предельной пользы | Предварительно зафиксированное правило uncertainty не подтверждает meaningful gain при прежнем качестве; retain baseline/reject-all допустимы. Нужны данные будущего разрешённого pilot, сейчас порог — неоткалиброванное operator decision. |
| Продолжить bounded increment | Есть полномочия/owner, reserve, resource headroom и заранее определённый вопрос, который increment может проверить; не обещание принятого результата. |

Safety/cap stop не является статистическим доказательством diminishing returns. Нельзя подстраивать acceptance threshold по held-out, заменять трудные задачи лёгкими, снимать assertions/timeouts или исключать независимый review ради экономии. Cost cap ограничивает расход, а качество остаётся условием acceptance.

## 4. Предлагаемый контракт admission и отмены

Принятый `beads_admission.observe` выдаёт readiness observation, не claim/launch; installed harness preparation не заявляет callbacks/resume/independent review/autonomous merge. Unified direction требует B→C и сохраняет budgets/recovery/fault/benefit obligations. Поэтому ниже **проект политики**, не утверждение о shipped scheduler. Beads остаётся task/dependency/history authority, Books read-only; archived pipeline/groups — исторические ссылки. Agent count зависит от задачи, независимая содержательная приёмка обязательна. [admission:232–254,329–338][tt-admission], [harness:12–14][tt-harness], [unified][tt-unified], [backlog][tt-backlog].

**Envelope project/task/attempt** связывает bead/run/owner/source/policy с absolute deadline; token/request limits и известным monetary cap при верифицированных price/usage; k/retry limits; peak processes/parallelism/memory/disk и retention envelope; резервом CI/review/cleanup. Если цена неизвестна, token/request cap честно ограничивает эти единицы, но не доказывает денежную границу. Неизвестный hard-required usage не даёт безопасно обещать следующий increment. Численные caps, веса и reserve устанавливаются позже по scoped измерениям/risk/operator policy; здесь production значений нет.

Перед effects отдельно нужны свежая readiness, atomic canonical claim с owner readback и имеющаяся project authorization. Reservation не выдаёт полномочия и не заменяет claim. Перед bounded increment резервируется его консервативная потребность плюс ещё необходимые review/CI/cleanup; после подтверждённого завершения reserve превращается в observed spend и освобождается лишь проверенный остаток. Concurrent reservations включаются в cap вместе с consumed; absolute deadline не сдвигается после retries. Политика не разрешает модели, аккаунты, другой проект или второй engine.

| Фаза cancellation — предложение | Что сохраняется / будущее необходимое evidence, сейчас NOT RUN |
| --- | --- |
| Stop-new-work | Отмена admission следующих stages/retries с event/source/owner identity. Canary: после cancel нет новых запрещённых launch/effect calls. |
| Trusted cancel текущего executor | Fixed trusted host interface, его acknowledged/unknown result; строка «cancelled» от worker не доказывает остановку. Canary: реальный supervised child получает cancel, дедлайн сохраняется. |
| Подтверждение cleanup | Child/process tree termination и освобождение локальных ресурсов с actual readback; до него reservation и uncertain usage не обнуляются. Canary: родитель/ребёнок/зависшая попытка, включая timeout, имеют наблюдаемый terminal outcome. |
| Reconcile artifacts/effects | Сверка effect identity/readback, сохранение original receipts и unknown fences; неизвестный remote effect не повторяется. Canary: lost acknowledgment приводит к reconcile, а не duplicate call. |
| Release verified remainder | Возврат только подтверждённо свободной части reserve, retained disk и понесённый spend остаются в cohort. Failed/cancelled не становится accepted/free. Canary: accounting включает сорванные и повторные attempts. |

Это требования будущей квалификации/испытаний, не fault evidence. Реальные state/receipts не удаляются; старые workers не запускаются. Смена retention/lifecycle требует отдельной принятой политики.

## 5. Per-project fairness без второй очереди

Для одной Windows-машины сначала разумно проверить **простые project caps + round-robin на безопасных bounded stage boundaries**, с отдельным task WIP и stage width. Сравнивать с weighted multi-resource reservations стоит лишь при наблюдаемом contention: доля проекта по ресурсу r `share_pr=reservation_pr/capacity_r`, dominant share — максимум этих долей; вес определяет entitlement, а не authorization. Приоритет/age могут выбирать следующий eligible increment в пределах caps. Это аналитическое предложение, не реализация алгоритма и не гарантия fairness.

| Failure mode | Предлагаемое ограничение и наблюдение |
| --- | --- |
| Один recursive task занимает всё | Per-task width и per-project reservation; bounded safe quantum, wait/served-share по проектам. k не увеличивает entitlement. |
| Малый проект всегда уступает активному | Round-robin/aging среди eligible projects; измерять max observed eligible wait и denied-for-budget причины, не объявлять finite wait guarantee без bounds. |
| Большая допустимая работа никогда не помещается | Aging с планируемым освобождением capacity/накоплением entitlement; max admissible chunk должен помещаться. Если минимальный безопасный chunk превышает ceiling — explicit infeasible/escalate, не starvation и не превышение лимита. |
| Дешёвая непрерывная работа вытесняет дорогую / лишняя сложность | Сравнить fixed caps/round-robin с weighted shares по accepted yield, tail wait и coordination overhead. Если улучшение не подтверждено, оставить простой вариант. Веса/кванты сейчас гипотезы. |
| Конфликт component/owner/dependency или main barrier | Eligibility/semantic ownership важнее fairness. Не прерывать unsafe effect; сохранять owner/unknown fence. Merge/main acceptance сериализованы **по repository**; ready analysis другого проекта не доказывает permission на него. |

Executor throughput ограничен также review, CI и serialized main service. В стационарной идеализации accepted throughput не превышает минимум их пропускных способностей; реальная зависимая очередь требует наблюдений, здесь их нет. Поэтому увеличение WIP/k/width может только увеличить waiting и stale-base rework. Считать caps или rotation «поставленным persistent pool» нельзя. Это материал для существующих `tt-auq.4/.5/.6/.7`, без их активации/закрытия и без изменения B/PR85 HOLD.

## 6. Метрики принятого результата и решение

| Метрика | Точное определение / missing, zero и censoring |
| --- | --- |
| Cost per accepted useful result | `Σ attributable cohort costs / unique independently accepted useful results cohort`, отдельно money/resource/active owner ledgers. В numerator все attempts/roles/failures/cancellations/retries/tools/review/CI/coordination и attributable setup; shared cost allocation фиксируется заранее. Accepted=0 → **undefined**, показать spend и0accepted. Missing spend → partial coverage, а не полный счёт или0. |
| Fixed / marginal / amortized | Setup/shared origin отдельно от новых increments; allocation по episodes или uses задаётся до сравнения и публикуется. Показывать both total cohort и marginal, не прятать fixed cost за произвольным большим denominator. |
| Coverage и yield | Planned→attempted→completed→selected→graded→accepted с count/причиной потери; accepted/planned, planned=0 undefined. Ungraded/unknown не увеличивают accepted и не превращаются автоматически в quality0. |
| Time-to-accepted / delivery | Release→independent acceptance; отдельно release→accepted exact-main/canonical delivery. Pending в cutoff right-censored; rejected/cancelled terminal spans отдельно. Не время до первого output или execution_completed. |
| Rework / overshoot | Review correction attempts и resource spend до acceptance; overshoot=`max(0,actual-cap)` в каждой единице. Unknown actual → unknown overshoot, не0. |
| Fairness | Per-project eligible enqueue→actual start/next service wait, observed tail/max wait, served resource share за фиксированное окно; blocked dependency/unauthorized отдельно от ready-wait. Без served capacity/eligibility denominators «равенство числа задач» не доказывает fairness. |
| Cancel/unknown | Cancel request→confirmed cleanup; pending cleanup censored в cutoff, отдельно counts attempted/acknowledged/confirmed/unknown и unknown effects. Быстрый acknowledgment не равен cleanup. |

Cohort заранее фиксирует задачи/repeats/arms, follow-up cutoff, source/model/policy/oracle и endpoint. Поздняя acceptance добавляет versioned follow-up, не переписывает старое окно; incomplete cohorts сравниваются с coverage/censoring, не как complete savings. Нужна независимая ground truth, а не самооценка selector. User-time saving требует сравнимого baseline owner effort. [evals](../harness-engineering/05-evals-and-observability.md).

**Решение: adapt как требования к evidence/accounting; defer optimizer и scheduler implementation.** Сейчас можно принять определения единиц, полный denominator, separate cache lineage и правило остановки optional refinement при сохранённых quality/security gates. Нельзя выбрать экономически лучший k/mode, установить production caps/weights или заявить savings без scoped usage/time/cost/quality measurements. Следующее отдельно разрешённое исследование могло бы проверить B0/BR/H с независимым oracle и одинаковым total cap; оно здесь NOT RUN. Документ не завершает parent epic, B/G1/G2/C, `tt-auq.4–.7`, не снимает PR85 HOLD и не чинит `tt-qrk.4`.

Независимые SPEC/DEV/TEST и whole-PR exact head/base, genuine acceptance status, фактически применимый успешный CI, expected-head merge, serialized exact-main acceptance и каноническое closure/readback остаются обязательными. Сам отчёт, docs artifact и закрытый bead не заменяют эти свидетельства. Приватные пути/настройки/credentials/runtime dumps не публикуются; здесь выполнены только чтение источников, расчётная сверка и статические проверки документа.

[ledger]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/ledger.py#L15-L125
[schedule-task]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/schedule.py#L634-L714
[modes]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/recursion.py#L354-L576
[roll]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/recursion.py#L271-L350
[runview]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/spec.py#L177-L187
[stage]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/recursion.py#L141-L268
[call]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/proposer.py#L117-L199
[cache]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/proposer.py#L333-L379
[select-call]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/schedule.py#L550-L600
[reflection]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/selection.py#L360-L486
[adapter]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/workbuddy.py#L753-L857
[judge]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/judge.py#L67-L159
[score]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/workbuddy.py#L986-L1004
[report]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/report.py#L80-L110
[report-spend]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/report.py#L37-L108
[resume]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/schedule.py#L433-L464
[config]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/config.py#L175-L179
[fingerprint]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/proposer.py#L500-L527
[cli-identity]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/run_sweep.py#L209-L235
[pool]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/selection.py#L93-L111
[streams]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/schedule.py#L752-L903
[guide]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/docs/EXPERIMENTS.md#L6-L28
[tt-admission]: https://github.com/Sibiya666/task-tower/blob/e5347b9cbfb7e36fad0d0cf1c1f02b6d5bbb0caf/task_tower/beads_admission.py#L232-L338
[tt-harness]: https://github.com/Sibiya666/task-tower/blob/e5347b9cbfb7e36fad0d0cf1c1f02b6d5bbb0caf/task_tower/harness.py#L12-L14
[tt-unified]: https://github.com/Sibiya666/task-tower/blob/e5347b9cbfb7e36fad0d0cf1c1f02b6d5bbb0caf/docs/superpowers/specs/2026-11-05-task-tower-unified-design.md
[tt-backlog]: https://github.com/Sibiya666/task-tower/blob/e5347b9cbfb7e36fad0d0cf1c1f02b6d5bbb0caf/docs/backlog.md
