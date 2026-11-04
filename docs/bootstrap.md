# Запуск после clone

Установите Python 3.11+ и выбранный harness обычным способом. Bootstrap не устанавливает программы, не покупает доступ и не читает ключи или файлы авторизации.

Для подключения GitHub выполните [полную настройку GitHub CLI, авторизации и Project](github-setup.md). Project создаётся/подключается **до импорта Issues**; локальный интерактивный режим ниже остаётся доступен и не означает полной готовности GitHub.

Из папки клона:

```powershell
# Windows
.\start.cmd
# Или Python напрямую
python bootstrap.py
```

```sh
# macOS/Linux (не требует executable bit после clone)
sh ./start.sh
```

Скрипт определит платформу и предложит Codex, Claude Code, OpenCode или собственный адаптер. Укажите путь к настоящему `using-superpowers/SKILL.md` установленного Superpowers. Выбор сохраняется для данного проекта; последующие запуски его повторяют. Другой проект: `--project PATH`, другой harness: `--harness claude`.

## Проверить настройку без вызова модели

```powershell
python bootstrap.py --harness codex --superpowers C:/path/to/using-superpowers/SKILL.md --dry-run
python bootstrap.py --harness codex --superpowers C:/path/to/using-superpowers/SKILL.md --configure-only
python bootstrap.py --launch
```

`--dry-run` не пишет файлов и не запускает harness; показанная команда ссылается на будущий context.md. `--configure-only` сохраняет настройку без запуска. В неинтерактивном окружении запуск требует явного `--launch`; флаги режимов взаимоисключающие. В обычном терминале выбранная сессия запускается сразу. `python -m task_tower bootstrap ...` — альтернативный вход.

Явное подключение перед настройкой/запуском задаётся четырьмя флагами вместе: `--github-repository OWNER/REPOSITORY --connection-id ID --connections /private/path/connections.json --runner-label LABEL`. Дополнительный `--project-url URL` выбирает существующий Project. Используйте приватный путь установки вне checkout. Отказ доступа Projects останавливает работу до сохранения harness-конфигурации и запуска. При этих флагах `--dry-run` показывает непроверенный план: не вызывает GitHub, не создаёт Project и не пишет connections; готовность этим не подтверждается. Последующий запуск без GitHub-флагов остаётся локальным и не повторяет проверку GitHub.

`--executable PATH` задаёт конкретный установленный бинарник. В Windows требуется native `.exe`: неявное исполнение `.cmd/.bat/.ps1` отключено. Для shell-wrapper можно явно задать native интерпретатор в custom adapter; конфигурация считается доверенным исполняемым кодом. На macOS/Linux используется доступный executable из PATH или указанный путь.

## Собственный harness

Скопируйте [пример descriptor v1](../examples/custom-harness.json), укажите свой executable и аргументы:

```sh
python3 bootstrap.py --harness custom --adapter ./my-adapter.json --superpowers /path/to/using-superpowers/SKILL.md --configure-only
python3 bootstrap.py --launch
```

`launch_argv` — массив, а не shell-строка. `{project}` и `{instructions}` подставляются с сохранением границ аргументов; фигурные скобки литералов экранируются как `{{` и `}}`. Настройка хранит доверенный snapshot descriptor, а не автоматически перечитывает меняющийся скрипт конфигурации. Изменить его можно повторным `--adapter`. Сам исполняемый файл может обновляться вне Task Tower; его provenance пока не фиксируется.

## Границы интеграции

В `.task-tower/config.json` сохраняются выбор, override executable, skill pin и custom snapshot; `.task-tower/context.md` содержит инструкции для harness. Эти локальные пути исключены Git. Версия skill фиксируется SHA-256; изменившийся skill блокирует повторный запуск, пока пользователь явно не укажет `--superpowers` снова. AGENTS.md/CLAUDE.md не перезаписываются. Доставка prompt не доказывает соблюдения Superpowers.

В Task Tower исключение уже задано в .gitignore. Для стороннего проекта предварительно добавьте `.task-tower/` в его локальный Git exclude или .gitignore: bootstrap не меняет Git-настройки другого проекта автоматически. Не добавляйте локальную конфигурацию в коммит.

Поддержан интерактивный запуск. Авторизация, выбор модели, разрешения и сессия остаются в выбранном harness. Автономная очередь, callbacks, resume, structured events, автоматическая независимая приёмка и merge этим launch adapter не реализованы и не рекламируются capabilities. Нет флагов auto-approve, bypass sandbox или нового платного аккаунта. Bootstrap запускает обычную сессию в терминале, а не sandbox или supervisor ночной задачи; остановка дерева после его аварии этим режимом не гарантируется.

`--overlay` отдельно запускает Windows overlay без видимой PowerShell-консоли. Сейчас это наблюдатель **данных Codex**; он ещё не показывает сессии Claude/OpenCode/custom. На macOS/Linux этот флаг явно отклоняется, запуск harness остаётся доступен.

## Первая проектная задача

Для экспериментального общего GitHub-бэклога предусмотрен отдельный [shared-worker](shared-conveyor.md).
Он использует подключённый Project и приватный профиль, атомарный захват и установленный Superpowers.
Обычный интерактивный bootstrap не включает его автоматически; полный PR/main цикл ещё проходит разработку.

[TT-BOOTSTRAP-001](tasks/TT-BOOTSTRAP-001.json) — пилот собственной карточки Task Tower:

```sh
python -m task_tower task show docs/tasks/TT-BOOTSTRAP-001.json
python -m task_tower task accept docs/tasks/TT-BOOTSTRAP-001.json --stage spec --reviewer spec-reviewer --evidence docs/tasks/evidence/TT-BOOTSTRAP-001/spec-review.md
```

Этапы: spec → development → test → postmerge. CLI проверяет отдельного от executor приёмщика, порядок, наличие и хеш свидетельств; повторная приёмка раннего этапа сбрасывает последующие. Для postmerge нужны `--commit SHA`, содержащийся в локальной main, и отчёт реальной проверки этой версии. До этого статус `awaiting_merge`.

Это файловый пилот хранилища, не готовая очередь: назначения и вызовы приёмщиков выполняются агентами текущего чата. Reviewer ID пока организационный, не аутентифицированный; карточка и отчёты доступны редактированию владельцем. Хеш доказательства защищает от случайной устарелости файла, но сам по себе не связывает изменившийся код с проверкой: отчёты должны указывать проверенные версии/хеши. Проверка ancestry подтверждает только наличие указанного коммита в main, а полноту результата подтверждает приёмщик. Не использовать карточку как защищённый CI gate.

## Проверки

`python -m unittest discover -s tests -v`. Fixture harness действительно запускается отдельным процессом, получает cwd и context и возвращает код выхода без модели или расходов. Текущая CI/postmerge-проверка выполняется только на Windows по решению пользователя от 2026-11-04; macOS/Linux отложены в следующую версию. Наличие workflow не считается доказательством успешной проверки до завершения job.

CLI источники: [Claude](https://code.claude.com/docs/en/cli-reference), [OpenCode](https://opencode.ai/docs/cli/), [Codex](https://learn.chatgpt.com/docs/non-interactive-mode).
