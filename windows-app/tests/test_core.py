import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import DeviceRegistry, DroidDeskServer, make_handler


class Clock:
    def __init__(self) -> None:
        self.value = 1_700_000_000.0

    def __call__(self) -> float:
        return self.value


class DeviceRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.registry = DeviceRegistry(Path(self.temp.name) / "state.json", self.clock)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def pair_device(self) -> tuple[str, str]:
        code = self.registry.new_pairing_code().code
        result = self.registry.pair(code, "Galaxy", "16")
        return result["deviceId"], result["token"]

    def test_pairing_is_single_use_and_token_authenticates(self) -> None:
        code = self.registry.new_pairing_code().code
        result = self.registry.pair(code, "Galaxy", "16")

        self.assertEqual(self.registry.authenticate(result["token"]), result["deviceId"])
        with self.assertRaises(PermissionError):
            self.registry.pair(code, "Second phone", "15")
        with self.assertRaises(PermissionError):
            self.registry.authenticate("wrong-token")

    def test_pairing_code_expires(self) -> None:
        code = self.registry.new_pairing_code().code
        self.clock.value += 301

        with self.assertRaises(PermissionError):
            self.registry.pair(code, "Galaxy", "16")

    def test_status_command_and_ack_flow(self) -> None:
        device_id, token = self.pair_device()
        self.registry.update_status(
            self.registry.authenticate(token),
            {"deviceName": "Galaxy A06", "androidVersion": "16", "batteryLevel": 82},
        )
        command_id = self.registry.queue_command(device_id, "OPEN_SETTINGS")

        self.assertEqual(
            self.registry.commands_after(device_id, 0),
            [{"id": command_id, "type": "OPEN_SETTINGS"}],
        )
        self.registry.acknowledge(device_id, command_id, "completed")
        self.assertEqual(self.registry.devices()[0]["commands"][0]["result"], "completed")

        with self.assertRaises(ValueError):
            self.registry.queue_command(device_id, "RUN_SHELL")

    def test_raw_token_is_not_persisted(self) -> None:
        _device_id, token = self.pair_device()
        serialized = self.registry.state_path.read_text(encoding="utf-8")

        self.assertNotIn(token, serialized)
        persisted_device = json.loads(serialized)["devices"].popitem()[1]
        self.assertIn("tokenHash", persisted_device)

    def test_invalid_battery_is_rejected(self) -> None:
        device_id, _token = self.pair_device()
        for battery in (-1, 101, "90", True):
            with self.subTest(battery=battery), self.assertRaises(ValueError):
                self.registry.update_status(
                    device_id,
                    {"deviceName": "Galaxy", "androidVersion": "16", "batteryLevel": battery},
                )

    def test_http_pair_status_and_command_poll(self) -> None:
        server = DroidDeskServer(("127.0.0.1", 0), make_handler(self.registry))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        code = self.registry.new_pairing_code().code

        pair_request = urllib.request.Request(
            base + "/api/v1/pair",
            data=json.dumps(
                {"pairCode": code, "deviceName": "Galaxy", "androidVersion": "16"}
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(pair_request) as response:
            paired = json.load(response)

        token = paired["token"]
        device_id = paired["deviceId"]
        status_request = urllib.request.Request(
            base + "/api/v1/status",
            data=json.dumps(
                {"deviceName": "Galaxy A06", "androidVersion": "16", "batteryLevel": 75}
            ).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(status_request) as response:
            self.assertTrue(json.load(response)["ok"])

        command_id = self.registry.queue_command(device_id, "SYNC_NOW")
        command_request = urllib.request.Request(
            base + "/api/v1/commands?after=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(command_request) as response:
            commands = json.load(response)["commands"]
        self.assertEqual(commands, [{"id": command_id, "type": "SYNC_NOW"}])


if __name__ == "__main__":
    unittest.main()
