"""多用户系统数据库模块."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

if TYPE_CHECKING:
    pass

# 数据库路径（放在项目根目录的 .nexus 目录下）
_project_root = Path(__file__).parent.parent.parent.parent
_db_path = _project_root / ".nexus" / "multi_user.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)

# SQLite 数据库引擎
engine = create_engine(
    f"sqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)


def init_db() -> None:
    """初始化数据库表（幂等调用）."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """获取数据库会话（自动初始化）."""
    init_db()
    return Session(engine)


def create_all_tables() -> None:
    """强制创建所有表（用于首次初始化）."""
    SQLModel.metadata.create_all(engine)