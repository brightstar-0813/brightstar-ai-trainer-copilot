"""Localhost WebSocket bridge between jt pipelines and the Chrome extension.

Roles (declared in the first `hello` message, which must carry the shared token):
  - extension: the single Chrome extension that drives claude.ai / chatgpt.com
  - client:    any jt process that wants a prompt answered (see client.py)

Each provider (claude, gpt, ...) is served one job at a time. A client that has
asked a provider keeps that provider's lock until it disconnects, so follow-up
messages in the same chat cannot be interleaved with another client's job.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
from typing import Any

from websockets.asyncio.server import ServerConnection, serve

from .. import config

log = logging.getLogger("jt.bridge")

DEFAULT_JOB_TIMEOUT = 300


class Bridge:
    def __init__(self, host: str, port: int, token: str, job_timeout: int = DEFAULT_JOB_TIMEOUT):
        self.host, self.port, self.token = host, port, token
        self.job_timeout = job_timeout
        self.grace = 30  # extra seconds beyond the job timeout before the bridge gives up
        self.ext: ServerConnection | None = None
        self.ext_info: dict[str, Any] = {}
        self.ext_since: float = 0.0
        self.locks: dict[str, asyncio.Lock] = {}
        self.holders: dict[str, ServerConnection] = {}
        self.pending: dict[str, tuple[asyncio.Future, ServerConnection]] = {}
        self.current: dict[str, str] = {}  # provider -> job id

    # ---- connection entry -------------------------------------------------
    async def handler(self, ws: ServerConnection) -> None:
        origin = ws.request.headers.get("Origin") if ws.request else None
        if origin and not origin.startswith("chrome-extension://"):
            await ws.close(1008, "origin not allowed")
            return
        try:
            hello = json.loads(await asyncio.wait_for(ws.recv(), 10))
        except Exception:
            await ws.close(1008, "hello required")
            return
        supplied = str(hello.get("token", ""))
        if hello.get("type") != "hello" or not hmac.compare_digest(supplied, self.token):
            await ws.close(1008, "bad token")
            return
        role = hello.get("role")
        if role == "extension":
            await self._serve_extension(ws, hello)
        elif role == "client":
            await self._serve_client(ws)
        else:
            await ws.close(1008, "unknown role")

    # ---- extension side ---------------------------------------------------
    async def _serve_extension(self, ws: ServerConnection, hello: dict) -> None:
        if self.ext is not None:
            try:
                await self.ext.close(1000, "replaced")
            except Exception:
                pass
        self.ext, self.ext_since = ws, time.time()
        self.ext_info = {"version": hello.get("version", "?")}
        await ws.send(json.dumps({"type": "hello_ok"}))
        log.info("extension connected (v%s)", self.ext_info["version"])
        try:
            async for raw in ws:
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                elif t == "status":
                    self.ext_info.update({k: v for k, v in msg.items() if k != "type"})
                elif t == "result":
                    entry = self.pending.get(msg.get("id", ""))
                    if entry and not entry[0].done():
                        entry[0].set_result(msg)
                elif t == "progress":
                    entry = self.pending.get(msg.get("id", ""))
                    if entry:
                        await self._safe_send(entry[1], msg)
        finally:
            if self.ext is ws:
                self.ext = None
                log.info("extension disconnected")
                for fut, _ in list(self.pending.values()):
                    if not fut.done():
                        fut.set_result({"ok": False, "code": "ext_disconnected",
                                        "error": "extension disconnected"})

    # ---- client side ------------------------------------------------------
    async def _serve_client(self, ws: ServerConnection) -> None:
        await ws.send(json.dumps({"type": "hello_ok"}))
        tasks: set[asyncio.Task] = set()
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") == "status":
                    await ws.send(json.dumps({"type": "status", **self.status()}))
                elif msg.get("type") == "open":
                    await self._open_provider(ws, msg)
                elif msg.get("type") == "ask":
                    task = asyncio.create_task(self._handle_ask(ws, msg))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for provider, holder in list(self.holders.items()):
                if holder is ws:
                    del self.holders[provider]
                    self.locks[provider].release()

    async def _handle_ask(self, ws: ServerConnection, msg: dict) -> None:
        job_id = msg["id"]
        provider = msg["provider"]
        lock = self.locks.setdefault(provider, asyncio.Lock())
        if self.holders.get(provider) is not ws:
            await lock.acquire()
            self.holders[provider] = ws
        if self.ext is None:
            await self._safe_send(ws, {"type": "result", "id": job_id, "ok": False,
                                       "code": "no_extension",
                                       "error": "Chrome extension is not connected to the bridge"})
            return
        timeout = int(msg.get("timeout") or self.job_timeout)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[job_id] = (fut, ws)
        self.current[provider] = job_id
        try:
            await self.ext.send(json.dumps({
                "type": "job", "id": job_id, "provider": provider,
                "prompt": msg["prompt"], "new_chat": bool(msg.get("new_chat", True)),
                "url": msg.get("url"), "timeout": timeout,
            }))
            try:
                res = await asyncio.wait_for(fut, timeout + self.grace)
            except asyncio.TimeoutError:
                await self._notify_ext({"type": "cancel", "id": job_id})
                res = {"ok": False, "code": "timeout", "error": f"no reply within {timeout}s"}
            out = {"type": "result", "id": job_id, "ok": bool(res.get("ok")),
                   "text": res.get("text", ""), "error": res.get("error", ""),
                   "code": res.get("code", "")}
            await self._safe_send(ws, out)
        except asyncio.CancelledError:
            await self._notify_ext({"type": "cancel", "id": job_id})
            raise
        except Exception as e:  # noqa: BLE001
            await self._safe_send(ws, {"type": "result", "id": job_id, "ok": False,
                                       "code": "bridge_error", "error": repr(e)})
        finally:
            self.pending.pop(job_id, None)
            if self.current.get(provider) == job_id:
                self.current.pop(provider, None)

    # ---- helpers ----------------------------------------------------------
    def status(self) -> dict:
        return {
            "extension_connected": self.ext is not None,
            "extension": self.ext_info,
            "connected_for_s": int(time.time() - self.ext_since) if self.ext else 0,
            "busy": dict(self.current),
        }

    @staticmethod
    async def _safe_send(ws: ServerConnection, payload: dict) -> None:
        try:
            await ws.send(json.dumps(payload))
        except Exception:
            pass

    async def _open_provider(self, ws: ServerConnection, msg: dict) -> None:
        provider = str(msg.get("provider") or "")
        if provider not in ("claude", "gpt"):
            await self._safe_send(ws, {"type": "open_fail", "code": "bad_provider",
                                       "error": "provider must be claude or gpt"})
            return
        if self.ext is None:
            await self._safe_send(ws, {"type": "open_fail", "code": "no_extension",
                                       "error": "Chrome extension is not connected to the bridge"})
            return
        await self._notify_ext({"type": "open_provider", "provider": provider, "url": msg.get("url")})
        await self._safe_send(ws, {"type": "open_ok", "provider": provider})

    async def _config_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            method, path, headers, body = await self._read_http(reader)
            await self._write_http(writer, *self._route_http(method, path, headers, body))
        except Exception:
            try:
                writer.write(b"HTTP/1.1 500 Internal Server Error\r\nConnection: close\r\n\r\n")
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()

    async def _read_http(
        self, reader: asyncio.StreamReader
    ) -> tuple[str, str, dict[str, str], bytes]:
        """Parse a single HTTP/1.1 request (headers + optional JSON body)."""
        buf = b""
        while b"\r\n\r\n" not in buf and len(buf) < 64 * 1024:
            chunk = await asyncio.wait_for(reader.read(4096), 5)
            if not chunk:
                break
            buf += chunk
        if b"\r\n\r\n" not in buf:
            raise ValueError("incomplete HTTP headers")
        head, rest = buf.split(b"\r\n\r\n", 1)
        lines = head.split(b"\r\n")
        request_line = lines[0].decode("latin1", errors="replace")
        parts = request_line.split()
        if len(parts) < 2:
            raise ValueError("bad request line")
        method, path = parts[0], parts[1]
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if b":" not in line:
                continue
            k, v = line.split(b":", 1)
            headers[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
        length = int(headers.get("content-length") or 0)
        if length > 1_000_000:
            raise ValueError("body too large")
        body = rest
        while len(body) < length:
            chunk = await asyncio.wait_for(reader.read(length - len(body)), 5)
            if not chunk:
                break
            body += chunk
        return method, path, headers, body[:length]

    def _route_http(
        self, method: str, path: str, headers: dict[str, str], body: bytes
    ) -> tuple[int, bytes, str]:
        from . import local_api

        path_only = path.split("?", 1)[0]
        if path_only == "/ext-config" and method.upper() in ("GET", "OPTIONS"):
            if method.upper() == "OPTIONS":
                return 204, b"", "application/json"
            payload = {
                "bridgeUrl": f"ws://127.0.0.1:{self.port}",
                "token": self.token,
                "extensionVersion": config.extension_version(),
                "apiBase": f"http://127.0.0.1:{self.port + 1}",
            }
            return 200, json.dumps(payload).encode(), "application/json"

        if path_only.startswith("/api/") or path_only == "/api":
            status, data = local_api.dispatch(
                method=method,
                path=path,
                headers=headers,
                body=body,
                token=self.token,
                bridge_status=self.status(),
            )
            if status == 204:
                return 204, b"", "application/json"
            return status, json.dumps(data).encode(), "application/json"

        return 404, b'{"ok":false,"error":"not found"}', "application/json"

    async def _write_http(
        self, writer: asyncio.StreamWriter, status: int, body: bytes, content_type: str
    ) -> None:
        reason = {
            200: "OK",
            204: "No Content",
            400: "Bad Request",
            401: "Unauthorized",
            404: "Not Found",
            500: "Internal Server Error",
        }.get(status, "OK")
        headers = [
            f"HTTP/1.1 {status} {reason}",
            f"Content-Type: {content_type}",
            "Cache-Control: no-store",
            "Access-Control-Allow-Origin: *",
            "Access-Control-Allow-Headers: Authorization, Content-Type, X-JT-Token",
            "Access-Control-Allow-Methods: GET, POST, OPTIONS",
            "Connection: close",
        ]
        if status != 204:
            headers.append(f"Content-Length: {len(body)}")
        writer.write(("\r\n".join(headers) + "\r\n\r\n").encode() + (body if status != 204 else b""))
        await writer.drain()

    async def _serve_ext_config(self) -> None:
        """Localhost HTTP for /ext-config and the side-panel /api/* routes."""
        try:
            server = await asyncio.start_server(self._config_handler, "127.0.0.1", self.port + 1)
        except OSError as e:
            log.warning("extension config port %s unavailable: %s", self.port + 1, e)
            return
        self.config_port = self.port + 1
        log.info("extension API on http://127.0.0.1:%s (/ext-config, /api/*)", self.config_port)
        async with server:
            await server.serve_forever()

    async def _notify_ext(self, payload: dict) -> None:
        if self.ext is not None:
            await self._safe_send(self.ext, payload)

    async def run(self) -> None:
        config_task = asyncio.create_task(self._serve_ext_config())
        try:
            async with serve(self.handler, self.host, self.port, max_size=16 * 1024 * 1024,
                             ping_interval=None):
                log.info("bridge listening on ws://%s:%s", self.host, self.port)
                await asyncio.Future()
        finally:
            config_task.cancel()
            await asyncio.gather(config_task, return_exceptions=True)


def serve_forever() -> None:
    token = config.bridge_token()
    if token in ("", "change-me"):
        raise SystemExit("Set JT_BRIDGE_TOKEN in .env first (run: jt init)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    try:
        asyncio.run(Bridge(config.bridge_host(), config.bridge_port(), token).run())
    except KeyboardInterrupt:
        pass
