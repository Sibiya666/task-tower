# Автоматическая postmerge-приёмка

Поручение: локальный таск-менеджер сам получает события GitHub, запускает отдельного приёмщика и обновляет карточку. База — merged PR#4, aab8fb5. Работа ведётся отдельно от чужих изменений overlay.

## Сквозной поток

Запущенный `python -m task_tower worker --config FILE [--once]` опрашивает GitHub Actions workflow `.github/workflows/postmerge.yml`. Нужен включённый компьютер; OS service/autostart и интерфейс книг не входят в этот шаг. Результаты всех обязательных платформ одного run/attempt объединяются. Отсутствующие результаты означают ожидание, failed означает postmerge_failed, только полный passed допускает приёмщика.

GitHub источник проверяет workflow provenance, PR merged/main, repository и точный merge SHA; task_ids сверяются с явными маркерами PR. ZIP читается без распаковки на диск, с ограничением размеров и количества entries; payload и delivery_key проверяются повторно. Используются страницы API, недоступные/истёкшие artifacts не считаются успехом. Token берётся из GH_TOKEN/GITHUB_TOKEN, существующего gh auth либо Git credential helper без интерактивных запросов; в конфиг/логи/запрос приёмщику не сохраняется и не передаётся внешнему storage при redirect.

## Состояние и восстановление

SQLite journal в .task-tower хранит task+commit, run/attempt, состояния ожидания/ошибки/приёмки/завершения и результат агента. Захват атомарный; повторный poll не создаёт второго приёмщика. После аварии running не перезапускается автоматически: это неопределённый исход, нужен явный retry оператора. Принятый сохранённый ответ может быть повторно применён без нового вызова модели. Повторы неограниченного расхода запрещены; один reviewer на task+commit до явного retry. За poll действует max_reviews, по умолчанию 1.

Старый failed event не отменяет done по более позднему SHA. Новый merge для уже завершённой задачи автоматически не переоткрывает её; это требует нового задания или явного сброса. Непривязанные события не угадывают карточку. Никакие команды из event не исполняются.

## Приёмщик

Проверяет чистую detached копию точного merge SHA, критерии карточки, предшествующие приёмки и CI; получает pin Superpowers. Codex запускается отдельным `exec` с read-only sandbox, JSON schema и timeout. Custom reviewer использует доверенный review_argv с {request}, {result}, {checkout}; общий файловый JSON-протокол. Прочие launch-only harness не объявляются поддерживающими автоматическое ревью. Модель/авторизация остаются пользовательскими; bypass flags не применяются. GitHub token удаляется из env дочернего процесса.

Ответ: task_id, commit, verdict approve/reject/needs_input, summary, findings[]. Несовпадение SHA/ID, невалидный ответ, timeout или ошибка CLI не закрывают задачу. Доказательство сохраняется в docs/tasks/evidence/{id}/postmerge-{sha}.json. Это независимая сессия от исполнителя; аутентификация личности модели и аппаратная изоляция от враждебного кода не обещаются.

## Карточка

Нужны ранее принятые spec/development/test с актуальными хешами. Legacy stale по-прежнему блокирует, молчаливой миграции нет. Дополнительный postmerge_state даёт видимые состояния pending/reviewing/failed/needs_input; статус done только через accept_task(postmerge) и актуальный ответ approve. Приёмка проверяет commit в main: допускаются только refs/heads/main или refs/remotes/origin/main (worker обновляет origin/main без переключения пользовательской ветки). Сохранённый main_ref повторно проверяется при чтении карточки.

Во время ревью отслеживается snapshot карточки; пользовательские изменения/смена prior evidence дают needs_input вместо перезаписи решения. Запись статусов/отчётов локальная и атомарная, не коммитит/push автоматически. Сервис не меняет код проверяемого проекта, GitHub авторизацию или внутреннюю БД Codex. Рабочие копии создаются в управляемом runtime-каталоге; это не замена security sandbox.

## Проверки

Реальные temp Git repos, fixture GitHub API/ZIP и отдельный reviewer subprocess: получение→три платформы→один запуск→approve→done; repeat→без второго запуска; failed/missing/reject/timeout/invalid/stale/restart/mutating card→не done. Отдельно secret redirection и env. Настоящий GitHub source и Codex проверяются ограниченным --once после локальных тестов; факт работы с моделью не выводится из fixture-тестов.
