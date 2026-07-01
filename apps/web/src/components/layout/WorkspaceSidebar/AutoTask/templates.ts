import { toDatetimeLocalValue } from "./scheduleFormat";
import type { AutoTaskDraft, AutoTaskTemplate } from "./types";

const EMPTY_DRAFT: AutoTaskDraft = {
  title: "",
  prompt: "",
  triggerType: "interval",
  triggerValue: "86400",
  enabled: true,
  modelId: "",
  overlapPolicy: "skip",
  bindSessionId: "",
  sessionStrategy: "new_each_time",
  continuationPrompt: "",
  maxContinuations: -1,
  taskCategory: "scheduled",
  firstRunPolicy: "next_scheduled",
  stopOnConsecutiveErrors: 10,
  stopOnSignal: true,
};

const TEMPLATE_LIBRARY: readonly AutoTaskTemplate[] = [
  {
    id: "daily-branch-refresh",
    name: "每日自动化会话",
    summary: "每天新建一条普通会话，做一次工作区巡检或续推。",
    title: "每日自动巡检会话",
    prompt:
      "这是一次自动启动会话。请读取当前工作区的任务上下文、最新结果与关键文件，在这条新会话里完成一轮巡检或推进，并把关键结论写回工作区对象。",
    triggerType: "interval",
    triggerValue: "86400",
  },
  {
    id: "weekday-evening-review",
    name: "工作日晚间会话",
    summary: "适合工作日固定时间拉起一条会话做收口检查。",
    title: "工作日晚间检查会话",
    prompt:
      "现在进入工作日晚间检查。请在这条新会话里检查今天新增的工作区会话、执行结果和待处理事项，生成简短巡检记录，并明确下一步最值得继续推进的对象。",
    triggerType: "cron",
    triggerValue: "0 18 * * 1-5",
  },
  {
    id: "weekly-report",
    name: "每周周报会话",
    summary: "适合每周汇总工作区进展、证据和下一步计划。",
    title: "每周总结会话",
    prompt:
      "请在这条新会话里汇总当前工作区本周的推进情况，整理主线、候选会话、关键证据、已证伪方向和下周建议，输出为一份可直接回看的周报摘要。",
    triggerType: "cron",
    triggerValue: "0 20 * * 5",
  },
  {
    id: "literature-survey",
    name: "PaperVault 文献综述",
    summary: "围绕指定主题自动检索 PaperVault 论文、生成综述草稿，并在关键节点暂停等待审核。",
    title: "文献综述：",
    prompt:
      "你是 PaperVault 文献综述自动化 Agent。请围绕本工作区当前研究主题，使用 PaperVaultSearch / PaperVaultStats 或调用 researcher / reviewer / data_analyst 子 Agent，按 plan -> collect -> filter -> analyze -> draft -> review -> iterate -> complete 生命周期推进。\n\n每轮执行纪律：\n1. 读取 research/{topic}/ 下已有产物，避免重复。\n2. 每次只推进一个阶段。\n3. 所有结论必须标注来源论文 title + url。\n4. 关键节点（检索策略、候选列表、综述大纲、最终综述）调用 AskUser(type='confirm') 暂停等待确认。\n5. 最终确认后调用 auto_task_signal(action='complete')，阻塞时调用 auto_task_signal(action='pause')。\n\n产物路径：research/{topic}/candidate_papers.md、research/{topic}/trends.json、research/{topic}/survey_draft.md、.aiasys/memory/workspace_memory.md。",
    triggerType: "continuous",
    triggerValue: "",
    taskCategory: "continuous",
    sessionStrategy: "bind_session",
    continuationPrompt:
      "继续推进文献综述。先读取已有产物，判断当前阶段，然后执行下一个最小可交付步骤。",
  },
];

export function createEmptyAutoTaskDraft(): AutoTaskDraft {
  return { ...EMPTY_DRAFT };
}

export function buildDraftFromTemplate(
  template: AutoTaskTemplate,
): AutoTaskDraft {
  const isContinuous = template.taskCategory === "continuous";
  return {
    title: template.title,
    prompt: template.prompt,
    triggerType: template.triggerType,
    triggerValue:
      template.triggerType === "once"
        ? toDatetimeLocalValue(template.triggerValue)
        : template.triggerValue,
    enabled: true,
    modelId: "",
    overlapPolicy: "skip",
    bindSessionId: "",
    sessionStrategy: template.sessionStrategy ?? "new_each_time",
    continuationPrompt: template.continuationPrompt ?? "",
    maxContinuations: -1,
    taskCategory: template.taskCategory ?? "scheduled",
    firstRunPolicy: isContinuous ? "immediate" : "next_scheduled",
    stopOnConsecutiveErrors: 10,
    stopOnSignal: true,
  };
}

export function getAutoTaskTemplates(): AutoTaskTemplate[] {
  return TEMPLATE_LIBRARY.map((template) => ({ ...template }));
}

export function getDefaultAutoTaskTemplate(): AutoTaskTemplate {
  return { ...TEMPLATE_LIBRARY[0] };
}
