"""Моделі запитів API (pydantic). Межі розмірів захищають сервер від надто важких задач."""
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from mco.constraints import OPERATORS

MAX_ROWS = 100_000
MAX_CRITERIA = 50

Sense = Literal['max', 'min']


class CriterionIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sense: Sense = 'max'
    weight: float = Field(default=1.0, ge=0)


class ConstraintIn(BaseModel):
    column: str = Field(min_length=1, max_length=200)
    op: str
    value: str | float | int

    @field_validator('op')
    @classmethod
    def known_op(cls, v):
        if v not in OPERATORS:
            raise ValueError(f'невідомий оператор «{v}»; допустимі: {", ".join(OPERATORS)}')
        return v


class DiscreteProblem(BaseModel):
    """Постановка дискретної задачі: таблиця альтернатив, критерії, обмеження."""
    records: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_ROWS)
    name_column: str | None = None
    criteria: list[CriterionIn] = Field(min_length=2, max_length=MAX_CRITERIA)
    constraints: list[ConstraintIn] = Field(default_factory=list, max_length=100)
    missing: Literal['error', 'drop', 'median'] = 'error'


class SolveRequest(BaseModel):
    problem: DiscreteProblem
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    problem: DiscreteProblem
    methods: list[str] | None = None


class SensitivityRequest(BaseModel):
    problem: DiscreteProblem
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    criterion: str
    steps: int = Field(default=41, ge=3, le=201)


class MonteCarloRequest(BaseModel):
    problem: DiscreteProblem
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    samples: int = Field(default=1000, ge=10, le=10_000)
    concentration: float = Field(default=30.0, gt=0, le=1000)
    seed: int = Field(default=0, ge=0)


class WeightsRequest(BaseModel):
    """Дані потрібні для ентропії та CRITIC, порядок – для ROC, матриця – для AHP."""
    criteria: list[CriterionIn] = Field(min_length=2, max_length=MAX_CRITERIA)
    records: list[dict[str, Any]] | None = Field(default=None, max_length=MAX_ROWS)
    order: list[str] | None = None
    matrix: list[list[float]] | None = None


# --------------------------------------------------------------------- неперервні задачі
class VariableIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    lo: float = 0.0
    hi: float = 10.0


class ObjectiveIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expr: str = Field(min_length=1, max_length=500)
    sense: Sense = 'max'
    weight: float = Field(default=1.0, ge=0)


class ContConstraintIn(BaseModel):
    expr: str = Field(min_length=1, max_length=500)
    op: Literal['≤', '≥', '=', '<=', '>=']
    rhs: float = 0.0


class ContinuousProblem(BaseModel):
    variables: list[VariableIn] = Field(min_length=1, max_length=30)
    objectives: list[ObjectiveIn] = Field(min_length=2, max_length=6)
    constraints: list[ContConstraintIn] = Field(default_factory=list, max_length=50)
    starts: int = Field(default=8, ge=1, le=50)


class ContinuousSolveRequest(BaseModel):
    problem: ContinuousProblem
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class NsgaParams(BaseModel):
    pop_size: int = Field(default=100, ge=4, le=1000)
    generations: int = Field(default=100, ge=1, le=2000)
    pc: float = Field(default=0.9, ge=0, le=1)
    eta_c: float = Field(default=15.0, gt=0, le=100)
    eta_m: float = Field(default=20.0, gt=0, le=100)
    seed: int = Field(default=0, ge=0)


class FrontRequest(BaseModel):
    problem: ContinuousProblem
    method: Literal['chebyshev', 'eps', 'weighted', 'nsga2'] = 'chebyshev'
    points: int = Field(default=30, ge=2, le=500)
    nsga: NsgaParams = Field(default_factory=NsgaParams)


class ShopLoadRequest(BaseModel):
    pages: int = Field(default=2, ge=1, le=20)
    use_cache: bool = True
