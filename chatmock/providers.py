from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List
from urllib.parse import urljoin

import requests
from flask import Response, jsonify, make_response

from .http import build_cors_headers
from .responses_api import canonicalize_responses_input


OPENAI_COMPAT_PROVIDER_PROTOCOL = "openai"
PROVIDER_CHAT_PASSTHROUGH_FIELDS = (
    "temperature",
    "top_p",
    "max_tokens",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "enable_thinking",
    "thinking",
    "reasoning_effort",
)


@dataclass(frozen=True)
class ProviderModel:
    public_id: str
    upstream_id: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str | None
    models: tuple[ProviderModel, ...]
    enabled: bool
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer "
    chat_completions_path: str = "/chat/completions"
    completions_path: str = "/completions"
    responses_path: str | None = None


@dataclass(frozen=True)
class ProviderRoute:
    provider: ProviderConfig
    requested_model: str
    upstream_model: str
    public_model: str


DEFAULT_ZAI_MODELS = (
    "glm-5.2",
    "glm-5.1",
    "glm-5",
    "glm-5-turbo",
    "glm-4.7",
    "glm-4.5-air",
)
DEFAULT_XIAOMI_MODELS = (
    "mimo-v2.5-pro",
    "mimo-v2.5",
)
DEFAULT_DEEPSEEK_MODELS = (
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
)
DEFAULT_LOCAL_MODELS: tuple[str, ...] = ()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _env_api_key(name: str) -> str | None:
    value = os.getenv(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _split_embedded_base_url(api_key: str | None) -> tuple[str | None, str | None]:
    if not isinstance(api_key, str) or not api_key.startswith("("):
        return None, api_key
    close = api_key.find(")")
    if close <= 1:
        return None, api_key
    maybe_url = api_key[1:close].strip()
    key = api_key[close + 1 :].strip()
    if not (maybe_url.startswith("http://") or maybe_url.startswith("https://")):
        return None, api_key
    if maybe_url.endswith("/anthropic"):
        maybe_url = maybe_url[: -len("/anthropic")] + "/v1"
    return maybe_url, key or None


def _models_from_ids(ids: Iterable[str], provider_name: str) -> tuple[ProviderModel, ...]:
    models: List[ProviderModel] = []
    for model_id in ids:
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        upstream_id = model_id.strip()
        public_id = upstream_id
        prefixed = f"{provider_name}/{upstream_id}"
        aliases = (prefixed,) if prefixed != public_id else ()
        models.append(ProviderModel(public_id=public_id, upstream_id=upstream_id, aliases=aliases))
    return tuple(models)


def _preset_provider(
    *,
    name: str,
    base_url_env: str,
    api_key_env: str,
    models_env: str,
    enable_env: str,
    default_base_url: str,
    default_models: tuple[str, ...],
    responses_path: str | None = None,
    require_api_key: bool = True,
) -> ProviderConfig:
    api_key = _env_api_key(api_key_env)
    embedded_base_url, api_key = _split_embedded_base_url(api_key)
    models = _split_csv(os.getenv(models_env)) or default_models
    enabled = _truthy(os.getenv(enable_env)) or bool(api_key) or bool(_split_csv(os.getenv(models_env)))
    if require_api_key and not api_key and not _truthy(os.getenv(enable_env)):
        enabled = False
    return ProviderConfig(
        name=name,
        base_url=_normalize_base_url(embedded_base_url or os.getenv(base_url_env) or default_base_url),
        api_key=api_key,
        models=_models_from_ids(models, name),
        enabled=enabled,
        responses_path=responses_path,
    )


def _parse_custom_providers() -> tuple[ProviderConfig, ...]:
    raw = os.getenv("CHATMOCK_PROVIDERS_JSON")
    if not isinstance(raw, str) or not raw.strip():
        return ()
    try:
        parsed = json.loads(raw)
    except Exception:
        return ()
    entries = parsed if isinstance(parsed, list) else parsed.get("providers") if isinstance(parsed, dict) else None
    if not isinstance(entries, list):
        return ()

    out: List[ProviderConfig] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        base_url = entry.get("base_url") or entry.get("baseURL")
        if not isinstance(name, str) or not name.strip() or not isinstance(base_url, str) or not base_url.strip():
            continue
        api_key = entry.get("api_key")
        api_key_env = entry.get("api_key_env")
        if not isinstance(api_key, str) or not api_key.strip():
            api_key = _env_api_key(api_key_env) if isinstance(api_key_env, str) else None
        models = entry.get("models")
        if isinstance(models, str):
            model_ids = _split_csv(models)
        elif isinstance(models, list):
            model_ids = tuple(item for item in models if isinstance(item, str) and item.strip())
        else:
            model_ids = ()
        enabled = entry.get("enabled")
        out.append(
            ProviderConfig(
                name=name.strip().lower(),
                base_url=_normalize_base_url(base_url),
                api_key=api_key.strip() if isinstance(api_key, str) and api_key.strip() else None,
                models=_models_from_ids(model_ids, name.strip().lower()),
                enabled=bool(enabled) if isinstance(enabled, bool) else True,
                api_key_header=entry.get("api_key_header") if isinstance(entry.get("api_key_header"), str) else "Authorization",
                api_key_prefix=entry.get("api_key_prefix") if isinstance(entry.get("api_key_prefix"), str) else "Bearer ",
                chat_completions_path=entry.get("chat_completions_path")
                if isinstance(entry.get("chat_completions_path"), str)
                else "/chat/completions",
                completions_path=entry.get("completions_path") if isinstance(entry.get("completions_path"), str) else "/completions",
                responses_path=entry.get("responses_path") if isinstance(entry.get("responses_path"), str) else None,
            )
        )
    return tuple(out)


def load_provider_configs() -> tuple[ProviderConfig, ...]:
    providers = [
        _preset_provider(
            name="zai",
            base_url_env="CHATMOCK_ZAI_BASE_URL",
            api_key_env="CHATMOCK_ZAI_API_KEY",
            models_env="CHATMOCK_ZAI_MODELS",
            enable_env="CHATMOCK_ENABLE_ZAI",
            default_base_url="https://api.z.ai/api/coding/paas/v4",
            default_models=DEFAULT_ZAI_MODELS,
        ),
        _preset_provider(
            name="xiaomi",
            base_url_env="CHATMOCK_XIAOMI_BASE_URL",
            api_key_env="CHATMOCK_XIAOMI_API_KEY",
            models_env="CHATMOCK_XIAOMI_MODELS",
            enable_env="CHATMOCK_ENABLE_XIAOMI",
            default_base_url="https://token-plan-sgp.xiaomimimo.com/v1",
            default_models=DEFAULT_XIAOMI_MODELS,
        ),
        _preset_provider(
            name="deepseek",
            base_url_env="CHATMOCK_DEEPSEEK_BASE_URL",
            api_key_env="CHATMOCK_DEEPSEEK_API_KEY",
            models_env="CHATMOCK_DEEPSEEK_MODELS",
            enable_env="CHATMOCK_ENABLE_DEEPSEEK",
            default_base_url="https://api.deepseek.com",
            default_models=DEFAULT_DEEPSEEK_MODELS,
        ),
        _preset_provider(
            name="ollama",
            base_url_env="CHATMOCK_OLLAMA_BASE_URL",
            api_key_env="CHATMOCK_OLLAMA_API_KEY",
            models_env="CHATMOCK_OLLAMA_MODELS",
            enable_env="CHATMOCK_ENABLE_OLLAMA",
            default_base_url="http://localhost:11434/v1",
            default_models=DEFAULT_LOCAL_MODELS,
            responses_path="/responses",
            require_api_key=False,
        ),
        _preset_provider(
            name="lmstudio",
            base_url_env="CHATMOCK_LM_STUDIO_BASE_URL",
            api_key_env="CHATMOCK_LM_STUDIO_API_KEY",
            models_env="CHATMOCK_LM_STUDIO_MODELS",
            enable_env="CHATMOCK_ENABLE_LM_STUDIO",
            default_base_url="http://localhost:1234/v1",
            default_models=DEFAULT_LOCAL_MODELS,
            responses_path="/responses",
            require_api_key=False,
        ),
    ]
    providers.extend(_parse_custom_providers())
    return tuple(provider for provider in providers if provider.enabled)


def iter_provider_models() -> tuple[tuple[str, str], ...]:
    rows: List[tuple[str, str]] = []
    seen: set[str] = set()
    for provider in load_provider_configs():
        for model in provider.models:
            if model.public_id in seen:
                continue
            seen.add(model.public_id)
            rows.append((model.public_id, provider.name))
    return tuple(rows)


def _route_from_prefixed_model(provider: ProviderConfig, requested: str) -> ProviderRoute | None:
    prefix = f"{provider.name}/"
    alt_prefixes = (prefix,)
    if provider.name == "lmstudio":
        alt_prefixes = (prefix, "lm-studio/")
    for candidate_prefix in alt_prefixes:
        if requested.startswith(candidate_prefix) and len(requested) > len(candidate_prefix):
            upstream = requested[len(candidate_prefix) :]
            return ProviderRoute(provider, requested, upstream, requested)
    return None


def find_provider_route(model: Any) -> ProviderRoute | None:
    if not isinstance(model, str) or not model.strip():
        return None
    requested = model.strip()
    lowered = requested.lower()
    for provider in load_provider_configs():
        prefixed = _route_from_prefixed_model(provider, lowered)
        if prefixed is not None:
            return ProviderRoute(provider, requested, prefixed.upstream_model, requested)
        for provider_model in provider.models:
            names = (provider_model.public_id, provider_model.upstream_id, *provider_model.aliases)
            if lowered in (name.lower() for name in names):
                return ProviderRoute(
                    provider=provider,
                    requested_model=requested,
                    upstream_model=provider_model.upstream_id,
                    public_model=provider_model.public_id,
                )
    return None


def _provider_headers(provider: ProviderConfig) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers[provider.api_key_header] = f"{provider.api_key_prefix}{provider.api_key}"
    return headers


def _provider_url(provider: ProviderConfig, path: str) -> str:
    normalized_path = path.lstrip("/")
    return urljoin(provider.base_url.rstrip("/") + "/", normalized_path)


def _cors_response(body: Any, status: int = 200) -> Response:
    resp = make_response(jsonify(body), status)
    for key, value in build_cors_headers().items():
        resp.headers.setdefault(key, value)
    return resp


def _copy_upstream_response(upstream: requests.Response, *, stream: bool = False) -> Response:
    headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in ("content-encoding", "content-length", "transfer-encoding", "connection")
    }
    if stream:
        resp = Response(
            upstream.iter_content(chunk_size=None),
            status=upstream.status_code,
            headers=headers,
            mimetype=upstream.headers.get("Content-Type") or "text/event-stream",
        )
    else:
        resp = Response(
            upstream.content,
            status=upstream.status_code,
            headers=headers,
            mimetype=upstream.headers.get("Content-Type") or "application/json",
        )
    for key, value in build_cors_headers().items():
        resp.headers.setdefault(key, value)
    return resp


def _post_provider_json(
    route: ProviderRoute,
    path: str,
    payload: Dict[str, Any],
    *,
    stream: bool,
) -> tuple[requests.Response | None, Response | None]:
    try:
        upstream = requests.post(
            _provider_url(route.provider, path),
            headers=_provider_headers(route.provider),
            json=payload,
            stream=stream,
            timeout=600,
        )
    except requests.RequestException as exc:
        return None, _cors_response({"error": {"message": f"{route.provider.name} request failed: {exc}"}}, 502)
    return upstream, None


def proxy_provider_endpoint(route: ProviderRoute, path: str, payload: Dict[str, Any]) -> Response:
    outbound = dict(payload)
    outbound["model"] = route.upstream_model
    stream = bool(outbound.get("stream"))
    upstream, error = _post_provider_json(route, path, outbound, stream=stream)
    if error is not None:
        return error
    assert upstream is not None
    return _copy_upstream_response(upstream, stream=stream)


def _responses_input_to_messages(raw_input: Any) -> List[Dict[str, Any]]:
    canonical = canonicalize_responses_input(raw_input)
    if not isinstance(canonical, list):
        return []
    messages: List[Dict[str, Any]] = []
    for item in canonical:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        role = item.get("role") if item.get("role") in ("system", "assistant", "user") else "user"
        content = item.get("content")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue
        parts: List[Dict[str, Any]] = []
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype in ("input_text", "output_text"):
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append({"type": "text", "text": text})
                elif ptype == "input_image":
                    image_url = part.get("image_url")
                    if isinstance(image_url, str):
                        parts.append({"type": "image_url", "image_url": {"url": image_url}})
        if len(parts) == 1 and parts[0].get("type") == "text":
            messages.append({"role": role, "content": parts[0].get("text") or ""})
        elif parts:
            messages.append({"role": role, "content": parts})
    return messages


def _responses_payload_to_chat_payload(payload: Dict[str, Any], route: ProviderRoute) -> Dict[str, Any]:
    messages = _responses_input_to_messages(payload.get("input"))
    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.insert(0, {"role": "system", "content": instructions.strip()})

    chat_payload: Dict[str, Any] = {
        "model": route.upstream_model,
        "messages": messages or [{"role": "user", "content": ""}],
        "stream": bool(payload.get("stream")),
    }
    for key in PROVIDER_CHAT_PASSTHROUGH_FIELDS:
        if key in payload:
            chat_payload[key] = payload[key]
    if "max_output_tokens" in payload and "max_tokens" not in chat_payload:
        chat_payload["max_tokens"] = payload["max_output_tokens"]
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        chat_payload["response_format"] = response_format
    return chat_payload


def _chat_completion_to_response_object(
    body: Dict[str, Any],
    *,
    requested_model: str,
) -> Dict[str, Any]:
    choice = {}
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            choice = first
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    content = message.get("content") if isinstance(message.get("content"), str) else ""
    output_item = {
        "type": "message",
        "role": "assistant",
        "id": f"msg_{uuid.uuid4().hex}",
        "content": [{"type": "output_text", "text": content}],
    }
    response_obj: Dict[str, Any] = {
        "id": body.get("id") if isinstance(body.get("id"), str) else f"resp_{uuid.uuid4().hex}",
        "object": "response",
        "created_at": body.get("created") if isinstance(body.get("created"), int) else int(time.time()),
        "status": "completed",
        "model": requested_model,
        "output": [output_item],
    }
    usage = body.get("usage")
    if isinstance(usage, dict):
        response_obj["usage"] = usage
    return response_obj


def _stream_chat_as_responses(upstream: requests.Response, *, requested_model: str) -> Iterable[bytes]:
    response_id = f"resp_{uuid.uuid4().hex}"
    output_id = f"msg_{uuid.uuid4().hex}"
    created = int(time.time())
    created_evt = {
        "type": "response.created",
        "response": {
            "id": response_id,
            "object": "response",
            "created_at": created,
            "status": "in_progress",
            "model": requested_model,
            "output": [],
        },
    }
    yield f"data: {json.dumps(created_evt)}\n\n".encode("utf-8")
    try:
        for raw in upstream.iter_lines(decode_unicode=False):
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
            if not line.startswith("data: "):
                continue
            data = line[len("data: ") :].strip()
            if not data:
                continue
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            choices = chunk.get("choices") if isinstance(chunk, dict) else None
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0] if isinstance(choices[0], dict) else {}
            delta = first.get("delta") if isinstance(first.get("delta"), dict) else {}
            text = delta.get("content")
            if isinstance(text, str) and text:
                evt = {
                    "type": "response.output_text.delta",
                    "item_id": output_id,
                    "output_index": 0,
                    "content_index": 0,
                    "delta": text,
                }
                yield f"data: {json.dumps(evt)}\n\n".encode("utf-8")
    finally:
        upstream.close()

    completed_evt = {
        "type": "response.completed",
        "response": {
            "id": response_id,
            "object": "response",
            "created_at": created,
            "status": "completed",
            "model": requested_model,
            "output": [],
        },
    }
    yield f"data: {json.dumps(completed_evt)}\n\n".encode("utf-8")
    yield b"data: [DONE]\n\n"


def proxy_provider_responses(route: ProviderRoute, payload: Dict[str, Any]) -> Response:
    if route.provider.responses_path:
        outbound = dict(payload)
        outbound["model"] = route.upstream_model
        upstream, error = _post_provider_json(
            route,
            route.provider.responses_path,
            outbound,
            stream=bool(outbound.get("stream")),
        )
        if error is not None:
            return error
        assert upstream is not None
        if upstream.status_code < 400:
            return _copy_upstream_response(upstream, stream=bool(outbound.get("stream")))
        upstream.close()

    chat_payload = _responses_payload_to_chat_payload(payload, route)
    upstream, error = _post_provider_json(
        route,
        route.provider.chat_completions_path,
        chat_payload,
        stream=bool(chat_payload.get("stream")),
    )
    if error is not None:
        return error
    assert upstream is not None
    if upstream.status_code >= 400:
        return _copy_upstream_response(upstream, stream=False)

    if bool(chat_payload.get("stream")):
        resp = Response(
            _stream_chat_as_responses(upstream, requested_model=route.requested_model),
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for key, value in build_cors_headers().items():
            resp.headers.setdefault(key, value)
        return resp

    try:
        body = upstream.json()
    except Exception:
        body = {"error": {"message": "Provider response was not valid JSON"}}
        return _cors_response(body, 502)
    finally:
        upstream.close()
    if not isinstance(body, dict):
        return _cors_response({"error": {"message": "Provider response was not a JSON object"}}, 502)
    return _cors_response(_chat_completion_to_response_object(body, requested_model=route.requested_model), 200)
