# MIRTVONLINE

Русский ниже, English further down.

## Русский

Каталог, телепрограмма и поиск телеканалов прямо в Home Assistant, с кнопкой
**«На ТВ»**, голосовыми командами и скриптами для автоматизаций и ИИ-агента.

Дополнение не хранит и не пересылает видео. Оно собирает каталог из публичных
бесплатных плейлистов и ваших собственных, загружает программу передач и говорит
телевизору, что включить; поток телевизор берёт прямо из источника.

Подробная справка по самому сайту открывается кнопкой **«?»** на сайте. Здесь то, что
касается Home Assistant: установка, настройки, запуск на ТВ, голос, данные и обновление.

### Вкладки дополнения

В Home Assistant: **Настройки** → **Приложения** (в старых версиях «Дополнения») →
**MIRTVONLINE**. Сверху четыре вкладки:

| Вкладка | Что там |
|---|---|
| **Информация** (Info) | Установка, **Запуск**/**Остановка**, **Перезапуск**, **Обновить**, переключатели «Показывать на боковой панели» и «Автообновление» |
| **Документация** (Documentation) | Этот текст |
| **Конфигурация** (Configuration) | Настройки дополнения, см. раздел «Настройки» ниже |
| **Журнал** (Log) | Что делает дополнение: запуск, сборка каталога, место на диске, ошибки |

### Установка

1. Добавьте репозиторий в Home Assistant, как описано в README репозитория.
2. Откройте **MIRTVONLINE** → **Установить** (Install). Home Assistant сам собирает
   образ из папки дополнения, это занимает несколько минут.
3. Включите **Показывать на боковой панели** (Show in sidebar).
4. **Автообновление** (Auto update) оставьте выключенным, см. раздел «Обновление».
5. Нажмите **Запустить** (Start). В **Журнале** появится строка
   `MIRTVONLINE: profile S, language ru, time zone …`.

### Вход: токен не нужен

Сайт открывается пунктом **MIRTVONLINE** в боковой панели Home Assistant, на телефоне
в приложении Home Assistant (Companion) так же. Отдельного адреса, пароля или
токена нет: Home Assistant уже проверил ваш логин.

Про `MIH_API_TOKEN`. Это ключ для случая, когда сайт открывают напрямую по адресу и
порту, в обход Home Assistant (например, на отдельном сервере). В дополнении он не
нужен и вводить его некуда: дополнение само создаёт случайный ключ в своей папке
`/data/.api_token`, чтобы закрыть сервер от других контейнеров, а запросы из боковой
панели проходят без него. Наружу порты не открываются. Поэтому в **«Настройки»** сайта
вместо поля для токена написано, что он не нужен.

Связь с самим Home Assistant (телевизоры, создание скриптов, уведомления) тоже не
требует ручного токена: Home Assistant выдаёт дополнению служебный ключ при запуске.

### Первые часы

Сразу после установки каталог пуст. Дополнение само ищет публичные плейлисты,
проверяет их потоки и добавляет рабочие каналы: первые десятки обычно появляются в
течение часа, дальше каталог растёт сам. Ход работы виден на странице сайта
**«Статус»**.

Свой плейлист (например, от провайдера) пока добавляется без отдельной кнопки: сайт →
**«Настройки»** → внизу **«Документация API»** → запрос `POST /api/v1/sources` с полями
`name` и `url`. Дальше задача «Обновление плейлистов» перечитывает его раз в сутки.

### Настройки

Вкладка **Конфигурация**. После изменения нажмите **Сохранить** (Save), затем на
вкладке **Информация** — **Перезапуск** (Restart): настройки читаются при запуске.

| Настройка | Что делает |
|---|---|
| **Язык уведомлений и скриптов** (`language`) | ru, en или vi. Язык уведомлений в Home Assistant, а также названий и голосовых фраз скриптов, которые создаёт кнопка «Создать в Home Assistant». Сайт, включая события и сводки задач на странице «Статус», показывается на языке из браузера: **«Настройки»** → **«Язык интерфейса»** (по умолчанию язык браузера; события и сводки бывают только на ru, en, vi, для остальных языков по-английски) |
| **Профиль данных** (`profile`) | Сколько потоков дополнение набирает из найденных плейлистов: S — до 6 000 (любой сервер с 4 ГБ), M — до 15 000 (Raspberry Pi 5, мини-ПК), L — до 30 000 (мини-ПК). В профиле L одновременно проверяется 8 потоков вместо 4. Ваши собственные плейлисты в лимит не входят и никогда не удаляются |
| **Страна дома** (`home_country`) | Две буквы, например `de`. Каналы этой страны идут первыми, когда набран лимит профиля, и попадают в каталог, даже если с сервера выглядят заблокированными по стране. Пусто: таких поблажек нет |
| **Языки каналов** (`channel_languages`) | Коды языков через запятую, например `ru, en`. Когда набран лимит профиля, дополнение дальше берёт только каналы на этих языках, страны дома и избранные, а место освобождает за счёт худших прочих найденных потоков. Пусто: язык из первой настройки |
| **Часовой пояс** (`timezone`) | Для программы передач и ночного расписания задач (программа обновляется в 03:30), например `Europe/Berlin`. Пусто: часовой пояс Home Assistant |
| **Токен GitHub** (`github_token`) | Необязательно. Любой токен без прав: поиск плейлистов ищет и по коду на GitHub, а не только по репозиториям |

### Лёгкий режим и расписание

Дополнение настроено под домашний сервер: фоновые задачи идут строго по одной и
уступают место сайту, каталог пересобирается, только когда его данные изменились, и
не чаще раза в час. Поэтому новое появляется не мгновенно.

| Задача | Когда |
|---|---|
| Поисковик плейлистов | каждые 30 мин; поиск заново первые 3 дня ежедневно, потом раз в месяц |
| Упаковщик плейлистов | каждые 15 мин, по 60 потоков |
| Обновление плейлистов (только ваши добавленные) | раз в сутки |
| Обновление телепрограммы | раз в сутки в 03:30 по часовому поясу дополнения |
| Проверка потоков | раз в неделю |
| Оповещения по темам | каждые 5 мин: напоминание в «События» за 15 мин до передачи по вашей теме |
| Сводка за сутки | ежедневно в 09:00, итог дня в «События» |

Задачу можно запустить вручную: сайт → **«Статус»** → **«Запустить»**.

### Запуск на ТВ

Кнопка **«На ТВ»** включает канал на телевизоре, который уже есть в Home Assistant.
Свой скрипт для этого не нужен. Дополнение находит телевизоры среди медиаплееров HA;
разные записи одного ТВ (например, ADB и Google Cast одного Android TV) видны как
один телевизор. Порядок попыток:

1. **ADB** (интеграция Android Debug Bridge): поток открывается в **VLC**, иначе в
   **Just Player**; выключенный ТВ сначала включается. Поставьте один из плееров на ТВ
   из Google Play.
2. **Google Cast**.
3. **AirPlay** (интеграция Apple TV).
4. Любой другой медиаплеер HA, который умеет открывать ссылку (DLNA и т. п.).

Какой ТВ включать: сайт → **«Настройки»** → **«Телевизор»**. **«ТВ по умолчанию для
всех»** хранится в дополнении, **«ТВ в этом браузере»** заменяет его для одного
телефона или компьютера. Если телевизор в HA один, выбирать ничего не нужно.

В **«Настройки»** → **«Кнопка «На ТВ»»** обычно выбрано **«Напрямую на ТВ через Home
Assistant»**, менять ничего не нужно. **«Через свой скрипт HA»** нужен, только если вы
сами дописали `script.mih_play` (см. ниже): дополнение отдаёт ему адреса потоков, а ТВ
включает скрипт. Варианта «Через агента» в дополнении нет, для агента есть скрипт
`script.mirtv_channel`.

Samsung, LG и другие ТВ без Android TV: подключите приставку с Google TV
(Chromecast с Google TV и похожие), и она появится в HA как обычный телевизор.

### Голос, скрипты и агент

Кнопке «На ТВ» скрипты не нужны. Они нужны, чтобы включать канал из самого Home
Assistant: голосом через Assist, из автоматизаций, с панелей и из ИИ-агента.

Создать: сайт → **«Настройки»** → **«Скрипты и голосовые команды»** → **«Создать в
Home Assistant»**. Там видно, что уже есть (✓) и чего нет (—). Существующие скрипты и
автоматизации не перезаписываются, править их можно в HA: **Настройки** →
**Автоматизации и сцены** → **Скрипты** / **Автоматизации**. Создаются:

- `script.mirtv_channel` «MIRTVONLINE: включить канал»: включает канал по названию.
  Поле `channel` — название, как его говорят; `tv` — медиаплеер, необязательно (без
  него ТВ по умолчанию).
- `automation.mirtvonline_voice`: фразы для Assist без ИИ. На русском: «включи канал
  …», «включи на телевизоре …», «поставь канал …», «переключи на канал …», «канал …».
  На английском: «play channel …», «turn on channel …», «put on channel …», «switch to
  channel …», «watch … on tv». Фразы берутся на языке из настройки **«Язык
  уведомлений и скриптов»** в момент создания.
- `script.mih_play` «MIRTVONLINE: свой запуск потока»: шаблон для способа «Через свой
  скрипт HA», если хотите запускать поток по-своему.

**Assist с ИИ** (OpenAI, Anthropic, Ollama и другие): **Настройки** → **Голосовые
ассистенты** → **Открыть доступ** → **+ Открыть доступ к объектам** → «MIRTVONLINE:
включить канал». После этого можно говорить свободно.

**Внешний ИИ-агент** (Claude и другие): добавьте в HA интеграцию **Model Context
Protocol Server** (**Настройки** → **Устройства и службы** → **+ Добавить
интеграцию**) и откройте скрипт для Assist, как выше. Агент подключается к
`http://<адрес HA>:8123/api/mcp` с долгоживущим токеном Home Assistant (**Профиль** →
**Безопасность** → **Создать токен**) и видит скрипт как инструмент. Это токен
самого HA, не `MIH_API_TOKEN`.

**Из автоматизации или с панели**: действие `script.mirtv_channel` с данными
`channel: "Матч ТВ"` и, если нужно, `tv: media_player.…`.

Агент или голос передают только название. Дополнение само находит канал, выбирает
лучший поток и включает его. Если не вышло (канал не найден, нет рабочего потока, ТВ
недоступен), в HA появляется уведомление «MIRTVONLINE: канал не включился».

### Данные и резервные копии

Всё хранится в папке дополнения `/data`: база, снимки плейлистов, выгрузки. В
резервные копии Home Assistant попадают база и настройки (избранное, ручные
категории, ТВ по умолчанию, режим 18+); снимки и выгрузки не попадают, они
создаются заново. При удалении дополнения его данные удаляются.

После каждой сборки каталога в **Журнал** пишется, сколько она длилась и пик памяти,
и сколько места занято, например:
`catalog built in 3.2 s: 1520 channels, peak memory 240 MB` и
`data on disk: 310 MB (database 280, snapshots 20, export 2, other 8)`.
То же видно на сайте: **«Статус»** → **«Данные на диске»**. Ожидаемо для профиля S:
около 1 ГБ на диске и до 600 МБ памяти; M: 2–3,5 ГБ и до 900 МБ.

### Обновление

Только вручную: вкладка **Информация** → **Обновить** (Update), когда HA покажет
новую версию; перед этим прочитайте список изменений (CHANGELOG). Home Assistant
заново соберёт образ, это несколько минут; данные и настройки сохраняются.
**Автообновление** держите выключенным.

### Если что-то не так

- **Каталог пуст** через несколько часов: **Журнал** и сайт → **«Статус»** →
  **«События»**; проверьте, что у сервера есть интернет.
- **«На ТВ» не видит телевизор**: ТВ должен быть в HA как медиаплеер (интеграции
  Android Debug Bridge, Google Cast или Apple TV).
- **ТВ включается, но видео нет** (ADB): поставьте на ТВ VLC или Just Player.
- **Голосовая фраза не срабатывает**: проверьте, что автоматизация создана
  (**«Скрипты и голосовые команды»** на сайте) и включена в HA, а фраза на том языке,
  который был в настройке при создании.

### Пока не сделано

Мастер первого запуска; кнопка для своего плейлиста на сайте; еженедельное обновление
справочника каналов; пуши на телефон; вариант «Через агента» (MCP самого дополнения).

---

## English

A catalog, TV guide and search for live TV channels inside Home Assistant, with an
**On TV** button, voice commands and scripts for automations and an AI agent.

The add-on does not store or relay any video. It builds the catalog from public free
playlists and your own, loads the TV guide and tells the TV what to play; the TV takes
the stream straight from its source.

The site's own help opens with the **?** button on the site. This page covers the
Home Assistant side: install, options, launch on a TV, voice, data and updates.

### The add-on's tabs

In Home Assistant: **Settings** → **Apps** (older versions: Add-ons) → **MIRTVONLINE**.
Four tabs at the top:

| Tab | What is there |
|---|---|
| **Info** | Install, **Start**/**Stop**, **Restart**, **Update**, the **Show in sidebar** and **Auto update** switches |
| **Documentation** | This page |
| **Configuration** | The add-on's options, see Options below |
| **Log** | What the add-on does: start, catalog builds, disk use, errors |

### Install

1. Add the repository to Home Assistant as the repository README says.
2. Open **MIRTVONLINE** → **Install**. Home Assistant builds the image from the add-on
   folder itself, a few minutes.
3. Turn on **Show in sidebar**.
4. Keep **Auto update** off, see Update below.
5. Press **Start**. The **Log** shows `MIRTVONLINE: profile S, language ru, time zone …`.

### Sign-in: no token needed

The site opens from **MIRTVONLINE** in the Home Assistant sidebar, the same in the
Home Assistant (Companion) app on a phone. There is no separate address, password or
token: Home Assistant has already checked your login.

About `MIH_API_TOKEN`: it is the key for opening the site directly by address and port,
bypassing Home Assistant (say, on a separate server). The add-on does not need it and
has nowhere to type it: it makes a random key in its own `/data/.api_token` to keep
other containers out, and the sidebar's requests pass without it. No ports are opened
to the outside. That is why the site's **Settings** say the token is not needed instead
of showing a token field.

Talking to Home Assistant itself (TVs, creating scripts, notifications) needs no
manual token either: Home Assistant gives the add-on a service key on start.

### The first hours

Right after install the catalog is empty. The add-on finds public playlists, checks
their streams and adds the working channels: the first few dozen usually within an
hour, then the catalog keeps growing. The site's **Status** page shows the progress.

Your own playlist (from a provider, say) has no button yet: site → **Settings** →
**API documentation** at the bottom → `POST /api/v1/sources` with `name` and `url`. The
"Your playlists" job then rereads it daily.

### Options

The **Configuration** tab. After a change press **Save**, then **Restart** on the
**Info** tab: options are read on start.

| Option | What it does |
|---|---|
| **Notification and script language** (`language`) | ru, en or vi. The language of Home Assistant notifications and of the names and voice phrases of the scripts **Create in Home Assistant** makes. The site, the events and job summaries on its **Status** page included, uses the language picked in the browser: **Settings** → **Interface language** (default: the browser's language; events and summaries exist in ru, en and vi only, other languages get English) |
| **Data profile** (`profile`) | How many streams the add-on takes from the playlists it finds: S up to 6,000 (any 4 GB box), M up to 15,000 (Raspberry Pi 5, mini PC), L up to 30,000 (mini PC). Profile L checks 8 streams at once instead of 4. Your own playlists don't count towards the limit and are never removed |
| **Home country** (`home_country`) | Two letters, e.g. `de`. Channels of this country come first once the profile's limit is reached, and get into the catalog even if they look geo-blocked from the server. Empty: no such exceptions |
| **Channel languages** (`channel_languages`) | Language codes separated by commas, e.g. `ru, en`. Once the profile's limit is reached the add-on only takes channels in these languages, of the home country and favourites, making room by dropping the worst other found streams. Empty: the language from the first option |
| **Time zone** (`timezone`) | For the TV guide and the nightly job schedule (the guide updates at 03:30), e.g. `Europe/Berlin`. Empty: Home Assistant's time zone |
| **GitHub token** (`github_token`) | Optional. Any token with no permissions: the playlist search also searches code on GitHub, not just repositories |

### Light mode and schedule

Tuned for a home box: background jobs run strictly one at a time and give way to the
site; the catalog is rebuilt only when its data changed and at most hourly. So new
things do not show up instantly.

| Job | When |
|---|---|
| Playlist scout | every 30 min; the search starts over daily for 3 days, then monthly |
| Playlist packer | every 15 min, 60 streams a run |
| Your playlists (only the ones you added) | daily |
| TV guide | daily at 03:30, add-on time zone |
| Re-check of working streams | weekly |
| Topic alerts | every 5 min: a reminder under Events 15 min before a programme on your topic |
| Daily digest | daily at 09:00, the day's summary under Events |

Run a job by hand: site → **Status** → **Run**.

### Launch on a TV

**On TV** starts the channel on a TV Home Assistant already knows, with no script of
your own. The add-on finds the TVs among Home Assistant's media players; the entities
of one TV (e.g. ADB and Google Cast of the same Android TV) show up as one TV. It
tries, in order:

1. **ADB** (Android Debug Bridge integration): opens the stream in **VLC**, else in
   **Just Player**; a TV that is off is turned on first. Install one of the two players
   on the TV from Google Play.
2. **Google Cast**.
3. **AirPlay** (Apple TV integration).
4. Any other media player that can play a link (DLNA and the like).

Which TV: site → **Settings** → **TV**. **Default TV for everyone** is kept in the
add-on, **TV in this browser** overrides it for one phone or computer. With a single TV
in Home Assistant nothing needs picking.

In **Settings** → **The “On TV” button** **Straight to the TV through Home Assistant**
is normally chosen; nothing needs changing. **Through your own HA script** is only for
when you wrote `script.mih_play` yourself (see below): the add-on hands it the stream
addresses and the script starts the TV. The add-on has no “Through the agent” choice;
for an agent there is `script.mirtv_channel`.

Samsung, LG and other TVs without Android TV: plug in a Google TV box (Chromecast with
Google TV and the like); it shows up in Home Assistant as a normal TV.

### Voice, scripts and an agent

**On TV** needs no scripts. Scripts are for starting a channel from Home Assistant
itself: by voice through Assist, from automations, dashboards and an AI agent.

Create them: site → **Settings** → **Scripts and voice commands** → **Create in Home
Assistant**. It shows what exists (✓) and what is missing (—). Existing scripts and
automations are never overwritten; edit them in Home Assistant: **Settings** →
**Automations & scenes** → **Scripts** / **Automations**. It creates:

- `script.mirtv_channel` "MIRTVONLINE: turn on a channel": turns a channel on by name.
  Field `channel` is the name as people say it; `tv` is a media player, optional
  (default TV without it).
- `automation.mirtvonline_voice`: phrases for Assist without an AI. English: "play
  channel …", "turn on channel …", "put on channel …", "switch to channel …", "watch …
  on tv". Russian: «включи канал …», «включи на телевизоре …», «поставь канал …»,
  «переключи на канал …», «канал …». The phrases follow the **Notification and script
  language** option at the time of creation.
- `script.mih_play` "MIRTVONLINE: own stream launch": a template for the "own HA
  script" way, if you want to play the stream your own way.

**Assist with an AI** (OpenAI, Anthropic, Ollama and others): **Settings** → **Voice
assistants** → **Expose** → **+ Expose entities** → "MIRTVONLINE: turn on a channel".
Then speak freely.

**An outside AI agent** (Claude and others): add the **Model Context Protocol Server**
integration (**Settings** → **Devices & services** → **+ Add integration**) and expose
the script to Assist as above. The agent connects to `http://<HA address>:8123/api/mcp`
with a Home Assistant long-lived token (**Profile** → **Security** → **Create token**)
and sees the script as a tool. That is Home Assistant's own token, not `MIH_API_TOKEN`.

**From an automation or a dashboard**: the action `script.mirtv_channel` with
`channel: "BBC One"` and, if needed, `tv: media_player.…`.

Voice and the agent pass only the name. The add-on finds the channel, picks the best
stream and starts it. If that fails (no such channel, no working stream, TV not
reachable), Home Assistant shows the notification "MIRTVONLINE: the channel did not
start".

### Data and backups

Everything lives in the add-on's own `/data`: the database, playlist snapshots,
exports. Home Assistant backups include the database and settings (favorites, manual
categories, default TV, 18+ mode); snapshots and exports are left out and are made
again. Uninstalling the add-on deletes its data.

After every catalog build the **Log** prints its time, peak memory and disk use, e.g.
`catalog built in 3.2 s: 1520 channels, peak memory 240 MB` and
`data on disk: 310 MB (database 280, snapshots 20, export 2, other 8)`.
The site shows the same under **Status** → **Data on disk**. Expected for profile S:
about 1 GB on disk and up to 600 MB of memory; M: 2–3.5 GB and up to 900 MB.

### Update

By hand only: **Info** tab → **Update** when Home Assistant offers a new version; read
the changelog first. Home Assistant rebuilds the image, a few minutes; data and
options stay. Keep **Auto update** off.

### Troubleshooting

- **The catalog is still empty** after a few hours: see the **Log** and site →
  **Status** → **Events**; check that the box has internet.
- **On TV sees no TV**: the TV must be a media player in Home Assistant (Android Debug
  Bridge, Google Cast or Apple TV integration).
- **The TV turns on but shows nothing** (ADB): install VLC or Just Player on the TV.
- **A voice phrase does nothing**: check that the automation exists (**Scripts and
  voice commands** on the site) and is on in Home Assistant, and that the phrase is in
  the language the option had at creation.

### Not done yet

The first-run wizard; a button for your own playlist on the site; the weekly channel
directory refresh; phone pushes; the **Through the agent** way (the add-on's own MCP).
