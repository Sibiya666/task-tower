# Harness²: доказательства эффекта и план воспроизведения

Дата: 2026-11-05. Задача `tt-bx1.2`; upstream `google-research/harness2@6868817518876de8fd170c6a8354daca273b6191`, принятый Task Tower main `e021e0c8c38f1ea9af6bf1860d2eedcff97edca1`. Изучены первичные исходники и статья; upstream, модели, тесты продукта и предлагаемые ниже эксперименты **НЕ ЗАПУСКАЛИСЬ**. Это не воспроизведение опубликованных процентов и не оценка ожидаемого выигрыша Task Tower.

**Доказательств достаточно, чтобы обосновать отдельное сравнение, но недостаточно для переноса заявленного выигрыша в Task Tower.** В release исходный baseline исключён из выбора финального результата, при k=1 selector не вызывается, ошибки judge исключаются из среднего, а обычный запуск не восстанавливает автоматически paper split. Полезный следующий результат — заранее определённый протокол с исходным harness как допустимым победителем, полным учётом неудач и отдельной проверкой загрязнения данных.

## Что опубликовано и насколько этому соответствует release

Pinned README ведёт на arXiv2610.14224. [Карточка arXiv][paper-abs] указывает единственную опубликованную версию v1 от9октября2026; [PDF v1][paper] содержит титульную дату12октября. Версия зафиксирована явно: commit репозитория не доказывает побайтовое соответствие всем экспериментальным окружениям статьи.

В статье: executor Gemini3.5Flash/GLM-5 × OpenCode/Codex; editor ClaudeOpus4.8; k=1 и parallel k=5. Три независимых потока, mean/SD. Test: WorkBuddy40/35/25 задач code/web/office; JobBench34 из65; LAB100, dev24 отдельно. Судьи: WorkBuddy Gemini3.5Flash, JobBench Opus4.8, LAB Sonnet4.6. Результаты — условные на эти выборки/судей. [§3.1, приложения B–D][paper].

| Claim | Первичное evidence и условия | Confidence и предел вывода |
| --- | --- | --- |
| До +11,5 пункта WorkBuddy | Table1: GLM-5/OpenCode, k=1, macro-average64,2→75,7 | Высокая уверенность в соответствии headline таблице; независимого воспроизведения нет |
| До +4,5 пункта JobBench | Table2: Gemini/OpenCode, k=1, score31,5→36,0 | Подтверждает опубликованное сравнение, не абсолютную долю принятых задач Task Tower |
| До +11,8 п.п. LAB | Table2: GLM-5/OpenCode, k=1, Partial59,6→71,4 | Partial — доля критериев, не all-pass задач |
| Не универсальное превосходство | Table2: Gemini/Codex LAB, Harness²75,6 против Meta-Harness76,5 | Отрицательное ограничение headline; лучший метод зависит от ячейки |
| Parallel k=5 улучшает k=1 | Tables1–2, те же четыре конфигурации/test sets: WB Avg.+2,9–3,9; JB+3,0–4,2; LAB Partial+2,6–6,7 | Опубликованные изменения средних; дополнительный compute, не равнобюджетный выигрыш |
| Library помогает дальнейшей адаптации | §4/Fig7, Gemini/OpenCode: JB-library→WB, k=1, code/web/office дополнительно +0,6/+0,5/+2,9 | Поддержка конкретного cross-benchmark переноса; не гарантия нового домена |
| Leave-one-out reuse улучшает score | AppE.2/Fig11, k=1: WB77,5→79,4; JB36,0→37,7 | Offline completed-library без собственной записи, но с позднейшими задачами; повторное исполнение — confound, не online gain |
| Harness переносится между моделями | AppE.3/Fig12: Gemini3.5/OpenCode→GLM-5/Gemini3.7/Opus4.8, без дополнительной адаптации, WB code/office | Условный cross-model эффект; величина зависит от executor/domain |
| Release сохраняет условия воспроизведения | Guide требует одинаковые model/task/network settings; JobBench revision фиксируется только после download | Проверяемое требование и metadata-механика; нет собственного свидетельства равенства исторических запусков |
| Внешние rubric не попадают в feedback | Context проверяет leak paths/verdicts, но guide сообщает фактическую загрузку публичной rubric Codex rollout | Локальная фильтрация реализована; полное отсутствие contamination не подтверждено |
| Средний score отражает весь запуск | `core.report.summarise` считает mean только graded; ungraded считает отдельно, незавершённые задачи могут отсутствовать | Высокая уверенность в семантике кода; среднее без coverage недостаточно для оценки надёжности |

Числа первых четырёх строк сверены с [таблицами1–2, PDF страницы8–9][paper-tables]; headline также присутствует в [README:41–45][readme]. Confidence здесь относится к подтверждённости конкретного утверждения источником, а не к вероятности успеха продукта. Последние три строки основаны на [experiment guide][experiments], [context guards][context] и [report denominator][report-core]. Raw per-task результаты исторических paper streams, их manifests и точные environments в этом аудите не получены; статистическое воспроизведение не заявляется.

Дополнительные четыре строки проверены по [Tables1–2/§3.2][paper-tables], [§4/Fig7][paper-transfer] и [AppE.2–E.3][paper-loo]. Confidence: источник подтверждает эти ограниченные claims; все **NOT REPRODUCED**. Точные manifests transfer-поднаборов и raw uncertainty этих сравнений не получены; общий test inventory не подменяет их. Offline LOO, online stream и cross-model deployment требуют отдельных сравнений в предложенном протоколе. Наличие результата transfer не даёт права считать произвольную накопленную память безопасной или полезной для Task Tower.

Есть явное расхождение population: приложениеB статьи описывает LAB1251/test100, release guide — полный stream1143. Без dataset manifests нельзя определить причину или считать их одинаковым набором. В статье #Steps — turns executor session, не полный recursive compute. [Appendix B][paper], [guide:44–48][experiments].

## Почему «запустить ту же команду» недостаточно

**Задачи и split.** CLI по умолчанию использует `--split all`. Адаптеры JobBench/LAB/WorkBuddy вызывают общий `tasks.select`: train/test требуют явный split-file; проверяются benchmark, дубликаты, пересечение и наличие IDs в установленном dataset. Проверка не требует включить в partition весь dataset. `split_tasks.py` создаёт локальное разбиение по domain, default train_fraction0.5 и seed42, с отказом перезаписи. Это новый split, не восстановленный paper split. Guide прямо говорит, что partitions не являются release assets; JobBench dataset определяется при download, его revision нужно сохранить. [Task selection][tasks], [split generator][split], [CLI][sweep], [guide:64–85][experiments].

**Порядок и бюджеты.** `--max-tasks` ограничивает число задач в каждом domain, а не весь запуск. Seed управляет порядком задач, не sampling модели; library зависит от порядка, поэтому смена stream — смена условия опыта. `--workers` задаёт одновременные domains при последовательных задачах внутри них. Равный k не означает равные токены, wall time или число всех служебных вызовов. [stream resolver][stream], [guide:6–28,44–68][experiments]. Нельзя путать budget рекурсии с разрешённым WIP координатора Task Tower.

**Выбор результата.** `selection_pool` строит только `agg1..aggk` или `c1..ck`, намеренно не использует переданный base и не предусматривает abstention. При k=1 scheduler вызывает `trivial_selection`: один пригодный final возвращается без selector session; пустой pool — ошибка. При selection failure scheduler записывает ошибку и не добавляет library entry как успешно выбранный результат. Reflection не превращает trivial selection в независимый quality review. [Pool][selection], [k=1][trivial], [реальный call site][schedule].

Следовательно, «выбран лучший» означает выбор среди допущенных finals, а не доказательство превосходства над исходным исполнением. Даже unchanged composed tree и отдельный base rollout имеют разные реализации случайного исполнения. Для Task Tower нужно сравнение outputs исходного harness с candidates, возможность сохранить исходный и возможность отвергнуть все варианты.

**Judge и знаменатель.** Отдельный `harness2-judge --bases` пишет `base_judged.json`; обычный report читает `judged.json` refined результатов, не строит сравнение с baseline автоматически. JobBench различает отсутствие output и failure judge; LAB возвращает None при неудачном judge; WorkBuddy может вернуть None и при прерванном provider rollout без artifact. Ноль баллов и неизвестная оценка — разные события. [Judge CLI][judge], [JB score][jb], [LAB score][lab], [WB score][wb]. В `summarise` знаменатель — graded rows, поэтому сравнение только этих средних может получить selection bias. Нужно дополнительно сверять planned→attempted→completed→selected→graded→accepted и причины потерь. Это вывод из кода, а не обвинение в недостоверности paper.

**Стоимость и resume.** Report явно подписывает свою USD-сумму как improver spend; это не полная цена executor+judge+CI+review. `_check_identity` сохраняет модели, endpoints, task stream/split/seed и отказывает несовместимому namespace. Однако run markers без прежнего inputs-key остаются reusable по совместимости; это нельзя принимать как свежую идентичность всех входов. [Spend][report-cli], [namespace guard][identity], [legacy markers][markers]. Нужны отдельные полные receipts, а не вывод о безопасности resume по одному каталогу.

Кроме того, `fingerprint(None)` возвращает строку `base`, не digest байтов наследуемого исходного harness. Для будущего B0 требуется реальный snapshot/hash исходной конфигурации. [Fingerprint implementation][fingerprint].

## Команды: подтверждённый синтаксис, не запуск

Ни одна команда ниже не выполнялась. Это примеры интерфейса pinned release для будущего отдельно разрешённого окружения, а не инструкция запускать Linux/POSIX launcher в текущем Windows workspace. Наличие `--dry-run` не даёт разрешения исполнять upstream: даже preview создаёт adapter и читает установленный dataset. [Actual parser и dry-run branch][sweep].

```text
harness2 --bench lab --k 1 --mode parallel --only-domains antitrust-competition --max-tasks 1 --dry-run
python scripts/split_tasks.py --bench lab --seed 42 --output splits/lab.json
harness2 --bench lab --k 1 --mode parallel --seed 42 --split-file splits/lab.json --split test
harness2-judge --bench lab --k 1 --mode parallel --seed 42 --bases
harness2-judge --bench lab --k 1 --mode parallel --seed 42
harness2-report --bench lab --k 1 --mode parallel --seed 42
```

Parser подтверждает `--mode` как alias `--modes`; judge/report используют тот же namespace seed/k/mode. Split-команда пишет файл; refinement и judge вызывают модели. Требуются dependencies/datasets, configured model identities и отдельный output root; scope этих prerequisites не разрешён данным исследованием. Команды демонстрируют release workflow, **не воспроизводят paper test IDs**. [Common CLI][common], [judge][judge], [report][report-cli], [guide][experiments].

## Предлагаемое сравнение Task Tower — NOT RUN

Цель — проверить, улучшает ли изменение harness принятый результат при сопоставимых ресурсах. Не предлагается сразу переносить upstream launcher или подключать production Beads/GitHub effects. Текущая архитектура, независимая приёмка и ограничения доверия описаны в [единой спецификации](../../superpowers/specs/2026-11-05-task-tower-unified-design.md), [trust-аудите](04-trust-and-isolation.md) и [acceptance-аудите](../harness-engineering/03-acceptance-gates-audit.md).

### До сбора результатов

1. Заморозить representative task inventory: документирование, небольшая правка кода, разбор CI/evidence, конфликт/восстановление. Исходные реальные задачи обезличить; исключить credentials и операции в production. Разделить development для настройки, закрытый held-out для оценки и regression для ранее выявленных ошибок. Родственные варианты одной задачи помещать в одну группу, иначе почти одинаковые задания протекут между split.
2. Зафиксировать три arms: **B0** исходный harness, **BR** повторные исполнения неизменённого harness с тем же независимым selector, **H** ограниченная оптимизация harness. Модель/version, данные, разрешения, сеть и evaluator неизменны. Выбор H обязан допускать baseline output, keep-original и reject-all; это предложенное отличие от release, не существующий upstream flag.
3. Основной вопрос — результат при одинаковом **total resource cap**, включающем proposer/selector/reflection/judge и retries. Отдельный анализ при одинаковом числе executor attempts помогает понять механизм, но не является cost-matched. Нельзя объявлять обе нормировки выполненными одновременно, если дополнительные вызовы не учтены. Publish actual spend, idle/queue time и число попыток каждого типа.
4. До первого confirmatory результата зафиксировать task IDs, порядок/seed schedule, repeats, primary metric, минимально полезный эффект, лимиты времени/денег/попыток и правила отказа. Конкретные sample size и caps выбираются по допустимому бюджету и оценке дисперсии; сейчас они **не определены**, запуск невозможен до их заполнения. Небольшой будущий pilot для планирования дисперсии не входит в confirmatory held-out.
5. Для transfer-эффекта отдельно определить либо frozen library перед held-out, либо online stream с библиотекой только из предыдущих задач без grade feedback; не смешивать эти эксперименты. У каждого arm/repeat свой начальный snapshot. Привязать whole stream к одной replicate identity: зависимые задачи одного обучающегося потока не становятся независимыми наблюдениями от смены task ID.

### Независимая оценка и остановка

Selector получает обезличенные deliverables и условия задачи, но не происхождение arm или hidden rubric; стабильная permutation фиксируется в manifest. Итоговый judge — отдельный контекст с неизменяемой rubric. Для объективных условий использовать детерминированные проверки; профессиональное суждение и ambiguous решения фиксировать отдельно. Автор candidate не принимает собственный результат. Rubric score не заменяет whole-PR/exact-main gates реальной поставки.

Primary metric предлагается `independently_accepted / planned_task_episodes`, где episode — одна заранее назначенная задача × repeat × arm, а внутренние retries/probes не увеличивают этот знаменатель. Accept/reject определяется заранее; неизвестный исход не считается accepted. Отдельно публиковать scored-only quality и coverage, все failed/missing/cancelled attempts, false accept/false reject, latency, owner time и `total_cost / accepted_results`. При нуле accepted стоимость принятого результата не определена, а не равна нулю. Если judge недоступен, outcome — ungraded: основной delivery numerator не растёт, но это не записывается как доказанный quality failure.

Для фиксированных independent task groups сравнивать paired разности B0/BR/H, сохранять repeats внутри task cluster; при online library использовать independent stream как единицу неопределённости. Предлагается paired cluster bootstrap interval с заранее заданным методом/seed; при нескольких streams интервал может быть нестабилен — показывать raw counts и range, не заявлять significance. Не смешивать score разных benchmarks или считать критерии одной задачи независимыми задачами. Корректировать план multiple comparisons заранее либо оставить остальные срезы описательными. Это проект анализа, не посчитанная статистика.

Остановить arm при несовпадении identity/policy, утечке rubric, запрещённом эффекте или исчерпанном cap. Не менять порог после просмотра held-out и не заменять трудные задачи лёгкими. Для инфраструктурного сбоя заранее ограничить retries; первоначальная попытка остаётся в ledger, новый attempt связан с причиной. При неизвестном внешнем результате сначала readback/reconcile, не повторение эффекта. Решение сохранить B0 или не принять ни один candidate считается допустимым результатом опыта.

### Контроль загрязнения и минимальный manifest

Release предупреждает о public rubrics и unrestricted network, а context guards проверяют файлы, не сетевой канал. Поэтому будущий эксперимент должен отделить evaluator/rubric от исполнителя, исключить benchmark/answer hosts и зафиксировать разрешённые внешние источники. Один denylist не доказывает отсутствие зеркал или предварительного знания модели. Нельзя назвать опубликованный результат «clean» без соответствующего evidence; нужно отдельно обозначить известную/неизвестную exposure. Устанавливать firewall/DNS/ACL сейчас не предлагается. [Guide:93–109][experiments], [context][context].

Proposed manifest — исследовательская запись, не новая task queue и не формат уже поставленного controller:

| Группа | Обязательные поля |
| --- | --- |
| Идентичность | project/repository, bead как ссылка, experiment/task/attempt/arm/repeat IDs, parent attempt; source commit/tree; upstream commit и dataset revision |
| Входы | hashes task files, split/ordered stream, initial harness/library, policy и evaluator rubric; model/provider resolved version, parser/runtime versions; seed scope и sampling settings |
| Условия | cap и фактический spend по ролям, network policy и наблюдение её действия, allowed effects, immutable evaluator version |
| Исходы | planned/attempted/completed/selected/graded/accepted отдельно; baseline/candidate IDs, abstain/fallback/error, judge status, outcome/artifact digest, reviewer и evidence links |
| Сохранение | timestamp, redaction/retention, append-only attempts и cancellation/reconciliation evidence; неизвестные fingerprints не заменяются пустым «совпадением» |

Rubric bytes и credentials в manifest для модели не включаются; хэш и ссылка на доверенное evidence не дают исполнителю доступ. Если metadata не может различить model/version или inputs, результат помечается ограниченно воспроизводимым и не используется как свежий paired comparison.

## Бесплатная проверка механики — проект, тоже NOT RUN

Ниже нет вызова upstream, модели или реального GitHub/Beads. Для будущей проверки достаточно синтетических записей и отдельного проверяющего, который применит описанные правила к каждой копии. Это проверка bookkeeping, не модельного качества. Общий fixture: tasks T1/T2, disjoint splits dev/test, arms B0/BR/H, фиксированные условные digests, candidate labels A/B и toy quality numbers без связи с реальными результатами.

| Проверка | Один изменяемый вход | Ожидаемый наблюдаемый результат |
| --- | --- | --- |
| Исходный вариант лучше | B0=0,8, H=0,6; оба valid | Выбирается B0; H не объявлен улучшением; оба scores сохранены |
| k=1 | Один H final без selector receipt | Можно учесть output, нельзя заявить независимый выбор; отдельный final judge остаётся обязательным |
| Ни одного пригодного | Все candidates нарушают обязательное условие | reject-all, accepted=0; denominator не исчезает |
| Ничья | B0=H при equal validity | Предопределённое правило keep-original; нет постфактум выбора arm |
| Потерянный judge | У одного completed attempt grade=null | ungraded count растёт; planned остаётся прежним; quality score не подменяется нулём |
| Устаревший вход | Меняется task hash при прежнем result hash | Результат не считается новым paired observation; требуется отдельная попытка/идентичность |
| Протечка split/rubric | T1 попал в оба split либо запрещённый rubric-marker в context | Контаминированная копия отвергнута; marker-тест не доказывает сетевую изоляцию |
| Скрытые затраты | Удалён selector/retry spend | Manifest incomplete; сравнение стоимости не публикуется как полное |

Для каждого fixture хранить before, mutation, ожидаемый и фактический verdict, исполнителя проверки и digest. Пока поле actual result везде `not_run`. Положительный исход этой механики разрешит утверждать лишь, что проверены заданные правила учёта; quality comparison потребует отдельного реального эксперимента с заранее заполненными параметрами.

## Решение по исследованию

Сейчас обоснованы source-level выводы о selection, partitions, denominator, resume и contamination, а также конкретный план проверки. Не получены независимые model-run результаты, paper per-task manifests и измерение эффекта на Task Tower. Поэтому рекомендация — сохранить исходный harness как контроль, сначала проверить механику и условия будущего сравнения, затем отдельно решать вопрос live-оценки. Это не разрешение на её запуск, не закрытие B/G1/G2/PR85 или эпика и не повтор завершённого ordinary-session пилота.

[paper-abs]: https://arxiv.org/abs/2610.14224v1
[paper]: https://arxiv.org/pdf/2610.14224v1
[paper-tables]: https://arxiv.org/pdf/2610.14224v1#page=8
[paper-transfer]: https://arxiv.org/pdf/2610.14224v1#page=11
[paper-loo]: https://arxiv.org/pdf/2610.14224v1#page=24
[readme]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/README.md#L41-L45
[experiments]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/docs/EXPERIMENTS.md#L6-L122
[tasks]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/tasks.py#L62-L88
[split]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/scripts/split_tasks.py#L29-L64
[sweep]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/run_sweep.py#L47-L145
[stream]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/schedule.py#L804-L845
[selection]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/selection.py#L93-L128
[trivial]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/selection.py#L360-L399
[schedule]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/schedule.py#L540-L615
[judge]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/judge.py#L114-L205
[jb]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/jobbench.py#L1155-L1171
[lab]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/lab.py#L981-L1022
[wb]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/benchmarks/workbuddy.py#L986-L1004
[report-core]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/report.py#L80-L110
[report-cli]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/report.py#L37-L108
[identity]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/run_sweep.py#L209-L235
[markers]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/runmark.py#L132-L159
[fingerprint]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/runmark.py#L42-L63
[context]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/core/context.py#L153-L175
[common]: https://github.com/google-research/harness2/blob/6868817518876de8fd170c6a8354daca273b6191/harness2/cli/_common.py#L97-L138
