# johnny-mnemonic

Карточки для изучения английских и французских слов с интервальными повторениями.
Python + tkinter + SQLite, без сторонних зависимостей.

```bash
python3.14 main.py          # запустить из консоли
./build_app.sh              # собрать Карточки.app и установить в «Программы»
python3.14 -m unittest      # тесты
```

## Правило повторений

| Ответ | Когда слово покажется снова |
|---|---|
| Не помню | ещё раз сегодня; серия «Запомнил» начинается заново |
| Сомневаюсь | завтра |
| Запомнил | через 5 дней |
| Запомнил в 3-й раз за 15 дней | через месяц |
| Запомнил после месячного перерыва | срок удваивается: 1 → 2 → 4 месяца… до года |

## Структура

Слои по чистой архитектуре — зависимости направлены только внутрь:

```
main.py                  точка входа: собирает слои вместе
cards/
  domain/                слово, оценки, правило повторений — чистый Python
    model.py             Word, Grade, Review, ошибки
    scheduling.py        SchedulingPolicy — через сколько дней показать слово
    repositories.py      интерфейсы хранилищ
  application/           сценарии использования
    dictionary.py        ведение словаря
    study.py             сессия повторения: очередь, ответы, прогресс
    preferences.py       выбранный язык
    ports.py             что нужно от внешнего мира: дата, раскладка клавиатуры
  infrastructure/        реализации интерфейсов
    sqlite_database.py   файл базы, схема, миграции
    sqlite_repositories.py
    keyboard_layout.py   переключение раскладки в macOS
  presentation/          интерфейс на tkinter
    app.py, learn_tab.py, words_tab.py, edit_dialog.py
    theme.py, widgets.py оформление и закруглённые виджеты
tests/
```

База лежит в `~/Library/Application Support/cards-learning/cards.db`.
