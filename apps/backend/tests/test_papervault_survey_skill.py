"""PaperVault 文献综述 Skill 可加载性测试。"""

from __future__ import annotations

from pathlib import Path

from app.skills.manager import get_skill_manager


SKILL_NAME = "papervault-survey-skill"


def test_papervault_survey_skill_is_discoverable() -> None:
    manager = get_skill_manager()
    store_names = {skill.name for skill in manager.list_store_skills()}
    assert SKILL_NAME in store_names, f"{SKILL_NAME} 未在 Skill 仓库中发现"


def test_papervault_survey_skill_entry_is_loadable() -> None:
    manager = get_skill_manager()
    backend_root = Path(__file__).resolve().parents[1]
    result = manager.get_skill_file_content(
        skill_name=SKILL_NAME,
        workspace_path=backend_root,
    )
    assert result is not None
    _skill_info, content, _refs = result
    assert "PaperVault 文献综述自动化" in content
    assert "+++" in content  # TOML frontmatter


def test_papervault_survey_skill_references_are_loadable() -> None:
    manager = get_skill_manager()
    backend_root = Path(__file__).resolve().parents[1]

    references = [
        "references/workflow.md",
        "references/prompts.md",
        "references/output-format.md",
    ]
    for ref in references:
        result = manager.get_skill_file_content(
            skill_name=SKILL_NAME,
            workspace_path=backend_root,
            relative_path=ref,
        )
        assert result is not None, f"无法加载 {ref}"
        _skill_info, content, _refs = result
        assert len(content.strip()) > 0, f"{ref} 为空"


def test_papervault_survey_skill_frontmatter_has_name_and_description() -> None:
    manager = get_skill_manager()
    backend_root = Path(__file__).resolve().parents[1]
    result = manager.get_skill_file_content(
        skill_name=SKILL_NAME,
        workspace_path=backend_root,
    )
    assert result is not None
    _skill_info, content, _refs = result
    # 简单检查 frontmatter 中是否包含 name 和 description
    assert "name = " in content
    assert "description = " in content
