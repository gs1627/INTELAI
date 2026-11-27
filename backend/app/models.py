from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Processor(Base):
    __tablename__ = "processor_catalogue"
    processor_id: Mapped[str] = mapped_column(String, primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String, default="Intel")
    tier: Mapped[int] = mapped_column(Integer)
    series: Mapped[int] = mapped_column(Integer)
    exact_sku: Mapped[str] = mapped_column(String, unique=True, index=True)
    cpu_specifications: Mapped[dict] = mapped_column(JSON, default=dict)
    gpu_specifications: Mapped[dict] = mapped_column(JSON, default=dict)
    npu_specifications: Mapped[dict] = mapped_column(JSON, default=dict)

class Laptop(Base):
    __tablename__ = "laptop_catalogue"
    laptop_id: Mapped[str] = mapped_column(String, primary_key=True)
    brand: Mapped[str] = mapped_column(String, index=True)
    model_name: Mapped[str] = mapped_column(String)
    retail_sku: Mapped[str] = mapped_column(String, default="")
    processor_id: Mapped[str] = mapped_column(ForeignKey("processor_catalogue.processor_id"))
    ram: Mapped[str] = mapped_column(String)
    gpu: Mapped[str] = mapped_column(String)
    storage: Mapped[str] = mapped_column(String)
    bios_version: Mapped[str] = mapped_column(String, default="unknown")
    driver_version: Mapped[str] = mapped_column(String, default="unknown")
    power_profile: Mapped[str] = mapped_column(String, default="unknown")
    price: Mapped[float] = mapped_column(Float)
    stock_status: Mapped[str] = mapped_column(String, default="unknown")

class BenchmarkTest(Base):
    __tablename__ = "benchmark_tests"
    test_id: Mapped[str] = mapped_column(String, primary_key=True)
    round_id: Mapped[str] = mapped_column(String, index=True)
    benchmark_version: Mapped[str] = mapped_column(String)
    task_definition: Mapped[dict] = mapped_column(JSON, default=dict)
    model_hash: Mapped[str] = mapped_column(String, default="")
    prompt_hash: Mapped[str] = mapped_column(String, default="")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

class BenchmarkSession(Base):
    __tablename__ = "benchmark_sessions"
    benchmark_session_id: Mapped[str] = mapped_column(String, primary_key=True)
    laptop_id: Mapped[str] = mapped_column(ForeignKey("laptop_catalogue.laptop_id"))
    test_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    operating_system: Mapped[str] = mapped_column(String, default="unknown")
    runtime_version: Mapped[str] = mapped_column(String, default="unknown")
    power_state: Mapped[str] = mapped_column(String, default="unknown")
    test_environment: Mapped[dict] = mapped_column(JSON, default=dict)

class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"
    result_id: Mapped[str] = mapped_column(String, primary_key=True)
    benchmark_session_id: Mapped[str] = mapped_column(ForeignKey("benchmark_sessions.benchmark_session_id"))
    test_id: Mapped[str] = mapped_column(ForeignKey("benchmark_tests.test_id"))
    completion_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    task_success: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_provider: Mapped[str] = mapped_column(String, default="UNKNOWN")
    verification_status: Mapped[str] = mapped_column(String, default="PENDING")
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
    benchmark_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)

class GameSession(Base):
    __tablename__ = "game_sessions"
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    current_laptop_id: Mapped[str | None] = mapped_column(String, nullable=True)
    persona: Mapped[str] = mapped_column(String, default="")
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str] = mapped_column(String, default="")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priorities: Mapped[list] = mapped_column(JSON, default=list)
    workloads: Mapped[list] = mapped_column(JSON, default=list)
    preferred_features: Mapped[list] = mapped_column(JSON, default=list)
    portability: Mapped[str] = mapped_column(String, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

class RoundEvent(Base):
    __tablename__ = "round_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id"), index=True)
    round_id: Mapped[str] = mapped_column(String)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String, default="PARTIAL")
    browser_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    local_runner_reference: Mapped[str] = mapped_column(String, default="")

class RecommendationResult(Base):
    __tablename__ = "recommendation_results"
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id"), primary_key=True)
    recommended_laptop_ids: Mapped[list] = mapped_column(JSON, default=list)
    comparison_profile_ids: Mapped[list] = mapped_column(JSON, default=list)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    price_differences: Mapped[dict] = mapped_column(JSON, default=dict)

class SessionHistory(Base):
    __tablename__ = "session_history"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class HandoffToken(Base):
    __tablename__ = "handoff_tokens"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Product(Base):
    __tablename__ = "products"
    product_id: Mapped[str] = mapped_column(String, primary_key=True)
    brand: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String, index=True)
    processor: Mapped[dict] = mapped_column(JSON, default=dict)
    ram_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display: Mapped[dict] = mapped_column(JSON, default=dict)
    battery: Mapped[dict] = mapped_column(JSON, default=dict)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="INR")
    ai_pc: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String, default="")
    verification_status: Mapped[str] = mapped_column(String, default="UNVERIFIED")
    is_sample: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

class Inventory(Base):
    __tablename__ = "demo_inventory"
    inventory_id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    location: Mapped[str] = mapped_column(String, default="DEMO")
    quantity: Mapped[int] = mapped_column(Integer, default=0)

class Reservation(Base):
    __tablename__ = "reservations"
    reservation_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id"), index=True)
    inventory_id: Mapped[str] = mapped_column(ForeignKey("demo_inventory.inventory_id"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="CONFIRMED", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

class DemoResult(Base):
    __tablename__ = "demo_results"
    demo_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id"), index=True)
    workload: Mapped[str] = mapped_column(String)
    input_reference: Mapped[str] = mapped_column(String, default="")
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_mode: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Associate(Base):
    __tablename__ = "associates"
    associate_id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Interaction(Base):
    __tablename__ = "interactions"
    interaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    associate_id: Mapped[str] = mapped_column(ForeignKey("associates.associate_id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.session_id"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.product_id"), nullable=True)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("reservations.reservation_id"), nullable=True)
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[str] = mapped_column(String, default="FOLLOW_UP_REQUIRED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
