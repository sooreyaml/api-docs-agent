"""Generate API reference HTML from OpenAPI schema."""
from __future__ import annotations

from html import escape
from typing import Any

from .docs_agent import STACKS


_NAME_EXAMPLES: dict[str, Any] = {
    "email": "user@example.com",
    "password": "P@ssw0rd123",
    "username": "johndoe",
    "name": "John Doe",
    "first_name": "John",
    "firstName": "John",
    "last_name": "Doe",
    "lastName": "Doe",
    "phone": "+1234567890",
    "phone_number": "+1234567890",
    "phoneNumber": "+1234567890",
    "address": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "country": "US",
    "zip": "94105",
    "zip_code": "94105",
    "url": "https://example.com",
    "website": "https://example.com",
    "title": "My Title",
    "description": "A short description",
    "message": "Hello, world!",
    "content": "Lorem ipsum dolor sit amet",
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "code": "ABC123",
    "otp": "123456",
    "amount": 99.99,
    "price": 29.99,
    "quantity": 1,
    "count": 10,
    "page": 1,
    "limit": 20,
    "offset": 0,
    "per_page": 20,
    "perPage": 20,
    "page_size": 20,
    "pageSize": 20,
    "sort": "created_at",
    "order": "desc",
    "search": "keyword",
    "query": "search term",
    "q": "search term",
    "status": "active",
    "type": "default",
    "role": "user",
    "currency": "USD",
    "language": "en",
    "locale": "en-US",
    "lat": 37.7749,
    "lng": -122.4194,
    "latitude": 37.7749,
    "longitude": -122.4194,
}


def _example_value_for_field(name: str, typ: str, schema: dict | None = None) -> Any:
    """Derive a realistic example value from field name, type, and optional schema."""
    if schema and isinstance(schema, dict):
        if "example" in schema:
            return schema["example"]
        if "default" in schema:
            return schema["default"]
        if "enum" in schema and schema["enum"]:
            return schema["enum"][0]

    name_lower = name.lower().replace("-", "_")
    if name_lower in _NAME_EXAMPLES:
        return _NAME_EXAMPLES[name_lower]
    if "id" in name_lower:
        return 1
    if "date" in name_lower or "time" in name_lower:
        return "2025-01-15T09:30:00Z"
    if "is_" in name_lower or name_lower.startswith("has_") or name_lower.startswith("enable"):
        return True

    type_lower = (typ or "").lower()
    if "int" in type_lower:
        return 0
    if type_lower in ("number", "float", "double"):
        return 0.0
    if type_lower == "boolean":
        return True
    if type_lower == "string":
        return "string"
    return "string"


def _generate_example_json(schema: dict | None, openapi_schema: dict, depth: int = 0) -> Any:
    """Build a complete example JSON value from a schema, recursively."""
    if not schema or not isinstance(schema, dict) or depth > 5:
        return None
    resolved = _resolve_schema(schema, openapi_schema)
    if not resolved or not isinstance(resolved, dict):
        return None

    if "example" in resolved:
        return resolved["example"]

    typ = resolved.get("type", "")
    if typ == "object" or resolved.get("properties"):
        obj: dict[str, Any] = {}
        for prop_name, prop_schema in (resolved.get("properties") or {}).items():
            if not isinstance(prop_schema, dict):
                continue
            prop_resolved = _resolve_schema(prop_schema, openapi_schema) or prop_schema
            prop_type = prop_resolved.get("type", _schema_type_str(prop_schema))
            if prop_type == "object" or prop_resolved.get("properties"):
                obj[prop_name] = _generate_example_json(prop_schema, openapi_schema, depth + 1)
            elif prop_type == "array":
                items = prop_resolved.get("items")
                if items and isinstance(items, dict):
                    item_val = _generate_example_json(items, openapi_schema, depth + 1)
                    obj[prop_name] = [item_val] if item_val is not None else []
                else:
                    obj[prop_name] = []
            else:
                obj[prop_name] = _example_value_for_field(prop_name, prop_type, prop_resolved)
        return obj
    if typ == "array":
        items = resolved.get("items")
        if items and isinstance(items, dict):
            item_val = _generate_example_json(items, openapi_schema, depth + 1)
            return [item_val] if item_val is not None else []
        return []
    return _example_value_for_field("", typ, resolved)


def _get_schema_by_name(openapi_schema: dict, name: str) -> dict | None:
    # Resolve a schema name from OpenAPI 3 (components/schemas) or Swagger 2 (definitions).
    components = openapi_schema.get("components", {}) or {}
    schemas = components.get("schemas", {}) or {}
    if name in schemas:
        return schemas[name]
    definitions = openapi_schema.get("definitions", {}) or {}
    return definitions.get(name)


def _resolve_ref(schema: dict | None, openapi_schema: dict) -> dict | None:
    # Resolve $ref to the actual schema from components/schemas (OAS3) or definitions (Swagger 2).
    if not schema or not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if not ref or not isinstance(ref, str):
        return schema
    if ref.startswith("#/components/schemas/"):
        name = ref.split("/")[-1]
        return _get_schema_by_name(openapi_schema, name)
    if ref.startswith("#/definitions/"):
        name = ref.split("/")[-1]
        return _get_schema_by_name(openapi_schema, name)
    return schema


def _schema_type_str(schema: dict) -> str:
    # Return a short type string for a schema (e.g. string, object, array of X).
    if not schema:
        return "any"
    ref = schema.get("$ref")
    if ref:
        return ref.split("/")[-1]
    typ = schema.get("type", "")
    if typ == "array":
        items = schema.get("items", {})
        item_ref = items.get("$ref") if isinstance(items, dict) else None
        if item_ref:
            return f"array of {item_ref.split('/')[-1]}"
        return f"array of {_schema_type_str(items) if isinstance(items, dict) else 'any'}"
    if typ == "object":
        return "object"
    return typ or "any"


def _render_schema_properties(
    schema: dict, openapi_schema: dict, required_set: set[str] | None = None
) -> str:
    # Render schema properties as HTML table rows. Handles nested $ref by inlining once.
    required_set = required_set or set(schema.get("required") or [])
    properties = schema.get("properties") or {}
    rows = []
    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            continue
        resolved = _resolve_schema(prop_schema, openapi_schema) or prop_schema
        typ = _schema_type_str(prop_schema)
        desc = (resolved.get("description") or prop_schema.get("description") or "").replace("\n", " ")
        req = "required" if prop_name in required_set else "optional"
        rows.append(
            f"<tr><td><code>{escape(prop_name)}</code></td><td><code>{escape(typ)}</code></td><td>{req}</td><td>{escape(desc)}</td></tr>"
        )
        # Nested object: show nested table
        if isinstance(resolved, dict) and resolved.get("type") == "object" and resolved.get("properties"):
            nested_table = _schema_to_html(resolved, openapi_schema)
            if nested_table:
                rows.append(f'<tr><td colspan="4" class="nested-schema">{nested_table}</td></tr>')
        if prop_schema.get("type") == "array" and isinstance(prop_schema.get("items"), dict):
            items = prop_schema["items"]
            if items.get("$ref"):
                pass
            elif items.get("type") == "object" and items.get("properties"):
                nested_table = _schema_to_html(items, openapi_schema)
                if nested_table:
                    rows.append(f'<tr><td colspan="4" class="nested-schema">Items: {nested_table}</td></tr>')
    return "".join(rows)


def _resolve_schema(schema: dict | None, openapi_schema: dict) -> dict | None:
    # Resolve $ref and allOf to a single schema for display.
    if not schema or not isinstance(schema, dict):
        return schema
    if schema.get("$ref"):
        resolved = _resolve_ref(schema, openapi_schema)
        return _resolve_schema(resolved, openapi_schema) if resolved else resolved
    if "allOf" in schema:
        all_of = schema.get("allOf") or []
        merged = {"type": "object", "properties": {}, "required": []}
        for part in all_of:
            part_resolved = _resolve_schema(part, openapi_schema) if isinstance(part, dict) else part
            if isinstance(part_resolved, dict):
                merged.setdefault("required", []).extend(part_resolved.get("required") or [])
                merged.setdefault("properties", {}).update(part_resolved.get("properties") or {})
        return merged
    return schema


def _schema_to_html(schema: dict | None, openapi_schema: dict, title: str = "") -> str:
    # Render a JSON schema (object with properties) as HTML table. Resolves $ref and allOf.
    if not schema:
        return ""
    resolved = _resolve_schema(schema, openapi_schema) or schema
    if not isinstance(resolved, dict):
        return ""
    if resolved.get("type") == "object" or resolved.get("properties"):
        required = set(resolved.get("required") or [])
        rows = _render_schema_properties(resolved, openapi_schema, required)
        if not rows:
            ref = schema.get("$ref")
            if ref:
                name = ref.split("/")[-1]
                return f'<p class="schema-ref">Schema: <code>{escape(name)}</code></p>'
            return ""
        header = "<thead><tr><th>Field</th><th>Type</th><th>Required</th><th>Description</th></tr></thead><tbody>"
        return f'<table class="schema-table">{header}{rows}</tbody></table>'
    ref = schema.get("$ref")
    if ref:
        name = ref.split("/")[-1]
        sub = _get_schema_by_name(openapi_schema, name)
        if sub:
            return _schema_to_html(sub, openapi_schema, name)
        return f'<p class="schema-ref">Schema: <code>{escape(name)}</code></p>'
    typ = schema.get("type", "any")
    return f'<p class="schema-type">Type: <code>{escape(typ)}</code></p>'


def _params_list(params: list[dict]) -> str:
    if not params:
        return ""
    rows = []
    for p in params:
        name = escape(p.get("name", ""))
        loc = p.get("in", "query")
        desc = escape((p.get("description") or "").replace("\n", " "))
        required = "required" if p.get("required") else "optional"
        rows.append(f"<tr><td><code>{name}</code></td><td>{loc}</td><td>{required}</td><td>{desc}</td></tr>")
    return "<table class=\"schema-table\"><thead><tr><th>Name</th><th>In</th><th>Required</th><th>Description</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _response_section(code: str, content: dict, openapi_schema: dict) -> str:
    # Build HTML for one response: description + body schema if present.
    desc = content.get("description", "") if isinstance(content, dict) else str(content)
    html_parts = [f"<p><strong>{escape(code)}</strong>: {escape(desc)}</p>"]
    media = content.get("content", {}) or {}
    for media_type, media_spec in media.items():
        if media_type not in ("application/json", "application/json; charset=utf-8"):
            continue
        schema = media_spec.get("schema") if isinstance(media_spec, dict) else None
        if schema:
            html_parts.append("<p><em>Response body:</em></p>")
            html_parts.append(_schema_to_html(schema, openapi_schema))
    return "".join(html_parts)


def _responses_list(responses: dict, openapi_schema: dict) -> str:
    if not responses:
        return ""
    items = []
    for code, content in responses.items():
        if not isinstance(content, dict):
            items.append(f"<li><strong>{escape(code)}</strong>: {escape(str(content))}</li>")
            continue
        items.append(f'<li class="response-block">{_response_section(code, content, openapi_schema)}</li>')
    return "<ul class=\"response-list\">" + "".join(items) + "</ul>"


def _request_body(body: dict, openapi_schema: dict) -> str:
    if not body:
        return ""
    content = body.get("content", {})
    if not content:
        return ""
    desc = body.get("description", "")
    parts = []
    if desc:
        parts.append(f"<p>{escape(desc)}</p>")
    for media_type, media_spec in content.items():
        if media_type not in ("application/json", "application/json; charset=utf-8"):
            continue
        schema = media_spec.get("schema") if isinstance(media_spec, dict) else None
        if schema:
            parts.append(_schema_to_html(schema, openapi_schema))
    return "".join(parts) if parts else ""


def _slug(s: str) -> str:
    # Safe HTML id from method + path.
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in s.lower()).strip("-")


def _has_auth(op: dict) -> bool:
    # True if operation has bearer (or similar) security. OpenAPI security is a list of
    # objects keyed by scheme name (e.g. {"bearerAuth": []}); we check the keys.
    sec = op.get("security") or []
    for s in sec:
        if not isinstance(s, dict):
            continue
        for key in s.keys():
            k = str(key).lower()
            if "bearer" in k or "jwt" in k or "oauth" in k or "token" in k:
                return True
    return False


def _how_to_call(method: str, path: str, op: dict, base_url: str) -> str:
    # HTML block: how to call this endpoint (method, URL, headers, curl).
    full_url = (base_url.rstrip("/") + path) if base_url else path
    needs_auth = _has_auth(op)
    has_body = method.upper() in ("POST", "PUT", "PATCH") and op.get("requestBody")
    parts = [
        '<div class="how-to-call">',
        "<p><strong>Request</strong></p>",
        f'<pre class="request-line"><span class="method method-{method.lower()}">{method.upper()}</span> {escape(full_url)}</pre>',
    ]
    if needs_auth:
        parts.append('<p class="call-headers"><strong>Headers</strong></p>')
        parts.append('<pre class="code-block">Authorization: Bearer &lt;your_token&gt;\nContent-Type: application/json</pre>' if has_body else '<pre class="code-block">Authorization: Bearer &lt;your_token&gt;</pre>')
    elif has_body:
        parts.append('<p class="call-headers"><strong>Headers</strong></p>')
        parts.append('<pre class="code-block">Content-Type: application/json</pre>')
    if has_body:
        parts.append('<p class="call-body">Send a JSON body; see <strong>Request body</strong> schema below.</p>')
    parts.append("</div>")
    return "".join(parts)


# --- JSON data builders for GET /api/agent-docs ---


def _schema_to_data(schema: dict | None, openapi_schema: dict) -> dict | None:
    # Return a JSON-serializable representation of a schema (for request/response body).
    if not schema or not isinstance(schema, dict):
        return None
    resolved = _resolve_schema(schema, openapi_schema) or schema
    if not isinstance(resolved, dict):
        return {"type": _schema_type_str(schema)}
    if resolved.get("type") == "object" or resolved.get("properties"):
        required = set(resolved.get("required") or [])
        properties = []
        for prop_name, prop_schema in (resolved.get("properties") or {}).items():
            if not isinstance(prop_schema, dict):
                continue
            typ = _schema_type_str(prop_schema)
            # Use the property's own description only (never the parent schema's, e.g. "Standard error response")
            desc = prop_schema.get("description") or ""
            if not desc:
                prop_resolved = _resolve_schema(prop_schema, openapi_schema)
                if isinstance(prop_resolved, dict):
                    desc = prop_resolved.get("description") or ""
            prop_resolved = _resolve_schema(prop_schema, openapi_schema) or prop_schema
            example = _example_value_for_field(prop_name, typ, prop_resolved if isinstance(prop_resolved, dict) else None)
            properties.append({
                "name": prop_name,
                "type": typ,
                "required": prop_name in required,
                "description": desc,
                "example": example,
            })
        return {"type": "object", "properties": properties}
    ref = schema.get("$ref")
    if ref:
        return {"type": ref.split("/")[-1], "$ref": ref}
    return {"type": resolved.get("type", "any")}


def _response_to_data(code: str, content: dict, openapi_schema: dict) -> dict:
    # One response as data: code, description, optional body_schema.
    desc = content.get("description", "") if isinstance(content, dict) else str(content)
    out = {"code": code, "description": desc}
    media = content.get("content", {}) or {} if isinstance(content, dict) else {}
    for media_type in ("application/json", "application/json; charset=utf-8"):
        if media_type not in media:
            continue
        media_spec = media.get(media_type)
        if isinstance(media_spec, dict):
            schema = media_spec.get("schema")
            if schema:
                out["body_schema"] = _schema_to_data(schema, openapi_schema)
        break
    return out


def _request_body_to_data(body: dict, openapi_schema: dict) -> dict | None:
    # Request body as data: description + schema.
    if not body or not isinstance(body, dict):
        return None
    content = body.get("content", {}) or {}
    for media_type in ("application/json", "application/json; charset=utf-8"):
        if media_type not in content:
            continue
        media_spec = content.get(media_type)
        if isinstance(media_spec, dict) and media_spec.get("schema"):
            return {
                "description": body.get("description", ""),
                "schema": _schema_to_data(media_spec["schema"], openapi_schema),
            }
    return None


def build_api_reference_data(openapi_schema: dict, base_url: str = "") -> dict:
    # Build API reference as JSON-serializable data for the docs UI (same structure for both use cases).
    paths = openapi_schema.get("paths", {})
    info = openapi_schema.get("info", {})
    title = info.get("title", "API Reference")
    version = info.get("version", "")
    description = info.get("description", "") or ""

    by_tag: dict[str, list[tuple[str, str, dict, str]]] = {}
    for path, path_item in sorted(paths.items()):
        for method in ("get", "post", "put", "patch", "delete", "options", "head"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            tags = op.get("tags") or ["Other"]
            tag = tags[0] if tags else "Other"
            endpoint_id = "endpoint-" + _slug(f"{method}-{path}")
            entry = (path, method.upper(), op, endpoint_id)
            if tag not in by_tag:
                by_tag[tag] = []
            by_tag[tag].append(entry)

    for path, path_item in sorted(paths.items()):
        if isinstance(path_item, dict) and "get" not in path_item and "post" not in path_item:
            for key in path_item:
                if key.lower() in ("get", "post", "put", "patch", "delete"):
                    continue
                op = path_item.get(key)
                if isinstance(op, dict) and ("summary" in op or "description" in op):
                    tag = (op.get("tags") or ["Other"])[0]
                    if tag not in by_tag:
                        by_tag[tag] = []
                    endpoint_id = "endpoint-" + _slug(f"{key}-{path}")
                    by_tag[tag].append((path, key.upper(), op, endpoint_id))

    sorted_tags = sorted(by_tag.keys())
    full_url_base = base_url.rstrip("/") if base_url else ""

    tags_payload = []
    for tag in sorted_tags:
        endpoints = []
        for path, method, op, endpoint_id in by_tag[tag]:
            params = op.get("parameters") or []
            req_body = op.get("requestBody") if isinstance(op.get("requestBody"), dict) else None
            responses = op.get("responses") or {}
            full_url = (full_url_base + path) if full_url_base else path
            needs_auth = _has_auth(op)
            has_body = method.upper() in ("POST", "PUT", "PATCH") and bool(req_body)

            parameters_data = []
            for p in params:
                p_schema = p.get("schema") or {}
                p_type = _schema_type_str(p_schema) if isinstance(p_schema, dict) else "string"
                p_name = p.get("name", "")
                p_example = _example_value_for_field(p_name, p_type, p_schema if isinstance(p_schema, dict) else None)
                parameters_data.append({
                    "name": p_name,
                    "in": p.get("in", "query"),
                    "required": bool(p.get("required")),
                    "description": (p.get("description") or "").replace("\n", " "),
                    "type": p_type,
                    "example": p_example,
                })
            responses_data = [
                _response_to_data(code, content, openapi_schema)
                for code, content in responses.items()
            ]
            request_body_data = _request_body_to_data(req_body, openapi_schema) if req_body else None

            example_body = None
            if req_body:
                rb_content = req_body.get("content", {}) or {}
                for mt in ("application/json", "application/json; charset=utf-8"):
                    ms = rb_content.get(mt)
                    if isinstance(ms, dict) and ms.get("schema"):
                        example_body = _generate_example_json(ms["schema"], openapi_schema)
                        break

            endpoints.append({
                "endpoint_id": endpoint_id,
                "path": path,
                "method": method,
                "summary": op.get("summary") or "",
                "description": (op.get("description") or "").replace("\n", "\n"),
                "how_to_call": {
                    "full_url": full_url,
                    "needs_auth": needs_auth,
                    "has_body": has_body,
                },
                "parameters": parameters_data,
                "request_body_schema": request_body_data,
                "example_body": example_body,
                "responses": responses_data,
            })
        tags_payload.append({"name": tag, "endpoints": endpoints})

    return {
        "title": title,
        "version": version,
        "description": description,
        "base_url": full_url_base or base_url,
        "tags": tags_payload,
        "stacks": [{"value": v, "label": l} for v, l in STACKS],
    }


def build_api_reference_html(openapi_schema: dict, base_url: str = "") -> str:
    # Build API reference with sidebar, overview, and per-endpoint 'how to call'.
    paths = openapi_schema.get("paths", {})
    info = openapi_schema.get("info", {})
    title = escape(info.get("title", "API Reference"))
    version = escape(info.get("version", ""))
    description = info.get("description", "")
    if description:
        description = description.replace("\n", "<br>\n")

    # Group operations by tag; collect (path, method, op, endpoint_id)
    by_tag: dict[str, list[tuple[str, str, dict, str]]] = {}

    for path, path_item in sorted(paths.items()):
        for method in ("get", "post", "put", "patch", "delete", "options", "head"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            tags = op.get("tags") or ["Other"]
            tag = tags[0] if tags else "Other"
            endpoint_id = "endpoint-" + _slug(f"{method}-{path}")
            entry = (path, method.upper(), op, endpoint_id)
            if tag not in by_tag:
                by_tag[tag] = []
            by_tag[tag].append(entry)

    for path, path_item in sorted(paths.items()):
        if isinstance(path_item, dict) and "get" not in path_item and "post" not in path_item:
            for key in path_item:
                if key.lower() in ("get", "post", "put", "patch", "delete"):
                    continue
                op = path_item.get(key)
                if isinstance(op, dict) and ("summary" in op or "description" in op):
                    tag = (op.get("tags") or ["Other"])[0]
                    if tag not in by_tag:
                        by_tag[tag] = []
                    endpoint_id = "endpoint-" + _slug(f"{key}-{path}")
                    by_tag[tag].append((path, key.upper(), op, endpoint_id))

    sorted_tags = sorted(by_tag.keys())

    # Top bar + Sidebar (Dojah-style)
    sidebar_parts = [
        '<header class="topbar">',
        f'<a href="#overview" class="topbar-logo">{title}</a>',
        '<nav class="topbar-tabs">',
        '<a href="#overview" class="topbar-tab active">Overview</a>',
        '<a href="#tag-' + _slug(sorted_tags[0]) + '" class="topbar-tab">API Reference</a>' if sorted_tags else '',
        '</nav>',
        '<div class="topbar-search" role="search"><span class="topbar-search-placeholder">Search docs… <kbd>⌘K</kbd></span></div>',
        '<a href="/docs" class="topbar-swagger">Swagger UI</a>',
        '</header>',
        '<aside class="sidebar" id="sidebar">',
        '<nav class="sidebar-nav">',
        '<p class="sidebar-category">GETTING STARTED</p>',
        '<ul class="sidebar-list">',
        '<li><a href="#overview" class="sidebar-link sidebar-link-overview"><span class="sidebar-icon">📖</span> Introduction</a></li>',
        '<li><a href="/docs" class="sidebar-link"><span class="sidebar-icon">▶</span> Try in Swagger</a></li>',
        '</ul>',
        '<p class="sidebar-category">API MODULES</p>',
        '<ul class="sidebar-list">',
    ]
    for tag in sorted_tags:
        tag_id = "tag-" + _slug(tag)
        icon = "🔌" if tag.lower() == "auth" else "📡" if tag.lower() == "messaging" else "📁"
        sidebar_parts.append(f'<li class="sidebar-tag-wrap">')
        sidebar_parts.append(f'<button type="button" class="sidebar-tag-toggle" aria-expanded="true" data-tag="{escape(tag_id)}"><span class="sidebar-icon">{icon}</span>{escape(tag)}<span class="sidebar-arrow">▼</span></button>')
        sidebar_parts.append('<ul class="sidebar-sublist" data-tag="' + escape(tag_id) + '">')
        for path, method, op, endpoint_id in by_tag[tag]:
            summary = (op.get("summary") or path)[:45] + ("…" if len((op.get("summary") or path)) > 45 else "")
            sidebar_parts.append(f'<li><a href="#{endpoint_id}" class="sidebar-link sublink" title="{escape(path)}"><span class="method method-{method.lower()}">{method}</span> {escape(summary)}</a></li>')
        sidebar_parts.append("</ul></li>")
    sidebar_parts.append("</ul></nav>")
    sidebar_parts.append("</aside>")

    # Main: Overview section then tag sections
    main_parts = ['<main class="content">']

    # Overview
    main_parts.append('<section id="overview" class="doc-section overview-section">')
    main_parts.append(f'<h1>Overview</h1>')
    main_parts.append(f'<p class="version-badge">Version {version}</p>')
    if description:
        main_parts.append(f'<div class="overview-description">{description}</div>')
    main_parts.append('<h2 id="overview-modules">Modules</h2>')
    main_parts.append('<div class="module-cards">')
    for tag in sorted_tags:
        tag_id = "tag-" + _slug(tag)
        count = len(by_tag[tag])
        main_parts.append(f'<a href="#{tag_id}" class="module-card"><span class="module-card-name">{escape(tag)}</span><span class="module-card-count">{count} endpoint{"s" if count != 1 else ""}</span></a>')
    main_parts.append("</div></section>")

    # Tag sections and endpoints
    for tag in sorted_tags:
        tag_id = "tag-" + _slug(tag)
        entries = by_tag[tag]
        main_parts.append(f'<section id="{tag_id}" class="doc-section">')
        main_parts.append(f'<h2 class="section-title">{escape(tag)}</h2>')
        for path, method, op, endpoint_id in entries:
            summary = escape(op.get("summary") or "")
            desc = op.get("description") or ""
            if desc:
                desc = desc.replace("\n", "<br>\n")
            params = op.get("parameters") or []
            req_body = op.get("requestBody") if isinstance(op.get("requestBody"), dict) else None
            responses = op.get("responses") or {}

            main_parts.append(f'<article id="{endpoint_id}" class="endpoint-card">')
            main_parts.append(f'<div class="endpoint-header"><span class="method method-{method.lower()}">{method}</span><code class="endpoint-path">{escape(path)}</code></div>')
            if summary:
                main_parts.append(f'<p class="endpoint-summary">{summary}</p>')
            if desc:
                main_parts.append(f'<div class="endpoint-description">{desc}</div>')

            main_parts.append(_how_to_call(method, path, op, base_url))

            main_parts.append(
                '<div class="code-example-block" data-path="' + escape(path) + '" data-method="' + escape(method) + '">'
            )
            main_parts.append("<h4>Implement in your stack</h4>")
            main_parts.append(
                '<p class="code-example-intro">Choose a framework and generate a ready-to-use example (includes auth and request setup).</p>'
            )
            # Tabs: Web then Mobile
            web_stacks = [(v, l) for v, l in STACKS if v in ("react-fetch", "react-axios", "vue3", "nextjs", "angular", "svelte", "vanilla")]
            mobile_stacks = [(v, l) for v, l in STACKS if v in ("react-native", "flutter", "swift-ios", "kotlin-android")]
            main_parts.append('<div class="code-example-tabs-wrap">')
            main_parts.append('<div class="code-example-tabs" role="tablist" aria-label="Frontend stack">')
            for i, (value, label) in enumerate(web_stacks + mobile_stacks):
                active = ' code-example-tab-active' if i == 0 else ''
                main_parts.append(
                    f'<button type="button" role="tab" class="code-example-tab{active}" data-stack="{escape(value)}" aria-selected="{"true" if i == 0 else "false"}">{escape(label)}</button>'
                )
            main_parts.append("</div>")
            main_parts.append('<button type="button" class="code-example-btn">Generate example</button>')
            main_parts.append("</div>")
            main_parts.append('<div class="code-example-output" hidden><pre class="code-example-pre"><code class="code-example-code"></code></pre><button type="button" class="code-example-copy" title="Copy">Copy</button></div>')
            main_parts.append('<div class="code-example-loading" hidden>Generating…</div>')
            main_parts.append('<div class="code-example-error" hidden></div>')
            main_parts.append("</div>")

            if params:
                main_parts.append("<h4>Parameters</h4>")
                main_parts.append(_params_list(params))
            if req_body:
                main_parts.append("<h4>Request body</h4>")
                main_parts.append(_request_body(req_body, openapi_schema))
            if responses:
                main_parts.append("<h4>Responses</h4>")
                main_parts.append(_responses_list(responses, openapi_schema))
            main_parts.append("</article>")
        main_parts.append("</section>")

    main_parts.append("</main>")

    # Right sidebar: On this page (TOC for current section)
    toc_parts = [
        '<aside class="toc">',
        '<p class="toc-title">On this page</p>',
        '<nav class="toc-nav">',
        '<ul class="toc-list">',
        '<li><a href="#overview" class="toc-link" data-id="overview">Overview</a></li>',
        '<li><a href="#overview-modules" class="toc-link" data-id="overview-modules">Modules</a></li>',
    ]
    for tag in sorted_tags:
        tag_id = "tag-" + _slug(tag)
        toc_parts.append(f'<li><a href="#{tag_id}" class="toc-link" data-id="{escape(tag_id)}">{escape(tag)}</a></li>')
        for path, method, op, endpoint_id in by_tag[tag]:
            summary = (op.get("summary") or path)[:36] + ("…" if len((op.get("summary") or path)) > 36 else "")
            toc_parts.append(f'<li class="toc-sublist"><a href="#{endpoint_id}" class="toc-link toc-sublink" data-id="{escape(endpoint_id)}">{escape(method)} {escape(summary)}</a></li>')
    toc_parts.append("</ul></nav></aside>")
    toc_html = "\n".join(toc_parts)

    sidebar_html = "\n".join(sidebar_parts)
    main_html = "\n".join(main_parts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - API Reference</title>
    <style>
        :root {{
            --side-width: 260px;
            --toc-width: 220px;
            --topbar-h: 56px;
            --bg: #0f172a;
            --bg-sub: #1e293b;
            --bg-main: #0f172a;
            --bg-card: #1e293b;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --accent-hover: #60a5fa;
            --border: #334155;
            --font: 'Inter', system-ui, -apple-system, sans-serif;
        }}
        * {{ box-sizing: border-box; }}
        .docs-body {{ margin: 0; font-family: var(--font); line-height: 1.65; color: var(--text); background: var(--bg-main); min-height: 100vh; }}
        .topbar {{
            position: fixed; top: 0; left: 0; right: 0; height: var(--topbar-h); z-index: 200;
            background: var(--bg); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 1.5rem; gap: 2rem;
        }}
        .topbar-logo {{ color: var(--text); text-decoration: none; font-weight: 700; font-size: 1.1rem; }}
        .topbar-logo:hover {{ color: var(--accent-hover); }}
        .topbar-tabs {{ display: flex; gap: 0.5rem; }}
        .topbar-tab {{ color: var(--text-muted); text-decoration: none; font-size: 0.9rem; padding: 0.4rem 0.75rem; border-radius: 6px; }}
        .topbar-tab:hover {{ color: var(--text); }}
        .topbar-tab.active {{ color: var(--accent); font-weight: 500; }}
        .topbar-search {{ flex: 1; max-width: 320px; }}
        .topbar-search-placeholder {{ color: var(--text-muted); font-size: 0.875rem; }}
        .topbar-search-placeholder kbd {{ background: var(--bg-sub); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem; margin-left: 0.25rem; }}
        .topbar-swagger {{ color: var(--accent); text-decoration: none; font-size: 0.875rem; }}
        .topbar-swagger:hover {{ color: var(--accent-hover); }}
        .sidebar {{
            width: var(--side-width); position: fixed; top: var(--topbar-h); left: 0; bottom: 0; overflow-y: auto; z-index: 100;
            background: var(--bg); border-right: 1px solid var(--border); padding: 1rem 0;
        }}
        .sidebar-category {{ font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em; color: var(--text-muted); margin: 1.25rem 1rem 0.5rem; text-transform: uppercase; }}
        .sidebar-list {{ list-style: none; margin: 0; padding: 0; }}
        .sidebar-list > li {{ margin: 0; }}
        .sidebar-link {{ display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; color: var(--text-muted); text-decoration: none; font-size: 0.875rem; transition: color 0.15s, background 0.15s; border-left: 3px solid transparent; }}
        .sidebar-link:hover {{ color: var(--accent-hover); }}
        .sidebar-link-overview {{ color: var(--text); font-weight: 500; }}
        .sidebar-link.active {{ color: var(--accent); background: rgba(59,130,246,0.1); border-left-color: var(--accent); }}
        .sidebar-icon {{ font-size: 0.9rem; opacity: 0.9; }}
        .sidebar-tag-wrap {{ margin-top: 0.25rem; }}
        .sidebar-tag-toggle {{ width: 100%; display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; background: none; border: none; color: var(--text); font-size: 0.875rem; font-weight: 500; cursor: pointer; text-align: left; font-family: inherit; }}
        .sidebar-tag-toggle:hover {{ color: var(--accent-hover); }}
        .sidebar-arrow {{ margin-left: auto; font-size: 0.65rem; transition: transform 0.2s; }}
        .sidebar-tag-wrap.collapsed .sidebar-arrow {{ transform: rotate(-90deg); }}
        .sidebar-tag-wrap.collapsed .sidebar-sublist {{ display: none; }}
        .sidebar-sublist {{ list-style: none; margin: 0; padding: 0 0 0 1.5rem; border-left: 1px solid var(--border); margin-left: 1rem; }}
        .sidebar-sublist .sublink {{ font-size: 0.8rem; padding: 0.4rem 0.5rem; }}
        .sidebar-sublist .sublink .method {{ font-size: 0.65rem; margin-right: 0.25rem; }}
        .content-wrap {{ display: flex; margin-left: var(--side-width); margin-top: var(--topbar-h); min-height: calc(100vh - var(--topbar-h)); }}
        .content {{ flex: 1; padding: 2rem 2.5rem 4rem; max-width: 52rem; min-width: 0; }}
        .doc-section {{ margin-bottom: 3rem; }}
        .doc-section h1 {{ font-size: 1.75rem; margin: 0 0 0.5rem; color: var(--text); font-weight: 600; }}
        .doc-section h2 {{ font-size: 1.25rem; margin: 2rem 0 1rem; color: var(--text); padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); font-weight: 600; }}
        .doc-section h2.section-title {{ margin-top: 0; }}
        .doc-section h4 {{ font-size: 0.9rem; margin: 1.25rem 0 0.5rem; color: var(--text-muted); font-weight: 600; }}
        .version-badge {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem; }}
        .overview-description {{ margin-bottom: 1.5rem; color: var(--text-muted); line-height: 1.7; }}
        .module-cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; margin-top: 1rem; }}
        .module-card {{
            display: block; padding: 1rem 1.25rem; background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px;
            text-decoration: none; color: var(--text); transition: border-color 0.2s, box-shadow 0.2s;
        }}
        .module-card:hover {{ border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }}
        .module-card-name {{ font-weight: 600; display: block; }}
        .module-card-count {{ font-size: 0.8rem; color: var(--text-muted); }}
        .endpoint-card {{
            background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem;
        }}
        .endpoint-header {{ display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.75rem; }}
        .endpoint-path {{ font-size: 0.9rem; word-break: break-all; background: var(--bg); color: var(--text-muted); padding: 0.25rem 0.5rem; border-radius: 6px; }}
        .method {{ font-size: 0.65rem; font-weight: 700; padding: 0.2rem 0.4rem; border-radius: 4px; letter-spacing: 0.02em; }}
        .method-get {{ background: #1e3a5f; color: #7dd3fc; }}
        .method-post {{ background: #14532d; color: #86efac; }}
        .method-put {{ background: #431407; color: #fdba74; }}
        .method-patch {{ background: #4c0519; color: #f9a8d4; }}
        .method-delete {{ background: #450a0a; color: #fca5a5; }}
        .endpoint-summary {{ font-weight: 500; margin: 0 0 0.5rem; color: var(--text); }}
        .endpoint-description {{ color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem; }}
        .how-to-call {{ background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
        .how-to-call .request-line {{ margin: 0 0 0.5rem; font-size: 0.85rem; color: var(--text-muted); }}
        .how-to-call .code-block {{ background: #0f172a; color: #e2e8f0; padding: 0.75rem 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.8rem; margin: 0.25rem 0 0; border: 1px solid var(--border); }}
        .how-to-call .call-headers {{ margin: 0.75rem 0 0.25rem; font-size: 0.85rem; color: var(--text-muted); }}
        .how-to-call .call-body {{ margin: 0.5rem 0 0; font-size: 0.85rem; color: var(--text-muted); }}
        .schema-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 0.5rem 0; border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }}
        .schema-table th, .schema-table td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); color: var(--text-muted); }}
        .schema-table th {{ background: var(--bg); color: var(--text); font-weight: 600; }}
        .schema-table .nested-schema {{ padding-left: 1rem; border-left: 2px solid var(--border); }}
        ul.response-list {{ list-style: none; padding: 0; margin: 0; }}
        ul.response-list li.response-block {{ margin-bottom: 1rem; padding: 1rem; background: var(--bg); border-radius: 8px; border-left: 4px solid var(--accent); color: var(--text-muted); }}
        code {{ background: var(--bg); color: var(--text-muted); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.85em; border: 1px solid var(--border); }}
        .schema-ref, .schema-type {{ margin: 0.25rem 0; color: var(--text-muted); font-size: 0.85rem; }}
        .code-example-block {{ margin: 1.25rem 0; padding: 1rem; background: var(--bg); border: 1px solid var(--border); border-radius: 10px; }}
        .code-example-block h4 {{ margin-top: 0; color: var(--text); }}
        .code-example-intro {{ color: var(--text-muted); font-size: 0.875rem; margin: 0 0 0.75rem; }}
        .code-example-tabs-wrap {{ display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin-bottom: 0.75rem; }}
        .code-example-tabs {{ display: flex; flex-wrap: wrap; gap: 0.25rem; align-items: center; }}
        .code-example-tab {{ padding: 0.35rem 0.65rem; border: 1px solid var(--border); border-radius: 6px; font-size: 0.8rem; background: var(--bg-card); color: var(--text-muted); cursor: pointer; transition: background 0.15s, color 0.15s; }}
        .code-example-tab:hover {{ color: var(--text); background: var(--bg); }}
        .code-example-tab.code-example-tab-active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
        .code-example-btn {{ padding: 0.45rem 0.9rem; background: var(--accent); color: #fff; border: none; border-radius: 6px; font-size: 0.875rem; font-weight: 500; cursor: pointer; }}
        .code-example-btn:hover {{ background: var(--accent-hover); }}
        .code-example-btn:disabled {{ opacity: 0.7; cursor: not-allowed; }}
        .code-example-output {{ position: relative; margin-top: 0.5rem; }}
        .code-example-pre {{ background: #0f172a; color: #e2e8f0; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.8rem; line-height: 1.5; margin: 0; border: 1px solid var(--border); }}
        .code-example-copy {{ position: absolute; top: 0.5rem; right: 0.5rem; padding: 0.25rem 0.5rem; font-size: 0.75rem; background: var(--border); color: var(--text); border: none; border-radius: 4px; cursor: pointer; }}
        .code-example-copy:hover {{ background: var(--text-muted); }}
        .code-example-loading {{ color: var(--text-muted); font-size: 0.875rem; margin-top: 0.5rem; }}
        .code-example-error {{ color: #f87171; font-size: 0.875rem; margin-top: 0.5rem; }}
        .toc {{ width: var(--toc-width); min-width: var(--toc-width); padding: 2rem 1rem 2rem 0; position: sticky; top: calc(var(--topbar-h) + 1rem); align-self: flex-start; }}
        .toc-title {{ font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em; color: var(--text-muted); margin: 0 0 0.75rem; text-transform: uppercase; }}
        .toc-list {{ list-style: none; margin: 0; padding: 0; }}
        .toc-link {{ display: block; padding: 0.35rem 0; color: var(--text-muted); text-decoration: none; font-size: 0.8rem; transition: color 0.15s; }}
        .toc-link:hover {{ color: var(--accent-hover); }}
        .toc-link.active {{ color: var(--accent); font-weight: 500; }}
        .toc-sublist {{ padding-left: 0.75rem; }}
        .toc-sublink {{ font-size: 0.75rem; }}
        @media (max-width: 1024px) {{ .toc {{ display: none; }} .content {{ padding-right: 1.5rem; }} }}
        @media (max-width: 768px) {{
            .sidebar {{ transform: translateX(-100%); transition: transform 0.2s; }}
            .sidebar.open {{ transform: translateX(0); }}
            .content-wrap {{ margin-left: 0; }}
            .content {{ padding: 1rem; }}
        }}
    </style>
</head>
<body class="docs-body">
    {sidebar_html}
    <div class="content-wrap">
        {main_html}
        {toc_html}
    </div>
    <script>
        (function() {{
            var links = document.querySelectorAll('.sidebar-link, .sublink');
            function highlight() {{
                var id = (location.hash || '#overview').slice(1);
                links.forEach(function(a) {{
                    var href = (a.getAttribute('href') || '').slice(1);
                    a.classList.toggle('active', href === id);
                }});
                document.querySelectorAll('.toc-link').forEach(function(a) {{
                    var dataId = a.getAttribute('data-id');
                    a.classList.toggle('active', dataId === id);
                }});
            }}
            window.addEventListener('hashchange', highlight);
            window.addEventListener('load', highlight);
            document.querySelectorAll('.sidebar-tag-toggle').forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                    var wrap = btn.closest('.sidebar-tag-wrap');
                    wrap.classList.toggle('collapsed');
                    btn.setAttribute('aria-expanded', wrap.classList.contains('collapsed') ? 'false' : 'true');
                }});
            }});
        }})();
        (function() {{
            var base = window.location.origin;
            document.querySelectorAll('.code-example-block').forEach(function(block) {{
                var path = block.getAttribute('data-path');
                var method = block.getAttribute('data-method');
                var tabList = block.querySelector('.code-example-tabs');
                var btn = block.querySelector('.code-example-btn');
                function getSelectedStack() {{
                    var active = block.querySelector('.code-example-tab.code-example-tab-active');
                    return active ? active.getAttribute('data-stack') : (tabList && tabList.querySelector('.code-example-tab') && tabList.querySelector('.code-example-tab').getAttribute('data-stack'));
                }}
                if (tabList) {{
                    tabList.querySelectorAll('.code-example-tab').forEach(function(tab) {{
                        tab.addEventListener('click', function() {{
                            tabList.querySelectorAll('.code-example-tab').forEach(function(t) {{ t.classList.remove('code-example-tab-active'); t.setAttribute('aria-selected', 'false'); }});
                            tab.classList.add('code-example-tab-active'); tab.setAttribute('aria-selected', 'true');
                        }});
                    }});
                }}
                var output = block.querySelector('.code-example-output');
                var codeEl = block.querySelector('.code-example-code');
                var copyBtn = block.querySelector('.code-example-copy');
                var loading = block.querySelector('.code-example-loading');
                var errEl = block.querySelector('.code-example-error');
                function showOutput(show) {{ output.hidden = !show; loading.hidden = true; errEl.hidden = true; }}
                function showErr(msg) {{ errEl.textContent = msg; errEl.hidden = false; loading.hidden = true; output.hidden = true; }}
                btn.addEventListener('click', function() {{
                    btn.disabled = true;
                    loading.hidden = false;
                    output.hidden = true;
                    errEl.hidden = true;
                    fetch(base + '/api-reference/generate-example', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ path: path, method: method, stack: getSelectedStack(), base_url: base }})
                    }}).then(function(r) {{
                        return r.json().then(function(d) {{
                            if (!r.ok) return Promise.reject({{ detail: d.detail || d.message || r.statusText }});
                            return d;
                        }});
                    }}).then(function(d) {{
                        codeEl.textContent = d.code || '';
                        showOutput(!!d.code);
                        btn.disabled = false;
                    }}).catch(function(e) {{
                        var msg = (e && (e.detail || e.message)) || 'Failed to generate example';
                        if (typeof msg === 'object') msg = JSON.stringify(msg);
                        showErr(msg);
                        btn.disabled = false;
                    }});
                }});
                copyBtn.addEventListener('click', function() {{
                    var text = codeEl.textContent;
                    if (text && navigator.clipboard && navigator.clipboard.writeText) {{
                        navigator.clipboard.writeText(text);
                        copyBtn.textContent = 'Copied!';
                        setTimeout(function() {{ copyBtn.textContent = 'Copy'; }}, 2000);
                    }}
                }});
            }});
        }})();
    </script>
</body>
</html>"""
    return html
