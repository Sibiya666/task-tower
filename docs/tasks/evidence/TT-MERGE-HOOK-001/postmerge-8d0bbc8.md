# Фактический postmerge PR #3

Main: 8d0bbc88a28cd954a8fa16fa731c92fd861e2d1c. Проверено 2026-11-01 через GitHub API.

Hook действительно запустился: https://github.com/Sibiya666/task-tower/actions/runs/41299727423 . Общий результат failure; три artifact опубликованы:

- task-tower-merge-3-linux: автоматические тесты прошли, exporter и upload прошли.
- task-tower-merge-3-windows: автоматические тесты прошли, exporter и upload прошли.
- task-tower-merge-3-macos: тесты не прошли; exporter и upload выполнились, финальный fail-step сохранил красный результат.

По GitHub logs macOS unit suite: 69 tests, failures=1, errors=13, skipped=3. Причина — fixture получает tempfile путь через системный /var symlink, а tasks._safe_path намеренно отвергает symlink в предках. Ошибки происходят до проверки карточки, в test_tasks и test_task_cli. Это не ошибка передачи merge-event; это найденная postmerge несовместимость тестового стенда.

Исправление fixture: канонический Path(temp.name).resolve() в двух общих setUp. Production-защита путей не меняется; symlink/junction regressions сохраняются. Локально после исправления: 69 tests, OK, skipped=1 на Windows. Фактическую macOS-проверку исправления должен подтвердить новый GitHub run.

Задача TT-MERGE-HOOK-001 остаётся незавершённой до успешного нового postmerge и приёмки. Legacy-свидетельства TT-BOOTSTRAP-001 по-прежнему требуют отдельной явной повторной приёмки; их значения этим исправлением не менялись.
