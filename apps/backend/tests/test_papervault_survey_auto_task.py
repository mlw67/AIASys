"""PaperVault 文献综述 AutoTask 端到端流程验证。

本测试验证：
1. 基于 literature-survey 模板语义创建 continuous AutoTask 可被正确持久化。
2. 执行器构建的 prompt 包含综述工作流标记、PaperVault 工具调用指令和停止信号。
3. 不依赖真实 LLM 调用（通过 mock agent_service.execute）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.agent import agent_service
from app.services.auto_tasks import engine as auto_task_engine
from app.services.auto_tasks.executor import _build_prompt
from app.services.auto_tasks.models import (
    AutoTask,
    AutoTaskTriggerType,
    TaskCategory,
)
from app.services.workspace_registry import WorkspaceRegistryService


SURVEY_CONTINUATION_PROMPT = """你是 PaperVault 文献综述自动化 Agent，当前负责围绕主题「federated learning」完成一份可审查的文献综述。

检索策略：
- 关键词：federated learning, privacy
- 会议范围：ICML, NeurIPS, ICLR
- 年份范围：2020-2025
- 要求有代码链接

产物路径：
- research/federated_learning/search_strategy.md
- research/federated_learning/candidate_papers.md
- research/federated_learning/trends.json
- research/federated_learning/survey_outline.md
- research/federated_learning/survey_draft.md
- .aiasys/memory/workspace_memory.md（仅追加关键结论）

当前阶段判断规则：
- 如果 search_strategy.md 不存在 -> plan（通过 AskUser 确认策略）
- 如果 candidate_papers.md 不存在 -> collect
- 如果 candidate_papers.md 存在但未标注已筛选 -> filter
- 如果 trends.json 不存在 -> analyze
- 如果 survey_outline.md 不存在 -> draft outline
- 如果 survey_draft.md 不存在 -> draft full survey
- 如果以上都存在 -> review / iterate / complete（ AskUser 决定）

每轮执行纪律：
1. 每轮开始前读取 research/federated_learning/ 下已有产物。
2. 判断当前阶段：collect -> filter -> analyze -> draft -> review -> iterate -> complete。
3. 每次只推进一个阶段，使用 PaperVaultSearch / PaperVaultStats 或 Task 子 Agent。
4. 所有结论必须标注来源论文 title + url。
5. 关键节点必须调用 AskUser(type="confirm") 暂停等待用户确认。
6. 无法继续时调用 auto_task_signal(action="pause")。
7. 综述最终确认后调用 auto_task_signal(action="complete")。
"""


def test_survey_continuation_prompt_is_injected_into_execution_prompt() -> None:
    task = AutoTask(
        task_id="survey-task-1",
        workspace_id="ws-survey",
        user_id="local_default",
        prompt="完成 federated learning 方向的文献综述",
        trigger_type=AutoTaskTriggerType.continuous,
        trigger_value="",
        task_category=TaskCategory.continuous,
        continuation_prompt=SURVEY_CONTINUATION_PROMPT,
    )

    prompt = _build_prompt(task)

    assert "目标: 完成 federated learning 方向的文献综述" in prompt
    assert "PaperVault 文献综述自动化 Agent" in prompt
    assert "PaperVaultSearch" in prompt
    assert "PaperVaultStats" in prompt
    assert "AskUser(type=\"confirm\")" in prompt
    assert 'auto_task_signal(action="pause")' in prompt
    assert 'auto_task_signal(action="complete")' in prompt


@pytest.mark.asyncio
async def test_continuous_survey_task_runs_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setattr(auto_task_engine, "WORKSPACE_DIR", str(tmp_path))
    service = WorkspaceRegistryService(tmp_path)
    service.create_workspace(
        user_id="local_default",
        title="Survey Workspace",
        workspace_id="ws-survey",
        initial_conversation_id="conv-survey",
    )
    monkeypatch.setattr(
        "app.services.auto_tasks.executor.get_workspace_registry_service",
        lambda: service,
    )

    captured_prompts: list[str] = []

    async def _fake_execute(*, prompt: str, **kwargs) -> str:
        captured_prompts.append(prompt)
        return "本轮已收集候选论文并写入 candidate_papers.md"

    monkeypatch.setattr(agent_service, "execute", _fake_execute)

    task = AutoTask(
        task_id="survey-task-2",
        workspace_id="ws-survey",
        user_id="local_default",
        prompt="完成 federated learning 方向的文献综述",
        trigger_type=AutoTaskTriggerType.continuous,
        trigger_value="",
        task_category=TaskCategory.continuous,
        bind_session_id="conv-survey",
        continuation_prompt=SURVEY_CONTINUATION_PROMPT,
    )
    auto_task_engine.AutoTaskStore.put_task("local_default", "ws-survey", task)

    await auto_task_engine._execute_and_persist(task)

    persisted = auto_task_engine.AutoTaskStore.get_task(
        "local_default", "ws-survey", "survey-task-2"
    )
    assert persisted is not None
    assert persisted.fired_count == 1
    assert persisted.status.value == "active"

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    assert "PaperVault 文献综述自动化 Agent" in prompt
    assert "PaperVaultSearch" in prompt
    assert "PaperVaultStats" in prompt


def test_survey_template_matches_skill_workflow_markers(tmp_path) -> None:
    """验证 AutoTask prompt 包含 Skill 中定义的关键产物路径和阶段规则。"""
    task = AutoTask(
        task_id="survey-task-3",
        workspace_id="ws-survey",
        user_id="local_default",
        prompt="完成 federated learning 方向的文献综述",
        trigger_type=AutoTaskTriggerType.continuous,
        trigger_value="",
        task_category=TaskCategory.continuous,
        continuation_prompt=SURVEY_CONTINUATION_PROMPT,
    )

    prompt = _build_prompt(task)

    for marker in [
        "research/federated_learning/",
        "collect -> filter -> analyze -> draft -> review -> iterate -> complete",
        "candidate_papers.md",
        "trends.json",
        "survey_draft.md",
    ]:
        assert marker in prompt, f"prompt 缺少关键标记: {marker}"
