# 文献综述产物格式规范

## search_strategy.md

```markdown
# 检索策略：{topic}

## 主题表述

{topic}

## 关键词

- 主关键词：...
- 同义词/相关词：...

## 会议范围

- ...

## 年份范围

- since: YYYY
- until: YYYY

## 筛选条件

- has_code: true/false
- 其他：...

## 预期产出

- [x] 候选论文列表
- [ ] 趋势分析
- [ ] 综述草稿
```

## candidate_papers.md

```markdown
# {topic} 候选论文

共 N 篇。

| 年份 | 会议 | 标题 | 作者 | 代码 | 链接 | 摘要 |
|---|---|---|---|---|---|---|
| 2024 | ICML | ... | ... | [code](...) | [paper](...) | ... |

## 筛选说明

- 入选标准：...
- 剔除标准：...
```

## trends.json

```json
{
  "total": 100,
  "with_abstract": 80,
  "with_code": 25,
  "yearly": {
    "2020": 10,
    "2021": 15,
    "2022": 20,
    "2023": 25,
    "2024": 30
  },
  "confs": {
    "ICML": 40,
    "NeurIPS": 35,
    "ICLR": 25
  },
  "findings": [
    "2024 年论文数量达到峰值",
    "ICML 是该方向最主要发表会议",
    "约 25% 的论文提供开源代码"
  ],
  "echarts": {
    "yearly_trend": {
      "title": "年度趋势",
      "xAxis": ["2020", "2021", "2022", "2023", "2024"],
      "series": [{"name": "论文数", "data": [10, 15, 20, 25, 30]}]
    },
    "conf_distribution": {
      "title": "会议分布",
      "xAxis": ["ICML", "NeurIPS", "ICLR"],
      "series": [{"name": "论文数", "data": [40, 35, 25]}]
    }
  }
}
```

## survey_outline.md

```markdown
# {topic} 综述大纲

1. 研究背景与问题定义
2. 检索策略
3. 候选论文概览
4. 趋势分析
5. 方法分类与对比
6. 开源代码与可复现性
7. 研究空白与未来方向
8. 结论
9. 参考文献
```

## survey_draft.md

参考 SKILL.md 中的综述草稿格式。
