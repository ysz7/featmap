<!-- featmap v1 -->
# Проект: featmap

CLI-инструмент для AI-поддерживаемой карты фичей проекта (MAP.md).
Сам не вызывает LLM: только файлы, парсер, валидатор — интеллект у ассистента.

## Слой: CLI

Точка входа: разбор аргументов, поиск корня репо, коды выхода.

### Команды init / check / links / version {#cli-commands}

**Что:** Разбирает аргументы, печатает нарушения как `MAP.md:<line>: <CODE>` и возвращает коды выхода (1 при ошибках, `--strict` для предупреждений).
**Файлы:** `src/featmap/cli.py`
**Зависит:** [Парсер MAP.md](#map-parser), [Валидатор](#validator), [Обратные ссылки](#reverse-links), [Инициализация](#initializer)
**Статус:** active

## Слой: Ядро

Детерминированный разбор и проверка карты, без эвристик и без LLM.

### Парсер MAP.md {#map-parser}

**Что:** Построчно разбирает MAP.md в модель данных с номерами строк; ловит нарушения формата F1–F10 как E1.
**Файлы:** `src/featmap/parser.py`
**Зависит:** —
**Статус:** active
**Используется:** <!-- autogen --> [Команды init / check / links / version](#cli-commands), [Валидатор](#validator), [Обратные ссылки](#reverse-links)

### Валидатор {#validator}

**Что:** Семантические проверки поверх модели: E2–E4, W1–W4 и V10 (`check --staged`: staged-файл фичи без staged-изменения её секции).
**Файлы:** `src/featmap/validator.py`
**Зависит:** [Парсер MAP.md](#map-parser), [Обратные ссылки](#reverse-links), [Git-утилиты](#git-utils)
**Статус:** active
**Используется:** <!-- autogen --> [Команды init / check / links / version](#cli-commands)

### Обратные ссылки {#reverse-links}

**Что:** Считает обратные рёбра из `**Зависит:**` и перегенерирует строки `**Используется:**`, не трогая остальной файл.
**Файлы:** `src/featmap/links.py`
**Зависит:** [Парсер MAP.md](#map-parser)
**Статус:** active
**Используется:** <!-- autogen --> [Команды init / check / links / version](#cli-commands), [Валидатор](#validator)

## Слой: Интеграция с проектом

Артефакты, которые featmap кладёт в репозиторий пользователя.

### Инициализация {#initializer}

**Что:** Идемпотентно создаёт MAP.md, блок правил между featmap:rules-маркерами в AGENTS.md/CLAUDE.md, ставит pre-commit hook, печатает bootstrap-промпт для непустых проектов.
**Файлы:** `src/featmap/initializer.py`, `src/featmap/templates/MAP.template.md`, `src/featmap/templates/agents_rules.md`, `src/featmap/templates/pre-commit`
**Зависит:** —
**Статус:** active
**Используется:** <!-- autogen --> [Команды init / check / links / version](#cli-commands)

### Git-утилиты {#git-utils}

**Что:** Обёртки над subprocess git: корень репо, список staged-файлов, диапазоны изменённых строк staged-диффа MAP.md.
**Файлы:** `src/featmap/gitutils.py`
**Зависит:** —
**Статус:** active
**Используется:** <!-- autogen --> [Валидатор](#validator)
