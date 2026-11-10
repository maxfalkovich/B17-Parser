# Фильтры B17

## Для LLM

- Начните с обязательных ограничений пользователя. Если подходящей темы нет в списке, соберите более широкую выборку и изучите полные анкеты.
- Передавайте значения из таблиц, а не отображаемые подписи. Пустые значения и значения по умолчанию можно не задавать.
- Не округляйте бюджет и не добавляйте отсутствующие пороги цены. Дополнительные варианты пошагового подбора перечислены отдельно.
- Город и формат задаются адресом каталога. Идентификаторы локаций действуют только в исходном городе; при его смене получите новый справочник.
- Несколько значений перечисляйте через запятую; логика «И»/«ИЛИ» не установлена.
- Составьте URL через `build-url`, затем проверьте выбранные значения командой `inspect` в той же сессии. Построение URL не выполняет сетевых запросов.

## Формат консультации

| Подпись | Адрес | Формат |
| --- | --- | --- |
| Личный приём Очно | https://www.b17.ru/psiholog/sankt-peterburg/ | очно |
| Онлайн-консультация Онлайн | https://www.b17.ru/online/ | онлайн |

Для смены формата меняйте адрес каталога. `frmt`, `f_city` и `f_mod` не передаются в URL.

## Параметры и варианты

### `vid` — Для кого

Один вариант. По умолчанию: `0`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `1` | Индивидуально |  |
| `2` | Семейная консультация |  |
| `3` | Для подростка |  |
| `4` | Детский психолог |  |
| `5` | Бизнес-консультирование |  |

Дополнительные варианты вне боковой панели (CLI пока не принимает):

| Значение | Исходная подпись | Где найдено |
| --- | --- | --- |
| `0` |  | быстрая форма |

### `location` — Район города

Несколько вариантов. По умолчанию: `(пусто)`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `` |  | по умолчанию |
| `301` | Автово |  |
| `345` | Адмиралтейская |  |
| `287` | Академическая |  |
| `298` | Балтийская |  |
| `321` | Беговая |  |
| `350` | Бухарестская |  |
| `324` | Василеостровская |  |
| `295` | Владимирская |  |
| `349` | Волковская |  |
| `291` | Выборгская |  |
| `311` | Горьковская |  |
| `325` | Гостиный двор |  |
| `286` | Гражданский проспект |  |
| `285` | Девяткино |  |
| `334` | Достоевская |  |
| `353` | Дунайская |  |
| `328` | Елизаровская |  |
| `347` | Звенигородская |  |
| `319` | Звёздная |  |
| `300` | Кировский завод |  |
| `340` | Комендантский проспект |  |
| `342` | Крестовский остров |  |
| `320` | Купчино |  |
| `337` | Ладожская |  |
| `302` | Ленинский проспект |  |
| `290` | Лесная |  |
| `335` | Лиговский проспект |  |
| `329` | Ломоносовская |  |
| `326` | Маяковская |  |
| `351` | Международная |  |
| `318` | Московская |  |
| `315` | Московские ворота |  |
| `299` | Нарвская |  |
| `312` | Невский проспект |  |
| `322` | Новокрестовская |  |
| `336` | Новочеркасская |  |
| `348` | Обводный канал |  |
| `331` | Обухово |  |
| `306` | Озерки |  |
| `317` | Парк Победы |  |
| `304` | Парнас |  |
| `310` | Петроградская |  |
| `308` | Пионерская |  |
| `327` | Площадь Александра Невского |  |
| `294` | Площадь Восстания |  |
| `292` | Площадь Ленина |  |
| `289` | Площадь Мужества |  |
| `288` | Политехническая |  |
| `323` | Приморская |  |
| `330` | Пролетарская |  |
| `338` | Проспект Большевиков |  |
| `303` | Проспект Ветеранов |  |
| `305` | Проспект Просвещения |  |
| `352` | Проспект Славы |  |
| `296` | Пушкинская |  |
| `332` | Рыбацкое |  |
| `346` | Садовая |  |
| `313` | Сенная площадь |  |
| `333` | Спасская |  |
| `344` | Спортивная |  |
| `341` | Старая Деревня |  |
| `297` | Технологический институт |  |
| `307` | Удельная |  |
| `339` | Улица Дыбенко |  |
| `314` | Фрунзенская |  |
| `293` | Чернышевская |  |
| `309` | Чёрная речка |  |
| `343` | Чкаловская |  |
| `354` | Шушары |  |
| `316` | Электросила |  |
| `359` | Всеволожск |  |
| `358` | Колпино |  |
| `356` | Красное село |  |
| `355` | Петергоф |  |
| `357` | Пушкин |  |
| `360` | Сестрорецк |  |

### `price1` — Стоимость: от

Один вариант. По умолчанию: `-`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `-` | - | по умолчанию |
| `500` | 500 |  |
| `1000` | 1000 |  |
| `1500` | 1500 |  |
| `2000` | 2000 |  |
| `3000` | 3000 |  |
| `5000` | 5000 |  |

### `price2` — Стоимость: до

Один вариант. По умолчанию: `-`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `-` | - | по умолчанию |
| `1000` | 1000 |  |
| `1500` | 1500 |  |
| `2000` | 2000 |  |
| `3000` | 3000 |  |
| `5000` | 5000 |  |
| `7000` | 7000 |  |

Дополнительные варианты вне боковой панели (CLI пока не принимает):

| Значение | Исходная подпись | Где найдено |
| --- | --- | --- |
| `2500` | до 2500 рублей (средняя) | пошаговый подбор |
| `4500` | до 4500 рублей (средняя для семейной) | пошаговый подбор |
| `6000` | до 6000 рублей | пошаговый подбор |
| `8000` | до 8000 рублей | пошаговый подбор |

### `vopros` — Мой вопрос

Несколько вариантов. По умолчанию: параметр не задан.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `73` | Депрессивное состояние |  |
| `94` | Низкая самооценка |  |
| `91` | Секс, сексуальность |  |
| `72` | Панические атаки, тревога |  |
| `67` | Семейные проблемы |  |
| `66` | Трудности в построении отношений |  |
| `78` | Нарушение пищевого поведения |  |
| `92` | Отношения с окружающими |  |
| `74` | Принятие решения, постановка цели |  |
| `110` | Созависимость, зависимость в отношениях |  |
| `68` | Психосоматика |  |
| `169` | Проблемы с пониманием своих желаний (узнать себя) |  |
| `82` | Психическое расстройство |  |
| `75` | Страхи и фобии |  |
| `164` | Выгорание (эмоциональное, профессиональное) |  |
| `162` | Неврозы и эмоциональные расстройства |  |
| `76` | Вредные привычки |  |
| `88` | Одиночество |  |
| `71` | Травма насилия |  |
| `93` | Навязчивое поведение, мысли |  |
| `77` | Эмоциональная зависимость |  |
| `84` | Помощь подростку |  |
| `65` | Проблемы с детьми |  |
| `100` | Профориентация |  |
| `171` | Социальная адаптация, социофобия |  |
| `69` | Развод |  |
| `70` | Смерть близкого человека |  |
| `168` | Взрослые дети и родители (взаимоотношения) |  |
| `161` | Агрессивность, приступы гнева |  |
| `81` | Психологическая поддержка |  |
| `114` | Стресс |  |
| `90` | Суицидальное поведение |  |
| `80` | Проблемы с деньгами |  |
| `170` | Проявление желаний и отстаивание собственного мнения |  |
| `167` | Помощь в проживании кризисов |  |
| `87` | Измена |  |
| `85` | Нарушения сна, бессонница |  |
| `86` | Беременность и роды |  |
| `165` | Конфликты (в семье и на работе) |  |
| `83` | Бедность эмоциональной жизни |  |
| `89` | Ревность |  |
| `163` | Кризис среднего возраста |  |
| `166` | Повторяющиеся родовые сценарии |  |
| `79` | Сложности в бизнесе |  |
| `136` | Сновидения, анализ сновидений |  |
| `95` | Сопровождение тяжелобольного |  |

### `metod` — Методы

Несколько вариантов. По умолчанию: параметр не задан.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `19` | Гештальт-терапия |  |
| `97` | Когнитивно-поведенческая терапия (КПТ) |  |
| `18` | Арт-терапия |  |
| `24` | Коучинг |  |
| `138` | Клиническая психология |  |
| `31` | Психоаналитическая терапия |  |
| `119` | Десенсибилизация и переработка с помощью движений глаз (ДПДГ / EMDR) |  |
| `115` | Метафорические ассоциативные карты (МАК) |  |
| `41` | Телесно-ориентированная терапия |  |
| `37` | Системная семейная терапия |  |
| `42` | Транзактный анализ |  |
| `45` | Эмоционально-образная терапия |  |
| `107` | Терапия принятия и ответственности (АСТ) |  |
| `36` | Символдрама |  |
| `98` | Схема-терапия |  |
| `20` | Гипнотерапия |  |
| `27` | Нейролингвистическое программирование (НЛП) |  |
| `30` | Психоанализ (классический) |  |
| `44` | Экзистенциальная психотерапия |  |
| `64` | Перинатальная психология |  |
| `32` | Психодрама |  |
| `38` | Системные расстановки |  |
| `46` | Юнгианский анализ |  |
| `22` | Песочная терапия |  |
| `28` | Поведенческая психотерапия |  |
| `29` | Позитивная психотерапия |  |
| `25` | Клиент-центрированная терапия |  |
| `35` | Сказкотерапия |  |
| `23` | Когнитивная терапия |  |
| `34` | Рационально-эмоционально-поведенческая терапия |  |
| `62` | Интегральное нейропрограммирование (Ковалев С.В.) |  |
| `43` | Трансперсональная психотерапия |  |
| `26` | Логотерапия |  |
| `40` | Танцевально-двигательная терапия |  |
| `33` | Психосинтез |  |
| `39` | Танатотерапия |  |
| `21` | Индивидуальная психология А. Адлера |  |

### `sex` — Пол

Один вариант. По умолчанию: `0`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `0` | Любой | по умолчанию |
| `2` | Жен |  |
| `1` | Муж |  |

### `spec` — Образование

Один вариант. По умолчанию: `(пусто)`, `0`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `` |  | по умолчанию |
| `1` | Психолог |  |
| `2` | Врач-психотерапевт |  |

Дополнительные варианты вне боковой панели (CLI пока не принимает):

| Значение | Исходная подпись | Где найдено |
| --- | --- | --- |
| `0` | показать всех | пошаговый подбор |

### `video` — Видеоприветствие

Флажок. По умолчанию: параметр не задан.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `1` | Видеоприветствие |  |

### `cotherapist` — Ко-терапевты

Флажок. По умолчанию: параметр не задан.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `1` | Ко-терапевты |  |

### `club_100` — «Клуб 100»

Флажок. По умолчанию: параметр не задан.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `1` | «Клуб 100» |  |

### `byfoto` — Вид списка

Один вариант; отображение. По умолчанию: `0`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `0` | Подробный | по умолчанию |
| `1` | Только фото | CLI не поддерживает |

Для сбора используйте `byfoto=0` (подробный вид) или не задавайте параметр.

### `sort` — Порядок

Один вариант; сортировка. По умолчанию: `0`.

| Значение | Исходная подпись | Примечание |
| --- | --- | --- |
| `0` | По рейтингу | по умолчанию |
| `2` | Числу обращений |  |

### `tag` — Найти специалиста

Текст. По умолчанию: `(пусто)`.

Минимальная длина: 3. Кодируйте текст для URL один раз.

## Города

Адреса из снимка индекса: 256.

| Город | Адрес |
| --- | --- |
| Москва | https://www.b17.ru/psiholog/moskva/ |
| Санкт-Петербург | https://www.b17.ru/psiholog/sankt-peterburg/ |
| Краснодар | https://www.b17.ru/psiholog/krasnodar/ |
| Минск | https://www.b17.ru/psiholog/minsk/ |
| Екатеринбург | https://www.b17.ru/psiholog/ekaterinburg/ |
| Новосибирск | https://www.b17.ru/psiholog/novosibirsk/ |
| Ростов-на-Дону | https://www.b17.ru/psiholog/rostov-na-donu/ |
| Нижний Новгород | https://www.b17.ru/psiholog/nijniy_novgorod/ |
| Казань | https://www.b17.ru/psiholog/kazan/ |
| Воронеж | https://www.b17.ru/psiholog/voronej/ |
| Абакан | https://www.b17.ru/psiholog/abakan/ |
| Адлер | https://www.b17.ru/psiholog/adler/ |
| Алматы | https://www.b17.ru/psiholog/almaty/ |
| Альметьевск | https://www.b17.ru/psiholog/almetevsk/ |
| Амстердам | https://www.b17.ru/psiholog/amsterdam/ |
| Анапа | https://www.b17.ru/psiholog/anapa/ |
| Ангарск | https://www.b17.ru/psiholog/angarsk/ |
| Анталья | https://www.b17.ru/psiholog/antalya/ |
| Арзамас | https://www.b17.ru/psiholog/arzamas/ |
| Армавир | https://www.b17.ru/psiholog/armavir/ |
| Архангельск | https://www.b17.ru/psiholog/arhangelsk/ |
| Астана | https://www.b17.ru/psiholog/astana/ |
| Астрахань | https://www.b17.ru/psiholog/astrahan/ |
| Ачинск | https://www.b17.ru/psiholog/achinsk/ |
| Баку | https://www.b17.ru/psiholog/baku/ |
| Балаково | https://www.b17.ru/psiholog/balakovo/ |
| Балашиха | https://www.b17.ru/psiholog/balashiha/ |
| Барановичи | https://www.b17.ru/psiholog/baranovichi/ |
| Барнаул | https://www.b17.ru/psiholog/barnaul/ |
| Барселона | https://www.b17.ru/psiholog/barcelona/ |
| Батайск | https://www.b17.ru/psiholog/bataysk/ |
| Батуми | https://www.b17.ru/psiholog/batumi/ |
| Белгород | https://www.b17.ru/psiholog/belgorod/ |
| Белград | https://www.b17.ru/psiholog/belgrad/ |
| Бердск | https://www.b17.ru/psiholog/berdsk/ |
| Берлин | https://www.b17.ru/psiholog/berlin/ |
| Бийск | https://www.b17.ru/psiholog/biysk/ |
| Бишкек | https://www.b17.ru/psiholog/bishkek/ |
| Благовещенск | https://www.b17.ru/psiholog/blagoveschensk/ |
| Бобруйск | https://www.b17.ru/psiholog/bobruysk/ |
| Борисов | https://www.b17.ru/psiholog/borisov/ |
| Братск | https://www.b17.ru/psiholog/bratsk/ |
| Брест | https://www.b17.ru/psiholog/brest/ |
| Брянск | https://www.b17.ru/psiholog/bryansk/ |
| Будва | https://www.b17.ru/psiholog/budva/ |
| Буэнос Айрес | https://www.b17.ru/psiholog/buenos_ayres/ |
| Валенсия | https://www.b17.ru/psiholog/valensiya/ |
| Варшава | https://www.b17.ru/psiholog/warsawa/ |
| Великий Новгород | https://www.b17.ru/psiholog/velikiy_novgorod/ |
| Верхняя Пышма | https://www.b17.ru/psiholog/verhnyaya_pyshma/ |
| Видное | https://www.b17.ru/psiholog/vidnoe/ |
| Вильнюс | https://www.b17.ru/psiholog/vilnyus/ |
| Витебск | https://www.b17.ru/psiholog/vitebsk/ |
| Владивосток | https://www.b17.ru/psiholog/vladivostok/ |
| Владикавказ | https://www.b17.ru/psiholog/vladikavkaz/ |
| Владимир | https://www.b17.ru/psiholog/vladimir/ |
| Волгоград | https://www.b17.ru/psiholog/volgograd/ |
| Волгодонск | https://www.b17.ru/psiholog/volgodonsk/ |
| Волжский | https://www.b17.ru/psiholog/voljskiy/ |
| Вологда | https://www.b17.ru/psiholog/vologda/ |
| Воскресенск | https://www.b17.ru/psiholog/voskresensk/ |
| Вроцлав | https://www.b17.ru/psiholog/vrotslav/ |
| Выборг | https://www.b17.ru/psiholog/vyborg/ |
| Гатчина | https://www.b17.ru/psiholog/gatchina/ |
| Гданьск | https://www.b17.ru/psiholog/gdansk/ |
| Геленджик | https://www.b17.ru/psiholog/gelendjik/ |
| Гомель | https://www.b17.ru/psiholog/gomel/ |
| Горячий ключ | https://www.b17.ru/psiholog/goryachiy_klyuch/ |
| Гродно | https://www.b17.ru/psiholog/grodno/ |
| Дананг | https://www.b17.ru/psiholog/danang/ |
| Дзержинск | https://www.b17.ru/psiholog/dzerjinsk/ |
| Димитровград | https://www.b17.ru/psiholog/dimitrovgrad/ |
| Дмитров | https://www.b17.ru/psiholog/dmitrov/ |
| Днепр (Днепропетровск) | https://www.b17.ru/psiholog/dnepropetrovsk/ |
| Долгопрудный | https://www.b17.ru/psiholog/dolgoprudnyy_moskva/ |
| Домодедово | https://www.b17.ru/psiholog/domodedovo/ |
| Донецк | https://www.b17.ru/psiholog/donetsk/ |
| Дубай | https://www.b17.ru/psiholog/dubay/ |
| Дубна | https://www.b17.ru/psiholog/dubna/ |
| Евпатория | https://www.b17.ru/psiholog/evpatoriya/ |
| Егорьевск | https://www.b17.ru/psiholog/egorevsk/ |
| Ейск | https://www.b17.ru/psiholog/eysk/ |
| Ереван | https://www.b17.ru/psiholog/erevan/ |
| Ессентуки | https://www.b17.ru/psiholog/essentuki/ |
| Железнодорожный | https://www.b17.ru/psiholog/jeleznodorojnyy/ |
| Жуковский | https://www.b17.ru/psiholog/jukovskiy/ |
| Запорожье | https://www.b17.ru/psiholog/zaporoje/ |
| Звенигород | https://www.b17.ru/psiholog/zvenigorod/ |
| Зеленоград | https://www.b17.ru/psiholog/zelenograd/ |
| Иваново | https://www.b17.ru/psiholog/ivanovo/ |
| Ивантеевка | https://www.b17.ru/psiholog/ivanteevka/ |
| Ижевск | https://www.b17.ru/psiholog/ijevsk/ |
| Иркутск | https://www.b17.ru/psiholog/irkutsk/ |
| Истра | https://www.b17.ru/psiholog/istra/ |
| Йошкар-Ола | https://www.b17.ru/psiholog/yoshkar-ola/ |
| Калининград | https://www.b17.ru/psiholog/kaliningrad/ |
| Калуга | https://www.b17.ru/psiholog/kaluga/ |
| Каменск-Уральский | https://www.b17.ru/psiholog/kamensk-uralskiy/ |
| Караганда | https://www.b17.ru/psiholog/karaganda/ |
| Кемерово | https://www.b17.ru/psiholog/kemerovo/ |
| Керчь | https://www.b17.ru/psiholog/kerch/ |
| Киев | https://www.b17.ru/psiholog/kiev/ |
| Киров | https://www.b17.ru/psiholog/kirov/ |
| Кисловодск | https://www.b17.ru/psiholog/kislovodsk/ |
| Кишинёв | https://www.b17.ru/psiholog/kishinev/ |
| Клин | https://www.b17.ru/psiholog/klin/ |
| Ковров | https://www.b17.ru/psiholog/kovrov/ |
| Коломна | https://www.b17.ru/psiholog/kolomna/ |
| Комсомольск-на-Амуре | https://www.b17.ru/psiholog/komsomolsk-na-amure/ |
| Королёв | https://www.b17.ru/psiholog/korolev/ |
| Костанай | https://www.b17.ru/psiholog/kostanay/ |
| Кострома | https://www.b17.ru/psiholog/kostroma/ |
| Краков | https://www.b17.ru/psiholog/krakov/ |
| Красногорск | https://www.b17.ru/psiholog/krasnogorsk/ |
| Красноярск | https://www.b17.ru/psiholog/krasnoyarsk/ |
| Курган | https://www.b17.ru/psiholog/kurgan/ |
| Курск | https://www.b17.ru/psiholog/kursk/ |
| Лида | https://www.b17.ru/psiholog/lida/ |
| Лимассол | https://www.b17.ru/psiholog/limassol/ |
| Липецк | https://www.b17.ru/psiholog/lipetsk/ |
| Лиссабон | https://www.b17.ru/psiholog/lissabon/ |
| Лобня | https://www.b17.ru/psiholog/lobnya/ |
| Лондон | https://www.b17.ru/psiholog/london/ |
| Луганск | https://www.b17.ru/psiholog/lugansk/ |
| Люберцы | https://www.b17.ru/psiholog/lyubertsy/ |
| Магнитогорск | https://www.b17.ru/psiholog/magnitogorsk/ |
| Майкоп | https://www.b17.ru/psiholog/maykop/ |
| Мариуполь | https://www.b17.ru/psiholog/mariupol/ |
| Махачкала | https://www.b17.ru/psiholog/mahachkala/ |
| Миасс | https://www.b17.ru/psiholog/miass/ |
| Минеральные Воды | https://www.b17.ru/psiholog/mineralnye_vody/ |
| Михайловск | https://www.b17.ru/psiholog/mihaylovsk/ |
| Могилёв | https://www.b17.ru/psiholog/mogilv/ |
| Молодечно | https://www.b17.ru/psiholog/molodechno/ |
| Мурманск | https://www.b17.ru/psiholog/murmansk/ |
| Муром | https://www.b17.ru/psiholog/murom/ |
| Мытищи | https://www.b17.ru/psiholog/mytischi/ |
| Мюнхен | https://www.b17.ru/psiholog/myunhen/ |
| Набережные Челны | https://www.b17.ru/psiholog/naberejnye_chelny/ |
| Нальчик | https://www.b17.ru/psiholog/nalchik/ |
| Наро-Фоминск | https://www.b17.ru/psiholog/naro-fominsk/ |
| Находка | https://www.b17.ru/psiholog/nahodka/ |
| Невинномысск | https://www.b17.ru/psiholog/nevinnomyssk/ |
| Нефтекамск | https://www.b17.ru/psiholog/neftekamsk/ |
| Нефтеюганск | https://www.b17.ru/psiholog/nefteyugansk/ |
| Нижневартовск | https://www.b17.ru/psiholog/nijnevartovsk/ |
| Нижнекамск | https://www.b17.ru/psiholog/nijnekamsk/ |
| Нижний Тагил | https://www.b17.ru/psiholog/nijniy_tagil/ |
| Нови Сад | https://www.b17.ru/psiholog/novi_sad/ |
| Новокузнецк | https://www.b17.ru/psiholog/novokuznetsk/ |
| Новомосковск | https://www.b17.ru/psiholog/novomoskovsk/ |
| Новополоцк | https://www.b17.ru/psiholog/novopolotsk/ |
| Новороссийск | https://www.b17.ru/psiholog/novorossiysk/ |
| Новочебоксарск | https://www.b17.ru/psiholog/novocheboksarsk/ |
| Новочеркасск | https://www.b17.ru/psiholog/novocherkassk/ |
| Новый Уренгой | https://www.b17.ru/psiholog/novyy_urengoy/ |
| Ногинск | https://www.b17.ru/psiholog/noginsk/ |
| Норильск | https://www.b17.ru/psiholog/norilsk/ |
| Нячанг | https://www.b17.ru/psiholog/nyachang/ |
| Обнинск | https://www.b17.ru/psiholog/obninsk/ |
| Одесса | https://www.b17.ru/psiholog/odessa/ |
| Одинцово | https://www.b17.ru/psiholog/odintsovo/ |
| Озерск | https://www.b17.ru/psiholog/ozersk/ |
| Омск | https://www.b17.ru/psiholog/omsk/ |
| Оренбург | https://www.b17.ru/psiholog/orenburg/ |
| Орехово-Зуево | https://www.b17.ru/psiholog/orehovo-zuevo/ |
| Орёл | https://www.b17.ru/psiholog/orl/ |
| Орск | https://www.b17.ru/psiholog/orsk/ |
| Павловский Посад | https://www.b17.ru/psiholog/pavlovskiy_posad/ |
| Павлодар | https://www.b17.ru/psiholog/pavlodar/ |
| Париж | https://www.b17.ru/psiholog/parij/ |
| Пенза | https://www.b17.ru/psiholog/penza/ |
| Первоуральск | https://www.b17.ru/psiholog/pervouralsk/ |
| Пермь | https://www.b17.ru/psiholog/perm/ |
| Петрозаводск | https://www.b17.ru/psiholog/petrozavodsk/ |
| Петропавловск-Камчатский | https://www.b17.ru/psiholog/petropavlovsk-kamchatskiy/ |
| Пинск | https://www.b17.ru/psiholog/pinsk/ |
| Подольск | https://www.b17.ru/psiholog/podolsk/ |
| Познань | https://www.b17.ru/psiholog/poznan/ |
| Полоцк | https://www.b17.ru/psiholog/polotsk/ |
| Прага | https://www.b17.ru/psiholog/praga/ |
| Псков | https://www.b17.ru/psiholog/pskov/ |
| Пушкин | https://www.b17.ru/psiholog/pushkin/ |
| Пушкино | https://www.b17.ru/psiholog/pushkino/ |
| Пхукет | https://www.b17.ru/psiholog/phuket/ |
| Пятигорск | https://www.b17.ru/psiholog/pyatigorsk/ |
| Раменское | https://www.b17.ru/psiholog/ramenskoe/ |
| Реутов | https://www.b17.ru/psiholog/reutov/ |
| Рига | https://www.b17.ru/psiholog/riga/ |
| Рыбинск | https://www.b17.ru/psiholog/rybinsk/ |
| Рязань | https://www.b17.ru/psiholog/ryazan/ |
| Самара | https://www.b17.ru/psiholog/samara/ |
| Саранск | https://www.b17.ru/psiholog/saransk/ |
| Саратов | https://www.b17.ru/psiholog/saratov/ |
| Саров | https://www.b17.ru/psiholog/sarov/ |
| Севастополь | https://www.b17.ru/psiholog/sevastopol/ |
| Северодвинск | https://www.b17.ru/psiholog/severodvinsk/ |
| Северск | https://www.b17.ru/psiholog/seversk/ |
| Сергиев Посад | https://www.b17.ru/psiholog/sergiev_posad/ |
| Серпухов | https://www.b17.ru/psiholog/serpuhov/ |
| Симферополь | https://www.b17.ru/psiholog/simferopol/ |
| Славянск-на-Кубани | https://www.b17.ru/psiholog/slavyansk-na-kubani/ |
| Смоленск | https://www.b17.ru/psiholog/smolensk/ |
| Солигорск | https://www.b17.ru/psiholog/soligorsk/ |
| Солнечногорск | https://www.b17.ru/psiholog/solnechnogorsk/ |
| Сосновый Бор | https://www.b17.ru/psiholog/sosnovyy_bor/ |
| Сочи | https://www.b17.ru/psiholog/sochi/ |
| Ставрополь | https://www.b17.ru/psiholog/stavropol/ |
| Стамбул | https://www.b17.ru/psiholog/stanbul/ |
| Старый Оскол | https://www.b17.ru/psiholog/staryy_oskol/ |
| Стерлитамак | https://www.b17.ru/psiholog/sterlitamak/ |
| Ступино | https://www.b17.ru/psiholog/stupino/ |
| Сургут | https://www.b17.ru/psiholog/surgut/ |
| Сызрань | https://www.b17.ru/psiholog/syzran/ |
| Сыктывкар | https://www.b17.ru/psiholog/syktyvkar/ |
| Таганрог | https://www.b17.ru/psiholog/taganrog/ |
| Таллин | https://www.b17.ru/psiholog/tallin/ |
| Тамбов | https://www.b17.ru/psiholog/tambov/ |
| Ташкент | https://www.b17.ru/psiholog/tashkent/ |
| Тбилиси | https://www.b17.ru/psiholog/tbilisi/ |
| Тверь | https://www.b17.ru/psiholog/tver/ |
| Тель-Авив | https://www.b17.ru/psiholog/tel-aviv/ |
| Тирасполь | https://www.b17.ru/psiholog/tiraspol/ |
| Тольятти | https://www.b17.ru/psiholog/tolyatti/ |
| Томск | https://www.b17.ru/psiholog/tomsk/ |
| Троицк | https://www.b17.ru/psiholog/troitsk/ |
| Туапсе | https://www.b17.ru/psiholog/tuapse/ |
| Тула | https://www.b17.ru/psiholog/tula/ |
| Тюмень | https://www.b17.ru/psiholog/tyumen/ |
| Улан-Удэ | https://www.b17.ru/psiholog/ulan-ude/ |
| Ульяновск | https://www.b17.ru/psiholog/ulyanovsk/ |
| Уссурийск | https://www.b17.ru/psiholog/ussuriysk/ |
| Усть-Каменогорск | https://www.b17.ru/psiholog/ust-kamenogorsk/ |
| Уфа | https://www.b17.ru/psiholog/ufa/ |
| Феодосия | https://www.b17.ru/psiholog/feodosiya/ |
| Фрязино | https://www.b17.ru/psiholog/fryazino/ |
| Хабаровск | https://www.b17.ru/psiholog/habarovsk/ |
| Хайфа | https://www.b17.ru/psiholog/hayfa/ |
| Ханты-Мансийск | https://www.b17.ru/psiholog/hanty-mansiysk/ |
| Харьков | https://www.b17.ru/psiholog/harkov/ |
| Хельсинки | https://www.b17.ru/psiholog/helsinki/ |
| Химки | https://www.b17.ru/psiholog/himki/ |
| Чебоксары | https://www.b17.ru/psiholog/cheboksary/ |
| Челябинск | https://www.b17.ru/psiholog/chelyabinsk/ |
| Череповец | https://www.b17.ru/psiholog/cherepovets/ |
| Черкесск | https://www.b17.ru/psiholog/cherkessk/ |
| Чехов | https://www.b17.ru/psiholog/chehov/ |
| Чита | https://www.b17.ru/psiholog/chita/ |
| Шахты | https://www.b17.ru/psiholog/shahty/ |
| Щёлково | https://www.b17.ru/psiholog/schelkovo/ |
| Электросталь | https://www.b17.ru/psiholog/elektrostal/ |
| Энгельс | https://www.b17.ru/psiholog/engels/ |
| Южно-Сахалинск | https://www.b17.ru/psiholog/yujno-sahalinsk/ |
| Ялта | https://www.b17.ru/psiholog/yalta/ |
| Ярославль | https://www.b17.ru/psiholog/yaroslavl/ |
| о. Бали | https://www.b17.ru/psiholog/bali/ |
