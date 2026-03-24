from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass
class ApplicationState:
    applications: dict[str, dict[str, Any]] = field(default_factory=dict)
    notifications: list[dict[str, str]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def reset(self) -> None:
        with self._lock:
            self.applications.clear()
            self.notifications.clear()

    def find_duplicate(self, applicant_name: str, requested_amount: float) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            for application in self.applications.values():
                created_at = datetime.fromisoformat(application["created_at"])
                if (
                    application["applicant_name"] == applicant_name
                    and application["requested_amount"] == requested_amount
                    and now - created_at <= timedelta(minutes=1)
                ):
                    return application.copy()
        return None

    def store_application(
        self,
        payload: dict[str, Any],
        risk_score: int | None,
        status: str,
        decision_reason: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        application = {
            "id": str(uuid4()),
            "applicant_name": payload["applicant_name"],
            "annual_income": payload["annual_income"],
            "requested_amount": payload["requested_amount"],
            "employment_status": payload["employment_status"],
            "status": status,
            "risk_score": risk_score,
            "decision_reason": decision_reason,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self.applications[application["id"]] = application
        self._record_notification(application["id"], status)
        return application.copy()

    def list_applications(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            applications = [item.copy() for item in self.applications.values()]
        if status is not None:
            applications = [item for item in applications if item["status"] == status]
        return sorted(applications, key=lambda item: item["created_at"])

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        with self._lock:
            application = self.applications.get(application_id)
            return application.copy() if application is not None else None

    def get_notifications(self) -> list[dict[str, str]]:
        with self._lock:
            return [item.copy() for item in self.notifications]

    def _record_notification(self, application_id: str, status: str) -> None:
        with self._lock:
            self.notifications.append({
                "application_id": application_id,
                "status": status,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
