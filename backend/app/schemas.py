from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class SessionIn(BaseModel):
    session_id: str | None = Field(default=None, min_length=8, max_length=80)
    current_laptop_id: str | None = None
    persona: str = Field(default="", max_length=30)
    budget: float | None = Field(default=None, ge=60000, le=200000)
    priority: str = Field(default="", max_length=80)
    priorities: list[str] = Field(default_factory=list, max_length=20)
    workloads: list[str] = Field(default_factory=list, max_length=30)
    preferred_features: list[str] = Field(default_factory=list, max_length=30)
    portability: str = Field(default="", max_length=40)

class EventIn(BaseModel):
    event_id: str = Field(min_length=8, max_length=80)
    session_id: str = Field(min_length=8, max_length=80)
    round_id: str = Field(min_length=1, max_length=50)
    outcome: str = Field(pattern="^(COMPLETED|PARTIAL|FAILED)$")
    browser_metrics: dict = Field(default_factory=dict)
    local_runner_reference: str = Field(default="", max_length=100)

class LaptopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    laptop_id: str
    brand: str
    model_name: str
    processor_id: str
    ram: str
    gpu: str
    storage: str
    price: float

class BenchmarkOut(BaseModel):
    result_id: str
    laptop_id: str
    brand: str
    model_name: str
    processor_sku: str
    tier: int
    series: int
    round_id: str
    completion_time: float | None
    fps: float | None
    task_success: bool
    verification_status: str
    sample_count: int
    test_date: datetime
    is_sample: bool

class BenchmarkIn(BaseModel):
    result_id: str
    benchmark_session_id: str
    laptop_id: str
    test_id: str
    completion_time: float | None = Field(default=None, gt=0)
    fps: float | None = Field(default=None, gt=0)
    task_success: bool
    execution_provider: str
    verification_status: str = "PENDING"
    sample_count: int = Field(default=1, ge=1, le=1000)
    is_sample: bool = False

