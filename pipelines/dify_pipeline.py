"""
Dify Pipeline for Open WebUI
Bridges Open WebUI (OpenAI API format) <-> Dify Chat API
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
        DIFY_BASE_URL: str = "http://192.168.1.100"
        DIFY_API_KEY: str = ""
        DIFY_APP_NAME: str = "Dify"

    def __init__(self):
        self.type = "manifold"
        self.name = "Dify: "

        self.valves = self.Valves(
            DIFY_BASE_URL=os.getenv("DIFY_BASE_URL", "http://192.168.1.100"),
            DIFY_API_KEY=os.getenv("DIFY_API_KEY", ""),
            DIFY_APP_NAME=os.getenv("DIFY_APP_NAME", "Dify"),
        )

        # conversation_id map: Open WebUI chat_id -> Dify conversation_id
        self._conv_map: dict[str, str] = {}

    async def on_startup(self):
        print(f"[dify_pipeline] startup, base_url={self.valves.DIFY_BASE_URL}")

    async def on_shutdown(self):
        print("[dify_pipeline] shutdown")

    async def on_valves_updated(self):
        print("[dify_pipeline] valves updated")

    def pipelines(self) -> list:
        return [{"id": "dify-app", "name": self.valves.DIFY_APP_NAME}]

    def _dify_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.valves.DIFY_API_KEY}",
            "Content-Type": "application/json",
        }

    def _extract_last_user_message(self, messages: List[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # multimodal content blocks
                    return " ".join(
                        block.get("text", "")
                        for block in content
                        if block.get("type") == "text"
                    )
                return str(content)
        return ""

    def _stream_dify(
        self, query: str, conversation_id: str, user_id: str
    ) -> Generator[str, None, None]:
        """Call Dify streaming API and yield OpenAI-compatible SSE lines."""
        url = f"{self.valves.DIFY_BASE_URL}/v1/chat-messages"
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "streaming",
            "conversation_id": conversation_id,
            "user": user_id,
        }

        resp = requests.post(
            url, json=payload, headers=self._dify_headers(), stream=True, timeout=120
        )
        resp.raise_for_status()

        chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
        new_conv_id = conversation_id

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

            event_type = event.get("event")

            if event_type == "message":
                answer_chunk = event.get("answer", "")
                # Store Dify conversation_id from first chunk
                if not new_conv_id and event.get("conversation_id"):
                    new_conv_id = event["conversation_id"]

                openai_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "dify-app",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": answer_chunk},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"

            elif event_type == "message_end":
                if event.get("conversation_id"):
                    new_conv_id = event["conversation_id"]

                openai_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "dify-app",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            elif event_type == "error":
                error_msg = event.get("message", "Dify error")
                raise RuntimeError(error_msg)

        # Save updated conversation_id
        if new_conv_id:
            self._new_conv_id = new_conv_id

    def _call_dify_blocking(self, query: str, conversation_id: str, user_id: str) -> str:
        """Non-streaming call to Dify."""
        url = f"{self.valves.DIFY_BASE_URL}/v1/chat-messages"
        payload = {
            "inputs": {},
            "query": query,
            "response_mode": "blocking",
            "conversation_id": conversation_id,
            "user": user_id,
        }

        resp = requests.post(
            url, json=payload, headers=self._dify_headers(), timeout=120
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("conversation_id"):
            self._new_conv_id = data["conversation_id"]

        return data.get("answer", "")

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        chat_id = body.get("chat_id", "default")
        user_id = body.get("user", {})
        if isinstance(user_id, dict):
            user_id = user_id.get("id", "openwebui-user")

        # Retrieve or start a Dify conversation
        dify_conv_id = self._conv_map.get(chat_id, "")

        query = self._extract_last_user_message(messages) or user_message
        self._new_conv_id = dify_conv_id

        is_streaming = body.get("stream", True)

        try:
            if is_streaming:
                result = self._stream_dify(query, dify_conv_id, str(user_id))
                # Consume generator and save conv_id after
                def _gen():
                    yield from result
                    if self._new_conv_id:
                        self._conv_map[chat_id] = self._new_conv_id

                return _gen()
            else:
                answer = self._call_dify_blocking(query, dify_conv_id, str(user_id))
                if self._new_conv_id:
                    self._conv_map[chat_id] = self._new_conv_id
                return answer

        except Exception as e:
            error = str(e)
            print(f"[dify_pipeline] error: {error}")
            return f"Error connecting to Dify: {error}"
