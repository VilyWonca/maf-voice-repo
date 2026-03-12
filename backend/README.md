Backend‑gateway (MVP)
======================

Этот сервис — тонкий **WebSocket‑gateway** между браузером на Raspberry Pi
(`maf_speaker_client`) и будущим voice‑pipeline (wake word, VAD, STT, LLM, TTS).

Сейчас реализован **MVP‑протокол**:

- принимает `session.start` и бинарные аудиокадры от фронта;
- держит простое in‑memory состояние сессии;
- отправляет обратно корректные по формату события:
  - `wake.detected`
  - `speech.started`
  - `speech.ended`
  - `assistant.processing`
  - `assistant.transcript`
  - `assistant.text`
  - `assistant.audio` + один бинарный аудиофрейм (в тестовом режиме)
  - `error`
  - `debug.pong`

Стек
----

- Python 3.10+
- `asyncio`
- [`websockets`](https://websockets.readthedocs.io/en/stable/) (низкоуровневый WS‑сервер)

Быстрый старт
-------------

1. Установка зависимостей (желательно в virtualenv):

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Запуск сервера из корня проекта:

   ```bash
   cd /home/harbi/Work/MAF   # или корень репозитория
   source backend/.venv/bin/activate
   BACKEND_PORT=8082 python -m backend.main
   ```

   По умолчанию сервер слушает `ws://0.0.0.0:8082/ws/voice`.

3. (Опционально) тестовый echo‑режим:

   ```bash
   ECHO_TEST_MODE=1 BACKEND_PORT=8082 python -m backend.main
   ```

   В этом режиме backend записывает несколько секунд аудио и возвращает его
   обратно как WAV — удобно, чтобы проверить путь аудио.

Структура backend
-----------------

```text
backend/
  main.py          # Точка входа, запускает WS‑сервер
  ws_server.py     # Цикл приёма WebSocket‑подключений и хендлер
  session.py       # Объект сессии и простая стейт‑машина
  protocol.py      # Типы JSON‑событий и кодек бинарного аудиофрейма
  config.py        # Порты, хост, флаги тестовых режимов
  requirements.txt # Python‑зависимости
```

В `backend/voice_pipeline/` живёт код Роли 2 (Voice / AI). Контракт и API для
него описаны в корневом `README.md`.

