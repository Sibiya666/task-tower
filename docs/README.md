# Документация Task Tower

[Быстрый старт и эксплуатация](../README.md)

## Внедрение и эксплуатация

- [Оверлей: запуск, управление, интерьеры и данные](overlay-usage.md).
- [Подключение локального Beads, хронология и публичный результат](local-beads-books.md).
- [Bootstrap: существующий Codex и Superpowers](bootstrap.md).
- [Trusted intake: existing native IDs and append-only operator reload](project-intake.md).
- [Headless: Docker, host-коннектор и явные операторские действия](runtime/headless-operation.md).
- [Происхождение скриншотов и обработка фона](screenshots/README.md).

## Текущая архитектура

Действующий маршрут — **Beads + Superpowers + готовый Codex**.
[Текущее направление](current-direction.md) и [AGENTS.md](../AGENTS.md) задают границы работы.

| Компонент | Ответственность |
| --- | --- |
| Beads / Dolt | Единственный источник задач, зависимостей, владельцев и истории |
| Superpowers | Спецификация и план по необходимости, реализация, тесты и независимая проверка |
| Codex | Существующие инструменты и сессии исполнителя и независимого reviewer |
| Task Tower | Прозрачный overlay, read-only Books и необходимые связи компонентов |
| GitHub | Исходники, PR, CI и принятый main |
| Markdown проекта | Спеки, планы, исследования, решения и отчёты |

Настольный оверлей наблюдает локальные сессии Codex. Books отдельно читает
configured embedded Beads; приватные пути и конфигурация остаются в native host.
Display-конфигурация и admission observation не дают прав на выполнение задач.
[Карта существующей связки](beads-superpowers-codex-map.md) отделяет поставленный
код от процедуры координатора; [admission](beads-admission.md) описывает границу
существующего read-only компонента.

Явный [headless-маршрут](runtime/headless-operation.md) использует Linux Docker
с отдельными Beads/runtime volumes и host-коннектор существующего Codex.
Репозитории и модельная авторизация остаются на хосте. Runtime-журнал хранит
попытки и решения, а не вторую очередь задач. Реализация или smoke сами по себе
не доказывают принятую доставку реального пилота.

Исходное `closed`, ответ модели, ссылка результата и отдельный зелёный тест
не заменяют независимые PR/main gates. Старые Windows/B/G1/G2-планы не являются
предварительным условием текущего маршрута.

## Правила изменения проекта

Актуальные требования к изоляции, проверкам, CI, privacy и приёмке находятся
в [AGENTS.md](../AGENTS.md). Устройство native/WebView-компонентов описано
в [overlay/README.md](../overlay/README.md); CLI аудита — в [readiness](readiness.md).
Нативная оконная/визуальная приёмка сейчас отложена согласно
[текущей границе приёмки](current-direction.md#текущая-граница-приёмки).
Это не отменяет применимые автоматические, contract и security проверки.

## Историческая справка

[Архив разделов прежнего README](history/README.md) сохраняет:

- [Переход с прежнего конвейера](history/README.md#переход-с-прежнего-конвейера).
- [Разработку и атрибуции](history/README.md#разработка).
- [Исторические интеграции](history/README.md#исторические-интеграции).
- Архитектурный снимок и команды прежнего README.

Датированная карта старых карточек остаётся в [backlog](backlog.md).
Архив — справка, а не команда возобновить старое выполнение, worker или monitor.

- [GitHub issue bot operator runbook](runtime/github-issue-webhook.md)
- [Issue bot source map](PROJECT_MAP.md)
