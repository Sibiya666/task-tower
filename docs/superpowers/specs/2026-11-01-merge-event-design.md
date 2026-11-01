# Событие слияния и postmerge Task Tower

Поручение владельца: обрабатывать слияния PR прямо из GitHub и включить этот этап в таск-менеджер. Событие GitHub — факт интеграции, не приёмка результата.

## Первый работающий транспорт

GitHub Actions слушает pull_request.closed для main и проверяет merged=true. Выполняется checkout точного merge_commit_sha, затем CLI-тесты на Windows/macOS/Linux. Каждый job публикует JSON-событие как artifact даже при провале тестов. Права contents:read; код не получает write token, не коммитит в main и не помечает задачу done. Не нужен публичный webhook endpoint на компьютере пользователя. Это серверный hook и переносимый event contract, а не работающий локальный HTTP-сервер.

PR связывается с задачей явной строкой `Task-Tower: TT-...` в description. Без маркера событие всё равно регистрируется, но не угадывает задачу. Непринятые/невалидные значения не подставляются в shell; parser читает event JSON из файла. Старый PR#2 уже merged до установки workflow: событие не придёт задним числом, нужна явная сверка/ручной replay.

## Event contract v1

Поля: version=1, kind=pull_request.merged, repository=owner/repo, pr_number, merge_commit (40 hex), task_ids, platform (windows/macos/linux), checks (passed/failed), run_url (GitHub Actions URL), delivery_key. Ключ доставки устойчив для одного run/attempt/platform и отличается у повторного прогона. Парсер проверяет action closed, merged=true, base.ref main, repository, URL и SHA. JSON — данные, не команды. Прогон CI не является решением независимого агента-приёмщика.

## Подключение к карточке

Первый этап — экспорт нормализованного события в GitHub artifact. Далее локальный сервис очереди сможет скачивать и применять его по repository+PR+merge SHA, с дедупликацией. Локальный CLI импорта в этом изменении не обещается: автоматического фонового получения на компьютер ещё нет.

Целевой переход: ожидает слияния → postmerge pending → postmerge checks passed/failed → независимый приёмщик → done либо возврат на исправление. Все обязательные платформы должны быть проверены; один успешный artifact не означает успешный общий прогон. Повторные доставки не запускают вторую приёмку. Очередь слияний удерживает следующий merge до финального результата, как задано родительской архитектурой.

## Найденный дефект пилота

Postmerge PR#2 обнаружил stale evidence: точные байты текстового отчёта меняются при checkout CRLF; часть сохранённых хешей также не соответствует закоммиченным версиям отчётов. Нельзя молча обновлять старые приёмки. Новые приёмки получают явную схему sha256-utf8-lf-v1 (нормализация только CRLF для UTF8 текста); binary/legacy остаются raw. Старые приёмки обновляются только через повторное независимое принятие актуального результата. Реальное изменение текста по-прежнему блокирует переход.

## Проверки

TDD для producer: merged/closed/main gate, fork repository consistency, task marker parsing/dedup, no marker, invalid SHA/URL/repository, закрытый без merge, delivery keys retries. Портируемость evidence: реальные Git checkout с autocrlf и stale text regression. Workflow проверяется код-ревью, фактический запуск заявляется только после GitHub execution. Никакой ретроактивной имитации успешного postmerge PR#2.

Источники: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request ; https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow . Слияние через GITHUB_TOKEN из другого workflow может не породить событие closed: будущий merge-controller должен использовать поддерживаемый dispatch/App путь или сверку main.
