// 页面间数据变更事件总线（对应 Python 的信号机制：
// expense_updated / budget_updated / project_updated 等）
// 数据变更后 emit；需要刷新的页面 listen 后重新加载。

import { emit, listen, type UnlistenFn } from "@tauri-apps/api/event";

/** 变更范围：与 Python 各页面信号一一对应 */
export type DataScope = "project" | "budget" | "expense" | "budgetPlan";

const CHANNEL = "data-changed";

/** 通知全局：某类数据已变更 */
export function notifyDataChanged(scope: DataScope): void {
  void emit(CHANNEL, { scope });
}

/** 订阅数据变更；返回取消订阅函数 */
export function onDataChanged(cb: (scope: DataScope) => void): () => void {
  let unlisten: UnlistenFn | undefined;
  void listen<{ scope: DataScope }>(CHANNEL, (event) => {
    cb(event.payload.scope);
  }).then((fn) => {
    unlisten = fn;
  });
  return () => unlisten?.();
}