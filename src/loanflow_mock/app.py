from __future__ import annotations

import httpx
from fastapi import FastAPI, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

from loanflow_mock.state import ApplicationState

ALLOWED_EMPLOYMENT_STATUSES = {
    "employed",
    "self_employed",
    "unemployed",
    "retired",
}


class ApplicationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    applicant_name: str = Field(min_length=1, max_length=100)
    annual_income: float = Field(ge=0)
    requested_amount: float = Field(ge=1000, le=500000)
    employment_status: str
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("applicant_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("applicant_name must not be blank")
        return value

    @field_validator("employment_status")
    @classmethod
    def validate_employment_status(cls, value: str) -> str:
        if value not in ALLOWED_EMPLOYMENT_STATUSES:
            allowed_values = ", ".join(sorted(ALLOWED_EMPLOYMENT_STATUSES))
            raise ValueError(f"employment_status must be one of: {allowed_values}")
        return value


class ApplicationResponse(BaseModel):
    id: str
    applicant_name: str
    annual_income: float
    requested_amount: float
    employment_status: str
    status: Literal["pending", "approved", "rejected", "error"]
    risk_score: int | None = Field(default=None, ge=0, le=100)
    decision_reason: str
    created_at: str
    updated_at: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: list[str]


def _make_decision(payload: dict, risk_score: int) -> tuple[str, str]:
    ratio = payload["annual_income"] / payload["requested_amount"]
    if payload["employment_status"] == "unemployed" and payload["requested_amount"] > 10_000:
        return "rejected", "Rejected due to unemployment and high requested amount"
    if risk_score < 30:
        return "rejected", "Rejected due to low risk score"
    if risk_score >= 70 and ratio >= 2.0:
        return "approved", "Auto-approved by risk policy"
    return "pending", "Queued for manual review"


def create_app(state: ApplicationState, risk_engine_url: str) -> FastAPI:
    app = FastAPI(
        title="LoanFlow Application API",
        version="1.0.0",
        description="Lightweight stand-in used for Robot Framework automation.",
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for error in exc.errors():
            path = ".".join(str(item) for item in error["loc"] if item != "body")
            details.append(f"{path}: {error['msg']}")
        payload = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
        )
        return JSONResponse(status_code=400, content=payload.model_dump())

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/applications")
    async def create_application(application: ApplicationRequest) -> JSONResponse:
        payload = application.model_dump(exclude_none=True)

        duplicate = state.find_duplicate(payload["applicant_name"], payload["requested_amount"])
        if duplicate is not None:
            return JSONResponse(status_code=200, content=jsonable_encoder(ApplicationResponse(**duplicate)))

        try:
            async with httpx.AsyncClient() as client:
                re_response = await client.post(
                    f"{risk_engine_url}/score",
                    json=payload,
                    timeout=5.0,
                )
            risk_score = re_response.json()["score"]
            status, decision_reason = _make_decision(payload, risk_score)
        except httpx.TimeoutException:
            risk_score = None
            status = "error"
            decision_reason = "Risk Engine timed out after 5 seconds"
        except httpx.ConnectError:
            return JSONResponse(
                status_code=503,
                content=ErrorResponse(
                    error_code="RISK_ENGINE_UNAVAILABLE",
                    message="Risk Engine unavailable",
                    details=["The Risk Engine service could not be reached"],
                ).model_dump(),
            )

        application_data = state.store_application(payload, risk_score, status, decision_reason)
        return JSONResponse(status_code=201, content=jsonable_encoder(ApplicationResponse(**application_data)))

    @app.get("/api/v1/applications")
    async def list_applications(
        status: Literal["pending", "approved", "rejected", "error"] | None = Query(default=None)
    ) -> JSONResponse:
        applications = [ApplicationResponse(**item) for item in state.list_applications(status)]
        return JSONResponse(status_code=200, content=jsonable_encoder(applications))

    @app.get("/api/v1/applications/{application_id}")
    async def get_application(application_id: str) -> JSONResponse:
        application = state.get_application(application_id)
        if application is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error_code="NOT_FOUND",
                    message="Application not found",
                    details=[f"No application exists with id {application_id}"],
                ).model_dump(),
            )
        return JSONResponse(status_code=200, content=jsonable_encoder(ApplicationResponse(**application)))

    return app
