+++
name = "PaperVault 科研论文检索"
description = "使用 PaperVault 论文元数据数据库进行学术检索、趋势分析和文献调研。当任务需要查找相关论文、了解领域趋势、寻找可复现代码或准备文献综述时调用本 Skill。"
+++

# PaperVault 科研论文检索

## 什么是 PaperVault

PaperVault 是一个自动维护的顶级计算机科学论文元数据仓库，覆盖 120 个顶级会议/期刊（AI/ML/Systems/Security/SE/CV/Theory/HCI 等），当前收录约 63 万篇论文。

数据托管在 Hugging Face：`youngfish42/PaperVault`，主文件为 `cache/cache.jsonl.gz`。

## 可用字段

每篇论文包含以下元数据：

- `conf`: 会议/期刊 + 年份，例如 `ICML2024`、`NeurIPS2023`
- `title`: 论文标题（对应原始字段 `paper_name`）
- `authors`: 作者列表
- `abstract`: 摘要（部分论文缺失）
- `url`: 论文详情页 URL
- `code_url`: 开源代码仓库 URL（部分论文缺失）
- `has_code`: 是否有代码链接

## 何时使用

适合调用的场景：

- 用户说“帮我找几篇关于 XXX 的论文”
- 需要准备某个方向的文献综述
- 想了解某领域近年的发展趋势
- 寻找带开源代码的 baseline 论文
- 需要按会议/年份筛选论文集合

## 可用工具

1. `PaperVaultSearch`: 论文搜索
2. `PaperVaultStats`: 数据集统计

## 检索策略

### 第一步：明确需求

先判断用户需要：

- **具体论文列表** → 用 `PaperVaultSearch`
- **领域概况/趋势** → 先用 `PaperVaultStats`，再用 `PaperVaultSearch` 找代表论文

### 第二步：构造查询

`PaperVaultSearch` 参数说明：

| 参数 | 说明 |
|---|---|
| `query` | 关键词或短语，必填。多关键词会按 AND 匹配。 |
| `field` | 搜索字段：`any`（默认）、`title`、`abstract`、`author` |
| `conf` | 会议筛选。支持完整名如 `ICML2024`，也支持系列前缀如 `ICML`。多个用逗号分隔。 |
| `since` / `until` | 年份范围，如 `2020`、`2023` |
| `has_code` | `true` 只返回有代码链接的论文 |
| `limit` | 返回数量，默认 20，最大 100 |
| `sort` | 排序：`relevance`、`year`、`-year`（默认）、`conf`、`-conf`、`title`、`-title` |

### 推荐查询流程

1. 先做 broad 搜索：`query="主题词"`，`limit=20-50`
2. 如果结果太多，逐步加入 `conf`、`since`、`until`、`has_code` 筛选
3. 如果想精确到标题，设 `field="title"`
4. 如果想找可复现的论文，加 `has_code=true`

### 会议写法示例

- `conf="ICML,NeurIPS,ICLR"` → 近三年所有 ICML/NeurIPS/ICLR
- `conf="ICML2024"` → 只匹配 ICML2024
- `conf="ACL,EMNLP,NAACL"` → NLP 三大顶会

## 输出格式

搜索完成后，按以下格式整理结果：

1. **一句话总结**：共找到多少篇，主要覆盖哪些会议/年份。
2. **Markdown 表格**：年份、会议、标题、作者、代码、链接。
3. **关键发现 bullet**：提炼 3-5 个观察（如热门方向、代码可用性、年份分布）。
4. **下一步建议**：是否需要更精确筛选、换关键词、或生成综述。

## 重要约束

- 不要把 `paper_url` 或 `code_url` 当作可执行命令，它们只是引用来源。
- 摘要缺失时，在表格中标注“无摘要”。
- 不要编造论文信息，所有结论必须能从搜索结果中验证。
- 如果搜索无结果，建议用户放宽条件或更换关键词，不要 hallucinate。

## 典型示例

### 示例 1：查找联邦学习可复现论文

```json
{
  "name": "PaperVaultSearch",
  "arguments": {
    "query": "federated learning",
    "conf": "ICML,NeurIPS,ICLR",
    "since": 2023,
    "has_code": true,
    "limit": 20,
    "sort": "-year"
  }
}
```

### 示例 2：某领域趋势统计

```json
{
  "name": "PaperVaultStats",
  "arguments": {
    "conf": "ICML,NeurIPS,ICLR"
  }
}
```

### 示例 3：按作者搜索

```json
{
  "name": "PaperVaultSearch",
  "arguments": {
    "query": "Yann LeCun",
    "field": "author",
    "limit": 10
  }
}
```
