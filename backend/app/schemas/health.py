from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["alive"]
    service: str


class ReadinessResponse(BaseModel):
    status: Literal["healthy"]
    service: str
    database: Literal["ok"]
