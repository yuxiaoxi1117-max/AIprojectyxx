"""
Dify Multi-App Pipeline for Open WebUI
Bridges Open WebUI (OpenAI API format) <-> Multiple Dify Chat Apps
Config: /app/dify_apps.json
"""

import json
import os
import time
import uuid
from typing import Generator, Iterator, List, Union

import requests
from pydantic import BaseModel


class Pipeline:
    class Valves(BaseModel):
        DIFY_BASE_URL: str = ""
        APPS_CONFIG_FILE: str = "/app/dify_apps.json"

    def __init__(self):
        self.type = "manifold"
        self.name = "Dify: "

        self.valves = self.Valves(
            DIFY_BASE_URL=os.getenv("DIFY_BASE_URL", ""),
        )

        self._apps: list[dict] = self._load_apps()
        # key: "{chat_id}:{app_id}" -> dify conversation_id
        self._conv_map: dict[str, str] = {}

    def _load_apps(self) -> list[dict]:
        try:
            with open(self.valves.APPS_CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"[dify_pipeline] failed to load apps config: {e}")
            return []

    async def on_startup(self):
        self._apps = self._load_apps()
        print(f"[dify_pipeline] loaded {len(self._apps)} app(s), base={self.valves.DIFY_BASE_URL}")

    async def on_shutdown(self):
        print("[dify_pipeline] shutdown")

    async def on_valves_updated(self):
        self._apps = self._load_apps()

    def pipelines(self) -> list:
        return [{"id": app["id"], "name": app["name"]} for app in self._apps]

    def _get_app(self, app_id: str) -> dict | None:
        for app in self._apps:
            if app["id"] == app_id:
                return app
        return None

    def _headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _last_user_message(self, messages: List[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    return " ".join(
                        b.get("text", "") for b in content if b.get("type") == "text"
                    )
                return str(content)
        return ""

    def _stream(
        self, query: str, conv_id: str, user_id: str, api_key: str
    ) -> Generator[str, None, str]:
        url = f"{self.valves.DIFY_BASE_URL}/v1/chat-messages"
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "streaming",
            "conversation_id": conv_id,
            "user": user_id,
        }

        resp = requests.post(
            url, json=payload, headers=self._headers(api_key), stream=True, timeout=120
        )
        resp.raise_for_status()

        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        new_conv_id = conv_id

        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str:
                continue

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            etype = event.get("event")

            if etype == "message":
                if not new_conv_id and event.get("conversation_id"):
                    new_conv_id = event["conversation_id"]
                chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "dify",
                    "choices": [{"index": 0, "delta": {"content": event.get("answer", "")}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            elif etype == "message_end":
                if event.get("conversation_id"):
                    new_conv_id = event["conversation_id"]
                chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "dify",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"

            elif etype == "error":
                raise RuntimeError(event.get("message", "Dify error"))

        return new_conv_id

    def _blocking(self, query: str, conv_id: str, user_id: str, api_key: str) -> tuple[str, str]:
        url = f"{self.valves.DIFY_BASE_URL}/v1/chat-messages"
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "blocking",
            "conversation_id": conv_id,
            "user": user_id,
        }
        resp = requests.post(
            url, json=payload, headers=self._headers(api_key), timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("answer", ""), data.get("conversation_id", conv_id)

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        app = self._get_app(model_id)
        if not app:
            return f"Error: app '{model_id}' not found in dify_apps.json"

        api_key = app["api_key"]
        chat_id = body.get("chat_id", "default")
        user_id = body.get("user", {})
        if isinstance(user_id, dict):
            user_id = user_id.get("id", "openwebui-user")

        conv_key = f"{chat_id}:{model_id}"
        dify_conv_id = self._conv_map.get(conv_key, "")
        query = self._last_user_message(messages) or user_message

        try:
            if body.get("stream", True):
                new_conv_id_holder = [dify_conv_id]

                def _gen():
                    gen = self._stream(query, dify_conv_id, str(user_id), api_key)
                    for chunk in gen:
                        yield chunk
                    # gen.return value not accessible via for-loop; use send protocol
                    # Instead, read updated conv_id from response events (handled inside _stream)

                # Wrap to capture new conv_id
                def _gen_with_save():
                    last_conv_id = dify_conv_id
                    url = f"{self.valves.DIFY_BASE_URL}/v1/chat-messages"
                    payload = {
                        "inputs": {},
                        "query": query,
                        "response_mode": "streaming",
                        "conversation_id": dify_conv_id,
                        "user": str(user_id),
                    }
                    resp = requests.post(
                        url, json=payload, headers=self._headers(api_key),
                        stream=True, timeout=120
                    )
                    resp.raise_for_status()
                    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"

                    for raw in resp.iter_lines():
                        if not raw:
                            continue
                        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("event")
                        if etype == "message":
                            if not last_conv_id and event.get("conversation_id"):
                                last_conv_id = event["conversation_id"]
                            out = {
                                "id": chunk_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model_id,
                                "choices": [{"index": 0, "delta": {"content": event.get("answer", "")}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(out)}\n\n"
                        elif etype == "message_end":
                            if event.get("conversation_id"):
                                last_conv_id = event["conversation_id"]
                            out = {
                                "id": chunk_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model_id,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                            }
                            yield f"data: {json.dumps(out)}\n\n"
                            yield "data: [DONE]\n\n"
                            self._conv_map[conv_key] = last_conv_id
                        elif etype == "error":
                            yield f"data: {json.dumps({'error': event.get('message', 'Dify error')})}\n\n"

                return _gen_with_save()
            else:
                answer, new_conv_id = self._blocking(query, dify_conv_id, str(user_id), api_key)
                self._conv_map[conv_key] = new_conv_id
                return answer

        except Exception as e:
            err = str(e)
            print(f"[dify_pipeline] error for app={model_id}: {err}")
            return f"Error: {err}"
