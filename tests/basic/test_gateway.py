"""Tests for the "one endpoint, many models" recipe in the docs.

A local OpenAI-compatible server stands in for a gateway/proxy that serves
many models behind a single base URL and a single API key.
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput

from aider.coders import Coder
from aider.commands import SwitchCoder
from aider.io import InputOutput
from aider.main import main
from aider.utils import GitTemporaryDirectory

EXPECTED_FILE = "def hello():\n    print('hello')"
WHOLE_FILE_REPLY = f"```python\n{EXPECTED_FILE}\n```"


class FakeGateway:
    """Minimal OpenAI-compatible endpoint which records the requests it gets."""

    def __init__(self, reply=WHOLE_FILE_REPLY):
        self.reply = reply
        self.requests = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._make_handler())
        self.host, self.port = self.httpd.server_address
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://{self.host}:{self.port}/v1"

    @property
    def models_dialed(self):
        return [req["model"] for req in self.requests]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _make_handler(self):
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args, **kwargs):
                pass

            def do_POST(self):
                length = int(self.headers.get("content-length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                gateway.requests.append(
                    {
                        "path": self.path,
                        "model": body.get("model"),
                        "auth": self.headers.get("authorization"),
                    }
                )
                if body.get("stream"):
                    self._stream(body)
                else:
                    self._json(body)

            def _json(self, body):
                payload = {
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "created": 0,
                    "model": body.get("model"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": gateway.reply},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                }
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _stream(self, body):
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()
                midpoint = len(gateway.reply) // 2
                for piece in (gateway.reply[:midpoint], gateway.reply[midpoint:]):
                    chunk = {
                        "id": "chatcmpl-1",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": body.get("model"),
                        "choices": [
                            {"index": 0, "delta": {"content": piece}, "finish_reason": None}
                        ],
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                final = {
                    "id": "chatcmpl-1",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": body.get("model"),
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                }
                self.wfile.write(f"data: {json.dumps(final)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        return Handler


class TestGateway(TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["OPENAI_API_KEY"] = "gw-key"
        os.environ["AIDER_CHECK_UPDATE"] = "false"
        os.environ["AIDER_ANALYTICS"] = "false"
        # Never send localhost traffic through a proxy which the CI env may define
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        os.environ["no_proxy"] = "127.0.0.1,localhost"
        # These models are unknown to litellm, which makes aider try to download
        # the model info database. Keep the tests on localhost only.
        self.info_patcher = patch("aider.models.ModelInfoManager._update_cache")
        self.info_patcher.start()
        self.gateway = None

    def tearDown(self):
        if self.gateway:
            self.gateway.stop()
        self.info_patcher.stop()
        os.environ.clear()
        os.environ.update(self.original_env)

    def run_aider(self, *args, return_coder=False):
        return main(
            list(args),
            input=DummyInput(),
            output=DummyOutput(),
            return_coder=return_coder,
        )

    def gateway_args(self):
        return ["--openai-api-base", self.gateway.base_url]

    def test_edits_go_to_the_endpoint_with_the_bare_model_name(self):
        with GitTemporaryDirectory():
            Path("hello.py").write_text("print('old')\n")
            self.gateway = FakeGateway()

            self.run_aider(
                "--model",
                "openai/any-vendor-model",
                *self.gateway_args(),
                "--yes",
                "--no-gitignore",
                "--message",
                "write hello.py",
                "hello.py",
            )

            self.assertEqual(Path("hello.py").read_text().strip(), EXPECTED_FILE)
            self.assertTrue(self.gateway.requests, "the gateway was never called")
            for request in self.gateway.requests:
                self.assertEqual(request["path"], "/v1/chat/completions")
                # The openai/ prefix tells aider which protocol to speak, it is not
                # part of the model name the endpoint is asked for
                self.assertEqual(request["model"], "any-vendor-model")
                self.assertEqual(request["auth"], "Bearer gw-key")

    def test_architect_and_editor_share_one_endpoint(self):
        with GitTemporaryDirectory():
            Path("hello.py").write_text("print('old')\n")
            self.gateway = FakeGateway()

            self.run_aider(
                "--architect",
                "--model",
                "openai/planner-model",
                "--editor-model",
                "openai/editor-model",
                *self.gateway_args(),
                "--yes",
                "--no-gitignore",
                "--message",
                "write hello.py",
                "hello.py",
            )

            dialed = self.gateway.models_dialed
            self.assertIn("planner-model", dialed)
            self.assertIn("editor-model", dialed)

    def test_metadata_file_quiets_the_unknown_model_warning(self):
        metadata = {
            "openai/any-vendor-model": {
                "max_tokens": 32000,
                "max_input_tokens": 128000,
                "max_output_tokens": 32000,
                "input_cost_per_token": 0.0000003,
                "output_cost_per_token": 0.0000012,
                "litellm_provider": "openai",
                "mode": "chat",
            }
        }

        def warned_about_unknown_model(metadata_present):
            with GitTemporaryDirectory():
                Path("hello.py").write_text("print('old')\n")
                if metadata_present:
                    Path(".aider.model.metadata.json").write_text(json.dumps(metadata))
                self.gateway = FakeGateway()
                warnings = []
                with patch.object(
                    InputOutput,
                    "tool_warning",
                    lambda _self, message="", *a, **k: warnings.append(message),
                ):
                    self.run_aider(
                        "--model",
                        "openai/any-vendor-model",
                        *self.gateway_args(),
                        "--yes",
                        "--no-gitignore",
                        "--message",
                        "write hello.py",
                        "hello.py",
                    )
                self.gateway.stop()
                self.gateway = None
                return [w for w in warnings if "Unknown context window size" in w]

        self.assertTrue(
            warned_about_unknown_model(metadata_present=False),
            "expected the unknown model warning without a metadata file",
        )
        self.assertFalse(
            warned_about_unknown_model(metadata_present=True),
            "metadata file should describe the model, silencing the warning",
        )

    def test_model_command_switches_models_on_the_same_endpoint(self):
        with GitTemporaryDirectory():
            Path("hello.py").write_text("print('old')\n")
            self.gateway = FakeGateway()

            coder = self.run_aider(
                "--model",
                "openai/first-model",
                *self.gateway_args(),
                "--yes",
                "--no-gitignore",
                "hello.py",
                return_coder=True,
            )

            # This is what the interactive loop does with a SwitchCoder
            try:
                coder.commands.cmd_model("openai/second-model")
            except SwitchCoder as switch:
                coder = Coder.create(io=coder.io, from_coder=coder, **switch.kwargs)
            else:
                self.fail("cmd_model did not switch models")

            self.assertEqual(coder.main_model.name, "openai/second-model")
            self.assertEqual(os.environ["OPENAI_API_BASE"], self.gateway.base_url)

            coder.run(with_message="write hello.py")
            self.assertIn("second-model", self.gateway.models_dialed)
