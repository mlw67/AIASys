# PaperVault 查询指南

## 字段说明

| 字段 | 含义 | 示例 |
|---|---|---|
| `conf` | 会议/期刊 + 年份 | `ICML2024`, `NeurIPS2023` |
| `title` | 论文标题 | `Federated Learning for Vision` |
| `authors` | 作者列表 | `["Alice Smith", "Bob Jones"]` |
| `abstract` | 摘要 | 可能为空 |
| `url` | 论文详情页 | 来自 ACL/OpenReview/DBLP 等 |
| `code_url` | 代码仓库 | 可能为空 |

## 会议系列前缀匹配

`conf` 参数支持两种写法：

1. **完整匹配**：`ICML2024` 只匹配该年份
2. **前缀匹配**：`ICML` 匹配所有 ICML 年份

## 关键词搜索行为

- `field="any"`：同时搜索 title、abstract、authors
- 多关键词按 AND 连接，要求同时出现
- 中文关键词可直接使用

## 排序选项

| sort | 含义 |
|---|---|
| `-year` | 年份降序（最新优先，默认） |
| `year` | 年份升序 |
| `relevance` | 相关度（只在有 query 时有效） |
| `title` / `-title` | 标题字母顺序 |
| `conf` / `-conf` | 会议名字母顺序 |
