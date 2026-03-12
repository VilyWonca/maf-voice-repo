Для команды из **3 человек** главное — разделить работу **не по файлам**, а по **слоям системы**, чтобы люди не блокировали друг друга.

У вас есть 3 естественных слоя:

1️⃣ **Device / Frontend (робот)**
2️⃣ **Voice backend (аудио + AI pipeline)**
3️⃣ **Infrastructure / Integration (сервер + протокол + стабильность)**

Так каждый человек владеет своим контуром.

---

# Рекомендуемое распределение

## 👤 Человек 1 — Device / Frontend (Raspberry Pi)

Отвечает за всё, что происходит **на самом роботе**.

### Основные задачи

* браузерное приложение
* микрофон
* WebAudio
* отправка аудиопотока
* получение ответа
* проигрывание звука
* UI на экране
* kiosk режим Chromium

### Что он пишет

Frontend:

```
frontend/
  App.tsx
  audio.ts
  ws.ts
  player.ts
  state.ts
  ui.tsx
```

### Его зона ответственности

* `getUserMedia`
* `AudioWorklet`
* отправка `audio.chunk`
* воспроизведение `assistant.audio`
* UI состояния

### Его KPI

робот:

* слышит
* отправляет звук
* получает ответ
* говорит
* показывает статусы

---

# 👤 Человек 2 — Voice / AI backend

Это **самая сложная часть**.

Он отвечает за **voice pipeline**.

### Основные задачи

* wake word
* VAD
* speech segmentation
* STT
* LLM orchestration
* TTS
* state machine

### Что он пишет

```
backend/
  wakeword.py
  vad.py
  state_machine.py
  stt.py
  llm.py
  tts.py
```

### Его зона ответственности

pipeline:

```
audio stream
 ↓
wake word
 ↓
VAD
 ↓
utterance segmentation
 ↓
STT
 ↓
LLM
 ↓
TTS
```

### Его KPI

робот:

* правильно ловит wake word
* не режет начало фразы
* правильно понимает конец речи
* даёт хороший ответ

---

# 👤 Человек 3 — Backend / Infra / Integration

Этот человек отвечает за **сервер и коммуникацию**.

Это glue-код всей системы.

### Основные задачи

* WebSocket server
* session management
* routing аудио
* протокол сообщений
* логирование
* масштабирование
* monitoring

### Что он пишет

```
backend/
  main.py
  ws_server.py
  session.py
  audio_buffer.py
  protocol.py
  config.py
```

### Его зона ответственности

```
browser
   ↓
WebSocket
   ↓
session manager
   ↓
voice pipeline
```

### Его KPI

* соединение стабильное
* нет потерь аудио
* корректные события
* сервер не падает

---

# Как эти роли взаимодействуют

```
           (1) Frontend
        Raspberry Pi browser
                │
                │ WebSocket
                ▼
        (3) Backend Gateway
                │
                ▼
        (2) Voice AI Pipeline
```

---

# Разбивка по этапам

## Этап 1 — Audio streaming

👤 Frontend

* getUserMedia
* AudioWorklet
* WebSocket streaming

👤 Backend

* WebSocket server
* принимать аудио

👤 Voice

* пока просто сохранять поток

Результат:
робот → сервер отправляет звук

---

## Этап 2 — Wake word

👤 Voice

* интеграция wake word

👤 Backend

* routing аудио

👤 Frontend

* UI событие wake detected

---

## Этап 3 — Speech detection

👤 Voice

* VAD
* endpointing

👤 Backend

* буферы аудио

👤 Frontend

* состояния `recording`

---

## Этап 4 — AI pipeline

👤 Voice

* STT
* LLM
* TTS

👤 Backend

* event routing

👤 Frontend

* проигрывание ответа

---

# Итоговые зоны

| Человек | Роль              | Основная зона                 |
| ------- | ----------------- | ----------------------------- |
| 1       | Device / Frontend | браузер на Raspberry Pi       |
| 2       | Voice / AI        | wake word, VAD, STT, LLM, TTS |
| 3       | Backend / Infra   | WebSocket, сессии, сервер     |

---

# Почему это хорошее разделение

Потому что:

* frontend не зависит от ML
* ML не зависит от UI
* backend glue не зависит от audio DSP

Все могут работать **параллельно**.

---

# Очень важный момент

Назначьте **одного человека system owner**.

Обычно это:

👉 человек №3 (backend/integration)

Он отвечает за:

* архитектуру
* протокол
* сборку всей системы
* деплой

Иначе маленькие команды часто разваливаются на несогласованных интерфейсах.

---

# Если сказать максимально просто

Для команды из **3 человек**:

👤 **Frontend / Device**
робот, браузер, микрофон, экран

👤 **Voice / AI**
wake word, VAD, STT, LLM, TTS

👤 **Backend / Infra**
сервер, websocket, сессии, протокол

---

Если хочешь, я могу дальше показать **реальный roadmap на 2 недели**, как такая команда из 3 человек собирает **первую рабочую версию голосового робота**.
