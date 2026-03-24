from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from loanflow_mock.app import create_app
from loanflow_mock.state import ApplicationState
from risk_engine_mock.app import create_risk_engine


class LoanFlowLibrary:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self) -> None:
        self._state: ApplicationState | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._base_url: str | None = None
        self._re_server: uvicorn.Server | None = None
        self._re_thread: threading.Thread | None = None
        self._re_url: str | None = None
        self._re_port: int | None = None

    def start_loanflow_api(self, host: str = "127.0.0.1", port: int | None = None) -> str:
        if self._server is not None and self._thread is not None and self._thread.is_alive():
            return self._base_url or ""

        re_url = self._start_risk_engine()

        port = port or self._find_free_port()
        self._state = ApplicationState()
        app = create_app(self._state, risk_engine_url=re_url)

        config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        self._base_url = f"http://{host}:{port}"
        self._wait_until_ready(f"{self._base_url}/health")
        return self._base_url

    def stop_loanflow_api(self) -> None:
        if self._server is not None and self._thread is not None:
            self._server.should_exit = True
            self._thread.join(timeout=5)
            self._server = None
            self._thread = None
            self._state = None
            self._base_url = None
        self._stop_risk_engine()
        self._re_port = None

    def reset_loanflow_state(self) -> None:
        self._require_state().reset()
        if self._re_server is None or self._re_thread is None or not self._re_thread.is_alive():
            self._start_risk_engine()
        else:
            self._post_json(f"{self._re_url}/configure", {"delay": 0})

    def stop_risk_engine(self) -> None:
        self._stop_risk_engine()

    def configure_risk_engine_delay(self, delay: float) -> None:
        if self._re_url is None:
            raise RuntimeError("Risk Engine is not running")
        self._post_json(f"{self._re_url}/configure", {"delay": float(delay)})

    def build_application_payload(
        self,
        applicant_name: str = "Maria Schmidt",
        annual_income: float = 80000,
        requested_amount: float = 20000,
        employment_status: str = "employed",
        notes: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "applicant_name": applicant_name,
            "annual_income": annual_income,
            "requested_amount": requested_amount,
            "employment_status": employment_status,
            "notes": notes,
        }
        return {k: v for k, v in payload.items() if v is not None}

    def get_notification_records(self) -> list[dict[str, str]]:
        return self._require_state().get_notifications()

    def notification_should_exist(self, application_id: str, status: str) -> None:
        notifications = self.get_notification_records()
        if not any(
            item["application_id"] == application_id and item["status"] == status
            for item in notifications
        ):
            raise AssertionError(
                f"No notification found for application_id={application_id!r} and status={status!r}"
            )

    def _start_risk_engine(self) -> str:
        self._stop_risk_engine()
        port = self._re_port or self._find_free_port()
        self._re_port = port

        app = create_risk_engine()
        config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
        self._re_server = uvicorn.Server(config)
        self._re_thread = threading.Thread(target=self._re_server.run, daemon=True)
        self._re_thread.start()

        self._re_url = f"http://127.0.0.1:{port}"
        self._wait_until_ready(f"{self._re_url}/health")
        return self._re_url

    def _stop_risk_engine(self) -> None:
        if self._re_server is None or self._re_thread is None:
            return
        self._re_server.should_exit = True
        self._re_thread.join(timeout=5)
        self._re_server = None
        self._re_thread = None
        self._re_url = None

    def _require_state(self) -> ApplicationState:
        if self._state is None:
            raise RuntimeError("LoanFlow API is not running. Call 'Start Loanflow Api' first.")
        return self._state

    def _wait_until_ready(self, url: str) -> None:
        deadline = time.monotonic() + 5
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        return
            except (URLError, OSError) as exc:
                last_error = exc
                time.sleep(0.05)
        raise RuntimeError(f"Service at {url} did not become ready in time: {last_error}")

    def _post_json(self, url: str, body: dict) -> None:
        req = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        urlopen(req, timeout=5).close()

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
