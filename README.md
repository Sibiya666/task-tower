# Task Tower — Башня агентов

Task3BRa registration/adoption/discovery now has [bounded independent acceptance and a925-test full receipt](docs/tasks/evidence/TT-GROUPS-001/task3bra-acceptance.md). Explicit registration uses actual private G/P/E/C/J inputs and existing v2 storage; it does not enable registered execution. Pure wire, resource scheduling, workspace proofs, Task17 interoperability and original hot recovery65 remain pending. Never apply registration or migration to live private state implicitly.

Issue18 Task1R-L adds strict v2 executor/pipeline capacity and harness-resource metadata loaders while preserving v1 outputs and two-slot behavior. Current execution entry points refuse v2 with `group_runtime_unavailable` before effects, including freshly reloaded watch policy; existing watch shutdown cleanup remains active. This enables metadata loading only: Resource scheduling and execution above two slots remain gated; G registration is covered by Task3BRa below. Original hot recovery [Issue65](https://github.com/Sibiya666/task-tower/issues/65) remains mandatory. [Scoped review and full-suite receipt](docs/tasks/evidence/TT-GROUPS-001/task1rl-acceptance.md).

Issue18 Task3A adds explicit cold pipeline-journal migration: `python -m task_tower.pipeline migrate --connections C --journal J --inspect|--apply` (choose one mode). An actual SQLite rollback-required error776 during the first existing-only read-only inspection returns exactly `{"status":"recovery_required","version":null}` with exit1 and leaves the original journal and sidecars untouched. Original automatic hot recovery remains mandatory current Windows [Issue65](https://github.com/Sibiya666/task-tower/issues/65). This storage slice does not enable G registration, resource scheduling or group execution, or complete Issue18. [Review and verification evidence](docs/tasks/evidence/TT-GROUPS-001/task3a-storage-acceptance.md).

Postmerge worker получает свежий `main` с отдельным сетевым лимитом fetch 60 секунд; локальные проверки Git ограничены 10 секундами. Ошибка fetch не разрешает приёмку или закрытие Issue. [Запуск и диагностика worker](docs/postmerge-worker.md).

Границы текущего релиза: новые нативные pipeline, группы и OpenCode квалифицируются для Windows. Нативные Linux/macOS вынесены в [следующую версию #58](https://github.com/Sibiya666/task-tower/issues/58); переносимый CLI и применимый трёхплатформенный CI сохраняются. [Матрица поддержки и задачи](docs/platform-support.md).

Один проект для организации агентной разработки и её визуализации. Проекты представлены фэнтезийными башнями, сессии — этажами, агенты — сотрудниками внутри помещений.

Сейчас работают **прозрачный Windows-оверлей** с локальными данными Codex, **CLI аудита готовности проектов**, bootstrap установленного harness и независимая приёмка после слияния. Подключения GitHub-проектов, три книги в CLI/HTML и очередь приёмки для self-hosted runners настраиваются отдельно; доступен [foreground-исполнитель Codex/custom](docs/executor.md) с устойчивой локальной очередью; локальный pipeline автоматических этапов реализован в этой ветке и проходит приёмку; автоматическое слияние остаётся в #17. Оверлей наблюдает за работой и сам не запускает агентов.

У каждого подключённого проекта свои Issues, GitHub Project и Markdown-артефакты. Приватный список подключений принадлежит установке, а не репозиторию продукта. [Подключения и книги](docs/github-books.md), [распределённая приёмка и установка runners](docs/github-projects.md).

[Процесс непрерывной и параллельной разработки](docs/development-process.md): после явной авторизации бэклога координатор запускает готовые независимые задачи по доступной ёмкости исполнителей, ресурсам и явным бюджетам, без фиксированного потолка «две задачи», и сам заполняет свободную ёмкость. Рабочие копии и приёмка раздельны; слияние и проверка main последовательны в каждом репозитории. Локальный исполнитель описан в [инструкции](docs/executor.md), pipeline этапов — в [операторском руководстве](docs/pipeline.md). Текущий runtime v1 сохраняет первоначальный предел в два слота; перенос ресурсной политики в runtime выполняется в #18. Третий установленный Codex-пилот прошёл шесть настоящих ролей, три одобрения и host-check до ready_for_pr; независимый аудит относится к source8981c6d и тестовому GitHub-транспорту. Свежие проверки ветки и main остаются обязательными. Группы и распределённое владение развиваются в #18/#19.


Книжная полка: «Идеи» хранит предложения, «Задачи» — этапы Milestone, крупные фичи в родительских Issues и их подзадачи, «Библиотека проекта» — связанные спеки, исследования и результаты. Этап и фича — отдельные связи: фича может проходить через несколько этапов. CLI/HTML сохраняет плоский список; оверлей добавляет иерархические книги через контекстное меню или Ctrl+B. Перед запуском задайте `TASK_TOWER_CONNECTIONS` с путём к личным подключениям: [инструкция](overlay/README.md#книги-проекта). Native-приёмка этой интеграции #23 фиксируется отдельно от браузерных тестов.

Для нового подключения сначала настройте GitHub CLI и создайте/подключите Project, затем импортируйте Issues: [пошаговая настройка с чистого clone](docs/github-setup.md). Bootstrap принимает явные GitHub-флаги и останавливает запуск при отказе Projects; локальный запуск без них не доказывает GitHub-готовность. [Roadmap и реальные Issues 13–28](docs/roadmap.md): фундамент #24, #14, #22, #15 и книги #23 прошли exact-main приёмку и автоматическое закрытие к main56f8ab1. Актуальные фазы и зависимости смотрите в [Issues](https://github.com/Sibiya666/task-tower/issues) и [Project](https://github.com/users/Sibiya666/projects/2). Исполнитель запускается явно через `executor work --once`; pipeline `work --once`/`watch` описан отдельно. Наличие команды не доказывает готовность без присмотра.

Работающий локальный watcher также может [публиковать успешную приёмку и закрывать связанную Issue](docs/github-publication.md). Для этого в приватной конфигурации явно задаются сопоставления задач и доверенный аккаунт; установка self-hosted runner для этого режима не требуется.

## Скриншоты

Реальные пользовательские скриншоты приложения с обработкой фона для документации. Экспорты — прозрачные PNG на одинаковом холсте 960×640 с сохранением пропорций. [Исходники и описание обработки](docs/screenshots/README.md).

![Башни проектов](docs/screenshots/overview.png)

**Обзор проектов.** Башня соответствует проекту, этаж — сессии. Свет в окнах показывает работу основного агента или субагентов. Высокие башни равномерно уменьшаются, как объекты вдали.

![Кабинет астролога](docs/screenshots/study.png)

**Небольшая команда.** Цельный кабинет астролога с двумя сотрудниками. Инструмент обозначает работу, песочные часы — ожидание. У каждого персонажа собственная подсказка с именем, ролью и состоянием.

![Большой зал](docs/screenshots/hall.png)

**Большая команда.** Готический зал с общим сводом и единым полом. Все сотрудники отображаются внутри помещения; мебель остаётся в глубине и у стен.

## Запуск

Выбор установленного Codex / Claude Code / OpenCode / собственного harness после clone:

```sh
python bootstrap.py
```

Python 3.11+; также доступны `start.cmd` на Windows и `sh start.sh` на macOS/Linux. Выбор и контекст Superpowers сохраняются локально. [Настройка, ограничения и первая задача Task Tower](docs/bootstrap.md).

Windows, Windows PowerShell 5.1 с WPF, WebView2 Runtime и Python 3.11+.

```powershell
.\overlay\start-tower.cmd
```

`overlay/launch-codex-tower.ps1` открывает установленное приложение Codex и оверлей. Ярлык рабочего стола указывает на него. Python ищется в bundled runtime Codex: при переносе проверьте путь в `overlay/run-html-overlay.ps1`. Node нужен для тестов и подготовки графики, а не для запуска готового оверлея.

Нажмите этаж, чтобы войти. ← возвращает к башням, ◆ закрепляет окно, × закрывает. Оба экрана перетаскиваются за рисунок; движение от 5 пикселей считается перетаскиванием. Поле башен прокручивается колёсиком.

Открытая комната сдвигается внутрь рабочей области текущего монитора с учётом панели задач и DPI. При возврате восстанавливаются прежние координаты и размер обзора, а также прокрутка поля башен. Перемещение комнаты не меняет сохранённое положение обзора; при недоступности прежнего места окно сдвигается в доступную рабочую область.

Оверлей также проверяет границы после перетаскивания/изменения размера и перед открытием настроек. Сохранённая позиция за пределами рабочей области корректируется; недоступные части окна и панели не сохраняются намеренно.

## Интерьеры и агенты

- Четыре размерности: кабинет для 1–4 сотрудников, мастерская для 5–8, зал для 9–16, большое помещение для 17+. По три цельных скина каждой размерности — всего 12.
- Размер выбирается **при входе** и сохраняется до выхода. Вариант закреплён по ID сессии. Новые агенты появляются в текущем помещении без смены фона.
- Все текущие сотрудники видимы, скрытого остатка `+N` нет. Новые агенты заходят на этаж; завершившие задачу выходят и исчезают. Уже завершённые исторические агенты при открытии комнаты не показываются. Персонажи распределены по полу и рисуются с учётом глубины.
- Песочные часы означают явное ожидание вашего решения по незакрытому запросу ввода/подтверждения. Обычный простой показан нейтральными точками. Текстовые вопросы в произвольном ответе не распознаются эвристически; без структурированного события ожидание не выдумывается.
- У разработчиков, проверяющих и исследователей/дизайнеров по четыре облика. Главный агент — маг. Модель стабильно выбирается по ID.
- Анимированы дыхание, рабочие движения, инструмент, песочные часы, облака за стеклом и свет свечей. Учитывается системное уменьшение движения.
- Башни сохраняют участки на поле и занимают несколько рядов. Наведение слегка осветляет камень выбранного этажа.
- Участки привязаны к правому краю, ближе к управлению, без пустой третьей колонки при двух проектах. При появлении нового работающего агента на открытом обзоре персонаж подходит к двери башни и входит; начальная загрузка и повторные обновления не воспроизводят этот вход.

### Мир, освещение и погода

Правый клик по сцене открывает компактные настройки. Постоянные кнопки управления остаются прежними. Освещение по умолчанию следует местному времени: рассвет 06–08, день 08–18, сумерки 18–20, ночь 20–06. Можно вручную выбрать день или ночь. Переключение плавное, без непрозрачной подложки поверх рабочего стола.

Солнце или луна на сцене показывают фазу освещения. В настройках есть строка «Сейчас: …» с местным временем или пометкой ручного режима. Сетка адаптируется к ширине окна: до трёх колонок, без обрезания башен по горизонтали; следующие ряды доступны вертикальной прокруткой.

Погода выбирается вручную: ясно, облачно, дождь, туман. Используются прозрачные пиксельные эффекты PixelFX; облака находятся за башнями, осадки не перехватывают мышь. Эффекты можно отключить. При системном уменьшении движения показывается статичный кадр.

Башни с более чем восемью сессиями в обзоре имеют компактный дальний силуэт из четырёх декоративных секций. Это уровень детализации обзора, а не удаление/объединение чатов: рядом показано настоящее число этажей. Нажмите плашку «N этажей» для полного списка сессий или переключения на изображение всех этажей. Подсветка декоративной секции означает активность хотя бы одной соответствующей реальной сессии.

Башня скрывается после 30 минут подтверждённого простоя. В настройках доступны 10/30/60 минут или отключение скрытия, а также «Показывать скрытые башни». Активность и ожидание решения возвращают/сохраняют башню; неизвестное состояние, ошибка и устаревший источник не запускают скрытие. Проекты, чаты и их данные не удаляются; участок сохраняется. Настройки и время простоя сохраняются только в локальном профиле WebView2.

## Данные

Сборщик раз в 3 секунды читает локальную `~/.codex/state_5.sqlite` в режиме `mode=ro` и JSONL-журналы. База, журналы и настройки Codex не изменяются; их содержимое не отправляется в сеть. Внутренние форматы Codex не являются стабильным публичным API.

Источник старше 12 секунд считается недоступным; активный журнал без событий более 180 секунд получает состояние «Нет свежих событий». В этих случаях свет не изображает подтверждённую работу. Guardian-сессии скрыты. Вложенные субагенты относятся к родительской сессии; проекты определяются по связям Codex, корням репозиториев и Git worktree.

Каждое окно получает свой сборщик и `overlay/runtime/snapshot-<pid>.json`; актуальный путь указан в `overlay/runtime/overlay-source.json`. Закрытие окна завершает только его сборщик. Runtime, профили браузера и приватные привязки проектов исключены из Git.

## Структура

```text
task_tower/       CLI аудита готовности (Python standard library)
tests/           тесты CLI
examples/        манифесты проектов
overlay/         Windows-хост, сборщик, UI, графика и тесты оверлея
  web/           HTML/CSS/Canvas и подготовленные PNG
  assets/        исходники графики и промпты
  vendor/        WebView2 SDK и лицензии PixelFX
docs/            архитектура, планы, отчёты, скриншоты
```

## CLI готовности

Получение merge-событий, отдельный агент-приёмщик и обновление карточек: [postmerge worker](docs/postmerge-worker.md).

```powershell
python -m task_tower audit --project C:/path/to/project --manifest examples/dialoid.project.json --output ../runtime/readiness.json
```

Без `--run-checks` выполняется аудит; с ним — явно запрошенные команды манифеста с ограничением времени и жизненного цикла процессов. Это не sandbox и не разрешение на автономное слияние. Коды выхода и ограничения: [документация CLI](docs/readiness.md).

## Проверки

```powershell
python -m unittest discover -s tests -v
Push-Location overlay
python -m unittest -v
node --test test-web.cjs test-room-skins.cjs test-presence.cjs test-presence-browser.cjs test-scene-position.cjs test-session-light.cjs test-tower-arrivals.cjs test-world-policy.cjs test-world-browser.cjs test-visual-audit.cjs
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File overlay.ps1 -SmokeTest
Pop-Location
```

Браузерным тестам нужны Playwright, Sharp и установленный Edge. Пути к bundled Node-модулям Codex сейчас машинно-зависимы. Нативная проверка использует реальные данные, сохраняет PNG в игнорируемую `overlay/runtime/` и закрывает тестовое окно.

## Разработка

См. [AGENTS.md](AGENTS.md), [архитектуру](docs/superpowers/specs/2026-11-01-agent-development-architecture-design.md) и [устройство оверлея](overlay/README.md). Не выдавайте планы оркестрации за реализованные возможности.

Графика создана через imagegen; исходники и промпты находятся в `overlay/assets/`. Эффекты PixelFX имеют MIT license и дополнительные атрибуции в `overlay/vendor/pixelfx/`. Условия WebView2 SDK сохранены в `overlay/vendor/webview2/sdk/`. Лицензия всего проекта отдельно не назначена.

## Foreground Issue dispatcher

`python -m task_tower dispatcher --connections PRIVATE_CONNECTIONS --config PRIVATE_CONFIG --journal PRIVATE_JOURNAL --once` delivers authorized ready identities to a trusted custom adapter. See [configuration, recovery and limits](docs/dispatcher.md). The default dispatcher polls in the foreground; delivery is not development execution or accepted task completion. Current task phases and integration receipts belong in repository Issues and the linked Project. The local [stage pipeline](docs/pipeline.md) coordinates bounded independently reviewed stages. Its third installed Codex pilot reached ready_for_pr after six real roles, three approvals and a host check at source8981c6d with fixture GitHub transport; every release still requires its own current CI and integration acceptance. Two slots overlap across different repositories while same-repository actions serialize. Explicit publication may create a PR; this pipeline never merges or closes an Issue.

Active-chat authorization continues to the next eligible backlog task after every main/postmerge/Issue-closure cycle without another continue. It does not establish a background development daemon.

## Explicit session capture

[Capture, idea promotion and legacy migration](docs/session-capture.md) use explicit input and the selected project. Original text/session provenance and native parent/milestone links are retained. Ideas do not execute implicitly; migration keeps the original card/evidence bytes and exposes drift while GitHub remains canonical. No all-chat scraping or Codex database writes are involved.

Task3BRb now has [bounded pure epoch/stage2/role3 shape acceptance](docs/tasks/evidence/TT-GROUPS-001/task3brb-stage-role-acceptance.md). These helpers do not choose a live run kind or grant epoch/resource/workspace authority. Legacy stage1/role2 file consumers remain exact; remaining group bodies and all durable consumers stay gated.

Task3BRb pure request3/check-aggregate2 syntax and owned macOS temporary-path fixture correction have [bounded acceptance](docs/tasks/evidence/TT-GROUPS-001/task3brb-request-check-acceptance.md). Actual group producers, instructions/check membership/current-epoch proof and durable consumers remain gated; parser shape success is not execution authority.

Pure group checkpoint2/evidence2 syntax has bounded independent acceptance; see docs/tasks/evidence/TT-GROUPS-001/task3brb-checkpoint-evidence-acceptance.md. Product manifest1 and legacy producers remain unchanged; syntax never grants group execution or epoch authority. Actual resource/workspace/epoch consumers and Windows hot recovery65 remain required.

The remaining pure group check-wrapper1/stage2 and verdict2 shapes passed bounded independent acceptance; see docs/tasks/evidence/TT-GROUPS-001/task3brb-verdict-wrapper-acceptance.md. All named wire syntax is present, while durable group consumers/execution remain closed pending actual resource/workspace/current-epoch authority.

Task4R internal read-only resource observations and conservative arithmetic have bounded independent spec/implementation acceptance and57-test regression; see docs/tasks/evidence/TT-GROUPS-001/task4r-observation-acceptance.md. Imported JSON/SQL history cannot install a current sample. No resource leases/claims or registered execution were enabled; actual transactional admission and workspace/epoch gates remain required.

Task4R genuine queue-only group producer is independently accepted with101 migration/registration/queue tests; see docs/tasks/evidence/TT-GROUPS-001/task4r-queued-acceptance.md. Queue metadata never grants execution. Preserve actual-context routing, immutable original delivery and fresh private policy binding; registered runtime remains closed until coupled claim/workspace consumers are accepted.


Bounded source-only group preparation/guard has independent specification/development acceptance and125 current regression tests; see docs/tasks/evidence/TT-GROUPS-001/task4r-source-guard-acceptance.md. The actual collector runs in a fixed contained host child under its original registration deadline, with a typed bounded control channel and mandatory parent cancellation. Source-observed is diagnostic only: no graph/admission/resource cache crosses into parent execution authority. This foundation rejects claimed Task/role/check/publication/idle events and does not activate registered grouped work. Keep all real claim/workspace/resource/epoch/Windows65/pilot/PR/main gates.
