# V2. MCP

## Что будет

Один инструмент:

```
transcribe_instagram_reel(url: string) -> {
  text, author, caption, duration, language, source_url, cached
}
```

В Claude Code, Codex или claude.ai пишете:

> Посмотри этот Reel и дай основные тезисы: https://instagram.com/reel/…

Агент вызывает инструмент и получает текст прямо в контекст. Больше не нужно «бот → скопировал → вставил в Claude».

## Как устроено

MCP не дублирует логику бота. Это ещё один тонкий интерфейс:

```python
# interfaces/mcp/server.py (набросок)
from mcp.server.fastmcp import FastMCP

core = build_core(Settings.from_env())
mcp = FastMCP("reel-to-text")

@mcp.tool()
async def transcribe_instagram_reel(url: str) -> dict:
    """Transcribe speech from a public Instagram Reel URL."""
    t = await core.transcribe(url, requester="mcp")
    return t.to_dict()
```

Кэш, лимиты, запасные пути и ошибки — те же, что у бота. Если бот и MCP работают в разных процессах, они делят один SQLite-файл, так что ролик, распознанный в боте, в MCP отдаётся из кэша бесплатно.

## Наш MCP или HikerAPI MCP

У HikerAPI есть готовый MCP-сервер [subzeroid/hikerapi-mcp](https://github.com/subzeroid/hikerapi-mcp): около сотни инструментов, сгенерированных из их OpenAPI (профили, посты, рилсы, сторис, комментарии, хэштеги). Изобретать его заново не нужно.

| Задача | Что брать |
|---|---|
| «Вот ссылка, дай текст / тезисы / сравни с моим постом» | наш `transcribe_instagram_reel` |
| Разбор аккаунта: последние рилсы автора, охваты, комментарии, хэштеги | HikerAPI MCP |
| И то и другое: «возьми 10 последних рилсов автора и дай тезисы каждого» | оба: HikerAPI MCP находит ролики, наш инструмент их расшифровывает |

Почему не заменить наш инструмент на HikerAPI MCP: он отдаёт только данные Instagram, распознавания речи в нём нет. Агенту пришлось бы самому доставать ссылку на MP4 и куда-то её нести. Плюс сотня инструментов в контексте ради одной операции — лишние токены и лишние шансы, что агент выберет не тот.
