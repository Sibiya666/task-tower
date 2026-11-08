# Передача проблем интеграции Task Tower — 2026-11-08

## Решение владельца

Работу над исправлениями остановить. Передать найденные проблемы отдельной
Markdown-веткой в проект Task Tower; дальнейшую разработку ведёт владелец.
Этот документ — отчёт, а не разрешение запускать workers, миграции или backlog.

Проверенная база: `7a816d7516abeb9b3c9b211ad4f53ee48589c3da` (`origin/main`).
Ниже разделены подтверждённые ограничения, наблюдавшийся сбой CI и ещё
не завершённая проверка реального исполнения.

## 1. Новые карточки не подхватываются работающим исполнителем

**Приоритет: высокий.** Пользователь ожидает: менеджер записывает задачу в
Beads, Task Tower сам забирает разрешённую ready-задачу и запускает Codex
с отдельным reviewer. Установленный путь этого пока не обеспечивает.

- `task_tower/connector/cli.py`, `work`: конфигурация загружается один раз;
  admission проходит только по исходному списку `assignments`.
- Service допускает только опубликованные immutable approved plans.
- Запущенный для Вейры HTTP service доступен, но managed ready возвращал 0,
  хотя native Beads содержал готовые карточки. Пустой managed ready не означал
  отсутствие задач в native-источнике.

**Ожидаемая приёмка:** записать новую разрешённую карточку после запуска
connector; без ручного claim/turn/start получить настоящий native claim,
author thread, отдельный reviewer и сохранённый результат. Сохранить лимиты,
approval callbacks, неизвестные исходы и границы credentials. Старый backlog
не должен становиться разрешённым автоматически.

## 2. Нельзя принять существующие native-карточки без пересоздания

**Приоритет: высокий.** `service/store.py::import_plan` создаёт новые
deferred-карточки через `bd create --id`; уже существующие IDs не являются
поддержанным сценарием adoption. Попытка приводит к reconciliation.
`_verify_row` старого пути ожидает только blocking dependencies и не допускает
существующие `parent-child` связи.

**Нужно:** явное принятие точного approved native snapshot с сохранением ID,
истории, parent-child, владельца и состояния. Проверять drift текста,
зависимостей, статуса и metadata до публикации и заново перед claim.
Не редактировать SQLite и не удалять родительские связи для обхода проверок.

## 3. Существующая база popo несовместима с текущим адаптером

**Приоритет: высокий для подключения popo.** В popo установлен Beads 1.0.2,
у нового изолированного подключения Вейры — 1.3.4. Проверены help-команды
старого бинарника: `history` не имеет `--events`, команды `events` нет.
`service/beads.py::history` требует `history <id> --events --limit 100`.
`service/cli.py` задаёт один `executable` на всю service config, отдельного
выбора версии по проекту нет.

База popo **не открывалась** новым бинарником, не копировалась и не
мигрировалась. Чужие WIP/claims не менялись. Нужен поддержанный compatibility
route либо отдельно согласованный и проверенный single-writer переход
с резервной копией. Не создавать вторую очередь того же проекта и не
подменять историю фиктивными событиями.

## 4. Delivery рассчитан на main, правила проектов отличаются

**Приоритет: высокий перед включением delivery.**
`connector/delivery.py` создаёт PR с `base='main'`; merge/postmerge также
проверяют main. Универсальное подключение текущих проектов этим не покрыто.

| Проект | Существенная граница |
| --- | --- |
| Вейра / asistent | RPG-ветка `codex/veyra-rpg`; не брать tsunade WIP за RPG base |
| popo | Default branch `master`; существующая база Beads 1.0.2 |
| Blue-Oyster | PR в `test`; merge выполняет владелец, агентам merge запрещён |
| dialoid | Локальный Git, remote отсутствует; не выдумывать GitHub delivery |

До поддержки этих политик `delivery_projects` оставлен пустым. Это допускает
границу execution/review, но не доказывает доставку PR или принятие main.
Нельзя включать auto-merge в Blue-Oyster или ослаблять защиты Task Tower.

## 5. Наблюдавшийся сбой Windows CI

[PR #119](https://github.com/Sibiya666/task-tower/pull/119),
[run 42518138586](https://github.com/Sibiya666/task-tower/actions/runs/42518138586),
job `128845664217`, shard 2: 282 теста, один error.

`OperatorCLITests.test_import_prints_canonical_published_batch_and_repeat_has_no_duplicate_effects`
упал в `setUp`, `tests/test_service_api.py::private_token`: процесс Windows
PowerShell подготовки приватного файла превысил 5 секунд. Причина задержки
не установлена; это не доказанный регресс нового кода и не успешный CI.
Scope и Linux headless container smoke к этому моменту прошли.

Попытка повторить один job была отклонена GitHub: весь workflow ещё выполнялся.
Повтор фактически не запущен. Не увеличивать таймауты и не ослаблять ACL
без диагностики. Итог остальных jobs после остановки работ не проверялся.

## Сохранённый незавершённый прототип

Ветка `codex/project-intake`,
H `367b11f0d62ce19f93b6bfac7d29f0586b325703`, B указан выше.
[PR #119](https://github.com/Sibiya666/task-tower/pull/119) переведён в **draft**;
не merged и не установлен в работающий service.

Прототип добавляет authenticated `plan adopt`, повторные readback,
parent/metadata fences и append-only reload approvals/assignments.
Ограничение прототипа: все adopted rows должны быть open/unassigned,
blockers — внутри approved batch; внешние parents допустимы. Исторические
закрытые blockers вне batch пока не поддержаны.

50 профильных тестов автора прошли; независимый reviewer одобрил точные H/B
и выполнил 43 профильных теста. Это не заменяет полный CI и реальный pilot.
Полный первоначальный macOS-прогон: 1115 тестов, 60 failures, 11 errors,
33 skips. Один новый fixture error исправлен и покрыт профильным rerun;
три представительных старых сбоя воспроизведены на неизменённом B. Остальные
сбои не объявлялись исправленными. Текущая проверка main не завершена.

## Состояние подключения и продолжение

- Разрешены только проекты текущего Codex: popo, dialoid, asistent/Вейра
  и Blue-Oyster — явный дочерний репозиторий общего проекта `project`.
  Соседние репозитории исключены; checkout `bot-role` не подменяет Blue-Oyster.
- Приватные файлы находятся на Mac в `~/.local/share/task-tower/veyra/`:
  `project-registry.json`, `service.json`, `service.pending.json`,
  `connector.json`, `project-intake-review.json`, `art-stock-intake.json`.
  Токены и конфигурацию целиком не публиковать.
- Исходный headless HTTP service ранее запущен на `127.0.0.1:8766`;
  новые pending-настройки не активированы. Connector, pool и автозапуск
  не запускались. Сохранить journal и claims при продолжении.
- Подготовленные native источники Вейры, asistent, dialoid, Blue-Oyster
  проверены штатным адаптером; источники новых проектов пока пусты.
- Native `veyra-v7l.9` — незавершённая интеграция; не закрывать как выполненную.
  Заказ артов: `.10` — задники, `.7` — портреты. Snapshot подготовлен,
  adoption/assignments не опубликованы, генерация не начата.
- В native карточках нет второго scheduler. Markdown — передача контекста.

Перед продолжением перечитать AGENTS и свежие native статусы, проверить
реальные процессы и CI, затем выбрать поддержанный integration route.
В рамках этой передачи не возобновлять исправления и не запускать задачи.
