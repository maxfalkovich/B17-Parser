# Парсер анкет психологов [B17.ru](https://www.b17.ru/)

Python CLI для сбора карточек и полных анкет из каталога B17 по готовому URL с фильтрами. Сохраняет описание, образование, методы, услуги, цены и полный полезный текст в UTF-8 JSONL, JSON или CSV. Поддерживает пагинацию, дедупликацию и возобновление; контактные разделы не запрашиваются.

**Код написан моделью GPT-6.1 Sol. Ревью кода человеком не проводилось.**

## Установка

Нужны Python 3.10+ и macOS или Linux. Выполняйте команды из папки проекта:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

## Авторизованная сессия

HTTP-режим работает анонимно или с явно указанным файлом cookies. Для импорта собственной сессии из Chrome на macOS:

```sh
python -m pip install -e '.[chrome-session]'
python scripts/import_chrome_session.py \
  --profile Default --output work/b17-cookies.txt
```

`Default` — папка профиля Chrome; другой профиль может называться `Profile 1`. Скрипт читает только cookies доменов B17, создаёт файл с правами `0600` и не перезаписывает существующие файлы. Система может запросить доступ к связке ключей macOS. Содержимое `work/` и файлы сессий остаются локально.

## Сбор анкет

Выставьте фильтры на B17 и скопируйте URL. Сначала проверьте, что сайт применил выбранные значения:

```sh
python -m b17_parser inspect \
  --url 'https://www.b17.ru/psiholog/sankt-peterburg/?vid=1&price1=3000&price2=5000' \
  --cookies-file work/b17-cookies.txt
```

Сбор до 50 анкет:

```sh
python -m b17_parser crawl \
  --url 'https://www.b17.ru/psiholog/sankt-peterburg/?vid=1&price1=3000&price2=5000' \
  --cookies-file work/b17-cookies.txt \
  --max-profiles 50 --max-requests 60 \
  --output data/psychologists.jsonl
```

Для анонимного режима уберите `--cookies-file`. `--max-profiles` — общее число успешных анкет, `--max-requests` — бюджет загрузок за запуск.

## Возобновление

Сохраните тот же URL, режим доступа, выходной файл и контрольную точку; увеличьте общий целевой лимит и добавьте `--resume`:

```sh
python -m b17_parser crawl \
  --url 'https://www.b17.ru/psiholog/sankt-peterburg/?vid=1&price1=3000&price2=5000' \
  --cookies-file work/b17-cookies.txt \
  --max-profiles 100 --max-requests 120 --resume \
  --output data/psychologists.jsonl
```

Если целевой лимит уже достигнут, новых запросов не будет. Рядом с JSONL сохраняются `.state.json` с прогрессом, `.report.json` со статусом и счётчиками, а при ошибках профилей — `.errors.jsonl`.

## Экспорт

```sh
python -m b17_parser export --input data/psychologists.jsonl \
  --output data/psychologists.json --format json
python -m b17_parser export --input data/psychologists.jsonl \
  --output data/psychologists.csv --format csv
```

Тексты не обрезаются; вложенные поля CSV записываются как JSON. [Пример JSONL](examples/profiles.sample.jsonl) содержит вымышленные данные. Неизвестные значения остаются `null` или пустыми списками; цены разных услуг хранятся отдельно в `services`, полный текст — в `raw_profile_text`.

## Фильтры для LLM

Названия, значения и правила URL находятся в [FILTERS.md](FILTERS.md); машиночитаемый справочник — [references/filters-spb.json](references/filters-spb.json). Передайте их LLM вместе с критериями поиска.

Сформировать URL без сетевого запроса:

```sh
python -m b17_parser build-url \
  --catalog references/filters-spb.json \
  --set vid=1 --set price1=3000 --set price2=5000
```

Команда печатает адрес для `inspect` и `crawl --url`. Несколько значений передаются как `--set metod=97,107`. Справочник можно обновить командой `filters`; параметры всех команд доступны через `python -m b17_parser --help`.

## Частота запросов и отчёты

По умолчанию пауза составляет 15 секунд плюс случайные 0–5 секунд, бюджет — 100 загрузок за запуск. Используйте общий файл ограничителя `work/access-state.json` для всех процессов. При ограничении доступа сбор останавливается и сохраняет часовой перерыв.

В `.report.json` указаны количество собранных анкет, оставшаяся работа и причина остановки: окончание выдачи, заданный лимит или ошибка.

## Тесты

```sh
if python -m pytest -q; then
  echo 'OK: тесты прошли'
else
  echo 'FAIL: устраните ошибки перед использованием новой выгрузки'
fi
```

Лицензия — [MIT](LICENSE).
