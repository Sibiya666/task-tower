# Настольный оверлей Task Tower

Канонический код визуального оверлея находится здесь, в `overlay/`. Запуск, возможности и скриншоты описаны в [общем README](../README.md).

- `collector.py` — read-only SQLite/JSONL адаптер Codex, привязка проектов/субагентов, свежесть состояний.
- `TowerHost.cs` — прозрачный WPF-хост с WebView2CompositionControl, отдельным сборщиком и ограниченным мостом native/UI.
- `run-html-overlay.ps1`, `overlay.ps1`, `start-tower.cmd` — загрузка SDK и запуск. `launch-codex-tower.ps1` открывает также Codex.
- `web/tower.js` — Canvas башен и цельных комнат, размещение/анимация агентов, индивидуальные подсказки.
- `prepare-room-skins.cjs` — 12 интерьеров, маски стекла, якоря света; генерирует `web/room-skins.js`.
- `prepare-unified-tower.cjs` — согласованные крыша, этаж и основание из одного исходника; генерирует `web/tower-art.css`.
- `prepare-employees.cjs`, `prepare-employee-variants.cjs` — четыре исходных персонажа и девять новых моделей.

`overlay-legacy.ps1`, `export-art.cjs`, `prepare-tower-art.cjs` сохранены как история старого арта; текущий запуск их не использует.

Для диагностики найдите текущий snapshot через `runtime/overlay-source.json`, а не через старый общий snapshot. Runtime и локальные привязки не должны попадать в Git.

Virtual host `https://tower.local/` раскрывает только `web/`; внешняя навигация блокируется. HTTP-сервер не запускается. Сохраняйте композиционный WebView2: обычный HWND-контрол нарушает прозрачность.

Проверки перечислены в общем README. Тесты коллектора, браузерные тесты и native smoke покрывают разные границы и не заменяют друг друга.
