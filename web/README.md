# Frontend (docs UI)

This folder can hold your Next.js app or a Lovable-built UI. Types for the API are in **`src/types/api-docs.ts`**.

## API base URL – do not use `/agent-docs`

- **`base_url`** in the API response (and what you send to `POST /api-reference/generate-example`) is the **API server root**, e.g. `https://your-api.com` or `http://localhost:8000`.
- **Do not** prefix it with `/agent-docs`. The path `/agent-docs` is only where the **docs UI** is served (the static frontend). The API routes live at the root of the same server:
  - `GET /api/agent-docs` – docs payload
  - `POST /api-reference/generate-example` – code generation
- So when calling the API from your frontend, use:
  - **Same origin:** `fetch('/api/agent-docs')` or `fetch(\`${origin}/api/agent-docs\`)`(no`/agent-docs` in the path).
  - **Configurable backend:** `fetch(\`${API_BASE_URL}/api/agent-docs\`)`where`API_BASE_URL`is e.g.`https://your-api.com` (no trailing `/agent-docs`).

If your UI is built with `basePath: '/agent-docs'` (Next.js), that only affects **asset and route paths** for the app itself; it does **not** change the backend API base URL.
