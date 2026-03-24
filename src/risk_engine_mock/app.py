from __future__ import annotations

from asyncio import sleep
from fastapi import FastAPI
from pydantic import BaseModel


class ScoreRequest(BaseModel):
    annual_income: float
    requested_amount: float


class ScoreResponse(BaseModel):
    score: int
    recommendation: str


def create_risk_engine() -> FastAPI:
    app = FastAPI(title="LoanFlow Risk Engine Mock")
    app.state.delay = 0.0

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/configure")
    async def configure(body: dict) -> dict[str, str]:
        app.state.delay = float(body.get("delay", 0))
        return {"status": "ok"}

    @app.post("/score")
    async def score(request: ScoreRequest) -> ScoreResponse:
        if app.state.delay > 0:
            await sleep(app.state.delay)
        ratio = request.annual_income / request.requested_amount
        if ratio >= 4.0:
            return ScoreResponse(score=82, recommendation="approve")
        if ratio >= 2.0:
            return ScoreResponse(score=55, recommendation="manual_review")
        return ScoreResponse(score=18, recommendation="reject")

    return app
