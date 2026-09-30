from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, le=100_000_000, max_digits=11, decimal_places=2)]
Rate = Annotated[Decimal, Field(ge=0, le=1000, max_digits=7, decimal_places=4)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Debt(StrictModel):
    id: UUID
    name: str = Field(min_length=1, max_length=60)
    balance: Money
    apr: Rate
    minimum_payment: Money


class Goal(StrictModel):
    name: str = Field(min_length=1, max_length=60)
    target_amount: Money
    saved_amount: Money = Decimal("0")
    target_date: date


class EmployerMatch(StrictModel):
    # Confirmed by the user's payroll estimate, not inferred from a match rate.
    additional_take_home_cost: Money
    additional_employer_match: Money


class Snapshot(StrictModel):
    as_of: date
    currency: Literal["USD"] = "USD"
    cash_balance: Money
    monthly_income: Money
    essential_expenses: Money
    discretionary_expenses: Money
    emergency_fund: Money
    emergency_months: int = Field(default=3, ge=1, le=12)
    debts: list[Debt] = Field(default_factory=list, max_length=20)
    goal: Goal | None = None
    employer_match: EmployerMatch | None = None

    @model_validator(mode="after")
    def consistent_snapshot(self):
        earmarked = self.emergency_fund + (self.goal.saved_amount if self.goal else 0)
        if earmarked > self.cash_balance:
            raise ValueError("Emergency and goal savings are separate portions of total cash; their sum cannot exceed it.")
        if len({d.id for d in self.debts}) != len(self.debts):
            raise ValueError("Every debt must have a unique ID.")
        if self.goal and self.goal.target_date <= self.as_of:
            raise ValueError("The goal deadline must be later than the snapshot date.")
        if self.as_of > date.today():
            raise ValueError("The snapshot date cannot be in the future.")
        if self.employer_match and self.employer_match.additional_employer_match > 0:
            if self.employer_match.additional_take_home_cost == 0:
                raise ValueError("Provide the additional take-home pay cost to unlock this match.")
        return self


class AnalysisRequest(StrictModel):
    request_id: UUID
    user_id: UUID
    snapshot: Snapshot


class FeedbackRequest(StrictModel):
    action_id: str = Field(default="overview", min_length=1, max_length=80)
    rating: Literal["helpful", "not_helpful"] | None = None
    action_status: Literal["accepted", "completed", "dismissed"] | None = None
    comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def has_feedback(self):
        if self.rating is None and self.action_status is None and not self.comment:
            raise ValueError("Choose a rating, action status, or comment.")
        return self


class Preferences(StrictModel):
    improvement_opt_in: bool
