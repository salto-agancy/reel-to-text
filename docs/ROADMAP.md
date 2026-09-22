# Roadmap

Порядок: V1 Telegram → дать 5–20 людям → посмотреть, пользуются ли вообще → V2 MCP → V3 iPhone.

После V1 следующие версии — дешёвые надстройки: ядро, получение ролика, Deepgram, кэш и ошибки уже есть.

## V1. Telegram-бот ✅

Сделано:

- ядро `ReelToText` и провайдеры HikerAPI, yt-dlp, Deepgram;
- основной путь «Deepgram сам забирает MP4 по ссылке» и запасной «скачать → отправить файл → удалить»;
- бета-доступ по списку ID, лимиты в час и в сутки, лимит длины ролика, таймауты;
- кэш по shortcode и защита от двойной оплаты одного ролика;
- длинный текст: разбивка на сообщения или `.txt`;
- systemd + пульс + автоперезапуск, `deploy/deploy.sh`;
- тесты без сети и ключей (`pytest`).

Что смотреть на бете:

- сколько расшифровок в день на человека (`/stats`, журнал `requests`);
- как часто срабатывает запасной путь (`stt_path=upload` в логах);
- какие ошибки видят люди (`fail ... code=` в логах).

## V2. MCP ⏳

Инструмент `transcribe_instagram_reel(url) -> Transcript`. Подробно: [MCP.md](MCP.md).

Шаги:

1. `interfaces/mcp/server.py` на официальном Python SDK `mcp` (FastMCP), транспорт streamable-http.
2. Внутри только `build_core(settings)` и вызов `core.transcribe(url, requester="mcp:<client>")`.
3. Авторизация: Bearer-токен из env; для claude.ai-коннектора — OAuth по тому же шаблону, что у остальных MCP на сервере.
4. Публикация через уже работающий Cloudflare Tunnel.
5. Тест: в Claude Code «дай тезисы этого Reel: <ссылка>».

## V3. iPhone Shortcut ⏳

Команда «В текст» в Share Sheet. Подробно: [IOS_SHORTCUT.md](IOS_SHORTCUT.md).

Шаги:

1. `interfaces/http/`: `POST /v1/transcribe {"url": "..."}` → `{"text": ..., ...}`, Bearer-токен на пользователя.
2. Публикация через Cloudflare Tunnel.
3. Собрать команду, выложить ссылку iCloud на команду в README.

Позже: «Спросить ChatGPT», «Сохранить в Заметки».

## Дальше

- Другие площадки: TikTok, YouTube Shorts, X video. Новый провайдер + расширение `urls.py`, объект `Transcript` тот же.
- Краткое содержание и тезисы через LLM как отдельная команда поверх того же транскрипта.
