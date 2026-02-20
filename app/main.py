from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from .config import settings
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from starlette.staticfiles import StaticFiles as StarletteStaticFiles

from .api_reference import build_api_reference_html, build_api_reference_data
from .docs_agent import (
    agent_chat,
    generate_example,
    generate_overview_summary,
    get_operation,
    STACKS,
)

app = FastAPI(title="My API", version="1.0.0")

# Path to frontend static export (only used when directory exists, e.g. after build)
FRONTEND_OUT = (Path(__file__).resolve().parent.parent / "frontend" / "out")

# Allow frontend hosted elsewhere to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENAPI_FETCH_TIMEOUT = 10.0

# When user provides a base URL, try these paths in order to discover the spec.
# Order: JSON first, then docs endpoints (content-negotiated), then YAML, then versioned/other.
SPEC_URL_SUFFIXES = [
    "/openapi.json",
    "/swagger.json",
    "/api-docs",
    "/docs",
    "/docs/",
    "/openapi.yaml",
    "/openapi.yml",
    "/swagger.yaml",
    "/swagger.yml",
    "/v3/api-docs",
    "/v1/openapi.json",
    "/api-docs.json",
    "/.well-known/openapi.json",
]

# Accept header: prefer JSON, allow YAML for content negotiation
OPENAPI_ACCEPT = (
    "application/json, application/vnd.oai.openapi+json, "
    "application/yaml, application/vnd.oai.openapi, text/yaml, */*"
)


def custom_openapi():
    if app.openapi_schema is None:
        app.openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            routes=app.routes,
        )
    return app.openapi_schema


def _origin_from_url(url: str) -> str:
    # Return scheme + netloc for allowlist checks (e.g. https://api.example.com).
    parsed = urlparse(url.strip().rstrip("/"))
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _check_allowed_origin(openapi_url: str) -> None:
    # Raise 403 if ALLOWED_OPENAPI_ORIGINS is set and openapi_url's origin is not in the list.
    if not settings.allowed_openapi_origins:
        return
    origin = _origin_from_url(openapi_url)
    if not origin:
        raise HTTPException(400, detail="openapi_url must be a valid http or https URL")
    allowed = [o.rstrip("/") for o in settings.allowed_openapi_origins]
    origin_normalized = origin.rstrip("/")
    if origin_normalized not in allowed:
        raise HTTPException(
            403,
            detail="This API docs instance is restricted to specific APIs. The given URL is not allowed.",
        )


def _fetch_external_openapi(openapi_url: str) -> dict:
    # Fetch OpenAPI/Swagger spec from a URL. Tries multiple common paths when given a base URL.
    _check_allowed_origin(openapi_url)
    parsed = urlparse(openapi_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, detail="openapi_url must be http or https")

    url = openapi_url.strip().rstrip("/")
    parsed = urlparse(url)
    path = (parsed.path or "").rstrip("/")
    path_lower = path.lower()

    # Direct spec URL: use as single candidate
    if url.lower().endswith(".json"):
        candidates = [url]
    elif url.lower().endswith((".yaml", ".yml")):
        candidates = [url]
    elif path_lower.endswith("/docs") or path_lower.endswith("/openapi") or path_lower.endswith("/api-docs"):
        # User gave exact docs/spec path (e.g. .../docs or .../docs/)
        candidates = [url]
    else:
        # Base URL: try common spec locations
        candidates = [url + suffix for suffix in SPEC_URL_SUFFIXES]

    last_error: str | None = None
    headers = {"Accept": OPENAPI_ACCEPT}
    for spec_url in candidates:
        try:
            with httpx.Client(timeout=OPENAPI_FETCH_TIMEOUT) as client:
                r = client.get(spec_url, headers=headers)
                r.raise_for_status()
                content_type = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
                # Prefer JSON when Content-Type indicates it
                if "json" in content_type or content_type in ("*/*", ""):
                    try:
                        data = r.json()
                    except Exception:
                        data = yaml.safe_load(r.text)
                elif "yaml" in content_type or spec_url.lower().endswith((".yaml", ".yml")):
                    data = yaml.safe_load(r.text)
                else:
                    # Fallback: try JSON first, then YAML
                    try:
                        data = r.json()
                    except Exception:
                        data = yaml.safe_load(r.text)
        except httpx.HTTPStatusError as e:
            last_error = f"Could not fetch spec: {e.response.status_code} from {spec_url}"
            continue
        except httpx.RequestError as e:
            last_error = f"Could not fetch spec (check URL and network): {e!s}"
            continue
        except Exception as e:
            last_error = f"Invalid response from {spec_url}: {e!s}"
            continue

        if not isinstance(data, dict):
            last_error = f"Response from {spec_url} is not a valid object"
            continue
        if "paths" not in data:
            raise HTTPException(
                502,
                detail="Fetched URL but it is not a valid OpenAPI/Swagger document (missing 'paths').",
            )
        if "openapi" not in data and "swagger" not in data:
            raise HTTPException(
                502,
                detail="Fetched URL but it is not a valid OpenAPI/Swagger document (missing 'openapi' or 'swagger' field).",
            )
        return data

    raise HTTPException(502, detail=last_error or "Failed to fetch OpenAPI spec from any tried URL.")


def _base_url_from_openapi_url(openapi_url: str) -> str:
    # Return base URL from openapi_url, stripping common spec paths/segments.
    parsed = urlparse(openapi_url.strip().rstrip("/"))
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    path_lower = path.lower()
    # Strip trailing spec filename or docs segment
    spec_endings = (
        "openapi.json", "swagger.json", "openapi.yaml", "swagger.yaml",
        "openapi.yml", "swagger.yml", "api-docs.json",
    )
    if path_lower.endswith("/api-docs") or path_lower.endswith("/docs") or path_lower.endswith("/openapi"):
        path = path.rsplit("/", 1)[0] or ""
    elif any(path_lower.endswith(ending) for ending in spec_endings):
        path = path.rsplit("/", 1)[0] or ""
    elif path_lower.endswith(".json") or path_lower.endswith(".yaml") or path_lower.endswith(".yml"):
        path = path.rsplit("/", 1)[0] or ""
    return f"{parsed.scheme}://{parsed.netloc}{path}" if path else f"{parsed.scheme}://{parsed.netloc}"


@app.get("/api/agent-docs")
def api_agent_docs_json(
    request: Request,
    openapi_url: str | None = Query(None, description="External API base URL or direct OpenAPI/Swagger JSON URL"),
):
    # Structured docs payload for the docs UI. No params = this app's OpenAPI (or DEFAULT_OPENAPI_URL if set); openapi_url = fetch that API's spec.
    effective_url = openapi_url or settings.default_openapi_url
    if effective_url:
        schema = _fetch_external_openapi(effective_url)
        base_url = _base_url_from_openapi_url(effective_url)
    else:
        schema = custom_openapi()
        base_url = str(request.base_url).rstrip("/")
    data = build_api_reference_data(schema, base_url=base_url)
    overview = generate_overview_summary(schema, settings.openai_api_key)
    if overview:
        data["overview_summary"] = overview
    return data


@app.get("/health")
def health():
    # Health check for load balancers and platforms.
    return {"status": "ok"}


@app.get("/docs", response_class=HTMLResponse)
def api_reference_page(request: Request):
    # Server-rendered API reference for this app's OpenAPI (legacy/alternate docs).
    schema = custom_openapi()
    base_url = str(request.base_url).rstrip("/")
    return build_api_reference_html(schema, base_url=base_url)


class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str = Field("", description="Message content")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., description="Conversation history")
    openapi_url: str | None = Field(None, description="When set, use this API's OpenAPI (external API)")
    context_tag_names: list[str] | None = Field(None, description="Optional list of API tag names to limit chat context to those modules")


class GenerateExampleRequest(BaseModel):
    path: str = Field(..., description="API path")
    method: str = Field(..., description="GET, POST, etc.")
    stack: str = Field(..., description="e.g. react-fetch, vue3, flutter")
    base_url: str | None = None
    openapi_url: str | None = Field(None, description="When set, use this API's OpenAPI for the operation (external API)")

@app.post("/api/agent/chat")
def api_agent_chat(request: Request, body: ChatRequest):
    # Chat with the API docs agent. Option A: context-only. Option B: with tool-calling.
    effective_url = body.openapi_url or settings.default_openapi_url
    if effective_url:
        schema = _fetch_external_openapi(effective_url)
        base_url = _base_url_from_openapi_url(effective_url)
    else:
        schema = custom_openapi()
        base_url = str(request.base_url).rstrip("/")
    messages = [{"role": m.role, "content": m.content or ""} for m in body.messages]
    reply = agent_chat(
        messages=messages,
        openapi_schema=schema,
        base_url=base_url,
        openai_api_key=settings.openai_api_key,
        use_tools=True,
        context_tag_names=body.context_tag_names,
    )
    return {"message": reply}


@app.post("/api-reference/generate-example")
def api_reference_generate_example(request: Request, body: GenerateExampleRequest):
    effective_url = body.openapi_url or settings.default_openapi_url
    if effective_url:
        schema = _fetch_external_openapi(effective_url)
        base_url = (body.base_url or _base_url_from_openapi_url(effective_url)).rstrip("/")
    else:
        schema = custom_openapi()
        base_url = (body.base_url or str(request.base_url)).rstrip("/")
    method = (body.method or "get").upper()
    allowed = {s[0] for s in STACKS}
    if body.stack not in allowed:
        raise HTTPException(400, detail=f"stack must be one of: {', '.join(sorted(allowed))}")
    op = get_operation(schema, body.path, method)
    if not op:
        raise HTTPException(404, detail=f"Operation {method} {body.path} not found in schema")
    code = generate_example(
        method=method,
        path=body.path,
        stack=body.stack,
        operation=op,
        base_url=base_url,
        openai_api_key=settings.openai_api_key,
    )
    return {"code": code}


class TryItOutRequest(BaseModel):
    url: str = Field(..., description="Full URL to call")
    method: str = Field(..., description="HTTP method")
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = Field(None, description="Raw request body string")
    openapi_url: str | None = Field(None, description="For origin validation")


TRY_IT_OUT_TIMEOUT = 30.0
TRY_IT_OUT_MAX_BODY = 2 * 1024 * 1024  # 2 MB cap on response body


@app.post("/api/try-it-out")
def api_try_it_out(body: TryItOutRequest):
    import time

    target_url = body.url.strip()
    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, detail="URL must be http or https")

    if body.openapi_url and settings.allowed_openapi_origins:
        _check_allowed_origin(body.openapi_url)
        allowed_origin = _origin_from_url(body.openapi_url)
        target_origin = _origin_from_url(target_url)
        if allowed_origin and target_origin and target_origin.rstrip("/") != allowed_origin.rstrip("/"):
            raise HTTPException(403, detail="Target URL origin does not match the documented API")

    method = (body.method or "GET").upper()
    req_headers = {k: v for k, v in body.headers.items() if k.lower() not in ("host", "content-length")}
    content = body.body.encode("utf-8") if body.body else None

    try:
        start = time.monotonic()
        with httpx.Client(timeout=TRY_IT_OUT_TIMEOUT, follow_redirects=True) as client:
            resp = client.request(method, target_url, headers=req_headers, content=content)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    except httpx.RequestError as e:
        raise HTTPException(502, detail=f"Request failed: {e!s}")

    resp_body = resp.text[:TRY_IT_OUT_MAX_BODY]
    resp_headers = {k: v for k, v in resp.headers.items()}

    return {
        "status_code": resp.status_code,
        "headers": resp_headers,
        "body": resp_body,
        "elapsed_ms": elapsed_ms,
    }


# --- Serve frontend static export at / (with SPA fallback) ---


def _make_static_with_spa_fallback(directory: Path):
    # ASGI app that serves static files and falls back to index.html for SPA client routes.
    static = StarletteStaticFiles(directory=str(directory), html=True)
    index_path = directory / "index.html"

    async def app(scope, receive, send):
        if scope["type"] != "http":
            await static(scope, receive, send)
            return
        got_404 = []

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and message.get("status") == 404:
                got_404.append(True)
                return  # Don't send 404 yet
            if message["type"] == "http.response.body" and got_404:
                return  # Drop 404 body
            await send(message)

        await static(scope, receive, send_wrapper)
        if got_404 and index_path.is_file():
            body = index_path.read_bytes()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"text/html; charset=utf-8"]],
                }
            )
            await send({"type": "http.response.body", "body": body})
    return app


if FRONTEND_OUT.is_dir():
    # Serve frontend at / (root). Redirect old /agent-docs links to /
    @app.get("/agent-docs", include_in_schema=False)
    def redirect_agent_docs():
        return RedirectResponse(url="/", status_code=302)

    @app.get("/agent-docs/", include_in_schema=False)
    def redirect_agent_docs_slash():
        return RedirectResponse(url="/", status_code=302)

    app.mount(
        "/",
        _make_static_with_spa_fallback(FRONTEND_OUT),
        name="frontend",
    )