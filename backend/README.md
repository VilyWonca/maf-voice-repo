Backend voice gateway (MVP)
===========================

This service is a thin **WebSocket gateway** between the Raspberry Pi browser
client (`maf_speaker_client`) and the future voice pipeline (wake word, VAD,
STT, LLM, TTS).

For now it implements an **MVP protocol**:

- accepts `session.start` and binary audio frames from the frontend
- maintains a simple in‑memory session state
- sends back fake but well‑formed events:
  - `wake.detected`
  - `speech.started`
  - `speech.ended`
  - `assistant.processing`
  - `assistant.transcript`
  - `assistant.text`
  - `assistant.audio` + one binary audio frame
  - `error`
  - `debug.pong`

Stack
-----

- Python 3.10+
- `asyncio`
- [`websockets`](https://websockets.readthedocs.io/en/stable/) (low‑level WS server)

Quickstart
----------

1. Install dependencies (ideally in a virtualenv):

   ```bash
   pip install -r requirements.txt
   ```

2. Run the server from the project root:

   ```bash
   cd /home/harbi/Work/MAF
   python -m backend.main
   ```

3. Point the frontend to this server by setting:

   ```bash
   export NEXT_PUBLIC_WS_URL="ws://localhost:8080/ws/voice"
   ```

   Then run `maf_speaker_client` as usual.

Project layout
--------------

```text
backend/
  main.py          # Entry point, starts WS server
  ws_server.py     # WebSocket accept loop and per-connection handler
  session.py       # In-memory session object and simple state machine
  protocol.py      # JSON event types and binary audio frame codec
  config.py        # Ports, hosts, timing constants
```

Later we can add:

```text
  wakeword.py
  vad.py
  stt.py
  llm.py
  tts.py
  audio_buffer.py
```

