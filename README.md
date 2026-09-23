# Reel To Text

Отправляете ссылку на Instagram Reel → получаете текст речи из ролика.

## Текущий статус

| Версия | Что | Статус |
|---|---|---|
| V1 | Telegram-бот [@salto_reel_to_text_bot](https://t.me/salto_reel_to_text_bot) | ✅ работает, открытый тест, версия заморожена |
| V2 | MCP-инструмент `transcribe_instagram_reel(url)` для Claude / Codex | ⏳ спроектирован, см. [docs/MCP.md](docs/MCP.md) |
| V3 | Кнопка «В текст» в меню «Поделиться» на iPhone | ⏳ спроектирована, см. [docs/IOS_SHORTCUT.md](docs/IOS_SHORTCUT.md) |

Попробовать: напишите [@salto_reel_to_text_bot](https://t.me/salto_reel_to_text_bot) и пришлите ссылку на Reel.

Сейчас V1 заморожена: собираем реальные запросы и статистику, V2 делаем только по данным. План развития: [docs/ROADMAP.md](docs/ROADMAP.md).

## Как работает

```
Instagram Reel (ссылка)
      ↓
Instagram Provider      HikerAPI, запасной вариант yt-dlp
      ↓  прямая ссылка на MP4
Reel To Text Core       кэш, лимиты, выбор провайдера, запасные пути
      ↓
Deepgram Nova-3         сам скачивает MP4 по ссылке
      ↓
Transcript              текст + автор + подпись + длительность + ссылка
      ↓
Telegram / MCP / iPhone
```

Видео обычно вообще не попадает на сервер: Deepgram забирает MP4 прямо с CDN Instagram. Если CDN его не пустил, сервер скачивает ролик во временную папку, отправляет файл в Deepgram и сразу удаляет.

Ролик на 2:49 проходит целиком примерно за 3–5 секунд.

## V1. Telegram-бот

Пользователь присылает боту ссылку, например `https://www.instagram.com/reel/DdOH1iLKWX9/`. Можно переслать текст из «Поделиться» целиком: бот сам найдёт в нём ссылку.

Бот отвечает «⏳ Расшифровываю…», а через несколько секунд меняет это сообщение на текст ролика. В конце указаны автор и длительность. Длинный текст приходит в нескольких сообщениях, а очень длинный отдельным `.txt`-файлом.

Команды:

- `/start`, `/help`: как пользоваться
- `/id`: показать свой Telegram ID (нужен для доступа в бету)
- `/stats` или `/stats 7`: только для админов, сводка за 1 или N дней (запросы, люди, кэш, платные, ошибки)

Консольный режим без Telegram (удобно проверять):

```bash
python -m reel_to_text transcribe "https://www.instagram.com/reel/DdOH1iLKWX9/"
python -m reel_to_text transcribe --json "<ссылка>"   # весь объект Transcript
```

## V2. MCP

Один инструмент `transcribe_instagram_reel(url)`. Тогда в Claude Code или Codex можно просто написать «посмотри этот Reel и дай тезисы: <ссылка>», и агент сам получит текст. MCP будет тонкой обёрткой над тем же ядром, логика не дублируется. Подробно, а также когда вместо него брать полноценный HikerAPI MCP: [docs/MCP.md](docs/MCP.md).

## V3. iPhone

«В текст» — не встроенная кнопка iPhone, а наша команда в приложении «Команды» (Shortcuts). Когда у команды включено «Показывать в меню „Поделиться“», она появляется в Instagram в меню «Поделиться». Нажал, через несколько секунд текст ролика уже в буфере обмена. Отдельное приложение писать не нужно. Подробно: [docs/IOS_SHORTCUT.md](docs/IOS_SHORTCUT.md).

## Архитектура

Telegram здесь интерфейс, а не само приложение. Вся логика живёт в ядре:

```
reel_to_text/
  core/                  ядро: одно на все интерфейсы
    service.py           ReelToText.transcribe(url) → Transcript
    urls.py              поиск ссылки и shortcode в любом тексте
    store.py             SQLite: кэш по shortcode + журнал запросов
    limits.py            лимит запросов на пользователя
    factory.py           сборка ядра из настроек
  providers/
    instagram/           HikerAPI, yt-dlp (общий контракт в base.py)
    transcription/       Deepgram (общий контракт в base.py)
  interfaces/
    telegram/            бот: только приём сообщения и вывод текста
```

Поэтому MCP или кнопка iPhone добавляются как ещё одна папка в `interfaces/`, без переписывания бота. Сменить источник Instagram или распознавание речи = добавить провайдер. Подробно: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Установка (от чистого VPS до работающего бота)

Нужно: Ubuntu 22.04+ с Python 3.10+, SSH-доступ с правами root.

1. Создайте бота у [@BotFather](https://t.me/BotFather) (`/newbot`) и сохраните токен.
2. Получите ключ Deepgram на [console.deepgram.com](https://console.deepgram.com) и ключ HikerAPI на [hikerapi.com/tokens](https://hikerapi.com/tokens).
3. Узнайте свой Telegram ID, например у [@userinfobot](https://t.me/userinfobot).
4. На сервере создайте `/opt/reel-to-text/.env` по образцу [.env.example](.env.example):
   ```bash
   ssh root@SERVER 'mkdir -p /opt/reel-to-text && nano /opt/reel-to-text/.env'
   ```
   Минимум: `TELEGRAM_BOT_TOKEN`, `DEEPGRAM_API_KEY`, `HIKERAPI_KEY`, `ADMIN_USER_IDS=<ваш ID>`.
5. С рабочей машины из папки репозитория:
   ```bash
   deploy/deploy.sh root@SERVER      # по умолчанию ssh-хост hostinger
   ```
   Скрипт копирует код, создаёт системного пользователя `reel-to-text`, venv, ставит зависимости, устанавливает systemd-службу и таймер проверки живости, перезапускает бота и показывает последние строки лога.
6. Напишите боту `/start` и пришлите ссылку на Reel.

Обновление: тот же `deploy/deploy.sh`. Секреты живут только на сервере, скрипт `.env` не трогает.

### Обслуживание

```bash
systemctl status reel-to-text              # жив ли
journalctl -u reel-to-text -f              # логи в реальном времени
systemctl restart reel-to-text             # перезапуск
cd /opt/reel-to-text && DATA_DIR=/var/lib/reel-to-text venv/bin/python -m reel_to_text health
```

Служба стартует сама после перезагрузки сервера и перезапускается при падении. Раз в 5 минут таймер `reel-to-text-health.timer` проверяет «пульс» бота (файл `/var/lib/reel-to-text/heartbeat`) и перезапускает его, если бот завис. Кэш и журнал запросов: `/var/lib/reel-to-text/reel_to_text.sqlite`.

### Локальная разработка

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env        # заполнить ключи
.venv/bin/python -m pytest  # тесты без сети и ключей
.venv/bin/python -m reel_to_text bot
```

## ENV

| Переменная | Зачем |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен бота |
| `DEEPGRAM_API_KEY` | распознавание речи |
| `HIKERAPI_KEY` | основной источник Instagram |
| `INSTAGRAM_PROVIDERS` | порядок провайдеров, по умолчанию `hikerapi,ytdlp` |
| `YTDLP_COOKIES_FILE` | необязательный файл cookies для yt-dlp |
| `DEEPGRAM_MODEL` | по умолчанию `nova-3` |
| `DEEPGRAM_LANGUAGE` | `multi` (русский + английский), либо `ru`, `en`, `detect` |
| `ACCESS_MODE` | `allowlist` (только список) или `open` (все) |
| `ALLOWED_USER_IDS` | Telegram ID бета-тестеров через запятую |
| `ADMIN_USER_IDS` | ID админов: без лимитов, есть `/stats` |
| `MAX_REEL_SECONDS` | максимальная длина ролика, по умолчанию 300 |
| `MAX_DOWNLOAD_MB` | потолок размера при скачивании в запасном пути |
| `RATE_LIMIT_PER_HOUR`, `RATE_LIMIT_PER_DAY` | лимит новых расшифровок на человека |
| `GLOBAL_DAILY_LIMIT` | общий потолок платных расшифровок за сутки на всех, включая админов; 0 = выключен |
| `HTTP_TIMEOUT`, `STT_TIMEOUT` | таймауты внешних API, секунды |
| `DATA_DIR` | где лежат кэш и пульс |

## Защита баланса

- Доступ только по списку ID, пока `ACCESS_MODE=allowlist`. Чужой пользователь получает свой ID и просьбу отправить его владельцу. В режиме `open` бот доступен всем.
- Общий суточный потолок `GLOBAL_DAILY_LIMIT` на всех: сколько бы людей ни пришло, за сутки не потратится больше заданного.
- Лимит новых расшифровок на человека в час и в сутки. Ролики из кэша бесплатны и в лимит не входят.
- Каждый ролик распознаётся один раз: результат кэшируется по shortcode. Если два человека одновременно прислали один ролик, платный запрос уходит один.
- Ролики длиннее `MAX_REEL_SECONDS` отклоняются до обращения в Deepgram (когда провайдер сообщает длительность; HikerAPI сообщает всегда).
- У всех внешних вызовов есть таймауты.

## Статистика

Каждый запрос с любого входа оставляет одну строку в таблице `events`, без текста ролика и без подписи:

`ts`, `user_id`, `reel_shortcode`, `duration`, `processing_ms`, `cache_hit`, `instagram_provider`, `stt_provider`, `stt_path`, `success`, `error_type`.

```bash
cd /opt/reel-to-text
DATA_DIR=/var/lib/reel-to-text venv/bin/python -m reel_to_text stats --days 30        # сводка
DATA_DIR=/var/lib/reel-to-text venv/bin/python -m reel_to_text stats --days 30 --csv  # сырые строки
```

Зачем: через 20–50 реальных запросов решить по данным, нужен ли MCP и что улучшать, а не развивать инфраструктуру вслепую.

## Ограничения

- Получение ролика зависит от внешнего провайдера. Instagram регулярно меняет внутренние API, и это может ломать получение Reel у любого провайдера.
- yt-dlp работает без платного API, но с серверных IP Instagram быстро отвечает `429 Too Many Requests`: на тесте это случилось уже на третьем запросе. Поэтому yt-dlp здесь только запасной путь.
- Только публичные ролики. Приватные аккаунты не поддерживаются.
- Если в ролике нет речи (только музыка), бот так и скажет.

## Лицензия

MIT
