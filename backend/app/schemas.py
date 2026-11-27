from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionCreate(InputModel):
    session_id: Optional[str] = Field(default=None, min_length=8, max_length=80)
    current_laptop_id: Optional[str] = Field(default=None, max_length=80)
    persona: Optional[str] = Field(default=None, max_length=40)
    budget: Optional[int] = Field(default=None, ge=55_000, le=10_000_000)
    priority: Optional[str] = Field(default=None, max_length=100)


class BlindPick(InputModel):
    sku_id: str = Field(min_length=3, max_length=80)
    visual_reason: str = Field(default="", max_length=500)


class ShopperDay(InputModel):
    persona: Literal["Student", "Creator", "First Job", "Gamer", "Everyday"]
    budget_ceiling: int = Field(ge=55_000, le=10_000_000)
    non_negotiable: str = Field(min_length=1, max_length=100)
    top_priority: str = Field(min_length=1, max_length=100)
    required_apps: list[str] = Field(default_factory=list, max_length=30)


class MissionRequest(InputModel):
    mission_id: str = Field(min_length=2, max_length=80)
    airplane_mode: bool = False


class ForegroundChallenge(InputModel):
    completed_steps: int = Field(ge=0, le=3)
    elapsed_ms: int = Field(ge=0, le=600_000)
    challenge_id: str = Field(default="three_missions", min_length=2, max_length=80)


class RecommendationRequest(InputModel):
    priority: str = Field(min_length=1, max_length=100)


class HandoffRequest(InputModel):
    preferred_contact: Literal["none", "associate"] = "none"


class AssociateLogin(InputModel):
    store_id: Optional[str] = Field(default=None, max_length=80)
    pin: Optional[str] = Field(default=None, min_length=4, max_length=32)
    demo_login: bool = False


class CompareRequest(InputModel):
    sku_ids: list[str] = Field(min_length=2, max_length=4)


class ChecklistUpdate(InputModel):
    states: dict[str, bool] = Field(default_factory=dict, max_length=30)


class CompleteInteraction(InputModel):
    action: Literal["trial", "quote", "purchase", "follow_up"]
    note: str = Field(default="", max_length=500)
    selected_sku_id: Optional[str] = Field(default=None, max_length=80)
