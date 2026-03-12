
**Raspberry Pi 4 → Chromium/browser frontend → WebSocket → backend**
с активацией по **wake word**.

Я дам это как **каркас системы**, чтобы можно было уже раскладывать в задачи и писать код.

---

# 1. Итоговая схема

```text
[Browser on Raspberry Pi]
  - UI
  - microphone capture
  - audio chunk sender
  - audio playback
  - screen states

          ||
          || WebSocket
          \/

[Backend]
  - stream session handler
  - audio buffer
  - wake word detector
  - VAD / endpointing
  - STT
  - LLM
  - TTS
  - response sender
```

---

# 2. Что должно быть на фронте

Фронт на Pi в браузере делает только лёгкие вещи:

* получает доступ к микрофону
* читает аудиосэмплы
* отправляет чанки на сервер
* получает события от сервера
* воспроизводит ответ
* показывает состояние на экране

То есть фронт — это **тонкий voice client**.

## Состояния фронта

Я бы сразу зафиксировал такие:

* `idle` — ждём ключевое слово
* `armed` — wake word услышан, ждём команду
* `recording` — пользователь говорит
* `processing` — сервер обрабатывает
* `speaking` — робот отвечает
* `error` — проблема со связью

---

# 3. Что должно быть на бэке

Бэкенд — это основной мозг.

Он должен:

* принять аудиопоток
* держать сессию конкретного устройства
* детектить wake word
* понимать начало речи
* понимать конец речи
* собирать utterance
* прогонять его через STT
* отправлять текст в LLM
* синтезировать ответ через TTS
* вернуть ответ фронту

---

# 4. Логика пайплайна

## Поведение

1. браузер постоянно шлёт аудиочанки
2. сервер получает поток
3. сервер в состоянии `IDLE` ищет wake word
4. как только wake word найден:

   * переводит сессию в `ARMED`
   * шлёт событие на фронт
5. дальше VAD ждёт начало речи
6. когда речь началась:

   * переводим в `RECORDING`
   * собираем utterance
7. когда тишина достигла порога:

   * завершаем utterance
   * переводим в `PROCESSING`
8. делаем `STT -> LLM -> TTS`
9. отправляем текст и аудио на фронт
10. фронт проигрывает звук
11. после окончания возвращаемся в `IDLE`

---

# 5. Минимальная структура проекта

## Frontend

```text
frontend/
  src/
    app/
      App.tsx
      state.ts
      ws.ts
      audio.ts
      player.ts
      ui.tsx
    worklets/
      mic-processor.js
```

## Backend

```text
backend/
  app/
    main.py
    ws_server.py
    session.py
    state_machine.py
    audio_buffer.py
    wakeword.py
    vad.py
    stt.py
    llm.py
    tts.py
    protocol.py
    config.py
```

---

# 6. Протокол между фронтом и сервером

Лучше сразу сделать **нормальный event protocol**.

## Front -> Backend

### старт сессии

```json
{
  "type": "session.start",
  "device_id": "robot-01"
}
```

### аудиочанк

Бинарно или мета + бинарно. Для простоты логики опишу как сообщение:

```json
{
  "type": "audio.chunk",
  "sample_rate": 48000,
  "channels": 1,
  "format": "f32le",
  "seq": 153
}
```

А сам чанк лучше слать **binary frame** отдельно.

---

## Backend -> Frontend

### wake word найден

```json
{
  "type": "wake.detected"
}
```

### пользователь начал говорить

```json
{
  "type": "speech.started"
}
```

### пользователь закончил говорить

```json
{
  "type": "speech.ended"
}
```

### сервер думает

```json
{
  "type": "assistant.processing"
}
```

### распознанный текст

```json
{
  "type": "assistant.transcript",
  "text": "какая сегодня погода"
}
```

### ответ ассистента

```json
{
  "type": "assistant.text",
  "text": "Сегодня в Амстердаме..."
}
```

### аудиоответ

```json
{
  "type": "assistant.audio",
  "format": "wav"
}
```

### ошибка

```json
{
  "type": "error",
  "message": "connection lost"
}
```

---

# 7. Frontend: что именно реализовать

## `audio.ts`

Этот модуль:

* вызывает `getUserMedia`
* поднимает `AudioContext`
* подключает `AudioWorklet`
* получает чанки `Float32`
* отправляет их по WebSocket

### логика

```ts
class MicStreamer {
  async start() {}
  stop() {}
  onChunk(cb: (chunk: Float32Array) => void) {}
}
```

---

## `ws.ts`

Этот модуль:

* открывает WebSocket
* шлёт `session.start`
* шлёт аудиочанки
* слушает события сервера

### логика

```ts
class VoiceSocket {
  connect() {}
  sendAudioChunk(chunk: ArrayBuffer) {}
  onEvent(cb: (event: ServerEvent) => void) {}
}
```

---

## `player.ts`

Этот модуль:

* принимает audio blob / bytes
* проигрывает ответ
* уведомляет UI о конце playback

### логика

```ts
class AudioPlayer {
  play(blob: Blob): Promise<void> {}
  stop(): void {}
}
```

---

## `state.ts`

Хранит состояние экрана:

```ts
type UIState =
  | "idle"
  | "armed"
  | "recording"
  | "processing"
  | "speaking"
  | "error";
```

---

# 8. Backend: что именно реализовать

## `session.py`

Одна websocket-сессия = один робот.

Хранит:

* `device_id`
* текущее состояние
* ring buffer
* текущий utterance buffer
* флаги wake/speech
* seq аудиопотока

Примерно так:

```python
class VoiceSession:
    def __init__(self, device_id: str, websocket):
        self.device_id = device_id
        self.websocket = websocket
        self.state = "IDLE"
        self.pre_roll = []
        self.utterance = []
        self.silence_ms = 0
        self.speech_started = False
```

---

## `state_machine.py`

Главный управляющий модуль.

Он принимает события:

* новый аудиочанк
* wake word найден
* речь началась
* речь закончилась
* ответ сгенерирован
* playback завершён

И меняет состояние.

### состояния

```python
IDLE
ARMED
RECORDING
PROCESSING
SPEAKING
```

---

## `audio_buffer.py`

Нужны два буфера:

### 1. `pre_roll`

Хранит последние 300–500 ms аудио, чтобы не съесть начало фразы.

### 2. `utterance_buffer`

Хранит текущую пользовательскую реплику.

---

## `wakeword.py`

Содержит адаптер к wake-word детектору.

Интерфейс:

```python
class WakeWordDetector:
    def feed(self, pcm_chunk) -> bool:
        ...
```

---

## `vad.py`

Содержит адаптер к VAD.

Интерфейс:

```python
class VoiceActivityDetector:
    def is_speech(self, pcm_chunk) -> bool:
        ...
```

---

## `stt.py`

```python
class STTService:
    async def transcribe(self, pcm_bytes: bytes) -> str:
        ...
```

## `llm.py`

```python
class LLMService:
    async def generate(self, text: str, session_id: str) -> str:
        ...
```

## `tts.py`

```python
class TTSService:
    async def synthesize(self, text: str) -> bytes:
        ...
```

---

# 9. Главная логика state machine

Вот базовая логика, которую вам и надо реализовать.

## IDLE

* все входящие чанки идут в wake word detector
* параллельно держим небольшой pre-roll buffer
* если wake word найден:

  * `state = ARMED`
  * отправляем фронту `wake.detected`

## ARMED

* ждём начало речи по VAD
* если речь началась:

  * переносим pre-roll в utterance
  * `state = RECORDING`
  * отправляем `speech.started`
* если за N секунд команда не началась:

  * `state = IDLE`

## RECORDING

* все чанки складываем в utterance buffer
* если VAD говорит speech:

  * `silence_ms = 0`
* если тишина:

  * увеличиваем `silence_ms`
* если `silence_ms > threshold`:

  * завершаем utterance
  * `state = PROCESSING`
  * отправляем `speech.ended`

## PROCESSING

* делаем `STT -> LLM -> TTS`
* отправляем:

  * transcript
  * text
  * audio
* `state = SPEAKING`

## SPEAKING

* фронт играет звук
* после `playback.finished`

  * `state = IDLE`

---

# 10. Псевдокод backend-цикла

```python
async def handle_audio_chunk(session: VoiceSession, chunk: bytes):
    pcm = normalize_audio(chunk)  # при необходимости

    session.pre_roll.append(pcm)

    if session.state == "IDLE":
        if wakeword_detector.feed(pcm):
            session.state = "ARMED"
            await session.send({"type": "wake.detected"})
        return

    if session.state == "ARMED":
        if vad.is_speech(pcm):
            session.utterance.extend(session.pre_roll.get_all())
            session.utterance.append(pcm)
            session.state = "RECORDING"
            session.silence_ms = 0
            await session.send({"type": "speech.started"})
        return

    if session.state == "RECORDING":
        session.utterance.append(pcm)

        if vad.is_speech(pcm):
            session.silence_ms = 0
        else:
            session.silence_ms += 20

        if session.silence_ms >= 1500:
            session.state = "PROCESSING"
            await session.send({"type": "speech.ended"})
            await process_utterance(session)
```

---

# 11. Псевдокод обработки utterance

```python
async def process_utterance(session: VoiceSession):
    await session.send({"type": "assistant.processing"})

    audio_bytes = b"".join(session.utterance)
    session.utterance.clear()

    text = await stt_service.transcribe(audio_bytes)
    await session.send({
        "type": "assistant.transcript",
        "text": text
    })

    answer = await llm_service.generate(text, session.device_id)
    await session.send({
        "type": "assistant.text",
        "text": answer
    })

    tts_audio = await tts_service.synthesize(answer)
    await session.send_binary_audio(tts_audio)

    session.state = "SPEAKING"
```

---

# 12. Frontend: минимальная логика UI

Фронт тупо реагирует на события сервера:

* `wake.detected` → `armed`
* `speech.started` → `recording`
* `speech.ended` → `processing`
* `assistant.processing` → `processing`
* `assistant.text` → показать текст на экране
* `assistant.audio` → проиграть аудио, `state = speaking`
* после окончания проигрывания → отправить `playback.finished`

---

# 13. Что делать с экраном

Экран должен показывать простые статусы:

* `idle` → “Жду команду”
* `armed` → “Слушаю”
* `recording` → “Говорите”
* `processing` → “Думаю”
* `speaking` → “Отвечаю”
* `error` → “Ошибка связи”

Плюс можно отдельной строкой показывать:

* распознанную реплику
* текст ответа

---

# 14. Что делать в первой версии, а что не делать

## В первой версии делаем

* wake word
* VAD
* endpointing
* websocket stream
* STT
* LLM
* TTS
* playback
* UI статусы

## Пока не делаем

* full duplex
* barge-in
* локальный wake word в браузере
* AEC
* сложную анимацию
* multi-user logic
* тонкую оптимизацию аудиоформатов

---

# 15. Как разбить на этапы реализации

## Этап 1

Сделать фронт, который:

* открывает микрофон
* шлёт чанки на сервер
* принимает события

## Этап 2

Сделать сервер, который:

* принимает поток
* пока просто пишет чанки в файл
* подтверждает получение

## Этап 3

Добавить wake word и VAD на сервере

## Этап 4

Добавить сбор utterance

## Этап 5

Подключить STT/LLM/TTS

## Этап 6

Подключить playback и экран

---

# 16. Самое важное архитектурное решение

Не смешивайте всё в один websocket handler.

Сделайте 3 чётких слоя:

## transport

приём/отправка websocket сообщений

## session/state

логика состояний робота

## AI services

STT / LLM / TTS

Тогда систему реально можно поддерживать.
