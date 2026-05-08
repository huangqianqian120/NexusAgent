"""Credits 计费系统（后置扣费）."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from sqlmodel import select

from nexus.multi_user.db import get_session
from nexus.multi_user.models import CreditTransaction, ModelPricing, User

log = logging.getLogger(__name__)

# 默认模型单价配置（USD per million tokens）
DEFAULT_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-20241022": {"input": 0.8, "output": 4.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "mini-max-01": {"input": 0.2, "output": 1.0},
    "MiniMax-Text-01": {"input": 0.2, "output": 1.0},
}

# ---- 统一 Credits 单价配置 ----
# 固定汇率：每 1000 tokens = UNIFORM_CREDITS_PER_1K Tokens Credits
UNIFORM_CREDITS_PER_1K = float(os.environ.get("UNIFORM_CREDITS_PER_1K", "0.001"))
# 即每 1000 tokens = 0.001 Credits，可根据实际情况调整

_pricing_file = Path(__file__).parent.parent.parent.parent / ".nexus" / "model_pricing.json"
_pricing_file.parent.mkdir(parents=True, exist_ok=True)


def get_model_pricing(model_id: str) -> tuple[float, float]:
    """
    获取模型的 input/output 单价（USD per million tokens）.

    优先级：数据库配置 > 本地 JSON 文件 > 默认配置
    """
    session = get_session()
    db_pricing = session.exec(
        select(ModelPricing).where(
            ModelPricing.model_id == model_id,
            ModelPricing.is_active,
        )
    ).first()
    session.close()

    if db_pricing:
        return db_pricing.input_cost_per_million, db_pricing.output_cost_per_million

    # 尝试从本地 JSON 文件读取
    if _pricing_file.exists():
        try:
            pricing_data = json.loads(_pricing_file.read_text())
            if model_id in pricing_data:
                p = pricing_data[model_id]
                return float(p.get("input", 0)), float(p.get("output", 0))
        except Exception:
            pass

    # 回退到默认配置
    if model_id in DEFAULT_PRICING:
        p = DEFAULT_PRICING[model_id]
        return p["input"], p["output"]

    # 未知模型返回默认值（警告）
    return 3.0, 15.0


def calculate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    计算一次 LLM 调用的费用（USD）.

    公式: (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    """
    input_price, output_price = get_model_pricing(model_id)
    cost = (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
    return round(cost, 8)


def deduct_credits(
    user_id: int,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    description: str = "",
) -> tuple[bool, str, float]:
    """
    后置扣费：检查余额，扣费，记录交易.

    返回: (成功标志, 消息, 实际扣费金额)
    """
    cost_usd = calculate_cost(model_id, input_tokens, output_tokens)
    cost_credits = cost_usd  # 1:1 映射 USD → Credits（后续可调整汇率）

    session = get_session()
    user = session.get(User, user_id)
    if not user:
        session.close()
        return False, "用户不存在", 0.0

    if user.credits_balance < float(cost_credits):
        session.close()
        return False, f"Credits 余额不足（需要 {cost_credits:.4f}，当前 {float(user.credits_balance):.4f}）", 0.0

    # 扣费
    user.credits_balance = float(user.credits_balance) - float(cost_credits)

    # 记录交易
    tx = CreditTransaction(
        user_id=user_id,
        amount=-float(cost_credits),
        balance_after=float(user.credits_balance),
        transaction_type="api_usage",
        description=description or f"LLM 调用: {model_id}",
        model=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
    session.add(tx)
    session.commit()
    session.close()

    return True, "扣费成功", float(cost_credits)


def charge_if_enough(
    user_id: int,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    description: str = "",
) -> tuple[bool, float]:
    """
    扣费（忽略余额不足错误，返回实际扣费）.

    用于 LLM 调用完成后，无论余额是否充足都尝试扣费。
    余额不足时记录负余额，后续要求充值。
    """
    cost_usd = calculate_cost(model_id, input_tokens, output_tokens)
    cost_credits = cost_usd

    session = get_session()
    user = session.get(User, user_id)

    new_balance = float(user.credits_balance) - float(cost_credits)
    user.credits_balance = float(new_balance)

    tx = CreditTransaction(
        user_id=user_id,
        amount=-float(cost_credits),
        balance_after=float(new_balance),
        transaction_type="api_usage",
        description=description or f"LLM 调用: {model_id}",
        model=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
    session.add(tx)
    session.commit()
    session.close()

    return True, float(cost_credits)


def get_user_balance(user_id: int) -> tuple[Optional[float], str]:
    """获取用户余额."""
    session = get_session()
    user = session.get(User, user_id)
    session.close()

    if not user:
        return None, "用户不存在"
    return user.credits_balance, "成功"


def check_balance_enough(user_id: int, estimated_cost: float) -> tuple[bool, str]:
    """预检查：估算费用是否足够."""
    session = get_session()
    user = session.get(User, user_id)
    session.close()

    if not user:
        return False, "用户不存在"
    if float(user.credits_balance) < estimated_cost:
        return False, f"余额不足（需要 ~{estimated_cost:.4f}，当前 {float(user.credits_balance):.4f}）"
    return True, "余额充足"


def charge_uniform(
    user_id: int,
    input_tokens: int,
    output_tokens: int,
    model_id: str = "",
    description: str = "",
) -> tuple[bool, str, float]:
    """
    统一扣费：不区分模型，按 token 总数扣 Credits。

    公式: total_tokens / 1000 * UNIFORM_CREDITS_PER_1K

    参数:
        user_id: 用户 ID
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
        model_id: 模型 ID（仅用于记录）
        description: 交易描述

    返回: (成功标志, 消息, 实际扣费金额)
    """
    total_tokens = input_tokens + output_tokens
    cost_credits = round(total_tokens / 1000.0 * UNIFORM_CREDITS_PER_1K, 8)

    session = get_session()
    user = session.get(User, user_id)
    if not user:
        session.close()
        return False, "用户不存在", 0.0

    new_balance = float(user.credits_balance) - cost_credits
    user.credits_balance = float(new_balance)

    tx = CreditTransaction(
        user_id=user_id,
        amount=-cost_credits,
        balance_after=float(new_balance),
        transaction_type="api_usage",
        description=description or "AI 对话消耗",
        model=model_id or "uniform",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=None,
    )
    session.add(tx)
    session.commit()
    session.close()

    log.info(
        "统一扣费: user_id=%d input=%d output=%d total=%d cost=%.6f credits",
        user_id, input_tokens, output_tokens, total_tokens, cost_credits,
    )
    return True, "扣费成功", cost_credits


def init_default_pricing() -> None:
    """初始化默认模型单价配置（幂等）."""
    session = get_session()
    for model_id, prices in DEFAULT_PRICING.items():
        existing = session.exec(
            select(ModelPricing).where(ModelPricing.model_id == model_id)
        ).first()
        if not existing:
            mp = ModelPricing(
                model_id=model_id,
                input_cost_per_million=prices["input"],
                output_cost_per_million=prices["output"],
            )
            session.add(mp)
    session.commit()
    session.close()


def list_all_pricing() -> list[dict]:
    """列出所有模型单价配置."""
    session = get_session()
    rows = session.exec(select(ModelPricing).order_by(ModelPricing.model_id)).all()
    session.close()
    return [
        {
            "model_id": r.model_id,
            "input_cost_per_million": r.input_cost_per_million,
            "output_cost_per_million": r.output_cost_per_million,
            "is_active": r.is_active,
            "description": r.description,
        }
        for r in rows
    ]