# Автоматическая postmerge-приёмка

Worker замыкает цепочку: GitHub artifact → проверка события и трёх платформ → отдельный reviewer process → локальная карточка задачи. Код workflow и source совместно проверяют repository, PR, SHA, run/attempt, marker и digest ZIP. Файлы artifact не распаковываются как пути и не исполняются.

## Настройка и запуск

Python 3.11+, Git, доступ Actions:read и установленный Codex. Для другого приёмщика задаётся machine-readable custom protocol; обычный интерактивный launch adapter не подходит автоматически.

1. Настройте bootstrap в выбранном проекте с реальным Superpowers SKILL.md (`--configure-only`).
2. Скопируйте [пример worker config](../examples/postmerge-worker.json) или используйте его с `--project`. `project` и относительный skill path считаются от каталога config. В примере skill pin берётся из локальной bootstrap-настройки; можно явно задать `reviewer.superpowers: {path, sha256}`.
3. Первый ограниченный запуск, без постоянного цикла:

```sh
python -m task_tower worker --config examples/postmerge-worker.json --project /path/to/project --once
```

Постоянный цикл:

```sh
python -m task_tower worker --config examples/postmerge-worker.json --project /path/to/project
```

Он работает, пока запущен процесс и включён компьютер. Автозагрузка ОС не устанавливается. Запуск можно оставить в терминале на ночь; Ctrl+C останавливает worker. При сетевой ошибке цикл ждёт следующий интервал, не закрывает задачи и не перезапускает уже захваченного приёмщика. Сообщения печатаются при изменении состояния, а не при каждом неизменном poll.

GitHub авторизация: GH_TOKEN/GITHUB_TOKEN, существующий `gh auth token` либо Git credential helper с отключёнными интерактивными запросами. Ключ не записывается в config и не выводится; GitHub-token удаляется из окружения приёмщика и из Authorization при redirect artifact на storage. Для private repo могут потребоваться дополнительные права существующей авторизации. Не добавляйте секреты в аргументы или JSON config.

`origin` проекта должен соответствовать configured GitHub repository. Worker делает fetch main, не переключая вашу ветку, и проверяет ancestry в origin/main. Исходники для ревью берутся в отдельную чистую detached копию точного SHA. Пользовательская грязная копия и её код не используются как тестовый стенд и не сбрасываются.

## Статусы и сбои

Карточки находятся в docs/tasks/TT-*.json. Связь PR задаётся `Task-Tower: TT-...` в description. Все prior spec/development/test должны быть приняты с актуальными хешами. Legacy stale требует явной повторной приёмки, автоматической миграции нет.

- Нет части платформ: awaiting_postmerge.
- Карточка ещё не появилась в локальном пуле: событие ждёт в journal и повторяется после её появления без вызова модели.
- CI failed: postmerge_failed, модель не запускается.
- Все обязательные платформы passed: postmerge_review, отдельный агент проверяет результат.
- approve на том же ID/SHA и неизменившемся задании: accept_task(postmerge) → done.
- reject: postmerge_failed; needs_input, timeout, невалидный ответ, stale или изменение задания: needs_input, не done.

Отчёты остаются в docs/tasks/evidence/{id}/postmerge-{sha}.json; изменения карточек и отчётов сохраняются локально без автоматического commit/push. Нужно исключить `.task-tower/` в Git вашего проекта; в Task Tower это уже сделано. Journal и runtime-копии живут там. Это локальное постоянное состояние, не облачная синхронизация карточек между компьютерами.

Повторная доставка task+SHA не вызывает второй процесс. Ответ сохраняется в SQLite **до** применения карточки, поэтому после такого сбоя его можно применить без второго вызова модели. После сбоя во время процесса journal сохраняет running: исход неизвестен, автоматического retry нет.

```sh
python -m task_tower worker --config worker.json --status
python -m task_tower worker --config worker.json --retry TT-ID COMMIT
# Только проверив, что старый reviewer действительно остановлен:
python -m task_tower worker --config worker.json --recover TT-ID COMMIT --confirm-stopped
```

Обычный retry отказывает для running/done. recover явно снимает только прерванный running по заявлению оператора; это не способ запускать конкурирующего приёмщика. max_reviews ограничивает новые вызовы за poll; timeout ограничивает один процесс. Точное денежное ограничение провайдера не обещается. Каждый task+SHA запускается один раз до явного retry. Внешние редактирования файла не являются транзакциями SQLite: snapshot проверяется повторно при приёмке и перед атомарной записью; при обнаруженном конфликте результат не применяется.

Новый merge сам не переоткрывает done. Старый failed run не может отменить done более позднего SHA. Новый недоступный run той же ветки блокирует принятие старого passed — ошибки получения не считаются успехом. Непривязанные PR не получают выдуманную задачу.

## Custom reviewer

```json
{
  "kind": "custom",
  "timeout_seconds": 300,
  "superpowers": {"path": "/path/to/SKILL.md", "sha256": "64 hex characters"},
  "review_argv": ["my-reviewer", "--request", "{request}", "--result", "{result}", "--checkout", "{checkout}"]
}
```

Request содержит task, verified bundle, checkout и pin. Result — ровно task_id, commit, verdict (`approve`/`reject`/`needs_input`), summary и findings (массив строк). Shell expansion не используется. Custom executable — доверенный код, который сам должен обеспечивать нужные права; Codex adapter запускается с read-only sandbox, без bypass flags или выбора новой модели. Доставка Superpowers-инструкций не заменяет проверку поведения агента.

Получение реального GitHub события, fixture subprocess и фактический вызов модели — разные уровни проверки; успешность каждого фиксируется отдельно в отчёте. Автоматическая приёмка не включает merge следующих PR или production deployment.
