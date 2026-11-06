# Execution contract and navigation Implementation Plan

> **ИСТОРИЯ / ЗАМЕНЕНО решением 2026-11-06.** Действующий маршрут: [Beads + Superpowers + готовый Codex](../../current-direction.md). Прежние Windows-квалификация, план B и порядок этапов ниже не действуют. Весь последующий текст, включая старые approvals, слова «текущая authority» и «следующий шаг», сохранён как датированный материал; не возобновлять по нему исполнение или claims. Независимые проверки, безопасность и PR/main gates сохраняются в актуальном AGENTS.md.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Поставить небольшой документационный контракт этапа A и проверяемую навигацию, не изменяя runtime и не выдавая source assessment за квалификацию.

**Architecture:** Beads хранит authority задач; Superpowers задаёт метод; Task Tower связывает будущий квалифицированный executor с evidence. Этот план меняет только документацию, сохраняет принятые компоненты и PR85/HOLD. B/C описываются как последующие gates, не исполняются.

**Tech Stack:** Markdown, существующие docs validation и independent review; Windows-only source inspection. Никаких новых зависимостей.

**Spec:** [2026-11-05-execution-contract-design.md](../specs/2026-11-05-execution-contract-design.md).

## Global Constraints

- Windows 10, одна машина; macOS/Linux/WSL/VPS/HTTP/multi-machine execution не входит в A.
- Beads — единственный канонический источник задач, dependencies, owner и history; GitHub — код/PR/CI.
- Superpowers остаётся методом анализа, планирования, разработки и независимого review.
- Модель, аккаунт, авторизация, scopes, ACL и приватная конфигурация не меняются и не читаются.
- A не запускает модели, native probes, тесты продукта, installed CLI commands, Beads mutations или PR85 runtime.
- Обязательная живая шестиролевая квалификация tt-auq.2 сохраняется; ordinary CI не заменяет её.
- Существующие независимые exact-head/base PR, актуальный CI и exact-main gates сохраняются; docs-only имеет runtime_tests:not_run.
- Старые claims, receipts, branches и пользовательский WIP сохраняются; executable ownership из JSON не восстанавливается.

## Review Focus

- Vendor API существует, но installed version не установлена: Task 1 обязан писать unknown, не qualified.
- Старый bootstrap направляет в GitHub worker: Task 1 должен сохранять историю, исключая её из текущего пути.
- Один green primitive или CI принимается за six-role delivery: Task 2 должен обнаружить такое смешение.
- Backlog markdown устарел относительно receipt: Task 1 различает source date и canonical state без DB mutation.
- Локальная ссылка работает только у автора: Task 2 проверяет переносимость всех добавленных ссылок и отсутствие персональных путей.

## Task 1: Документационный контракт и единый вход

**Files:** Create `docs/execution-contract.md`; Modify `README.md`, `AGENTS.md`, `docs/bootstrap.md`, `docs/backlog.md`. Не редактировать никакой другой файл в этой задаче и не трогать чужой незакоммиченный фрагмент без согласованного reconciliation координатора.

**Interfaces:** Consumes утверждённую spec выше, research architecture packet, текущие repository docs и публичные исходники/названные sanitized receipts. Produces контракт с шестью заголовками из spec и таблицей `Capability | Required behavior | Source/version | Evidence kind | Observed result | Unknown / next gate`; ссылки входов указывают на этот файл. Это интерфейс документации, не runtime schema.

- [ ] **Step 1: Зафиксировать существующие противоречия.** Прочитать текущие README/AGENTS/bootstrap/backlog, `task_tower/harness.py` capabilities и research evidence appendix; составить в отчёте Task 1 список исправляемых маршрутов и источники фактов. Не запускать CLI и не читать private config. Ожидается явное различение accepted ab91 и candidate CF либо более свежей подтверждённой базы, без объявления runtime PASS.
- [ ] **Step 2: Создать контракт.** Заполнить шесть разделов, все 13 capability rows, data/authority matrix и A/B/C gates из spec. Перенести уже известные version `0.166.0-alpha.6` и executable SHA256 из названного public protocol как prior observation; отдельно указать current equality not checked. Не заменять известное blanket unknown и не повышать vendor_documented до installed support. В `Next permitted action` указать docs review; после A — отдельный B feasibility/qualification plan, не немедленный model launch.
- [ ] **Step 3: Исправить четыре навигационных документа.** Сохранить уже добавленные координатором ссылки на architecture packet; в README и AGENTS дополнить только недостающую короткую ссылку на контракт, без дублирования разделов. В bootstrap явно отделить interactive launch от historical recipes; сохранённые старые команды не предлагать как текущий Beads path. В backlog добавить crosswalk существующих ID без новых IDs/claims/closure; использовать предоставленный свежий readback `.1 closed/.2 blocked/.3–.7 open` и не выдавать A за завершение исследовательских эпиков.
- [ ] **Step 4: Проверить документ вручную по матрице spec.** Сверить 13 строк и каждый обязательный запрет; проследить цепочку README → contract → admission/architecture/spec; убедиться, что все relative targets существуют. Ожидается ноль пропущенных capability rows и ноль неподтверждённых qualified/pass. Документационный scope не требует написания зеркальных unit tests или запуска полного suite.
- [ ] **Step 5: Передать diff на независимую task acceptance.** Reviewer проверяет spec compliance и качество всего документационного deliverable, включая current/target и source confidence. Исполнитель возвращает перечень изменённых файлов, нерешённые факты и hash-bound report; commit/PR выполняет координатор по существующей авторизации после review, не этот plan writer.

## Task 2: Независимая проверка переносимости и handoff в B

**Files:** Read five deliverable files и spec/plan; правки только в этих пяти docs при подтверждённых findings. Отдельный отчёт в evidence-месте, назначенном координатором; не добавлять приватные receipts в repository.

**Interfaces:** Consumes Task 1 exact diff/source identity. Produces verdict bound to reviewed bytes, список unknown installed capabilities и условие допуска отдельного B. Не выдаёт native receipt.

- [ ] **Step 1: Проверить пять Review Focus cases.** На actual diff подтвердить: vendor≠installed, historical≠active, process/CI≠six-role accepted, docs≠canonical DB, отсутствие личных абсолютных links. Проверка — независимое чтение фактических документов, не новый модельный benchmark.
- [ ] **Step 2: Проверить B/C handoff.** Reviewer называет все обязательные доказательства B и C без обращения к старому heartbeat. Убедиться, что неизвестность не заполнена флагом по памяти, таймауты не ослаблены, native qualification не перенесена в `.7`, а scope A не создаёт новый runtime/provider.
- [ ] **Step 3: Исправить только actionable findings.** Вернуть замечания Task 1 implementer, затем scoped re-review изменённых строк; не повторять неизменные тесты или исследования. Если решение требует новых прав/изменения обязательства, оставить конкретный blocked item координатору.
- [ ] **Step 4: Передать координатору готовый docs-кандидат.** Координатор отдельно обеспечивает fresh independent whole-diff exact head/base, настоящий acceptance context, применимый CI, expected-head merge и exact-main docs acceptance. Docs artifact обязан означать `runtime_tests:not_run`; отсутствие runtime artifact не скрывать. Этот план не заявляет ни одно из этих действий выполненным.

## Самопроверка плана

Spec coverage: продукт/границы/матрица/crosswalk/навигация покрыты Task 1; evidence discipline, переносимость и B/C gate — Task 2. Все пять Review Focus cases имеют явную проверку. Тестовый код не добавляется для текста; runtime/source functionality не меняется. Неизвестные installed capabilities — содержательный выход A, но остаются блокерами будущего исполнения. Никакая задача этого плана не меняет Beads state или PR85.
