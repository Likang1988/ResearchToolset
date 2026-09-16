// 10 个预算科目（顺序与后端 core::models::BudgetCategory 一致）
export const BUDGET_CATEGORIES = [
  "设备费",
  "材料费",
  "外协费",
  "燃动费",
  "会议差旅费",
  "出版文献费",
  "劳务费",
  "专家咨询费",
  "其他支出",
  "间接费用",
] as const;

export type BudgetCategory = (typeof BUDGET_CATEGORIES)[number];