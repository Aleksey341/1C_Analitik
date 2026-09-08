# Managed access: работа без OpenAI API key у пользователя

Клиент 1С Аналитик умеет работать в двух режимах:

1. Direct OpenAI: пользователь вводит собственный OpenAI API key.
2. Managed access: пользователь вводит только код доступа к 1С Аналитик. OpenAI API key хранится на сервере и никогда не попадает в установщик или на компьютер пользователя.

## Архитектура

```text
1С Аналитик на ПК
        |
        | Authorization: Bearer <код доступа>
        v
Vercel /api/chat/completions
        |
        | OPENAI_API_KEY хранится только в Environment Variables
        v
OpenAI API
```

Desktop-клиент уже совместим с gateway, потому что gateway предоставляет OpenAI-compatible endpoint `/chat/completions`.

## Развёртывание в Vercel

Репозиторий содержит serverless function:

```text
api/chat/completions.js
```

Подключите репозиторий `Aleksey341/1C_Analitik` к Vercel и задайте переменные окружения:

```text
OPENAI_API_KEY=<серверный ключ OpenAI>
OPENAI_MODEL=gpt-5.6-sol
MANAGED_ACCESS_CODE_HASHES=<sha256-код1>,<sha256-код2>,...
```

Серверный OpenAI API key нельзя добавлять в GitHub, `service.json`, исходный код или установщик.

## Создание кода доступа

На администраторском компьютере:

```powershell
python scripts/make_access_code.py
```

Скрипт выдаст два значения:

```text
ACCESS_CODE=1CA-...
SHA256=...
```

Пользователю передаётся только `ACCESS_CODE`. В Vercel в `MANAGED_ACCESS_CODE_HASHES` сохраняется только `SHA256`.

Для отключения пользователя удалите соответствующий hash из `MANAGED_ACCESS_CODE_HASHES`.

## Включение managed mode у всех установленных клиентов

После deployment получите базовый URL Vercel, например:

```text
https://one-c-analitik.vercel.app/api
```

Запишите его в публичный `service.json`:

```json
{
  "managed_base_url": "https://one-c-analitik.vercel.app/api",
  "mode": "managed"
}
```

При следующем запуске приложение само читает `service.json`. Если найден managed URL, оно переключает LLM endpoint на gateway и просит не OpenAI API key, а код доступа.

Если у пользователя ранее был прямой OpenAI key вида `sk-...`, при переключении на managed mode клиент очищает его локально, чтобы не отправить старый OpenAI secret на gateway.

## Автоматические обновления

Установленная Windows-версия проверяет последний GitHub Release при запуске. Если опубликована более новая версия, пользователь получает предложение обновиться. После согласия установщик скачивается, проверяется по SHA-256 digest из GitHub Release и запускается автоматически.

Постоянная ссылка на последнюю версию:

```text
https://github.com/Aleksey341/1C_Analitik/releases/latest/download/1C-Analitik-Setup.exe
```
