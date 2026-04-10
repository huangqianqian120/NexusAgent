"""Skill exports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from nexus.skills.registry import SkillRegistry
    from nexus.skills.types import SkillDefinition

__all__ = ["SkillDefinition", "SkillRegistry", "get_user_skills_dir", "load_skill_registry"]


def __getattr__(name: str):
    if name in {"get_user_skills_dir", "load_skill_registry"}:
        from nexus.skills.loader import get_user_skills_dir, load_skill_registry

        return {
            "get_user_skills_dir": get_user_skills_dir,
            "load_skill_registry": load_skill_registry,
        }[name]
    if name == "SkillRegistry":
        from nexus.skills.registry import SkillRegistry

        return SkillRegistry
    if name == "SkillDefinition":
        from nexus.skills.types import SkillDefinition

        return SkillDefinition
    raise AttributeError(name)
