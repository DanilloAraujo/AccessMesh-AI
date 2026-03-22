# AccessMesh-AI

AccessMesh-AI is a real-time accessible communication platform built around a multimodal pipeline:
text, speech, and gestures all converge into the same backend hub, are processed by an agent mesh,
and are redistributed with accessibility enrichments such as subtitles, sign-language gloss output,
translation, and text-to-speech audio.

## What The Solution Does

- Authenticates users with JWT and stores profile/preferences.
- Lets each participant choose a preferred communication mode: `text`, `voice`, or `sign_language`.
- Creates shared meeting rooms identified by a room id.
- Accepts multimodal input from the browser:
  - typed text
  - speech captured from microphone
  - hand gestures detected from camera
- Routes every input through the same AI pipeline.
- Broadcasts enriched output in real time to the meeting room.
- Persists users, sessions, and message history in Cosmos DB when configured.
- Generates meeting summaries on demand.

## Current Architecture

### Frontend

The frontend is a React + Vite application located in `frontend/`.

Main responsibilities:

- authentication and protected navigation
- room creation/join flow
- meeting UI for text, voice, and sign-language modes
- Web PubSub WebSocket connection management
- local gesture capture with MediaPipe
- speech capture with browser APIs and backend fallback

Important files:

- `frontend/src/App.tsx`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/context/MeetingContext.tsx`
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/MeetingRoom.tsx`
- `frontend/src/services/websocketService.ts`
- `frontend/src/hooks/useSpeechRecognition.ts`
- `frontend/src/components/GestureCamera.tsx`

### Backend

The backend is a FastAPI application located in `backend/`.
The app is created in `backend/app/factory.py` and exposed by `backend/main.py`.

Main responsibilities:

- JWT authentication and preference updates
- REST endpoints for chat, speech, hub, auth, and pubsub token issuance
- message routing and content safety screening
- orchestration of the agent mesh
- real-time dispatch via Azure Web PubSub
- persistence via Cosmos DB
- optional telemetry via Application Insights

Important files:

- `backend/main.py`
- `backend/app/factory.py`
- `backend/app/message_router.py`
- `backend/app/routes/auth_routes.py`
- `backend/app/routes/chat_routes.py`
- `backend/app/routes/speech_routes.py`
- `backend/app/routes/hub_routes.py`
- `backend/app/routes/pubsub_routes.py`

### Agent Mesh

The core processing pipeline is event-driven.
Instead of directly chaining services, the system publishes typed messages into an async bus and lets
specialized agents subscribe to the stages they care about.

Flow:

1. input arrives as text, speech, or gesture
2. `MessageRouter` screens it and creates a pipeline request
3. `AgentMeshPipeline` publishes a `TRANSCRIPTION` event
4. `RouterAgent` decides which downstream agents should act
5. `AccessibilityAgent` generates accessibility metadata and TTS audio
6. `TranslationAgent` adapts the message for sign language and translates when needed
7. `AvatarAgent` generates the final gloss sequence for sign rendering
8. `SummaryAgent` passively accumulates final messages for later summarization

Important files:

- `agents/agent_bus.py`
- `agents/pipeline.py`
- `agents/router_agent.py`
- `agents/accessibility_agent.py`
- `agents/translation_agent.py`
- `agents/avatar_agent.py`
- `agents/summary_agent.py`
- `shared/message_schema.py`

### MCP Layer

Agents call tools through an MCP-style abstraction.
By default, tools run in-process, but the client can also target an external MCP HTTP server.

Registered tools:

- `speech_to_text_tool`
- `gesture_recognition_tool`
- `text_to_sign_tool`
- `text_to_speech_tool`
- `meeting_summary_tool`
- `llm_classify_tool`
- `text_translation_tool`

Important files:

- `mcp/mcp_server.py`
- `mcp/mcp_client.py`
- `mcp/tool_registry.py`
- `mcp/tool_executor.py`
- `mcp/tools/`

## Realtime Delivery Model

Realtime delivery is split into two parts:

- the frontend obtains a room-scoped Web PubSub client URL from `POST /pubsub/token`
- the frontend opens a WebSocket, joins the room group, and receives message broadcasts

The backend also returns enriched payloads immediately to the sender so the UI can update optimistically.
History is reloaded from Cosmos DB or in-memory fallback when a participant joins late.

## Input Flows

### Text

The frontend posts text to `POST /chat/send`.
The backend runs the full agent pipeline and returns/broadcasts an enriched message containing:

- original text
- applied accessibility features
- optional sign gloss sequence
- optional translated text
- optional TTS audio

### Speech

Speech currently supports two browser-side capture paths:

- preferred path: native browser `SpeechRecognition`, then send text to `POST /speech/voice`
- fallback path: `MediaRecorder`, upload audio to `POST /speech/recognize`

The backend can transcribe through the MCP speech tool and then process the text through the same agent mesh.

### Gesture

Gesture input is detected locally in the browser with MediaPipe hand landmarks.
The client can also use AI fallback flows to send landmarks or frames to the backend.
The unified gesture path is posted through `POST /hub/message` with `input_type=gesture`.

## Persistence

When Azure Cosmos DB is configured, the backend stores:

- users
- sessions
- message history

When Cosmos DB is not configured, the app still runs, but persistence falls back to in-memory storage for
message history and disabled persistence for users/sessions where applicable.

## Azure Services Used

The system is designed to run with optional Azure integrations:

- Azure Web PubSub
- Azure Service Bus
- Azure Speech
- Azure Cosmos DB
- Azure AI Translator
- Azure Content Safety
- Azure Application Insights
- Azure Key Vault for configuration lookup

Most integrations are optional in local development.
If a service is not configured, the app typically degrades gracefully rather than failing startup.

## Configuration

Configuration is centralized in `shared/config.py`.
Settings are loaded in this order:

1. constructor args
2. Azure Key Vault secrets, when `AZURE_KEYVAULT_URL` is set
3. OS environment variables
4. `.env`

Common variables:

- `APP_HOST`
- `APP_PORT`
- `APP_RELOAD`
- `SECRET_KEY`
- `WEBPUBSUB_CONNECTION_STRING`
- `WEBPUBSUB_HUB_NAME`
- `SERVICEBUS_CONNECTION_STRING`
- `SERVICEBUS_TOPIC_NAME`
- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`
- `COSMOS_ENDPOINT`
- `COSMOS_KEY`
- `TRANSLATOR_KEY`
- `CONTENT_SAFETY_ENDPOINT`
- `CONTENT_SAFETY_KEY`
- `APPINSIGHTS_CONNECTION_STRING`
- `MCP_SERVER_URL`
- `MCP_API_KEY`
- `AZURE_KEYVAULT_URL`

## Local Development

### Backend

Create a virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

Run the backend:

```bash
python -m backend.main
```

Default backend URL:

```text
http://localhost:8000
```

### Frontend

Install dependencies:

```bash
cd frontend
npm install
```

Run the dev server:

```bash
npm run dev
```

Default frontend URL:

```text
http://localhost:5173
```

If needed, point the frontend to a different backend with:

```text
VITE_API_URL=http://localhost:8000
```

## Key API Endpoints

Auth:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`
- `PUT /auth/me/preferences`

Realtime:

- `POST /pubsub/token`

Multimodal messaging:

- `POST /chat/send`
- `GET /chat/history/{session_id}`
- `GET /chat/summary/{session_id}`
- `POST /speech/voice`
- `POST /speech/recognize`
- `GET /speech/token`
- `POST /speech/transcribe`
- `POST /hub/message`

Health and docs:

- `GET /`
- `GET /health`
- `GET /docs`
- `GET /redoc`

MCP:

- `GET /mcp/health`
- `GET /mcp/tools/list`
- `POST /mcp/tools/call`

## Current Constraints

- The repo currently has very little top-level product documentation outside this README.
- Frontend tests exist but are limited.
- Some external integrations depend on Azure credentials and will run in stub or degraded mode locally.
- The system supports graceful fallback paths, but production readiness still depends on correctly provisioning Azure services.

## Status

For a more explicit implementation snapshot, see:

- `docs/implementation-status.md`
