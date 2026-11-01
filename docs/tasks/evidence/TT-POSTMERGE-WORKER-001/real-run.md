# Реальный автоматический цикл

Дата: 2026-11-01. Реальная проверяемая задача — TT-MERGE-HOOK-001, merge commit aab8fb56d693b5da48a4a01f01dfa499e4659bcc (PR#4). Код worker — рабочая ветка этого PR; ещё не утверждение его собственного завершения в main.

## Получение

GitHubSource с существующим Git credential helper получил реальные artifacts PR#3/#4/#5. Токен не печатался и не сохранялся в конфиге. PR#3 имеет failed macOS; PR#4 того же задания имеет все три passed; PR#5 без task marker не получил выдуманную карточку. Проверены digest ZIP, API provenance и merge SHA. Событие PR#4 выбрано как актуальное для задачи.

## Независимый процесс

`python -m task_tower worker --config <local-runtime-config> --once` запустил отдельный Codex exec через установленный пользовательский бинарник, read-only sandbox, JSON schema и лимит 180 секунд. Новая модель/учётная запись не выбирались. Приёмщик работал в чистом detached checkout точного aab8fb5 и вернул:

> approve: scoped merge-event exporter; inspected implementation, matching prior acceptance hashes, independent fixture review and verified CI bundle Linux/Windows/macOS passed for this exact commit; no blocking findings.

Worker сам сохранил отчёт в проекте `docs/tasks/evidence/TT-MERGE-HOOK-001/postmerge-aab8fb56d693b5da48a4a01f01dfa499e4659bcc.json`, вызвал accept_task(postmerge) с origin/main и перевёл реальную карточку в done. Root не подставлял approve и не редактировал карточку вручную. Journal сохранил результат и done.

## Повтор

Второй реальный --once повторно получил GitHub события, вернул done без нового запуска приёмщика. LastWriteTimeUtc исходного result.json до и после совпал (`Reviewer result unchanged: True`). Ошибок источника не было.

Первый пробный запуск раньше остановился на временном Git fetch до обращения к модели; после отдельного успешного fetch второй запуск завершил цикл. Постоянный режим содержит retry сетевого/fetch-сбоя и не требует ложной приёмки для продолжения.

## Локальный watcher

Запущен фоновый Python worker без окна, polling каждые 30 секунд. Его локальные config/log/PID находятся в `runtime/postmerge-worker/` родительского рабочего каталога и не входят в Git. Он использует изолированную рабочую копию task-tower-worker для кода, основной task-tower — как проект карточек. Автозагрузка ОС не устанавливалась. После перезагрузки нужен новый запуск по инструкции docs/postmerge-worker.md.

Эта запись дополняет независимую fixture-тестовую приёмку; она не заменяет CI кода worker на трёх ОС и его собственную postmerge-приёмку. TT-BOOTSTRAP-001 со старыми raw-хешами автоматически не перепринималась.
