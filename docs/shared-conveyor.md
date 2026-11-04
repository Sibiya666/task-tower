# Общая очередь GitHub

Экспериментальная реализация в ветке `feat/shared-conveyor`, задача [#19](https://github.com/Sibiya666/task-tower/issues/19).
Она ещё не прошла полный цикл PR → main → независимая приёмка → автоматическое закрытие.
Существующий bootstrap запускает обычную интерактивную сессию; этот воркер настраивается отдельно.

Каждый проект использует свои Issues и Project. Сначала выполните [подключение Project](github-setup.md).
Приватные connections и профиль воркера храните вне checkout; credentials в JSON не записываются.
Используется существующая авторизация GitHub CLI. Ни установка harness, ни смена модели или аккаунта не выполняются.

## Запуск

Из checkout Task Tower с Python 3.11+:

```sh
python -m task_tower shared-worker status --connections /private/connections.json --config /private/worker.json
python -m task_tower shared-worker run --connections /private/connections.json --config /private/worker.json
```

`--once` делает один проход; `--max-tasks N` останавливает процесс после N полученных результатов.
Без этих флагов воркер опрашивает очередь и после выполнения берёт следующую задачу.
Это foreground-процесс, не установленная служба. Для второго процесса нужны отдельные `worker_id`, `worker_name` и `workspace_root`.
Нативный `run` пока разрешён только в Windows; на macOS/Linux он возвращает `unsupported_platform`
до чтения подключений, создания рабочих каталогов и обращения к GitHub. Команда `status` переносима.
Число процессов определяет оператор по ресурсам и бюджету; общего лимита «два» здесь нет.

Пример структуры приватного профиля (замените пути, UUID, номера и task ID реальными разрешёнными значениями):

```json
{
  "version": 1,
  "repository": "owner/repository",
  "worker_id": "21fa8457-1c54-499d-aafa-91ce0bc27049",
  "worker_name": "desktop-1",
  "assignee": "github-login",
  "workspace_root": "/private/task-tower/workers/desktop-1",
  "superpowers_root": "/installed/superpowers/skills",
  "interval_seconds": 10,
  "harness": {
    "kind": "codex",
    "argv": ["/installed/codex"],
    "timeout_seconds": 1800,
    "log_max_bytes": 1048576
  },
  "allowlist": [{"repository": "owner/repository", "issue": 123, "task_id": "TT-EXAMPLE-001"}],
  "plans": {"123": "docs/superpowers/plans/example.md"}
}
```

В Windows используйте абсолютные пути с `/` или экранируйте `\\` в JSON.
План должен существовать в коммите main, выбранном при захвате; локальная исходная копия должна содержать этот коммит.
Нужен установленный Superpowers. Встроенный адаптер поддерживает Codex; для своего harness используйте
`kind: custom`, `trusted: true` и фиксированный `argv`. Адаптер получает `--request FILE --result FILE`.
Issue не может задавать исполняемую команду. Claude/OpenCode требуют явно настроенного собственного адаптера;
готовность их нативного выполнения этим модулем не подтверждена.

## Владение и приёмка

Уже назначенные Issues пропускаются. Победитель атомарного создания служебного Git ref
`task-tower/claims/issue-<immutable-id>` назначает настроенный GitHub assignee и проверяет результат.
Покажите поле Assignees на Project: оно отображает тот же аккаунт. При общем аккаунте
конкретного воркера различает worker/session ID в записи захвата, а не имя assignee.
Публикация assignee не заменяет блокировку; два процесса не получают право исполнения из одной свободной карточки.

Перед запуском фиксируется и подтверждается намерение исполнения. Потерянный ответ запуска,
перезапуск или снятие assignee не разрешают повторный запуск. Автоматического удаления, TTL и
перехвата захватов нет. Сохраняйте служебные refs и приватные протоколы для диагностики.
Служебные claim-ветки исключены из push-триггера Portable CLI; кодовые ветки и PR сохраняют CI.
До попадания этого исключения в main не проводите массовый пилот захватов: прежний workflow запускает CI на каждом ref.

Каждая работа использует отдельный Git worktree в собственной приватной копии репозитория.
Хост сохраняет фактические сведения процесса и проверяет служебные настройки Git перед чтением результата.
Приватные Git-настройки проверяются в памяти; их содержимое не копируется в логи.
Унаследованные `GIT_*` удаляются из окружения harness. Перед вызовом сохраняется приватный
`execution-fence.json`: пока остановка всего дерева процессов не подтверждена, этот воркер
не получает следующую задачу, в том числе после перезапуска. Не удаляйте fence ради повторного запуска.
То же правило действует для каждого служебного Git-процесса до и после harness;
его фактический результат сохраняется отдельно перед проверкой cleanup.
`execution_completed` от harness переводит работу только в `awaiting_acceptance`; задача остаётся открытой.
Независимая приёмка и подтверждённый main обязательны. For new tasks, see the Windows pipeline handoff below; legacy results require separate acceptance.

Сейчас автоматически допускаются только явно разрешённые открытые autonomous-задачи без зависимостей;
задачи с зависимостями блокируются до подключения проверяемого selector. Не снимайте зависимости ради запуска.
Ошибки конфигурации/транспорта останавливают foreground-процесс с `needs_input`; supervisor/revoke/recovery требуют дальнейшей реализации.

## Проверенные границы

Два независимых Windows-процесса через общий HTTP fixture подтвердили единственный запуск,
назначение assignee, перекрытие работ и заполнение свободного места третьей задачей.
Использованы настоящие скрипты Superpowers и детерминированный harness.
Это не реальный GitHub/LLM, не две машины и не доказательство ночной готовности.
Переносимая логика сохраняется; нативная квалификация macOS/Linux остаётся следующей версией.

Отдельный [реальный GitHub-пилот владения #69 и исправление Windows handles](shared-conveyor-evidence.md)
проверяют серверную гонку и отказ повторного захвата. Его первоначальный cleanup failure сохранён;
эта проверка не заменяет полный запуск модели, приёмку main или автоматическое закрытие.


Scope amendment, explicit user decision 2026-11-04: all macOS/Linux actions, including CI, native/manual diagnostics and postmerge execution, are deferred to #58–#62. Current release execution and acceptance are Windows-only. Preserve portable code and historical receipts. Fresh Windows profiles must explicitly require windows; do not rewrite accepted history or treat old all-platform receipts as a new Windows acceptance.

## Windows pipeline handoff

For new tasks, `harness.kind: pipeline` delivers the claimed identity to the
existing [stage pipeline](pipeline.md) before any shared-worker model launch.
Legacy `custom`/`codex` results remain awaiting separate acceptance; they cannot
be converted into stage receipts or re-executed through this adapter.

Review this template before installing it outside source checkouts. Issue 123 is
a placeholder, not an authorization or installed pilot. Existing connections,
executor profiles, pinned skills and pipeline task policy must already exist.

```json
{
  "version": 1,
  "repository": "owner/repository",
  "worker_id": "21fa8457-1c54-499d-aafa-91ce0bc27049",
  "worker_name": "windows-pipeline-1",
  "assignee": "github-login",
  "workspace_root": "C:/TaskTower/private/shared-worker-1",
  "superpowers_root": "C:/installed/superpowers/skills",
  "interval_seconds": 10,
  "harness": {
    "kind": "pipeline",
    "connections": "C:/TaskTower/private/connections.json",
    "config": "C:/TaskTower/private/pipeline.json",
    "executor_config": "C:/TaskTower/private/executor.json",
    "journal": "C:/TaskTower/private/pipeline.db"
  },
  "allowlist": [{"repository": "owner/repository", "issue": 123, "task_id": "TT-EXAMPLE-001"}],
  "plans": {"123": "docs/superpowers/plans/example.md"}
}
```

The matching pipeline task keeps all existing required fields, profile, checks,
components, allowed paths and publication controls. Add `"shared_worker": true`
and `"ci_substitution": {"enabled": true, "required_platforms": ["windows"]}`.
Repository, Issue, task ID and plan must match the shared allowlist. Keep
publishing disabled until independently authorized. Existing history is unchanged.

`shared-worker run --once` consumes the confirmed intent, writes a private fence
and submits the claim UUID as the delivery ID. The existing journal creates a
queued run with no stage attempts or verdicts. The original worker saves the real
admission receipt, then CAS-confirms `awaiting_acceptance` with the exact run UUID
and consumer digest (selected journal path and installed policy/profiles). Only
that run/consumer may execute. A second journal cannot obtain authority from the
visible claim UUID. Ordinary dispatcher/adapter submits for these opted-in rows
are rejected before reserving an Issue's unique journal slot.

Run existing `pipeline work --once` or `pipeline watch` separately with those same
private files. Pending or foreign handoffs wait unclaimed, with no model launch.
Before preparation and every owned continuation, the pipeline checks immutable
Issue identity, claim criteria, assignment, current main and exact run/consumer.
Its existing role processes, containment, limits, independent reviews, checks,
checkpoints and PR consumer create genuine evidence. With publishing disabled it
stops at `ready_for_pr`; separately authorized publishing may reach `awaiting_pr`.
Neither means accepted main, Done or automatic closure. Assignee and claim remain.

A lost admission response leaves `execution_intent` and the private fence. A
lost final CAS response may leave a confirmed bound run on GitHub, while the
worker stays fenced. Neither permits resubmission, claim expiry or restart replay.
The CLI reports `needs_input` on failure. Inspect shared status and preserve
private `handoff.json`, `handoff-result.json`, `outcome.json`, the fence and both
journals. The outcome file binds the locally confirmed admission; a retained
fence still means final shared confirmation is unresolved. Do not delete state to
recover. Other independent workers may continue
unrelated authorized work. This mode installs no service or tools and changes no
authentication, model or provider.

### Remaining external evidence

Local implementation and regression scope are recorded separately in the
[Task 71 implementation record](evidence/2026-11-04-shared-pipeline-handoff.md).

The preserved real ownership pilot names [Issue #69](https://github.com/Sibiya666/task-tower/issues/69);
[Issue #71](https://github.com/Sibiya666/task-tower/issues/71) implements this local
handoff. Neither establishes a new successful full conveyor pilot. Fixture tests
cover admission, unknown/restart fencing and the existing six-role/check/local
PR-preparation path, with publication disabled. They are not real GitHub/model or
multi-machine evidence. The coordinator must explicitly name fresh authorized
pilot Issues in the existing writable Project, review private profiles, retain
native GitHub/harness evidence, obtain exact-head/base review and Windows CI, and
verify authorized exact-main acceptance and automatic closure. This run creates
no pilot Issues and performs no publishing. macOS/Linux/WSL execution, CI and
diagnostics remain deferred to #58-#62.
