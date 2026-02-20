from __future__ import annotations

import json
import logging
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

STACKS = [
    # Web
    ("react-fetch", "React + fetch"),
    ("react-axios", "React + axios"),
    ("vue3", "Vue 3"),
    ("nextjs", "Next.js"),
    ("angular", "Angular"),
    ("svelte", "Svelte"),
    ("vanilla", "Vanilla JS"),
    # Mobile
    ("react-native", "React Native"),
    ("flutter", "Flutter"),
    ("swift-ios", "Swift (iOS)"),
    ("kotlin-android", "Kotlin (Android)"),
]


def _has_auth(op: dict) -> bool:
    # OpenAPI security is keyed by scheme name (e.g. {"bearerAuth": []}); check keys.
    sec = op.get("security") or []
    for s in sec:
        if not isinstance(s, dict):
            continue
        for key in s.keys():
            k = str(key).lower()
            if "bearer" in k or "jwt" in k or "oauth" in k or "token" in k:
                return True
    return False


def _get_body_summary(op: dict) -> str:
    body = op.get("requestBody") or {}
    content = body.get("content") or {}
    schema = content.get("application/json", {}).get("schema") or content.get("application/json; charset=utf-8", {}).get("schema")
    if not schema:
        return ""
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    if ref:
        return ref.split("/")[-1]
    props = schema.get("properties") or {} if isinstance(schema, dict) else {}
    return ", ".join(props.keys()) if props else "body"


def _extract_operation_details(op: dict) -> dict:
    """Parse an OpenAPI operation into structured details with example values."""
    from .api_reference import _example_value_for_field, _generate_example_json, _resolve_schema, _schema_type_str

    params = op.get("parameters") or []
    path_params: list[dict[str, Any]] = []
    query_params: list[dict[str, Any]] = []
    header_params: list[dict[str, Any]] = []

    for p in params:
        p_schema = p.get("schema") or {}
        p_type = _schema_type_str(p_schema) if isinstance(p_schema, dict) else "string"
        p_name = p.get("name", "")
        example = _example_value_for_field(p_name, p_type, p_schema if isinstance(p_schema, dict) else None)
        entry = {"name": p_name, "type": p_type, "required": bool(p.get("required")), "example": example}
        loc = p.get("in", "query")
        if loc == "path":
            path_params.append(entry)
        elif loc == "query":
            query_params.append(entry)
        elif loc == "header":
            header_params.append(entry)

    body_fields: list[dict[str, Any]] = []
    example_body: dict[str, Any] | None = None
    req_body = op.get("requestBody") or {}
    content = req_body.get("content") or {}
    schema = None
    for mt in ("application/json", "application/json; charset=utf-8"):
        ms = content.get(mt)
        if isinstance(ms, dict) and ms.get("schema"):
            schema = ms["schema"]
            break
    if schema:
        resolved = _resolve_schema(schema, {}) or schema
        if isinstance(resolved, dict):
            for prop_name, prop_schema in (resolved.get("properties") or {}).items():
                if not isinstance(prop_schema, dict):
                    continue
                prop_type = _schema_type_str(prop_schema)
                example = _example_value_for_field(prop_name, prop_type, prop_schema)
                required_set = set(resolved.get("required") or [])
                body_fields.append({
                    "name": prop_name, "type": prop_type,
                    "required": prop_name in required_set, "example": example,
                })
        example_body = _generate_example_json(schema, {})
        if not isinstance(example_body, dict):
            example_body = None

    return {
        "path_params": path_params,
        "query_params": query_params,
        "header_params": header_params,
        "body_fields": body_fields,
        "example_body": example_body,
    }


def _build_url(base_url: str, path: str, details: dict) -> str:
    """Build URL with path param replacements and query string."""
    url = f"{base_url.rstrip('/')}{path}"
    for p in details["path_params"]:
        url = url.replace("{" + p["name"] + "}", str(p["example"]))
    if details["query_params"]:
        qs = "&".join(f"{p['name']}={p['example']}" for p in details["query_params"])
        url += f"?{qs}"
    return url


def _js_body_literal(details: dict) -> str:
    """Return a JS object literal string from example_body or body_fields."""
    if details["example_body"]:
        return json.dumps(details["example_body"], indent=2)
    if details["body_fields"]:
        obj = {f["name"]: f["example"] for f in details["body_fields"]}
        return json.dumps(obj, indent=2)
    return "{}"


def _dart_body_literal(details: dict) -> str:
    """Return a Dart map literal string from example_body."""
    body = details.get("example_body") or {f["name"]: f["example"] for f in details.get("body_fields", [])}
    if not body:
        return "{}"
    pairs = []
    for k, v in body.items():
        if isinstance(v, str):
            pairs.append(f"  '{k}': '{v}'")
        elif isinstance(v, bool):
            pairs.append(f"  '{k}': {'true' if v else 'false'}")
        else:
            pairs.append(f"  '{k}': {v}")
    return "{\n" + ",\n".join(pairs) + "\n}"


def _swift_body_literal(details: dict) -> str:
    """Return a Swift dictionary literal from example_body."""
    body = details.get("example_body") or {f["name"]: f["example"] for f in details.get("body_fields", [])}
    if not body:
        return "[:]"
    pairs = []
    for k, v in body.items():
        if isinstance(v, str):
            pairs.append(f'    "{k}": "{v}"')
        elif isinstance(v, bool):
            pairs.append(f'    "{k}": {"true" if v else "false"}')
        else:
            pairs.append(f'    "{k}": {v}')
    return "[\n" + ",\n".join(pairs) + "\n  ]"


def _kotlin_body_literal(details: dict) -> str:
    """Return a Kotlin JSONObject builder from example_body."""
    body = details.get("example_body") or {f["name"]: f["example"] for f in details.get("body_fields", [])}
    if not body:
        return 'JSONObject()'
    pairs = []
    for k, v in body.items():
        if isinstance(v, str):
            pairs.append(f'    .put("{k}", "{v}")')
        elif isinstance(v, bool):
            pairs.append(f'    .put("{k}", {"true" if v else "false"})')
        else:
            pairs.append(f'    .put("{k}", {v})')
    return "JSONObject()\n" + "\n".join(pairs)


def _template_example(
    method: str,
    path: str,
    stack: str,
    needs_auth: bool,
    body_summary: str,
    base_url: str,
    operation: dict | None = None,
) -> str:
    """Generate a deterministic code example without AI, using actual schema data."""
    details = _extract_operation_details(operation or {})
    url = _build_url(base_url, path, details)
    method_upper = method.upper()
    has_body = method_upper in ("POST", "PUT", "PATCH") and (details["body_fields"] or details["example_body"] or body_summary)
    body_json = _js_body_literal(details) if has_body else ""

    if stack == "vanilla":
        headers = []
        if needs_auth:
            headers.append('    "Authorization": "Bearer " + token,')
        if has_body:
            headers.append('    "Content-Type": "application/json",')
        headers_str = "\n".join(headers) if headers else ""
        body_line = f"\n  body: JSON.stringify({body_json})," if has_body else ""
        mid = ""
        if headers or has_body:
            mid = "\n  headers: {\n" + headers_str + "\n  }," + body_line
        return (
            f'const token = "YOUR_JWT_TOKEN";\n'
            f'const url = "{url}";\n\n'
            "fetch(url, {\n"
            f'  method: "{method_upper}",{mid}\n'
            "})\n"
            "  .then((res) => res.json())\n"
            "  .then((data) => console.log(data))\n"
            "  .catch((err) => console.error(err));"
        )

    if stack == "react-fetch":
        body_line = f"\n  body: JSON.stringify({body_json})," if has_body else ""
        auth_headers = '\n  headers: { ...headers, "Authorization": `Bearer ${token}` },' if needs_auth else "\n  headers,"
        return (
            'const token = "YOUR_JWT";\n'
            'const headers = { "Content-Type": "application/json" };\n\n'
            f'const response = await fetch("{url}", {{\n'
            f'  method: "{method_upper}",{auth_headers}{body_line}\n'
            "});\n"
            "const data = await response.json();\n"
            'if (!response.ok) throw new Error(data?.message || "Request failed");'
        )

    if stack == "react-axios":
        auth = '\n  headers: { Authorization: `Bearer ${token}` },' if needs_auth else ""
        body_arg = f", {body_json}" if has_body else ""
        base = base_url.rstrip("/")
        ax_path = url.replace(base, "") or path
        return (
            'import axios from "axios";\n\n'
            'const token = "YOUR_JWT";\n'
            "const api = axios.create({\n"
            f'  baseURL: "{base}",{auth}\n'
            "});\n\n"
            f'const {{ data }} = await api.{method.lower()}("{ax_path}"{body_arg});'
        )

    if stack == "vue3":
        body_arg = f",\n  body: JSON.stringify({body_json})" if has_body else ""
        auth_line = '\n    "Authorization": `Bearer ${token.value}`,' if needs_auth else ""
        return (
            'const token = ref("YOUR_JWT");\n'
            f'const url = "{url}";\n\n'
            "const response = await fetch(url, {\n"
            f'  method: "{method_upper}",\n'
            "  headers: {\n"
            '    "Content-Type": "application/json",' + auth_line + "\n"
            "  }" + body_arg + "\n"
            "});\n"
            "const data = await response.json();"
        )

    if stack == "nextjs":
        body_line = f"\n  body: JSON.stringify({body_json})," if has_body else ""
        auth_headers = '\n    Authorization: `Bearer ${token}`,' if needs_auth else ""
        return (
            'const token = "YOUR_JWT";\n'
            f'const res = await fetch("{url}", {{\n'
            f'  method: "{method_upper}",\n'
            "  headers: {\n"
            '    "Content-Type": "application/json",' + auth_headers + "\n"
            "  }," + body_line + "\n"
            "});\n"
            "const data = await res.json();"
        )

    if stack == "angular":
        body_line = f"\n  body: {body_json}," if has_body else ""
        auth_headers = '\n    "Authorization": `Bearer ${this.authService.getToken()}`,' if needs_auth else ""
        return (
            f'const url = "{url}";\n'
            "this.http.request<any>({\n"
            f'  method: "{method_upper}",\n'
            "  url,\n"
            '  headers: { "Content-Type": "application/json"' + auth_headers + " }," + body_line + "\n"
            "}).subscribe({ next: (data) => console.log(data), error: (err) => console.error(err) });"
        )

    if stack == "svelte":
        body_line = f",\n  body: JSON.stringify({body_json})" if has_body else ""
        auth_line = '\n    "Authorization": `Bearer ${token}`,' if needs_auth else ""
        return (
            'let token = "YOUR_JWT";\n'
            f'const url = "{url}";\n\n'
            "const res = await fetch(url, {\n"
            f'  method: "{method_upper}",\n'
            "  headers: {\n"
            '    "Content-Type": "application/json",' + auth_line + "\n"
            "  }" + body_line + "\n"
            "});\n"
            "const data = await res.json();"
        )

    if stack == "react-native":
        body_line = f"\n  body: JSON.stringify({body_json})," if has_body else ""
        auth_headers = '\n  headers: { ...headers, Authorization: `Bearer ${token}` },' if needs_auth else "\n  headers,"
        return (
            'const token = "YOUR_JWT";\n'
            'const headers = { "Content-Type": "application/json" };\n\n'
            f'const response = await fetch("{url}", {{\n'
            f'  method: "{method_upper}",{auth_headers}{body_line}\n'
            "});\n"
            "const data = await response.json();"
        )

    if stack == "flutter":
        dart_body = _dart_body_literal(details) if has_body else ""
        body_line = f"\n  body: jsonEncode({dart_body})," if has_body else ""
        auth_line = "\n    'Authorization': 'Bearer $token'," if needs_auth else ""
        return (
            "final token = 'YOUR_JWT';\n"
            f"final url = Uri.parse('{url}');\n"
            "final response = await http.request(\n"
            f"  url,\n  method: '{method_upper}',\n"
            "  headers: {\n"
            "    'Content-Type': 'application/json'," + auth_line + "\n"
            "  }," + body_line + "\n"
            ");\n"
            "final data = jsonDecode(response.body);"
        )

    if stack == "swift-ios":
        swift_payload = _swift_body_literal(details) if has_body else ""
        body_line = f'\nlet payload: [String: Any] = {swift_payload}\nrequest.httpBody = try? JSONSerialization.data(withJSONObject: payload)' if has_body else ""
        auth_line = '\nrequest.setValue("Bearer \\(token)", forHTTPHeaderField: "Authorization")' if needs_auth else ""
        return (
            'let token = "YOUR_JWT"\n'
            f'let url = URL(string: "{url}")!\n'
            "var request = URLRequest(url: url)\n"
            f'request.httpMethod = "{method_upper}"\n'
            'request.setValue("application/json", forHTTPHeaderField: "Content-Type")' + auth_line + body_line + "\n"
            "let (data, _) = try await URLSession.shared.data(for: request)\n"
            "let decoded = try JSONDecoder().decode(YourModel.self, from: data)"
        )

    if stack == "kotlin-android":
        kotlin_payload = _kotlin_body_literal(details) if has_body else ""
        body_part = (
            f'\nval payload = {kotlin_payload}\n'
            '    .post(payload.toString().toRequestBody("application/json".toMediaType()))'
            if has_body
            else f'\n    .method("{method_upper}", null)'
        )
        auth_line = '\n    .addHeader("Authorization", "Bearer $token")' if needs_auth else ""
        return (
            'val token = "YOUR_JWT"\n'
            f'val request = Request.Builder().url("{url}")' + auth_line + body_part + "\n"
            "    .build()\n"
            "val response = client.newCall(request).execute()\n"
            "val body = response.body?.string()"
        )

    return _template_example(method, path, "vanilla", needs_auth, body_summary, base_url, operation)


def _build_prompt(method: str, path: str, stack: str, summary: str, needs_auth: bool, body_summary: str, base_url: str, operation: dict | None = None) -> str:
    details = _extract_operation_details(operation or {})
    url = _build_url(base_url, path, details)

    param_lines = ""
    if details["path_params"]:
        param_lines += "\nPath parameters:\n"
        for p in details["path_params"]:
            param_lines += f"  - {p['name']} ({p['type']}), example: {p['example']}\n"
    if details["query_params"]:
        param_lines += "Query parameters:\n"
        for p in details["query_params"]:
            req = "required" if p["required"] else "optional"
            param_lines += f"  - {p['name']} ({p['type']}, {req}), example: {p['example']}\n"

    body_section = "None."
    if details["example_body"]:
        body_section = f"JSON object with these fields:\n{json.dumps(details['example_body'], indent=2)}"
    elif details["body_fields"]:
        body_section = "JSON object with fields:\n"
        for f in details["body_fields"]:
            req = "required" if f["required"] else "optional"
            body_section += f"  - {f['name']} ({f['type']}, {req}), example: {f['example']}\n"
    elif body_summary:
        body_section = f"JSON object with fields: {body_summary}"

    return f"""You are a documentation assistant. Generate a single, runnable code example for calling this API endpoint from a frontend application.

Endpoint: {method.upper()} {path}
Full URL (with example values): {url}
Summary: {summary}
Base URL: {base_url}
Authentication: {"Required (Bearer JWT in Authorization header). Assume the token is available (e.g. from login)." if needs_auth else "None."}
{param_lines}Request body: {body_section}

Stack: {stack}

Requirements:
- Output ONLY the code. No markdown fences, no explanation before or after.
- Use the exact stack requested: {stack}.
- Use realistic example values for all parameters and request body fields as shown above.
- For React: use functional components and hooks.
- For Vue 3: use Composition API (ref, async).
- For Next.js: use App Router; show fetch with headers.
- Always include the Authorization: Bearer header when authentication is required.
- Use "{url}" as the full URL.
- Keep the example minimal but complete enough to copy-paste and adapt.

Generate the code now:"""


def generate_example(
    method: str,
    path: str,
    stack: str,
    operation: dict | None,
    base_url: str,
    openai_api_key: str | None,
) -> str:
    
    # Generate a frontend code example for the given endpoint.
    # Uses OpenAI if openai_api_key is set (or from config); otherwise uses template.
    
    op = operation or {}
    needs_auth = _has_auth(op)
    body_summary = _get_body_summary(op)
    summary = (op.get("summary") or op.get("description") or "").strip()[:500]
    api_key = openai_api_key or settings.openai_api_key

    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            prompt = _build_prompt(method, path, stack, summary, needs_auth, body_summary, base_url, op)
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You output only code. No markdown, no explanation."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            code = (resp.choices[0].message.content or "").strip()
            if code.startswith("```"):
                lines = code.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                code = "\n".join(lines)
            if code:
                return code
        except Exception as e:
            logger.warning("OpenAI example generation failed: %s", e)

    return _template_example(method, path, stack, needs_auth, body_summary, base_url, op)


def get_operation(openapi_schema: dict, path: str, method: str) -> dict | None:
    # Get the OpenAPI operation object for path and method.
    paths = openapi_schema.get("paths") or {}
    path_item = paths.get(path)
    if not path_item or not isinstance(path_item, dict):
        return None
    m = method.lower()
    return path_item.get(m) if isinstance(path_item.get(m), dict) else None


def _api_summary_text(
    openapi_schema: dict,
    context_tag_names: set[str] | None = None,
) -> str:
    # Build a short text summary of the API for LLM context. If context_tag_names is set, only include endpoints in those tags.
    info = openapi_schema.get("info", {})
    title = info.get("title", "API")
    version = info.get("version", "")
    description = (info.get("description") or "").strip()[:800]
    paths = openapi_schema.get("paths", {}) or {}
    by_tag: dict[str, list[tuple[str, str, str]]] = {}
    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "options", "head"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            tags = op.get("tags") or ["Other"]
            tag = tags[0] if tags else "Other"
            if context_tag_names is not None and not (set(tags) & context_tag_names):
                continue
            summary = (op.get("summary") or op.get("description") or "").strip()[:120]
            if tag not in by_tag:
                by_tag[tag] = []
            by_tag[tag].append((method.upper(), path, summary))
    lines = [f"Title: {title}", f"Version: {version}"]
    if description:
        lines.append(f"Description: {description}")
    lines.append("Endpoints:")
    tag_order = sorted(by_tag.keys()) if context_tag_names is None else sorted(set(by_tag.keys()) & context_tag_names)
    for tag in tag_order:
        if tag not in by_tag:
            continue
        lines.append(f"  [{tag}]")
        for method, path, summary in by_tag[tag][:20]:
            lines.append(f"    {method} {path}" + (f" — {summary}" if summary else ""))
    if context_tag_names and not by_tag:
        lines.append("  (No endpoints in selected modules.)")
    return "\n".join(lines)


def generate_overview_summary(openapi_schema: dict, openai_api_key: str | None) -> str | None:
    """
    Use an LLM to generate a short introduction/overview for the API (2–4 sentences).
    Returns None if no API key or on error.
    """
    api_key = openai_api_key or settings.openai_api_key
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        api_text = _api_summary_text(openapi_schema)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You write brief, clear API overviews for documentation. Output only 2–4 sentences. No markdown, no bullets.",
                },
                {
                    "role": "user",
                    "content": f"Write a short introduction/overview for this API:\n\n{api_text}",
                },
            ],
            temperature=0.3,
        )
        summary = (resp.choices[0].message.content or "").strip()
        return summary if summary else None
    except Exception as e:
        logger.warning("OpenAI overview summary failed: %s", e)
        return None


# --- Chat agent (Option A: context-only; Option B: with tool-calling) ---

CHAT_SYSTEM_PREFIX = """You are a helpful assistant for an API. Use the API reference below to answer questions. Be concise. If the user asks for code, you can use the generate_code_example tool."""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_api_overview",
            "description": "Get the full API overview: title, version, description, and list of endpoints by tag.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_endpoint_details",
            "description": "Get details for a specific endpoint: parameters, request body, responses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "API path, e.g. /users"},
                    "method": {"type": "string", "description": "HTTP method: GET, POST, PUT, PATCH, DELETE"},
                },
                "required": ["path", "method"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_code_example",
            "description": "Generate a frontend/mobile code example for an endpoint in a given stack (e.g. react-fetch, vue3, nextjs, flutter).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "API path"},
                    "method": {"type": "string", "description": "GET, POST, etc."},
                    "stack": {"type": "string", "description": "Stack: react-fetch, react-axios, vue3, nextjs, angular, svelte, vanilla, react-native, flutter, swift-ios, kotlin-android"},
                },
                "required": ["path", "method", "stack"],
            },
        },
    },
]


def _run_tool(name: str, arguments: dict, openapi_schema: dict, base_url: str, openai_api_key: str | None) -> str:
    """Execute one agent tool and return the result as a string."""
    api_key = openai_api_key or settings.openai_api_key
    if name == "get_api_overview":
        return _api_summary_text(openapi_schema)
    if name == "get_endpoint_details":
        path = arguments.get("path", "")
        method = (arguments.get("method") or "get").upper()
        op = get_operation(openapi_schema, path, method)
        if not op:
            return f"Endpoint {method} {path} not found."
        params = op.get("parameters") or []
        body = op.get("requestBody") or {}
        responses = op.get("responses") or {}
        lines = [f"{method} {path}", op.get("summary") or op.get("description") or "", "Parameters:", *[f"  - {p.get('name')} ({p.get('in')}): {p.get('description') or ''}" for p in params], "Request body: " + str(body.get("description") or "see schema"), "Responses: " + ", ".join(responses.keys())]
        return "\n".join(lines)
    if name == "generate_code_example":
        path = arguments.get("path", "")
        method = (arguments.get("method") or "get").upper()
        stack = arguments.get("stack", "react-fetch")
        op = get_operation(openapi_schema, path, method)
        code = generate_example(method, path, stack, op, base_url, api_key)
        return code or "No code generated."
    return "Unknown tool."


def agent_chat(
    messages: list[dict],
    openapi_schema: dict,
    base_url: str,
    openai_api_key: str | None,
    use_tools: bool = True,
    context_tag_names: list[str] | None = None,
) -> dict:
    """
    Run the chat agent. Option A: use_tools=False, single completion with API context.
    Option B: use_tools=True, use tools and loop until final message.
    If context_tag_names is set, the initial API context is limited to those tags (modules).
    Returns {"role": "assistant", "content": "..."}.
    """
    api_key = openai_api_key or settings.openai_api_key
    if not api_key:
        return {"role": "assistant", "content": "Chat is not available (no API key configured)."}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        tag_set = set(context_tag_names) if context_tag_names else None
        api_summary = _api_summary_text(openapi_schema, context_tag_names=tag_set)
        system_content = f"{CHAT_SYSTEM_PREFIX}\n\nAPI reference:\n{api_summary}"
        if tag_set:
            system_content += "\n\n(Context is limited to the selected API modules above.)"
        all_messages: list[dict] = [{"role": "system", "content": system_content}, *messages]
        tools = AGENT_TOOLS if use_tools else None
        max_rounds = 10
        while max_rounds > 0:
            max_rounds -= 1
            kwargs = {"model": settings.openai_model, "messages": all_messages, "temperature": 0.3}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            resp = client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message
            if not msg:
                break
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                return {"role": "assistant", "content": (msg.content or "").strip() or "(No response)"}
            # Append assistant message with tool_calls
            assistant_msg = {"role": "assistant", "content": msg.content or ""}
            assistant_msg["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                for tc in tool_calls
            ]
            all_messages.append(assistant_msg)
            for tc in tool_calls:
                name = tc.function.name
                try:
                    import json
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = _run_tool(name, args, openapi_schema, base_url, api_key)
                all_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        return {"role": "assistant", "content": "I hit a limit on tool use. Please try a shorter question."}
    except Exception as e:
        logger.warning("Agent chat failed: %s", e)
        return {"role": "assistant", "content": f"Sorry, something went wrong: {e!s}"}
