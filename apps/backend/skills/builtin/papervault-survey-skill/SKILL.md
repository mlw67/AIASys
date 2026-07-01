+++
name = "PaperVault 文献综述自动化"
description = "以 PaperVault 论文元数据为基础，自动化完成主题驱动的文献综述。适用于用户给定研究方向后，由 Agent 主导检索、筛选、分析、起草综述草稿，并在关键节点暂停等待研究员审核。"
+++

# PaperVault 文献综述自动化

## 定位

本 Skill 是**主题驱动文献综述**的 AutoTask 工作流入口。它不替代 `papervault-research-skill` 的论文搜索能力，而是把搜索、筛选、统计、起草、审核组织成一个可自动运行的闭环。

适用场景：

- 用户说“帮我调研一下 XXX 方向”
- 需要为某个研究主题生成可审查的文献综述草稿
- 希望 Agent 自动收集论文、生成趋势分析、并在关键节点暂停等待确认

## 工作流生命周期

综述自动化遵循以下生命周期：

```
plan -> collect -> filter -> analyze -> draft -> review -> iterate -> complete
```

| 阶段 | 动作 | 关键工具/子 Agent |
|---|---|---|
| `plan` | 与用户确认主题、检索策略、会议范围、年份范围、是否需要代码链接 | `AskUser` |
| `collect` | 检索候选论文 | `PaperVaultSearch` / `Task(subagent_name="researcher")` |
| `filter` | 剔除低相关度论文，标注高质量候选 | `Task(subagent_name="reviewer")` |
| `analyze` | 生成趋势统计、会议分布、年度分布 | `PaperVaultStats` / `Task(subagent_name="data_analyst")` |
| `draft` | 聚合结果，生成综述草稿 | 主控 Agent + `WriteFile` |
| `review` | 暂停等待用户审核：检索策略 / 候选列表 / 大纲 / 草稿 | `AskUser` |
| `iterate` | 根据反馈继续检索、补充或重写 | 循环 collect → filter → analyze → draft |
| `complete` | 用户确认最终综述，写入 memory，标记任务完成 | `auto_task_signal(action="complete")` |

## 执行纪律

1. **每轮只做一件事**：不要在一次 AutoTask 轮次里同时做搜索、筛选、分析、起草。
2. **先读已有产物**：每轮开始前读取 `research/{topic}/` 下已有文件，避免重复。
3. **来源可追溯**：每条结论必须标注来源论文的 `title` 和 `url`。
4. **关键节点暂停**：以下节点必须调用 `AskUser(type="confirm")` 等待用户确认：
   - 检索策略确认
   - 候选论文列表确认
   - 综述大纲确认
   - 最终综述确认
5. **不 hallucinate**：如果搜索结果为空或质量不足，如实报告，不要编造论文。
6. **任务完成标记**：综述最终确认后，调用 `auto_task_signal(action="complete")`。
7. **阻塞时暂停**：遇到无法自行解决的问题（如数据未就绪、策略冲突），调用 `auto_task_signal(action="pause")`。

## 产物沉淀

所有产物写入当前工作区 `{workspace}/research/{topic}/`：

| 文件 | 内容 |
|---|---|
| `research/{topic}/search_strategy.md` | 确认后的检索策略 |
| `research/{topic}/candidate_papers.md` | 候选论文列表（Markdown 表格） |
| `research/{topic}/trends.json` | 趋势统计数据（JSON，可渲染 ECharts） |
| `research/{topic}/survey_outline.md` | 综述大纲 |
| `research/{topic}/survey_draft.md` | 综述草稿 |
| `.aiasys/memory/workspace_memory.md` | 追加关键结论 |

## 如何启动

### 方式一：从当前会话启动（推荐）

1. 用户提出主题。
2. 你（主控 Agent）先与用户确认检索策略（用 `AskUser`）。
3. 确认后，创建一个 `continuous` AutoTask 并绑定到当前会话：

```json
{
  "name": "CreateAutoTask",
  "arguments": {
    "trigger_type": "continuous",
    "title": "文献综述：{topic}",
    "prompt": "你是 PaperVault 文献综述自动化 Agent，当前负责围绕主题「{topic}」完成一份可审查的文献综述。\n\n检索策略：{strategy_summary}\n\n每轮执行纪律：\n1. 读取已有产物（research/{topic}/ 下文件）。\n2. 判断当前阶段（collect / filter / analyze / draft / review / iterate / complete）。\n3. 使用 PaperVaultSearch / PaperVaultStats 或调用 Task 子 Agent 推进一个阶段。\n4. 所有结论标注来源论文 title + url。\n5. 到达关键审核点时调用 AskUser(type='confirm')。\n6. 完成后调用 auto_task_signal(action='complete')。\n7. 阻塞时调用 auto_task_signal(action='pause')。\n\n产物路径：research/{topic}/",
    "bind_session_id": "<当前 session_id>",
    "session_strategy": "bind_session",
    "max_continuations": -1,
    "stop_on_signal": true
  }
}
```

4. AutoTask 启动后，按照生命周期自动推进。

### 方式二：单次会话执行

如果用户不想创建 AutoTask，也可以直接在当前会话中按生命周期逐步执行，手动调用 `PaperVaultSearch`、`PaperVaultStats`、`Task`、`WriteFile` 完成。

## 子 Agent 分工

### researcher

负责检索候选论文。Prompt 示例：

> 请围绕「{topic}」检索相关论文。使用 PaperVaultSearch，先 broad 搜索，再逐步用 conf/year/has_code 筛选。返回 Markdown 表格，包含：年份、会议、标题、作者、代码、链接、摘要（截断到 200 字）。

### reviewer

负责筛选高质量论文。Prompt 示例：

> 请审查 `research/{topic}/candidate_papers.md` 中的候选论文，剔除与主题不相关或质量不足的条目，保留最相关的 10-20 篇，并给出筛选理由。

### data_analyst

负责趋势分析。Prompt 示例：

> 请使用 PaperVaultStats 获取「{topic}」相关会议的统计信息，并生成趋势分析。将统计结果写入 `research/{topic}/trends.json`（ECharts 可渲染格式），并写出 3-5 条关键发现。

## 综述草稿格式

`research/{topic}/survey_draft.md` 建议结构：

```markdown
# {topic} 文献综述

## 1. 研究背景与问题定义

## 2. 检索策略

- 关键词：...
- 会议范围：...
- 年份范围：...
- 初始命中数：...

## 3. 候选论文概览

（引用 candidate_papers.md 中的表格）

## 4. 趋势分析

（引用 trends.json 的图表描述）

## 5. 方法分类与对比

## 6. 开源代码与可复现性

## 7. 研究空白与未来方向

## 8. 结论

## 参考文献

- [title](url)
```

## 与相邻 Skill 的边界

- `papervault-research-skill`：单次/轻量论文搜索，不提供综述工作流。
- `arxiv-search-skill`：补充下载 PDF，用于精读关键论文。
- `aiasys-memory-organizer-skill`：手动整理和压缩 memory，本 Skill 自动追加关键结论。
- `competition-research-skill`：面向竞赛实验闭环，本 Skill 面向文献综述。

## 重要约束

- 本 Skill 不执行代码复现，只生成综述文本和统计数据。
- 不要在未确认的情况下直接写入 workspace memory。
- 不要把 `paper_url` 当作可执行命令。
- 如果 PaperVault 数据未就绪，先调用 `PaperVaultSearch` 或 `PaperVaultStats` 触发自动同步。
