Интеграция Voice Pipeline (Роль 2)
==================================

Твоя задача: реализовать **voice‑pipeline** (wake word, VAD, STT, LLM, TTS)
и отдать его как **Python‑API**, которое вызывает backend‑gateway.

Общая схема
-----------

- Браузер (Raspberry Pi) ↔ WebSocket ↔ **Backend‑gateway (этот слой уже есть)**.
- Backend‑gateway ↔ **твоя voice‑pipeline библиотека** (этот документ).

Gateway уже умеет:

- принимать `session.start`, бинарные `audio.chunk`, `playback.finished`, `debug.ping`;
- парсить аудиокадры (`Float32 LE 48kHz mono`);
- держать состояние сессии (`idle/armed/recording/processing/speaking/error`);
- отправлять на фронт события:
  - `wake.detected`, `speech.*`, `assistant.*`, `error`, `debug.pong`.

Твоя часть —  пайплайн:

> поток аудио чанков → utterance → распознанный текст → ответ LLM → озвучка TTS

Где живёт твой код
------------------

Предлагаемая структура:

```text
backend/
  voice_pipeline/
    __init__.py
    pipeline.py      # основной класс VoicePipeline
    wakeword.py
    vad.py
    stt.py
    llm.py
    tts.py
```

Gateway уже живёт здесь:

```text
backend/
  ws_server.py
  session.py
  protocol.py
  config.py
```

Протокол WebSocket с фронтом менять **не нужно** — это зона ответственности Человека 3.

Публичный API, который ты реализуешь
------------------------------------

Минимально достаточный интерфейс, который gateway будет вызывать из своего кода:

```python
class VoicePipeline:
    def __init__(self) -> None:
        """
        Инициализация твоего пайплайна:
        - загрузка моделей / клиентов STT, LLM, TTS
        - инициализация wake word / VAD (если нужно заранее)
        """

    async def feed_audio_chunk(self, session_id: str, pcm_f32_mono_48k: bytes) -> None:
        """
        Gateway передаёт тебе очередной аудио‑чанк этой сессии.
        Формат см. ниже в разделе «Вход».
        """

    async def notify_speech_start(self, session_id: str) -> None:
        """
        Gateway перешёл в состояние RECORDING.
        Здесь ты очищаешь буферы / состояние для нового utterance.
        """

    async def notify_speech_end(self, session_id: str) -> None:
        """
        Gateway решил, что utterance закончился (endpointing на его стороне).
        После этого ты запускаешь свой пайплайн:
        - собираешь аудио utterance
        - делаешь STT
        - делаешь LLM
        - делаешь TTS
        """

    async def get_result(self, session_id: str) -> tuple[str, bytes]:
        """
        Gateway ждёт здесь результат для последнего utterance этой сессии.

        Возвращаешь:
        - transcript_text: str — финальный распознанный текст пользователя
        - tts_wav_bytes: bytes — байты WAV с озвучкой ответа ассистента
        """
```

Со стороны gateway (Человек 3):

- он будет вызывать `feed_audio_chunk` для каждого входящего аудиокадра;
- вызывать `notify_speech_start`, когда войдёт в RECORDING;
- вызывать `notify_speech_end`, когда закончит utterance;
- вызывать `await get_result` и затем отправлять на фронт:
  - `assistant.transcript { text }`
  - `assistant.text { text }`
  - `assistant.audio { format: "wav", mime_type: "audio/wav" }`
  - и следом бинарные байты `tts_wav_bytes`.

Сам WebSocket, JSON и статусы — это **не твоя зона**, ты просто возвращаешь данные через этот API.

Форматы аудио и ожидания по времени
-----------------------------------

### Вход (от gateway к тебе)

- `pcm_f32_mono_48k: bytes`
  - Float32 PCM
  - little-endian
  - 48000 Hz
  - mono
  - размер чанка может быть разным (не полагайся на фиксированные 128 сэмплов и т.п.).


### Выход (от тебя к gateway)

- `transcript_text: str`
  - финальный текст utterance (UTF‑8).
- `tts_wav_bytes: bytes`
  - полный WAV с озвучкой ответа.
  - PCM 16‑bit, mono, 16k или 48k (выбери формат под свой TTS).

Gateway **не смотрит внутрь** WAV — он просто отправляет его на фронт и ставит `mime_type = "audio/wav"`.


