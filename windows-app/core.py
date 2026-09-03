from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse


PROTOCOL_VERSION = 1
MAX_BODY_BYTES = 64 * 1024
PAIRING_TTL_SECONDS = 5 * 60
ALLOWED_COMMANDS = frozenset({"SHOW_HOME", "OPEN_SETTINGS", "SYNC_NOW"})


def default_state_path() -> Path:
    root = os.environ.get("APPDATA")
    base = Path(root) if root else Path.home() / ".droiddesk"
    return base / "DroidDesk" / "state.json" if root else base / "state.json"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _clean_text(value: Any, name: str, maximum: int = 80) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f"{name} must be 1-{maximum} characters")
    return value


@dataclass(frozen=True)
class PairingSession:
    code: str
    expires_at: float


class DeviceRegistry:
    def __init__(
        self,
        state_path: Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.state_path = state_path or default_state_path()
        self.clock = clock
        self._lock = threading.RLock()
        self._pairing: PairingSession | None = None
        self._devices: dict[str, dict[str, Any]] = {}
        self._next_command_id = 1
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            devices = payload.get("devices", {})
            if isinstance(devices, dict):
                self._devices = {
                    key: value
                    for key, value in devices.items()
                    if isinstance(key, str) and isinstance(value, dict)
                }
            self._next_command_id = max(1, int(payload.get("nextCommandId", 1)))
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            self._devices = {}
            self._next_command_id = 1

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        data = {
            "protocolVersion": PROTOCOL_VERSION,
            "nextCommandId": self._next_command_id,
            "devices": self._devices,
        }
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(self.state_path)

    def new_pairing_code(self) -> PairingSession:
        with self._lock:
            session = PairingSession(
                code=f"{secrets.randbelow(1_000_000):06d}",
                expires_at=self.clock() + PAIRING_TTL_SECONDS,
            )
            self._pairing = session
            return session

    def current_pairing(self) -> PairingSession | None:
        with self._lock:
            if self._pairing and self._pairing.expires_at > self.clock():
                return self._pairing
            self._pairing = None
            return None

    def pair(self, code: Any, device_name: Any, android_version: Any) -> dict[str, Any]:
        name = _clean_text(device_name, "deviceName")
        version = _clean_text(android_version, "androidVersion", 40)
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            raise PermissionError("Invalid or expired pairing code")

        with self._lock:
            session = self.current_pairing()
            if session is None or not hmac.compare_digest(session.code, code):
                raise PermissionError("Invalid or expired pairing code")
            self._pairing = None
            token = secrets.token_urlsafe(32)
            device_id = uuid.uuid4().hex
            now = self.clock()
            self._devices[device_id] = {
                "id": device_id,
                "name": name,
                "androidVersion": version,
                "batteryLevel": None,
                "lastSeen": now,
                "tokenHash": _token_hash(token),
                "commands": [],
            }
            self._save()
            return {
                "deviceId": device_id,
                "token": token,
                "protocolVersion": PROTOCOL_VERSION,
                "pollSeconds": 5,
            }

    def authenticate(self, token: str | None) -> str:
        if not token:
            raise PermissionError("Missing bearer token")
        candidate = _token_hash(token)
        with self._lock:
            for device_id, device in self._devices.items():
                stored = device.get("tokenHash", "")
                if isinstance(stored, str) and hmac.compare_digest(stored, candidate):
                    return device_id
        raise PermissionError("Invalid bearer token")

    def update_status(self, device_id: str, payload: dict[str, Any]) -> None:
        name = _clean_text(payload.get("deviceName"), "deviceName")
        version = _clean_text(payload.get("androidVersion"), "androidVersion", 40)
        battery = payload.get("batteryLevel")
        if isinstance(battery, bool) or not isinstance(battery, int) or not 0 <= battery <= 100:
            raise ValueError("batteryLevel must be an integer from 0 to 100")
        with self._lock:
            device = self._devices[device_id]
            device.update(
                name=name,
                androidVersion=version,
                batteryLevel=battery,
                lastSeen=self.clock(),
            )
            self._save()

    def queue_command(self, device_id: str, command_type: str) -> int:
        if command_type not in ALLOWED_COMMANDS:
            raise ValueError("Command is not allowlisted")
        with self._lock:
            if device_id not in self._devices:
                raise KeyError("Unknown device")
            command_id = self._next_command_id
            self._next_command_id += 1
            self._devices[device_id].setdefault("commands", []).append(
                {
                    "id": command_id,
                    "type": command_type,
                    "createdAt": self.clock(),
                    "acknowledgedAt": None,
                    "result": None,
                }
            )
            self._save()
            return command_id

    def commands_after(self, device_id: str, after: int) -> list[dict[str, Any]]:
        with self._lock:
            commands = self._devices[device_id].get("commands", [])
            return [
                {"id": item["id"], "type": item["type"]}
                for item in commands
                if int(item.get("id", 0)) > after
            ]

    def acknowledge(self, device_id: str, command_id: int, result: Any) -> None:
        clean_result = _clean_text(result, "result", 120)
        with self._lock:
            for command in self._devices[device_id].get("commands", []):
                if command.get("id") == command_id:
                    command["acknowledgedAt"] = self.clock()
                    command["result"] = clean_result
                    self._save()
                    return
        raise KeyError("Unknown command")

    def devices(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": item["id"],
                    "name": item.get("name", "Android device"),
                    "androidVersion": item.get("androidVersion", ""),
                    "batteryLevel": item.get("batteryLevel"),
                    "lastSeen": item.get("lastSeen", 0),
                    "commands": [dict(command) for command in item.get("commands", [])[-8:]],
                }
                for item in self._devices.values()
            ]


def _bearer(header: str | None) -> str | None:
    if not header or not header.startswith("Bearer "):
        return None
    return header[7:].strip()


def make_handler(registry: DeviceRegistry) -> type[BaseHTTPRequestHandler]:
    class DroidDeskHandler(BaseHTTPRequestHandler):
        server_version = "DroidDesk/1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length is required")
            try:
                length = int(raw_length)
            except ValueError as error:
                raise ValueError("Invalid Content-Length") from error
            if length < 0 or length > MAX_BODY_BYTES:
                raise ValueError("Request body is too large")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("Request body must be valid JSON") from error
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            return payload

        def _device_id(self) -> str:
            return registry.authenticate(_bearer(self.headers.get("Authorization")))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/health":
                    self._json(HTTPStatus.OK, {"ok": True, "protocolVersion": PROTOCOL_VERSION})
                    return
                if parsed.path == "/api/v1/commands":
                    device_id = self._device_id()
                    raw_after = parse_qs(parsed.query).get("after", ["0"])[0]
                    after = max(0, int(raw_after))
                    self._json(
                        HTTPStatus.OK,
                        {"commands": registry.commands_after(device_id, after)},
                    )
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            except PermissionError as error:
                self._json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
            except (ValueError, KeyError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self._read_json()
                if parsed.path == "/api/v1/pair":
                    response = registry.pair(
                        payload.get("pairCode"),
                        payload.get("deviceName"),
                        payload.get("androidVersion"),
                    )
                    self._json(HTTPStatus.CREATED, response)
                    return
                if parsed.path == "/api/v1/status":
                    registry.update_status(self._device_id(), payload)
                    self._json(HTTPStatus.OK, {"ok": True})
                    return
                prefix, suffix = "/api/v1/commands/", "/ack"
                if parsed.path.startswith(prefix) and parsed.path.endswith(suffix):
                    command_text = parsed.path[len(prefix) : -len(suffix)]
                    registry.acknowledge(
                        self._device_id(), int(command_text), payload.get("result")
                    )
                    self._json(HTTPStatus.OK, {"ok": True})
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            except PermissionError as error:
                self._json(HTTPStatus.UNAUTHORIZED, {"error": str(error)})
            except (ValueError, KeyError) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    return DroidDeskHandler


class DroidDeskServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

