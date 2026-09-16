// 跨页面数据变更事件（对齐 Python MainWindow 的 project_updated / budget_or_expense_updated
// 与 ProjectProgressWidget 的 progress_updated 信号）
// - project_updated：项目清单变更（新增/编辑/删除项目）
// - budget_or_expense_updated：预算/支出变更
// - progress_updated：甘特任务/进度变更（对齐 Python progress_updated 信号）
// 主页订阅这些事件在可见时自动刷新；业务页在操作成功后调用 emit。

type Listener = () => void;

const projectListeners = new Set<Listener>();
const budgetListeners = new Set<Listener>();
const progressListeners = new Set<Listener>();

export function onProjectUpdated(fn: Listener): () => void {
  projectListeners.add(fn);
  return () => {
    projectListeners.delete(fn);
  };
}

export function onBudgetOrExpenseUpdated(fn: Listener): () => void {
  budgetListeners.add(fn);
  return () => {
    budgetListeners.delete(fn);
  };
}

export function onProgressUpdated(fn: Listener): () => void {
  progressListeners.add(fn);
  return () => {
    progressListeners.delete(fn);
  };
}

export function emitProjectUpdated(): void {
  projectListeners.forEach((fn) => fn());
}

export function emitBudgetOrExpenseUpdated(): void {
  budgetListeners.forEach((fn) => fn());
}

export function emitProgressUpdated(): void {
  progressListeners.forEach((fn) => fn());
}