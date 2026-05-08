"""NexusAgent 多用户系统."""

from nexus.multi_user.db import create_all_tables, get_session, init_db
from nexus.multi_user.models import CreditTransaction, ModelPricing, User
from nexus.multi_user.auth import create_jwt, decode_jwt, hash_password, verify_password
from nexus.multi_user.credits import (
    calculate_cost,
    check_balance_enough,
    deduct_credits,
    get_model_pricing,
    get_user_balance,
    init_default_pricing,
    list_all_pricing,
)
from nexus.multi_user.middleware import require_admin, require_auth, optional_auth

__all__ = [
    "create_all_tables",
    "get_session",
    "init_db",
    "User",
    "CreditTransaction",
    "ModelPricing",
    "create_jwt",
    "decode_jwt",
    "hash_password",
    "verify_password",
    "calculate_cost",
    "check_balance_enough",
    "deduct_credits",
    "get_model_pricing",
    "get_user_balance",
    "init_default_pricing",
    "list_all_pricing",
    "require_admin",
    "require_auth",
    "optional_auth",
]
