# Независимая приёмка: что действительно блокирует переход

Дата: 2026-11-05. Исследование `tt-e4n.3`, продолжение [аудита пяти подсистем](01-five-subsystems-audit.md). Курс изучен на `6420da2d57c901c401fc909354a7f5f7fce81882`, Task Tower — на принятом main `78e8d1b13847d9037da245a66653dd566be5b190`. Это анализ исходников и сохранённых свидетельств; тесты курса, продукта и предлагаемые отрицательные проверки здесь **НЕ ЗАПУСКАЛИСЬ**.

Главный результат: независимое review и точная привязка к исходникам уже применены в реальной документационной поставке PR87. В ходе аудита выявлено отсутствие защиты main; после отдельного прямого указания пользователя координатор включил branch protection и проверил её чтением. Теперь обязательность трёх статусов закреплена настройками GitHub. Однако Books/admission не являются автоматическим контроллером приёмки: содержательную независимость verdict, свежую пару head/base и exact-main completion по-прежнему проверяет координатор.

## Что именно проверяет курс

Verification gap в курсе — расхождение между заявлением агента о готовности и независимой проверкой. Указанный там ориентир менее 5% — учебная цель, не измеренная характеристика Task Tower. Для измерения нужны реальные попытки, заявления о готовности, независимые результаты и знаменатель; один успешный PR этой метрики не даёт. [Определение и метрики курса][course-metrics].

| Наблюдение в исходниках | Что оно способно показать | Чего из него не следует |
| --- | --- | --- |
| `test_harness.py::test_ci_exists` ищет файл workflow; shell-тест ищет команды проверок, настройки hooks и считает файлы ворот | Нужные элементы представлены в дереве | Команды действительно эквивалентны, hooks включены, GitHub требует статус, два файла дают независимые барьеры |
| `test_04_gates_and_hooks.sh` создаёт синтаксически испорченный Python/JS и вызывает `ruff check` / `node --check`, ожидая отказ | При фактическом запуске с доступным инструментом проверяется различение этого плохого входа | Отказ merge при устаревшем review или отсутствие обходного пути; при отсутствии инструментов ветка пропускается |
| `test_harness.py` запускает собственный pytest против плохой/хорошей fixture и проверяет код завершения | Плохая fixture вызывает хотя бы один отказ набора, хорошая проходит выбранный набор | Каждое отдельное правило имеет отрицательный тест и подключено к живому переходу |
| Golden-проверки читают YAML, число кейсов, категории, критерии и объявленные baseline rates | Контракт набора задан и пригоден для последующего измерения | Модель выполнила кейсы, baseline измерен сейчас, acceptance сработал в реальной поставке |

Основания: [Python-проверки CI и golden metadata][course-python], [плохая и хорошая fixture][course-fixtures], [shell-проверки наличия ворот][course-gates], [реальный вызов инструментов на плохих файлах][course-mutation], [shell golden contract без запуска модели][course-golden]. Сам курс отдельно выделяет L0 static, L1 tool, L2 live golden и L3 drift; последние два не входят в обычный `make test`. Это полезное разделение нужно сохранить и в отчётности Task Tower. [Уровни тестирования][course-levels].

Практический вывод: статический поиск годится для раннего обнаружения отсутствующего элемента. Проверка плохого файла подтверждает конкретный checker. Чтобы подтвердить gate, нужно предъявить неверный пакет самому механизму перехода и наблюдать отказ без побочного merge/close. Эти три результата нельзя заменять друг другом.

## Текущий путь Task Tower и границы доказательств

| Участок | Реальная проверка и граница |
| --- | --- |
| Books и admission | Books читает состояние/историю, а admission сверяет source pin, чистоту и ready/show через readonly-команды; результат — `eligible_observation`. Это не claim, review, merge или закрытие Beads. `closed` в книге остаётся состоянием источника, не сертификатом принятого результата. [Books][books], [admission][admission] |
| PR CI | Aggregate требует успешного результата применимого маршрута. Docs-validator заново классифицирует исходники, проверяет whitespace и новые битые локальные ссылки, выдаёт `runtime_tests: not_run`. Runtime-verifier проверяет реальные manifests и покрытие inventory. Ни один из этих результатов не заменяет review содержания. [PR workflow][pr-ci], [docs validator][docs-ci], [runtime verifier][runtime-ci] |
| Postmerge CI | Workflow ограничен merged PR в main, работает с merge SHA и публикует типизированный результат. Он проверяет исходники/тесты, но не выполняет независимую содержательную приёмку и не закрывает каноническую карточку Beads. [Postmerge workflow][post-ci] |
| Координатор | По действующим требованиям проверяет независимый whole-diff verdict на текущие head/base, CI, mergeability и findings; публикует настоящий `task-tower/pr-acceptance`, сливает с expected head; затем проверяет exact main, CI, независимый main verdict и канонический readback. Это текущий процесс, а не поставленный unattended controller. [Правила интеграции][rules], [единая спецификация][unified] |
| GitHub settings: до изменения | Read-only GET `repos/Sibiya666/task-tower/branches/main/protection` вернул HTTP404 с явным `Branch not protected`; GET `repos/Sibiya666/task-tower/rules/branches/main` успешно вернул `[]`. Это наблюдение 2026-11-05 до изменения, а не вывод из одного общего 404 и не текущее утверждение об отсутствии защиты. |
| GitHub settings: после изменения | По отдельному указанию пользователя «Защити main» координатор включил защиту и получил фактический readback `protected:true`: PR обязателен, strict checks и enforce admins включены; требуются `scope` и `unittest (windows-latest)` от GitHub Actions app15368, а также `task-tower/pr-acceptance` без app binding. Force push/deletion запрещены, conversations должны быть разрешены. Human approving review count равен 0: AI acceptance не выдан за человеческое approval. |

Оба состояния сохранены координатором с фактическими ответами API. Первоначальная запись получила 422 без изменения; исправленный запрос применён после нового чтения, итог проверен отдельными GET protection/branch. Это подтверждённая конфигурация, **не отрицательный production-тест**. [REST branch protection][github-protection] описывает параметры защиты; [REST branch rules][github-rules] возвращает активные применимые правила, включая уровни организации/репозитория, но исключает evaluate/disabled. Более ранняя пометка «unknown» и первоначальное отсутствие защиты не описывают состояние после изменения.

Защита требует наличие успешных статусов, но не читает смысл reviewer receipt. У `task-tower/pr-acceptance` нет привязки к конкретному app: независимость издателя и содержательная обоснованность остаются отдельной обязанностью процесса. Strict up-to-date check не заменяет повторное принятие на изменившийся base. Разрешённые conversations также не равны всем findings вне GitHub threads. Эти ограничения нельзя закрыть одним флагом protected.

**Один наблюдавшийся положительный цикл.** [PR87][pr87] прошёл независимое whole-diff review: head `9797bddb59d0854ac356cd3afd3ce3c0c4c4a233`, base `4d27b161ec1110e32a519debed907bd89b26cbc0`; reviewer `trust_pr_acceptor` отличался от автора. [PR CI 42101647346][pr87-ci] проверял proposed merge `199f454b3aa3c299e07f774ddb8bf6929f9ca070`, чьи родители и дерево были отдельно сверены с принятой парой. После merge принят exact main `78e8d1b13847d9037da245a66653dd566be5b190`, [postmerge CI 42102319627][pr87-post] и отдельный reviewer `trust_main_acceptor`. Проверены фактические ZIP/artifact digests и `documentation.validation`; runtime tests остались `not_run`.

Координатор затем закрыл только `tt-bx1.4`: readback сохранил assignee `task-tower-security-research-coordinator`, историю и closure event `0ce86513-92c3-5782-b0f9-b2f1c0caa38a`. Публичные итоги: [PR87 receipt][pr87-receipt], [Issue49 receipt][issue49-receipt]. Это свидетельство одного ручного документационного цикла, не отрицательного тестирования всех ворот, не квалификация B и не наблюдение доставки C в открытой Books.

**Архивная проверка остаётся архивной.** В текущем дереве сохранены старые file-card `tasks.py` и `postmerge_worker.py`. Их тесты действительно содержат отрицательные assertions: same-author/stale evidence, commit вне main, missing/failed platform и rejected review. [Stage/main tests][legacy-tasks], [postmerge tests][legacy-post]. Но file-card `done` не равен каноническому Beads close; сравнение строк actor не аутентифицирует независимость, а проверка ancestry main не заменяет приёмку точного текущего main. Эти тесты в данном аудите только прочитаны. Старые macOS/Linux fixtures не разрешают новые платформенные запуски. Возобновление архивного conveyor не предлагается. [Статус архитектуры][rules].

## Двенадцать отрицательных случаев

Ниже — **проект воспроизводимой проверки, все 12 случаев NOT RUN**. Для каждого случая исходный вход `P0` одинаков: отдельный минимальный текстовый пакет без базы, приватных логов и credentials. В нём есть task/spec/plan, author/reviewer IDs, полный diff, head H, base B, однозначное approve на H/B, настоящие ссылки/результаты применимых CI, отсутствие незакрытых blocking findings; для postmerge — target main, merge M, exact-main CI и отдельный main verdict на M. Ссылки PR87 служат примером формы свидетельств, не разрешением повторить его эффекты.

Порядок будущей проверки: изготовить 12 независимых копий `P0`, внести только мутацию строки таблицы, передать отдельному reviewer с правилами [интеграции][rules], записать конкретную причину отказа и итоговое состояние. Здесь **M** означает детерминированное ручное решение по пакету: при отсутствующем/неверном обязательном поле не выдавать разрешение перехода. Это не имя функции или выдуманная CLI-команда. **A** указывает только на существующий архивный тест с близкой проверкой; его исполнение в будущем потребует отдельного безопасного окружения и не докажет enforcement нового пути. Никаких реальных merge/close для опыта не нужно.

| № / одна мутация `P0` | Какой переход должен остаться запрещён | Где отказ сейчас и какое свидетельство доступно | Безопасная проверка и ожидаемый результат |
| --- | --- | --- | --- |
| 1. Удалить required verdict | review → accepted / merge eligible | M: обязательная независимая приёмка; CI не восполняет отсутствующее решение. A: `test_cannot_skip_or_self_accept` [stage tests][legacy-tasks] | M перечисляет отсутствующий verdict; пакет остаётся awaiting review, merge permission не выдано |
| 2. Заменить approve на reject при тех же H/B | review → accepted / merge | M; A: `test_rejection_never_closes` проверяет отказ старого postmerge worker, не PR gate [postmerge tests][legacy-post] | M читает явное reject; пакет остаётся rejected/needs correction, переход не разрешён |
| 3. Заменить verdict на «в целом хорошо, если…» | review → accepted / merge | M: неоднозначность не трактуется как approval; текущего автоматического Beads parser этого решения не показано | M фиксирует неразрешённое условие; awaiting clarification/review, не accepted |
| 4. Установить reviewer ID равным author ID | authored → independently accepted | M проверяет авторство и отдельный процесс; A: `test_cannot_skip_or_self_accept`, строковое сравнение [stage tests][legacy-tasks] | M отклоняет self-accept независимо от model label; нужен другой приёмщик, merge permission отсутствует |
| 5. Изменить current head H → H2, оставить verdict H/B | accepted → merge | M: свежая проверка пары перед эффектом и expected-head merge; CI на H2 не обновляет verdict [rules][rules] | M сравнивает current H2 с reviewed H; stale acceptance, требуется whole-diff review нового head |
| 6. Изменить current base B → B2, оставить verdict H/B | accepted → merge | M: повторная сверка base и сериализация; expected-head один не проверяет base [rules][rules] | M обнаруживает B2 ≠ B; прежнее принятие недействительно, нужны актуальные проверки/приёмка |
| 7. Один обязательный current CI сделать failed/cancelled | CI checked → merge eligible | PR aggregate не выдаёт успешный результат проваленного маршрута; после изменения protection требует успешные checks, M проверяет конкретный run [PR CI][pr-ci] | M читает current run и failure; исправление/проверка ожидаются, merge запрещён. Защита подтверждена чтением настроек, production refusal не испытывался |
| 8. Удалить один required current CI/result/artifact | CI checked → merge eligible | Protection требует checks; M проверяет нужные artifacts, runtime verifier требует complete manifests [runtime verifier][runtime-ci] | M отмечает недостающее свидетельство; unknown/waiting CI, не green-by-absence; docs-маршрут не требует намеренно skipped runtime. Настройки не заменяют чтение artifact |
| 9. Добавить unresolved blocking finding без resolution | review → accepted / merge | M: whole-diff acceptor обязан учитывать blockers; отдельного live Beads transition predicate не показано [rules][rules] | M сопоставляет finding и отсутствие принятого исправления; needs correction, merge запрещён даже при approve-ярлыке |
| 10. Заменить target main на feature, оставить merged label | merged → exact-main accepted / done | Postmerge workflow ограничен main; M проверяет фактический target и M. A: `test_postmerge_requires_commit_on_main` [stage tests][legacy-tasks] | M видит несовпадение target; canonical completion не разрешено, не-main merge не принимается как main |
| 11. Заменить применимый exact-main CI на failed | merged → done / следующий сериализованный merge | M удерживает main barrier; A: `test_failed_checks_do_not_launch_agent` [postmerge tests][legacy-post] | M сохраняет failed postmerge, карточка не закрывается как успешно выполненная; следующий merge ждёт восстановления/приёмки |
| 12. Удалить exact-main CI либо independent main verdict | merged → done / следующий сериализованный merge | M; A: `test_missing_platform_waits_without_reviewer` покрывает отсутствие старого platform evidence, не новый docs/main verdict [postmerge tests][legacy-post] | Отдельно повторить копию для каждого удаляемого поля; M фиксирует missing evidence, awaiting main acceptance, completion и следующий merge запрещены |

Столбец с ожидаемым состоянием описывает решение эксперимента, а не новые статусы схемы Beads. Отказ в ручной проверке подтвердит качество решения reviewer на этих входах; автоматический enforcement можно заявлять лишь после проверки реального будущего контроллера и его границы эффектов. Старый green test или новый grep не закрывает этот пробел. Повтор после неизвестного исхода нельзя превращать в повтор merge/close: сначала нужны readback и восстановление идентичности события.

## Что передавать независимому приёмщику

Минимальный пакет — каноническая задача с критериями и зависимостями, принятые spec/plan, полный фактический diff, точные head/base и source tree/tested merge binding, реальные применимые CI outputs/artifacts, список findings и доказательства их разрешения. Для main добавляются фактический merge SHA, результаты именно этого SHA, отдельный main verdict; для завершения — канонический readback и история. История рассуждений автора может пояснить выбор, но не передаёт его уверенность как готовую оценку.

Курс рекомендует отдельную сессию, чистый контекст и по возможности другую модель. Его собственное «по возможности» не означает обязательную смену модели. [Роли в курсе][course-roles]. В Task Tower необходим отличающийся от исполнителя reviewer, способный проверить требования и реальные результаты; число агентов определяется задачей. Другая модель сама по себе независимость не удостоверяет. Если reviewer исправил проверяемый текст, он стал соавтором этих изменений и для их принятия нужен другой reviewer. [Unified §5.1 и §7][unified].

Для PR87 известны отдельные reviewer identities и их bound verdicts. Из этого не выводится доказанная OS-изоляция процессов или закрытие G1/G2: они относятся к самостоятельной квалификации harness. Аналогично missing acceptance нельзя исправлять одним увеличением числа агентов.

## Решения, которые следуют из аудита

1. **Сохранить действующий ручной gate и точно подписывать результаты.** Docs validation, независимое review и canonical closure — три разных свидетельства. PR87 показывает работоспособный документационный цикл; он не является готовым unattended acceptance controller.
2. **Разделять исправленную конфигурацию и оставшийся пробел семантики.** Выявленное отсутствие protection устранено координатором по отдельному разрешению пользователя и подтверждено readback. Required status теперь настроен, но GitHub не доказывает из него независимость reviewer, правильность head/base receipt или exact-main acceptance. Отрицательные production-пробы не проводились; дополнительных изменений прав этот отчёт не разрешает.
3. **Использовать 12 случаев как вход для уже существующих задач.** Архивный [Issue17][issue17] не возобновляется. В актуальном [backlog][backlog] `tt-auq.5` отвечает за восстановление main и сериализованный барьер, `tt-auq.6` — за сбои и независимых приёмщиков перед ночным режимом. Для `.5` особенно существенны смена base, missing/failed postmerge и неизвестный исход; для `.6` — все отрицательные случаи и доказательство отказа именно на границе эффекта. Это исследовательские входы, не выполненные acceptance criteria этих задач.
4. **Не считать неизвестное успехом.** Live отрицательные прогоны, verification-gap статистика и enforcement будущего Beads controller пока не подтверждены. Source-аудит завершает узкую аналитическую задачу, но не B/C, не соседний `tt-e4n.2` и не исследовательский epic.

[course-metrics]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/README.md#L3980-L3990
[course-python]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/tests/test_harness.py#L230-L296
[course-fixtures]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/tests/test_harness.py#L307-L335
[course-mutation]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/tests/test_04_gates_and_hooks.sh#L86-L100
[course-gates]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/tests/test_04_gates_and_hooks.sh#L1-L150
[course-golden]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/tests/test_05_golden_tasks.sh#L1-L143
[course-levels]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/tests/README.md#L144-L155
[course-roles]: https://github.com/justxor/Harness_ru/blob/6420da2d57c901c401fc909354a7f5f7fce81882/README.md#L1817-L1826
[books]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/task_tower/beads_books.py#L53-L132
[admission]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/task_tower/beads_admission.py#L301-L344
[pr-ci]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/.github/workflows/cli.yml#L97-L103
[docs-ci]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/task_tower/ci_docs.py#L343-L364
[runtime-ci]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/task_tower/ci_unittest.py#L68-L145
[post-ci]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/.github/workflows/postmerge.yml#L1-L144
[rules]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/AGENTS.md#L7-L34
[unified]: ../../superpowers/specs/2026-11-05-task-tower-unified-design.md
[legacy-tasks]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/tests/test_tasks.py#L139-L180
[legacy-post]: https://github.com/Sibiya666/task-tower/blob/78e8d1b13847d9037da245a66653dd566be5b190/tests/test_postmerge_worker.py#L69-L105
[github-protection]: https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection
[github-rules]: https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch
[pr87]: https://github.com/Sibiya666/task-tower/pull/87
[pr87-ci]: https://github.com/Sibiya666/task-tower/actions/runs/42101647346
[pr87-post]: https://github.com/Sibiya666/task-tower/actions/runs/42102319627
[pr87-receipt]: https://github.com/Sibiya666/task-tower/pull/87#issuecomment-6668403404
[issue49-receipt]: https://github.com/Sibiya666/task-tower/issues/49#issuecomment-6668404538
[issue17]: https://github.com/Sibiya666/task-tower/issues/17
[backlog]: ../../backlog.md
