# Open WebUI on Wodby

What Wodby sets up for Open WebUI on this service. Open WebUI runs from the official `ghcr.io/open-webui/open-webui` image, unchanged. It is a chat interface: it runs no model itself and calls model APIs.

## Linked services

| Link | Variables |
| --- | --- |
| PostgreSQL (required) | `DATABASE_URL` |
| OpenAI-compatible API (optional), such as vLLM | `OPENAI_API_BASE_URL` (`http://<host>:<port>/v1`), `OPENAI_API_KEY` (the linked service's `api_key` token) |

## What the manifest sets

- `WEBUI_ADMIN_EMAIL` and `WEBUI_ADMIN_PASSWORD` come from the required admin settings. Open WebUI creates this administrator at startup only when the database has no users, then turns public sign-up off. Changing the settings later changes nothing; the password is changed in Open WebUI.
- `WEBUI_SECRET_KEY` is a generated token. It signs sign-in sessions; changing it signs everyone out.
- `WEBUI_URL` is the environment's primary URL.
- `CORS_ALLOW_ORIGIN` is built at container start from the routed hosts (`WODBY_HOSTS`), as `https://` and `http://` origins separated by `;`. Only those origins can open the WebSocket. Setting `CORS_ALLOW_ORIGIN` on the service replaces the computed list. Adding or removing a domain marks the service for redeploy.
- `ENABLE_OLLAMA_API` is `false`; there is no Ollama service.
- `DATA_DIR` is `/data`, the volume. The embedding, speech and tokenizer models stay where the image has them, so they are not downloaded at startup.
- `HOME` is `/data/home`. The container runs as user 2000 in group 0.
- Port 8080. `/health` is the liveness and startup check; `/ready` also checks the database.

## Configuration saved in the database

Open WebUI stores most settings in its database on the first start and then ignores the matching variables: `WEBUI_URL`, `ENABLE_OLLAMA_API`, `OPENAI_API_BASE_URL`, `OPENAI_API_KEY`, sign-up and others. They are changed in **Admin Panel → Settings** and survive redeploys. A model link added to an existing app therefore has no effect; add the connection in Open WebUI. `RESET_CONFIG_ON_START=true` makes Open WebUI read the variables again, but also discards every setting changed in the admin panel.

Variables that are not saved, such as `DATABASE_URL`, `WEBUI_SECRET_KEY` and `CORS_ALLOW_ORIGIN`, apply on every start.

## Data

| Place | Content |
| --- | --- |
| PostgreSQL | users, chats, settings, models, prompts, knowledge metadata |
| `/data/uploads` | uploaded files |
| `/data/vector_db` | document search index (embedded Chroma) |
| `/data/cache` | generated images, audio and other caches |

The manifest declares no backup, import or action for this service. Back up the database and the volume together. The service runs one replica; several would need pgvector, Redis and shared file storage.
