# 文献综述自动化工作流详解

## 阶段 1：Plan（规划）

目标：与用户确认研究主题和检索策略。

### 需要确认的问题

1. 研究主题的具体表述是什么？
2. 关键词有哪些？（主关键词 + 同义词）
3. 关注哪些会议/期刊？（如 ICML/NeurIPS/ICLR/ACL/CVPR 等）
4. 年份范围？（如 2020-2025）
5. 是否只关注有开源代码的论文？
6. 期望输出什么？（候选列表 / 趋势图 / 综述草稿 / 全部）
7. 综述目标长度和深度？

### 产物

- `research/{topic}/search_strategy.md`

## 阶段 2：Collect（收集）

目标：检索候选论文。

### 执行步骤

1. 读取 `search_strategy.md`。
2. 使用 `PaperVaultSearch` 进行 broad 搜索：`query=主关键词`, `limit=50`。
3. 根据结果逐步加入 `conf`、`since`、`until`、`has_code` 筛选。
4. 必要时调用 `Task(subagent_name="researcher")` 进行多角度检索。

### 产物

- `research/{topic}/candidate_papers.md`

## 阶段 3：Filter（筛选）

目标：从候选集中剔除低相关度论文。

### 执行步骤

1. 读取 `candidate_papers.md`。
2. 调用 `Task(subagent_name="reviewer")` 审查。
3. 保留 10-20 篇最相关论文。

### 产物

- 更新后的 `research/{topic}/candidate_papers.md`

## 阶段 4：Analyze（分析）

目标：生成趋势统计和可视化数据。

### 执行步骤

1. 使用 `PaperVaultStats` 获取全局/会议级统计。
2. 调用 `Task(subagent_name="data_analyst")` 分析趋势。
3. 将结果写入 `trends.json`（ECharts 格式）。

### 产物

- `research/{topic}/trends.json`

## 阶段 5：Draft（起草）

目标：生成综述草稿。

### 执行步骤

1. 读取 `candidate_papers.md` 和 `trends.json`。
2. 先起草 `survey_outline.md`。
3. 暂停等待用户确认大纲（AskUser）。
4. 根据确认后的大纲写 `survey_draft.md`。

### 产物

- `research/{topic}/survey_outline.md`
- `research/{topic}/survey_draft.md`

## 阶段 6：Review（审核）

目标：用户确认最终综述。

### 执行步骤

1. 展示 `survey_draft.md` 摘要。
2. 调用 `AskUser(type="confirm")` 询问是否通过。
3. 如果用户要求整改，进入 Iterate 阶段。
4. 如果通过，追加关键结论到 `.aiasys/memory/workspace_memory.md`。

## 阶段 7：Iterate（迭代）

目标：根据反馈改进综述。

### 触发条件

- 用户指出某部分需要补充
- 用户要求增加某个子方向
- 用户认为候选论文不够

### 执行步骤

1. 根据反馈调整检索策略。
2. 回到 Collect/Filter/Analyze/Draft 中的适当阶段。
3. 更新产物。

## 阶段 8：Complete（完成）

目标：标记任务完成。

### 执行步骤

1. 确保最终产物已写入。
2. 调用 `auto_task_signal(action="complete")`。
3. 向用户总结完成内容。
