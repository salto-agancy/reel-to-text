# Архитектура

## Главное решение

Telegram, MCP и iPhone — тонкие интерфейсы над одним ядром. Ни один интерфейс не ходит в HikerAPI или Deepgram напрямую, все вызывают:

```python
transcript = await core.transcribe(text_or_url, requester="tg:123")
```

Почему так: через месяц добавить MCP или кнопку iPhone — это 50–100 строк в `interfaces/`, а не переписывание бота. Кэш, лимиты, обработка ошибок и запасные пути работают одинаково во всех входах.

## Поток одного запроса

```
text_or_url
  → urls.extract_shortcode()            ссылка ищется в любом тексте, в том числе в тексте из «Поделиться»
  → store.get_transcript(shortcode)     есть в кэше → вернуть, бесплатно
  → уже распознаётся тот же ролик?      → дождаться его, второй раз не платить
  → limiter.check(requester)            лимит в час / в сутки
  → InstagramProvider.get_reel()        по очереди из INSTAGRAM_PROVIDERS
  → проверка длительности               длиннее MAX_REEL_SECONDS → отказ до оплаты
  → stt.transcribe_url(video_url)       Deepgram сам скачивает MP4
       └ RemoteFetchFailed → скачать во временную папку → stt.transcribe_file() → удалить
  → Transcript → store.put_transcript()
```

## Провайдеры Instagram

Контракт в `providers/instagram/base.py`: `get_reel(shortcode) -> ReelMedia`.

Ошибки делятся на два вида:

- `ReelNotFound`, `NotAVideo` — проблема в самом ролике. Следующий провайдер не пробуем.
- `ProviderUnavailable` — проблема у провайдера (ключ, баланс, 429, сеть). Пробуем следующий.

| Провайдер | Когда |
|---|---|
| `hikerapi` | основной. `GET /v1/media/by/code`, заголовок `x-access-key`, отдаёт `video_url`, `video_duration`, автора и подпись |
| `ytdlp` | запасной, без платного API. С серверных IP быстро упирается в 429 |

Новый провайдер (Apify, свой скрейпер, другой API) = новый класс с методом `get_reel` + строка в `core/factory.py`.

## Распознавание речи

Контракт в `providers/transcription/base.py`: `transcribe_url(url)` и `transcribe_file(path)`.

Deepgram Nova-3, `language=multi`: русский и английский, в том числе вперемешку в одном ролике. `smart_format` выключен, потому что портит русские числительные. Абзацы берутся из ответа Deepgram (`paragraphs=true`).

## Transcript — стандартный объект

`text`, `source_url`, `shortcode`, `author`, `caption`, `duration`, `language`, `instagram_provider`, `stt_provider`, `stt_path` (`remote_url` или `upload`), `created_at`, `cached`.

Тот же объект будет у TikTok, YouTube Shorts и X video, когда они появятся: вход — любая ссылка, выход — один формат.

## Хранилище

SQLite в `DATA_DIR`:

- `transcripts` — кэш по shortcode (JSON объекта Transcript);
- `requests` — журнал платных запросов для лимитов, старше двух суток удаляется.

## Эксплуатация

- systemd-служба `reel-to-text`, long polling: не нужны ни домен, ни webhook.
- `Restart=always` + запуск при загрузке.
- Пульс: бот раз в 30 секунд пишет время в `DATA_DIR/heartbeat`; таймер раз в 5 минут перезапускает службу, если пульсу больше 3 минут.
- Логи в journald. Логгер `httpx` приглушён, потому что в URL Instagram CDN есть подписанные токены.
- Служба работает от отдельного системного пользователя, запись разрешена только в `/var/lib/reel-to-text`.
