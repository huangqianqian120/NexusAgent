"""多用户系统数据模型."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel


# ---- 用户相关 ----


class User(SQLModel, table=True):
    """用户账号."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str  # bcrypt 哈希
    username: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    credits_balance: float = Field(default=0.0, sa_column=Column(Numeric(18, 4)))
    last_login_at: Optional[datetime] = None


class CreditTransaction(SQLModel, table=True):
    """Credits 变动记录."""

    __tablename__ = "credit_transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    amount: float = Field(default=0.0, sa_column=Column(Numeric(18, 4)))  # 正数=增加，负数=消费
    balance_after: float = Field(default=0.0, sa_column=Column(Numeric(18, 4)))  # 变动后余额
    transaction_type: str  # admin_allocation / api_usage / refund / bonus
    description: str = ""
    # API 使用相关（可选）
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---- API Key 相关 ----


class ApiKey(SQLModel, table=True):
    """系统级 API Key 配置（管理员设置，提供给所有用户使用）."""

    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)  # anthropic / openai / ...
    api_key: str  # 加密存储更好，这里先明文（后续可加固）
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---- 模型单价配置 ----


class ModelPricing(SQLModel, table=True):
    """模型单价配置（管理员可编辑）."""

    __tablename__ = "model_pricing"

    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: str = Field(index=True, unique=True)  # e.g. "claude-sonnet-4-20250514"
    input_cost_per_million: float = Field(default=3.0)  # USD per million input tokens
    output_cost_per_million: float = Field(default=15.0)  # USD per million output tokens
    is_active: bool = Field(default=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)