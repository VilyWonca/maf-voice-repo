Интеграция Voice Pipeline (Роль 2)
==================================

Этот репозиторий содержит backend‑gateway (Роль 3) и контракт для Voice / AI пайплайна (Роль 2).

Твоя задача как Роль 2: реализовать **voice‑pipeline** (wake word, VAD, STT, LLM, TTS)
и отдать его как **Python‑API**, которое вызывает gateway. WebSocket, протокол с фронтом
и деплой уже сделаны.

1. Где живёт твой код
---------------------

Структура:

```text
backend/
  config.py
  main.py
  protocol.py
  session.py
  ws_server.py
  requirements.txt

  voice_pipeline/
    __init__.py        # можешь создать
    pipeline.py        # здесь твой класс VoicePipeline
    wakeword.py        # по желанию
    vad.py             # по желанию
    stt.py             # по желанию
    llm.py             # по желанию
    tts.py             # по желанию
```

Gateway уже реализован в `backend/*.py`. Протокол WebSocket с фронтом менять **не нужно**.

2. Как запустить backend
------------------------

```bash
git clone git@github.com:VilyWonca/maf-voice-repo.git
cd maf-voice-repo

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Обычный запуск gateway:

```bash
cd ~/maf-voice-repo      # корень репо
source backend/.venv/bin/activate
BACKEND_PORT=8082 python -m backend.main
```

В этом режиме backend:

- слушает WebSocket на `ws://localhost:8082/ws/voice`;
- принимает `session.start`, бинарные `audio.chunk`, `playback.finished`, `debug.ping`;
- ведёт состояния `idle/armed/recording/processing/speaking/error`;
- отправляет на фронт события `wake.detected`, `speech.*`, `assistant.*`, `error`, `debug.pong`
  (когда будет подключён твой пайплайн).

Тестовый echo‑режим (можно включать для отладки звука):

```bash
cd ~/maf-voice-repo
source backend/.venv/bin/activate
ECHO_TEST_MODE=1 BACKEND_PORT=8082 python -m backend.main
```

В этом режиме backend:

- ~5 секунд пишет аудио;
- шлёт `assistant.*` события;
- возвращает WAV с записанным голосом обратно (для проверки пути аудио).

3. Публичный API, который ты реализуешь
---------------------------------------

Gateway будет вызывать твой класс `VoicePipeline` из `backend/voice_pipeline/pipeline.py`.

Минимально достаточный интерфейс:

```python
class VoicePipeline:
    def __init__(self) -> None:
        """
        Инициализируешь свои модели / клиентов:
        - wake word
        - VAD
        - STT
        - LLM
        - TTS
        """

    async def feed_audio_chunk(self, session_id: str, pcm_f32_mono_48k: bytes) -> None:
        """
        Gateway передаёт очередной аудио‑чанк этой сессии.
        Формат: Float32 PCM, little-endian, 48000 Hz, mono.
        payload = содержимое бинарного фрейма без 8‑байтного заголовка.
        """

    async def notify_speech_start(self, session_id: str) -> None:
        """
        Gateway перешёл в состояние RECORDING.
        Обнуляешь буферы / состояние для нового utterance.
        """

    async def notify_speech_end(self, session_id: str) -> None:
        """
        Gateway решил, что utterance закончился.
        После этого ты:
        - собираешь аудио utterance
        - делаешь STT
        - делаешь LLM
        - делаешь TTS
        """

    async def get_result(self, session_id: str) -> tuple[str, bytes]:
        """
        Gateway ждёт здесь результат для последнего utterance.

        Возвращаешь:
        - transcript_text: str — финальный текст пользователя
        - tts_wav_bytes: bytes — байты WAV с озвучкой ответа
        """
```

Со стороны gateway:

- он вызывает `feed_audio_chunk` на каждый аудиокадр;
- вызывает `notify_speech_start`, когда входит в RECORDING;
- вызывает `notify_speech_end`, когда закончил utterance;
- `await get_result` и дальше сам шлёт на фронт:
  - `assistant.transcript { text }`
  - `assistant.text { text }`
  - `assistant.audio { format: "wav", mime_type: "audio/wav" }`
  - и затем `tts_wav_bytes` как бинарный фрейм.

4. Форматы аудио
----------------

### Вход (gateway → твой пайплайн)

- `pcm_f32_mono_48k: bytes`
  - Float32 PCM
  - little-endian
  - 48000 Hz
  - mono
  - размер чанка может меняться.

### Выход (твой пайплайн → gateway)

- `transcript_text: str`
  - текст utterance (UTF‑8).
- `tts_wav_bytes: bytes`
  - валидный WAV:
    - PCM 16‑bit,
    - mono,
    - 16k или 48k (что проще для твоего TTS).

Gateway не парсит WAV, он только отправляет его в браузер (`audio/wav`).

5. Что сделать в первую очередь
-------------------------------

1. Реализовать заглушечный `VoicePipeline`, который:
   - в `feed_audio_chunk` просто накапливает чанки в память,
   - в `notify_speech_end` помечает utterance как готовый,
   - в `get_result` возвращает:
     - фиксированный текст `"echo test"`,
     - простой WAV (тишина или тон).
2. Когда это будет работать end‑to‑end, заменить заглушки на реальный
   пайплайн из `Описание проекта/for_voice_robot.md`:
   - wake word,
   - VAD/endpointing,
   - STT,
   - LLM,
   - TTS.

