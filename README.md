# AccessMesh-AI

AccessMesh-AI is the service core of an accessibility-focused real-time communication platform built around Azure services. The current repository snapshot already contains the shared configuration layer, the message contract used by the pipeline, and a set of service wrappers for speech, translation, gesture recognition, summarization, telemetry, persistence, and real-time delivery.

At this stage, the repository is centered on backend service integration. The folders `backend/`, `frontend/`, `docs/`, and `infrastructure/` exist, but the implementation currently present in the workspace is concentrated in `services/` and `shared/`.

## Current Status

Implemented in this repository:

- Centralized application settings with `.env` support and Azure Key Vault integration.
- Message schemas for the accessibility pipeline.
- Azure Web PubSub integration for real-time delivery.
- Azure Speech token issuance and server-side audio transcription.
- Azure Translator text translation.
- Gesture recognition from labels, landmarks, and image frames.
- Azure OpenAI-based transcript summarization.
- Azure Cosmos DB persistence for sessions, messages, and users.
- Azure Service Bus transport wrapper for asynchronous messaging.
- Azure Content Safety text moderation.
- Azure Application Insights telemetry integration.
- Azure Neural TTS audio synthesis with viseme generation for avatar lip-sync.

Partially implemented or intentionally left as future work:

- Backend API layer and route handlers.
- Frontend application.
- Infrastructure-as-code definitions.
- 3D sign-language avatar synthesis.
- Full orchestration layer connecting all services into a running end-to-end app.

## Repository Structure

```text
AccessMesh-AI/
|-- README.md
|-- requirements.txt
|-- backend/                # Reserved for API/backend runtime code
|-- docs/                   # Project documentation
|-- frontend/               # Reserved for frontend runtime code
|-- infrastructure/         # Reserved for IaC and deployment artifacts
|-- services/               # Implemented service wrappers and Azure integrations
|-- shared/                 # Shared configuration and message contracts
```

## Implemented Modules

### Shared Layer

- `shared/config.py`
	- Centralizes runtime settings.
	- Supports `.env` loading.
	- Supports Azure Key Vault secret resolution through a custom Pydantic settings source.
	- Declares settings for Web PubSub, Speech, OpenAI, Cosmos DB, Content Safety, Translator, Service Bus, Application Insights, JWT, and CORS.

- `shared/message_schema.py`
	- Defines the system-wide message contract.
	- Includes message types such as `audio_chunk`, `transcription`, `gesture`, `translated`, `accessible`, `avatar_ready`, `summary`, `system`, and `error`.
	- Provides Pydantic models for validation and serialization.

### Service Layer

- `services/webpubsub_service.py`
	- Creates Azure Web PubSub client instances.
	- Generates client access tokens.
	- Sends events to all clients, a group, or a specific user.
	- Adds and removes users from groups.
	- Exposes a simple connection health check.

- `services/speech_service.py`
	- Issues Speech tokens for client-side use.
	- Performs server-side audio transcription from raw bytes.

- `services/translator_service.py`
	- Sends text to Azure Translator.
	- Supports source-language auto-detection and target-language translation.

- `services/gesture_service.py`
	- Converts gesture labels into readable text.
	- Recognizes gestures from hand landmarks using rule-based classification.
	- Recognizes gestures from image frames using Azure OpenAI vision/chat completions.

- `services/summarization_service.py`
	- Summarizes transcript collections using Azure OpenAI.
	- Returns summary text and key bullet points.
	- Offers both async and sync variants.

- `services/avatar_service.py`
	- Uses Azure Speech Neural TTS.
	- Returns audio as base64 MP3 plus viseme timing events for avatar lip-sync.
	- Includes a placeholder for future sign-language avatar synthesis.

- `services/cosmos_service.py`
	- Initializes Azure Cosmos DB database and containers.
	- Stores and retrieves sessions, messages, and users.
	- Supports async persistence operations.

- `services/servicebus_service.py`
	- Wraps Azure Service Bus topic publishing.
	- Creates receivers for topic subscriptions.
	- Acts as transport infrastructure for eventual agent orchestration.

- `services/content_safety_service.py`
	- Uses Azure Content Safety to analyze text.
	- Blocks content according to a configurable severity threshold.

- `services/telemetry_service.py`
	- Configures Azure Monitor / Application Insights.
	- Tracks spans for agent execution.
	- Records custom telemetry events.

- `services/keyvault_service.py`
	- Reads and writes secrets from Azure Key Vault.
	- Uses `DefaultAzureCredential`.
	- Supports cached service instances.

## How the Intended Pipeline Works

Although the orchestration layer is not yet present in this workspace, the implemented services clearly indicate the intended flow:

1. A participant sends audio, gesture, or text input.
2. Input is normalized into the message models from `shared/message_schema.py`.
3. Speech and gesture services transform raw input into text.
4. Content Safety can validate text before downstream use.
5. Translation and accessibility-oriented processing produce audience-specific outputs.
6. Avatar/TTS generation can create voice output with viseme data.
7. Messages are persisted in Cosmos DB.
8. Real-time updates are broadcast through Azure Web PubSub.
9. Background or decoupled processing can flow through Azure Service Bus.
10. Telemetry spans and events are captured in Application Insights.

## Configuration Overview

Configuration is centralized in `shared/config.py` and currently covers:

- Runtime settings: host, port, debug, reload.
- Security: JWT algorithm, expiration, signing secret, CORS origins.
- Azure Web PubSub.
- Azure Speech.
- Azure OpenAI for summarization and gesture recognition.
- Avatar/TTS settings.
- Azure Cosmos DB.
- Azure Content Safety.
- Azure Translator.
- Azure Service Bus.
- Azure Application Insights.
- Azure Key Vault.

Secrets may come from either:

- Environment variables and `.env`.
- Azure Key Vault via `AZURE_KEYVAULT_URL` and the custom settings source.

## Dependencies

The current dependency set in `requirements.txt` confirms that the repository is prepared for:

- FastAPI and Uvicorn.
- Authentication with JWT.
- Azure SDK integrations for Web PubSub, Service Bus, Cosmos DB, Speech, Content Safety, Translator, Key Vault, Identity, and Monitor.
- Pydantic and pydantic-settings.
- HTTP clients and multipart handling.

## Documentation

- `docs/architecture.md`: architectural view of the current implementation.
- `docs/implementation-status.md`: detailed inventory of what is implemented, partial, or pending.

## Local Setup Notes

1. Create a Python virtual environment.
2. Install dependencies from `requirements.txt`.
3. Provide the required Azure credentials through `.env` or Key Vault.
4. Instantiate the services from the modules in `services/` from your API layer or worker runtime.

Example installation:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Recommended Next Steps

1. Add the backend API layer that exposes these services through FastAPI endpoints.
2. Implement the orchestration layer that consumes and emits `shared.message_schema` models.
3. Add a frontend that connects through Azure Web PubSub.
4. Add infrastructure definitions under `infrastructure/`.
5. Document environment variables in a dedicated `.env.example` file.
