# Канонический бэклог Task Tower

Актуализация 2026-11-05: Beads/Dolt хранит задачи, иерархию, зависимости и хронологию; Superpowers задаёт процесс разработки; GitHub хранит код, PR/CI и внешние ссылки на прежние Issues. Книжки Task Tower читают настроенный локальный Beads-проект.

25 прежних открытых Issues получили актуальные требования и ссылки на реальные Beads ID. Исходная история сохранена в GitHub и его истории редактирования; старые machine metadata в исторических блоках экранированы. HTML-collapse сам по себе не препятствует машинному разбору. Исторические запуски, receipts, claims/fences и статусы завершённых задач не импортировались и не выдумывались. Хронология новых карточек начинается с реального административного создания.

## Границы первого релиза

Текущее направление — одна Windows-машина, локальный embedded Beads и read-only книжки с уже принятой функциональностью. Эта актуализация не добавляет ночной пул, постоянный stage controller или автоматическое закрытие Beads. Ночной режим, VPS/HTTP/server, несколько машин, Linux/macOS/WSL и квалификация старых карточек остаются будущими этапами. Наличие карточки не разрешает их выполнение.

По явному решению пользователя известная нерешённая `tt-qrk.4` не блокирует первый релиз. Она остаётся открытой/blocked по отсутствию данных о причине и наблюдается отдельно; [условия и наблюдение](ci-known-issues.md). Это не разрешение принимать красный, отменённый или неполный CI, ослаблять assertions/timeouts либо обходить независимую PR/main-приёмку.

## Статусы и работа с очередью

Все 29 будущих узлов ниже созданы в состоянии `deferred`, без исполнителя и без новых блокеров первого релиза. Они видны в Beads и книжках, но не попадают в `bd ready`. GitHub Issues остаются открытыми внешними справочными карточками; они не являются второй исполняемой очередью. Прежние отменённые #17/#18 не используются как действующие зависимости.

Для будущей активации нужен согласованный объём этапа и независимо принятая Superpowers-спецификация. Только затем карточка снимается с defer в настроенном Beads-проекте, проверяются зависимости и она захватывается одним исполнителем. Зависимость-ready не отменяет deferred или границы авторизации. Embedded-режим по-прежнему допускает одного писателя; распределённая блокировка не заявляется.

Каждая реализация проходит независимые приёмки спеки, разработки и тестов, свежую whole-diff PR-приёмку точных head/base, настоящий `task-tower/pr-acceptance`, все применимые CI, expected-head merge и независимую exact-main приёмку с подлинными артефактами. Слияния сериализуются. Для docs-only работает отдельно принятый typed route с `runtime_tests:not_run`; skipped runtime не превращается в runtime pass. Завершение в каноническом Beads сейчас выполняет координатор после фактических gates и проверяет запись истории; это не встроенный product-autoclose.

## Карта карточек

ID действуют в настроенном каноническом Beads-проекте Task Tower; это не номера GitHub Issue и не инструкция создавать такие ID вручную в пустой базе. При подключении другой установки сначала согласуется источник Beads, без неявной миграции или восстановления исполнительного владения. Четыре узла без GitHub Issue закрывают пробел планирования локальной доставки, не создавая собственную очередь/БД рядом с Beads.

### Следующий этап Windows: локальная и ночная доставка

| Beads | Внешняя карточка | Планируемый результат | Родитель | Зависимости |
| --- | --- | --- | --- | --- |
| `tt-auq.4` | [#25](https://github.com/Sibiya666/task-tower/issues/25) | Windows/Beads: бюджеты, health, остановка и восстановление локального координатора | `tt-auq` | `tt-auq.2`, `tt-auq.3` |
| `tt-auq.5` | [#26](https://github.com/Sibiya666/task-tower/issues/26) | Windows/Beads: восстановление main и сериализованный барьер слияний | `tt-auq` | `tt-auq.3` |
| `tt-auq.6` | [#27](https://github.com/Sibiya666/task-tower/issues/27) | Windows/Beads: испытания сбоев и независимых приёмщиков перед ночным режимом | `tt-auq` | `tt-auq.2`, `tt-auq.4`, `tt-auq.5` |
| `tt-auq.7` | [#28](https://github.com/Sibiya666/task-tower/issues/28) | Windows/Beads: ограниченный локальный пилот и измерение пользы агентной разработки | `tt-auq` | `tt-auq.4`, `tt-auq.5`, `tt-auq.6` |
| `tt-auq` | Новый локальный узел | Следующий этап Windows: локальная Beads/Superpowers-доставка авторизованного бэклога | — | — |
| `tt-auq.1` | Новый локальный узел | Windows/Beads: канонический допуск, project identity и stage evidence contract | `tt-auq` | — |
| `tt-auq.2` | Новый локальный узел | Windows/Beads: локальная непрерывная координация обязательных Superpowers-этапов | `tt-auq` | `tt-auq.1` |
| `tt-auq.3` | Новый локальный узел | Windows/Beads: сериализованная PR/main-приёмка и проверяемое закрытие координатором | `tt-auq` | `tt-auq.2` |

### Исследования Harness² и Harness Engineering

| Beads | Внешняя карточка | Планируемый результат | Родитель | Зависимости |
| --- | --- | --- | --- | --- |
| `tt-bx1` | [#44](https://github.com/Sibiya666/task-tower/issues/44) | [Epic] Harness²: глубокий анализ улучшения автономной мультиагентной системы Task Tower | — | — |
| `tt-e4n` | [#45](https://github.com/Sibiya666/task-tower/issues/45) | [Epic] Harness Engineering: глубокий аудит и улучшения автономной мультиагентной системы Task Tower | — | — |
| `tt-bx1.1` | [#46](https://github.com/Sibiya666/task-tower/issues/46) | Harness²: разобрать алгоритм, контракты и соответствие актуальной архитектуре Task Tower | `tt-bx1` | — |
| `tt-bx1.2` | [#47](https://github.com/Sibiya666/task-tower/issues/47) | Harness²: проверить исследовательские доказательства и составить воспроизводимый план сравнения | `tt-bx1` | `tt-bx1.1` |
| `tt-bx1.3` | [#48](https://github.com/Sibiya666/task-tower/issues/48) | Harness²: проанализировать память, перенос опыта и инвалидирование устаревших результатов | `tt-bx1` | `tt-bx1.1` |
| `tt-bx1.4` | [#49](https://github.com/Sibiya666/task-tower/issues/49) | Harness²: оценить безопасность пробных исполнений и неизменяемую политику автономии | `tt-bx1` | `tt-bx1.1` |
| `tt-bx1.5` | [#50](https://github.com/Sibiya666/task-tower/issues/50) | Harness²: оценить стоимость рекурсии, планирование и критерии её применения | `tt-bx1` | `tt-bx1.1` |
| `tt-e4n.1` | [#51](https://github.com/Sibiya666/task-tower/issues/51) | Harness Engineering: проверить первоисточники и провести аудит пяти подсистем Task Tower | `tt-e4n` | — |
| `tt-e4n.2` | [#52](https://github.com/Sibiya666/task-tower/issues/52) | Harness Engineering: исследовать холодный старт, handoff и восстановление между сессиями | `tt-e4n` | `tt-e4n.1` |
| `tt-e4n.3` | [#53](https://github.com/Sibiya666/task-tower/issues/53) | Harness Engineering: проверить реальность независимой приёмки и разработать негативные сценарии барьеров | `tt-e4n` | `tt-e4n.1` |
| `tt-e4n.4` | [#54](https://github.com/Sibiya666/task-tower/issues/54) | Harness Engineering: проанализировать граф стадий, владение и отказоустойчивую мультиагентную координацию | `tt-e4n` | `tt-e4n.1` |
| `tt-e4n.5` | [#55](https://github.com/Sibiya666/task-tower/issues/55) | Harness Engineering: спроектировать эталонные задачи, наблюдаемость и метрики полезности автономии | `tt-e4n` | `tt-e4n.1` |
| `tt-bx1.6` | [#56](https://github.com/Sibiya666/task-tower/issues/56) | Harness²: сформировать решение о применении, roadmap улучшений и ограниченный pilot design | `tt-bx1` | `tt-bx1.1`, `tt-bx1.2`, `tt-bx1.3`, `tt-bx1.4`, `tt-bx1.5` |
| `tt-e4n.6` | [#57](https://github.com/Sibiya666/task-tower/issues/57) | Harness Engineering: свести аудит и Harness² в приоритизированную программу улучшений Task Tower | `tt-e4n` | `tt-e4n.1`, `tt-e4n.2`, `tt-e4n.3`, `tt-e4n.4`, `tt-e4n.5`, `tt-bx1.6` |

### Несколько машин — будущая версия

| Beads | Внешняя карточка | Планируемый результат | Родитель | Зависимости |
| --- | --- | --- | --- | --- |
| `tt-m9l` | [#19](https://github.com/Sibiya666/task-tower/issues/19) | vNext: распределённое Beads-исполнение на нескольких машинах | — | `tt-auq`, `tt-auq.4`, `tt-auq.5`, `tt-auq.6` |

### Linux/macOS — будущая версия

| Beads | Внешняя карточка | Планируемый результат | Родитель | Зависимости |
| --- | --- | --- | --- | --- |
| `tt-2wz` | [#58](https://github.com/Sibiya666/task-tower/issues/58) | [Feature] vNext: нативная Beads/Superpowers-разработка на Linux/macOS/WSL | — | `tt-auq` |
| `tt-2wz.1` | [#59](https://github.com/Sibiya666/task-tower/issues/59) | vNext: нативное владение и завершение Beads/Superpowers-процессов на Linux | `tt-2wz` | `tt-auq.2` |
| `tt-2wz.2` | [#60](https://github.com/Sibiya666/task-tower/issues/60) | vNext: нативное владение и завершение Beads/Superpowers-процессов на macOS | `tt-2wz` | `tt-auq.2` |
| `tt-2wz.4` | [#61](https://github.com/Sibiya666/task-tower/issues/61) | vNext: ресурсы и локальная координация Beads-агентов на Linux/macOS | `tt-2wz` | `tt-2wz.1`, `tt-2wz.2`, `tt-auq.4` |
| `tt-2wz.3` | [#62](https://github.com/Sibiya666/task-tower/issues/62) | vNext: квалификация OpenCode/custom harness для Beads/Superpowers на POSIX | `tt-2wz` | `tt-2wz.1`, `tt-2wz.2`, `tt-auq.2` |

### Старые карточки — будущая версия

| Beads | Внешняя карточка | Планируемый результат | Родитель | Зависимости |
| --- | --- | --- | --- | --- |
| `tt-v69` | [#66](https://github.com/Sibiya666/task-tower/issues/66) | vNext: проверяемое принятие исторических карточек без исходной stage provenance | — | `tt-auq.3` |

## При передаче другому harness

Читайте AGENTS/README и текущую карточку из подключённого Beads-проекта. Идеи, спеки, исследования и результаты остаются Markdown-артефактами репозитория со ссылками из карточек. Не превращайте старые GitHub metadata или исторические Markdown-протоколы в executable authority. Настройки, database/executable paths и credentials остаются приватными. Клонирование репозитория не устанавливает текущий операторский monitor и не разворачивает сервер или фоновый пул.
