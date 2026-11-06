# Beads → Superpowers → Codex → GitHub → Books

Карта `tt-ltz`, 2026-11-06. Действующее направление —
[Beads + Superpowers + готовый Codex](current-direction.md).
Исходники продукта закреплены на принятом main
`212fb0b3904219e0540da8d3a164dc8e1340fe5c` (PR101).
Это source-only результат; приложение, harness и модель для диагностики не запускались.

## Исходная задача и свидетельства

Исходные acceptance criteria канонической `tt-ltz`, прочитанные до claim:

> One versioned concise report with exact source references, confirmed current capabilities and gaps, original task criteria and independently reviewed feasible target. Target has one user-visible Books result, bounded input/effects and actual verification; keep privacy, missing/partial history, source state != acceptance and all actual PR/main/CI gates. No invented runtime observations. Independently accept report at actual PR H/B, genuine CI/status/protected merge and exact-main before canonical close/readback. No dependency on old Windows programme; preserve all owned/paused work.

Native `show`, `ready` и две формы `history` подтвердили свободную ready-задачу
без зависимостей; atomic claim и отдельный `show` подтвердили
`task-tower-tt-ltz-coordinator` / `in_progress`. Event journal содержит реальный
`claimed` этого actor; Dolt snapshots сами по себе не заменяют actor/event journal.
Bounded read-only `list --all --id tt-ltz --limit 1 --json` вернул её `notes`.
Это наблюдения исходного Beads, не доказательство работы UI или принятой поставки.
Приватные locator/config/DB paths и raw receipts в отчёт не включены.

| Версия / источник | Точная граница знания |
| --- | --- |
| Task Tower | SHA выше закрепляет все указанные ниже code references; эта поставка меняет только документацию. Books config и public envelope имеют `version: 1`. |
| Beads/Dolt | Используется существующий canonical embedded источник. В этой работе наблюдались native show/ready/claim/readback/heartbeat/history/events/list. Installed semver не переизмерялась и не выводится из имени каталога; новая runtime qualification не нужна для текущего маршрута. |
| Superpowers | Каталог навыков помечен `7.0.1`; воспроизводимые hashes двух прочитанных инструкций: writing-plans `a6c67c1900064347c2a329990dd3c555657c51c3ec53b259a08aa01a2c26139a`, requesting-code-review `2180e14a448e9410bec88e6646a2d1f0ce7fdd58de27388c1e052e929679d2bc`. Это identity текста метода, не runtime acceptance. |
| Координационный навык | Прочитанный task-tower-coordinate SHA256 `9411d2ad11c37f3c82108ff0fb5060c58851ebe2bfb8e076aee360faf9e463ef`: текущий маршрут и gates; персональный навык не shipped executor. |
| Готовый Codex | Текущая сессия предоставляет supported spawn/message/followup/wait/list/interrupt и managed worktree tools. Installed binary version здесь не измерялась. [Официальная документация subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), прочитанная 2026-11-06, подтверждает capability, но является mutable источником, не pin бинарника. |

## Карта существующей связки

| Переход | Уже поставлено / точный source | Что делает координатор |
| --- | --- | --- |
| Beads task → source facts | [beads_admission.py](../task_tower/beads_admission.py):232–233,322–338 читает bounded readonly ready/show и возвращает observation. [beads_books.py](../task_tower/beads_books.py):55–92 проецирует scoped identity, owner, state, parent, dependencies и event chronology. | Читает исходные criteria/dependencies/owner/events/fences, заново проверяет readiness, выполняет native atomic claim и readback. Display config и admission packet прав на исполнение не дают. |
| Criteria → Superpowers artifacts | Прочитанные `brainstorming/SKILL.md:225`, `writing-plans/SKILL.md:16,59–67`: spec в `docs/superpowers/specs/`, plan в `docs/superpowers/plans/`, source/criteria/проверяемые steps. Для поведения — TDD; для этого source-only отчёта — проверка фактов, ссылок и scope. | Подбирает нужный объём метода, связывает артефакты с тем же Bead, фиксирует исходный SHA и отдельную ветку/worktree. План не становится второй очередью/владением. |
| Артефакты → Codex work/review | Supported инструменты текущей сессии дают отдельные контексты и управляемые worktrees. `requesting-code-review/SKILL.md:36–40` требует исходные требования и actual base/head; `verification-before-completion/SKILL.md:17–38` — фактическую проверку до заявления успеха. | Даёт минимальный brief исполнителю и другому reviewer. Автор не принимает свой результат; наличие subagent API само по себе независимости verdict не доказывает. |
| Actual diff → GitHub PR/main | [.github/workflows/cli.yml](../.github/workflows/cli.yml):1–4,9–22,62–103: PR CI, scope classifier и стабильный aggregate. [postmerge.yml](../.github/workflows/postmerge.yml):3–8,19–28,94–103: exact merge checkout и typed docs artifact. [ci_docs.py](../task_tower/ci_docs.py):344–364: повторная классификация, whitespace/new-local-links и `runtime_tests: not_run`. | Получает свежую independent whole-PR приёмку actual head **и** base, genuine `task-tower/pr-acceptance`, весь применимый CI, resolved blockers и protected expected-head merge; затем отдельно exact-main CI/artifact и независимую postmerge-приёмку. Changed H/B аннулирует verdict. |
| Принятый main → canonical history → Books | [beads_books.py](../task_tower/beads_books.py):119–144: фиксированные readonly/sandbox list/config/events; [overlay_books.py](../task_tower/overlay_books.py):16,41–53,58–89: public allowlist и progressive mixed sources. [books-view.js](../overlay/web/books-view.js):31–41 показывает данные задачи и хронологию. | После настоящих gates закрывает только свою задачу guarded native командой и читает state/events обратно. Затем сверяет настоящее Books отображение с источником, когда такое наблюдение разрешено. Автоматического product-close/dispatcher этот код не поставляет. |

## Что уже достаточно и где настоящий пробел

Существующих Beads, Superpowers и Codex достаточно для ручного координируемого
цикла разработки/независимого review/защищённой поставки. Новый executor, task
engine, постоянный граф ролей, worker, hook/setup или установка плагина для него
не нужны. GitHub Actions проверяет исходники, а не исполняет Beads очередь.

Books уже показывает identity/owner/state/dependencies/history. Границы:
1000 задач,5000 событий/проект,100 событий/карточку,25s read budget;
missing/disabled/pruned/inconsistent history остаётся visibly partial
([local-beads-books.md](local-beads-books.md), `beads_books.py:15,112,127–144`).
Beads `done` нормализуется в source `closed`, а не accepted;
`books-policy.js:74–76,108` не превращает его в verified done.

**Узкий подтверждённый пробел отображения:** `beads_books.py:65–69` не переносит
`notes`, acceptance criteria или close reason; `results` всегда пуст.
`books-view.js:39–40` для Beads не рисует result/evidence field. Поэтому публичная
запись результата, реально существующая в canonical `notes`, не доходит до
деталей Books. Прочитанный native list подтвердил наличие `notes` на `tt-ltz`;
это подтверждение input field, не запуск нового adapter/UI.

Ссылки, уже включённые в description, доступны как обычный текст — для простого
показа task/state/history продуктовая правка не нужна. Это не structured evidence
и не независимо проверенная acceptance. Existing source navigation ограничена
same-repository Issue/PR/milestone и SHA-pinned Markdown
(`books-view.js:7–19`); Actions/artifact navigation не объявляется готовой.

## Один полезный целевой результат для tt-x6t

**В деталях одного настоящего scoped Bead показать публичную запись результата
поставки из канонического источника рядом с его owner/state/history.**
Выбранная задача — сама `tt-x6t`, после отдельного claim; её delivery может
добавить один read-only блок «Свидетельства результата» для заранее явно
размеченной публичной записи в `notes`. До реализации её независимый spec/plan
закрепляет точный marker/формат, scope и критерии. Это предложение цели, не
готовый parser/design и не разрешение сейчас изменять `tt-x6t`.

Минимальный field scope: один explicitly public block, не произвольные notes;
до4KiB UTF-8, до4 source references, без private paths, raw config, credentials,
HTML или исполнения Markdown/команд. Начальный набор references — только
существующие поддержанные same-repository PR и SHA-pinned Markdown; реальные
main SHA и review/typed-CI facts можно показать текстом со ссылкой на committed
публичный receipt. Повторно использовать действующий source URL validator,
не расширять native navigation на local files/Actions/исполняемые файлы.
Отсутствующий/malformed/over-limit block — явное «не записано/недоступно»;
приватные поля вне public block не копировать. Запись помечена как сведения
Beads, не автоматический verdict; `closed` не повышается до accepted.

Если перед implementation выяснится, что согласованный реальный сценарий целиком
покрыт существующим description, выполнить и документировать именно этот путь
без code change. По данным метода одной только установки навыков/плагинов для
реализации продукта недостаточно; фактический gap определяет scope, не наоборот.

Проверка будущей доставки:

1. До эффектов закрепить canonical criterion, allowed fields/effects и plan,
   получить независимую приёмку; заново проверить readiness/dependencies/owner
   и native claim/readback. Не менять старые claims/dependencies/HOLD/pause.
2. Если нужен public block: наблюдаемые RED/GREEN adapter/envelope/UI проверки
   на реальном формате с privacy/size/unsafe URL/missing/partial-history cases;
   затем применимые actual CI и независимые DEV/TEST/PR/main gates.
3. После exact-main acceptance записать только публичные genuine artifact/PR/
   main/review references в canonical public block своей задачи, затем bounded
   source readback. Не подделывать историческую acceptance и не импортировать
   чужие receipts.
4. Под отдельным action-specific разрешением на необходимое app-наблюдение
   открыть настоящие Books существующего источника и сверить scoped `tt-x6t`,
   owner/state/dependencies/event chronology и публичный результат. Ни браузерный
   fixture, ни статический отчёт этого не заменяет. При отсутствии разрешения/
   источника/наблюдения `tt-x6t` остаётся незавершённой с конкретным blocker.
   Затем guarded close/readback и проверка actual closed source state без
   утверждения автоматической acceptance. Текущий `tt-ltz` этих эффектов не делает.

## Приёмка этой карты

Два read-only scout контекста проверили shipped source и method/tool boundary;
это входы автора, не приёмка собственного отчёта. Отдельный независимый acceptor
проверяет исходные criteria, весь actual diff, точные references и feasibility.
Далее действуют обычные PR/head/base/status/CI/protected-merge/exact-main gates;
только после них координатор закрывает `tt-ltz` и читает native history/events.
Docs-only artifact означает `documentation.validation`, не runtime pass.

Без новых native/model/harness/provider experiments, чтения private configs,
auth/account/model/ACL/policy/settings/install changes и старых workers/мониторов.
`tt-auq.2` и PR85 HOLD, owned CI bugs, PAUSED `.5`, прежние связи и WIP сохранены.
Старый B/G1/G2 не является prerequisite текущей карты или `tt-x6t`.
