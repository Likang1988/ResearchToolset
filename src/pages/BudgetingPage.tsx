// 预算编制页：6 列可编辑三级树（课题/预算名称 | 型号规格|简要内容 | 单价(元) | 数量 | 经费数额(元) | 备注）
// + 单价×数量自动联动金额、父项递归汇总、顶层清空单价/数量
// + 按钮：添加预算 / 增加同级 / 增加子级(最多三级) / 删除该级 / 保存数据 / 导出数据
// + 导出走 BudgetExportDialog 配置后 invoke export_budget_data（Rust 已实现）
// 数据模型对应后端 services::budget_plan：计划 → 10 类别占位节点 → 条目。

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { save } from "@tauri-apps/plugin-dialog";
import BudgetExportDialog, { type BudgetExportConfig } from "../components/BudgetExportDialog";
import { emitBudgetOrExpenseUpdated } from "../data/events";

// 10 个预算类别中文 label（与后端 BUDGET_CATEGORY_LABELS 顺序一致）
const BUDGET_CATEGORY_LABELS = [
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
];

// 与后端 services::budget_plan::BudgetPlanNode 对齐
interface ItemNode {
  id: number | null;
  name: string;
  specification: string;
  unitPrice: number;
  quantity: number;
  amount: number;
  remarks: string;
}

interface CategoryNode {
  label: string; // 类别名（标准类别或用户自定义）
  amount: number;
  remarks: string;
  items: ItemNode[];
  expanded: boolean;
}

interface PlanNode {
  id: number | null;
  name: string;
  totalAmount: number;
  remarks: string;
  categories: CategoryNode[];
  expanded: boolean;
}

// Rust 端返回的 snake_case 结构（services::budget_plan::BudgetPlanNode 等）
interface BudgetPlanDTO {
  id: number;
  name: string;
  total_amount: number;
  remarks: string | null;
  categories: BudgetCategoryDTO[];
}
interface BudgetCategoryDTO {
  category: string;
  amount: number;
  remarks: string | null;
  items: BudgetItemDTO[];
}
interface BudgetItemDTO {
  id: number;
  name: string;
  specification: string | null;
  unit_price: number;
  quantity: number;
  amount: number;
  remarks: string | null;
}

const emptyItem = (): ItemNode => ({
  id: null,
  name: "请输入该级预算名称",
  specification: "",
  unitPrice: 0,
  quantity: 0,
  amount: 0,
  remarks: "",
});

const emptyCategory = (label: string): CategoryNode => ({
  label,
  amount: 0,
  remarks: "",
  items: [],
  expanded: true,
});

const emptyPlan = (): PlanNode => ({
  id: null,
  name: "请输入课题名称",
  totalAmount: 0,
  remarks: "",
  categories: BUDGET_CATEGORY_LABELS.map(emptyCategory),
  expanded: true,
});

// 条目层变化后重算：类别金额 = Σ条目金额；计划金额 = Σ类别金额
const recalcPlan = (p: PlanNode): PlanNode => {
  const categories = p.categories.map((c) => ({
    ...c,
    amount: c.items.reduce((s, it) => s + (Number(it.amount) || 0), 0),
  }));
  return {
    ...p,
    categories,
    totalAmount: categories.reduce((s, c) => s + (Number(c.amount) || 0), 0),
  };
};

const num = (v: number | string): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

// 深拷贝计划树（计划→类别→条目三层）。updater 必须纯函数：
// StrictMode 下会被 double-invoke，若 splice/push 到 prev 共享的嵌套数组，
// 两次调用叠加会导致「按一次加两条」的 bug。
const deepCopyPlans = (prev: PlanNode[]): PlanNode[] =>
  prev.map((p) => ({
    ...p,
    categories: p.categories.map((c) => ({ ...c, items: [...c.items] })),
  }));

// 选中位置的表示：null = 未选中；kind plan/category/item
interface Selection {
  kind: "plan" | "category" | "item";
  pi: number;
  ci?: number;
  ii?: number;
}

const fmt2 = (v: number) => (Number.isFinite(v) ? v.toFixed(2) : "0.00");

export default function BudgetingPage() {
  const [plans, setPlans] = useState<PlanNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Selection | null>(null);
  // 删除确认（自绘对话框，WKWebView 不支持 window.confirm）
  const [confirmDelete, setConfirmDelete] = useState<Selection | null>(null);
  // 导出配置对话框开关
  const [exportDialogOpen, setExportDialogOpen] = useState(false);

  // 加载全部预算计划
  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const trees = await invoke<BudgetPlanDTO[]>("list_budget_plans");
      // Rust 返回 snake_case（total_amount 等）→ 转换为前端 camelCase
      const nodes: PlanNode[] = trees.map((t) => ({
        id: t.id,
        name: t.name,
        totalAmount: num(t.total_amount),
        remarks: t.remarks ?? "",
        expanded: true,
        categories: t.categories.map((c) => ({
          label: c.category,
          amount: num(c.amount),
          remarks: c.remarks ?? "",
          expanded: true,
          items: c.items.map((it) => ({
            id: it.id,
            name: it.name,
            specification: it.specification ?? "",
            unitPrice: num(it.unit_price),
            quantity: Math.round(num(it.quantity)),
            amount: num(it.amount),
            remarks: it.remarks ?? "",
          })),
        })),
      }));
      setPlans(nodes);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // —— 单元格编辑（不可变更新） ——
  const patchItem = (sel: Selection, patch: Partial<ItemNode>) => {
    if (sel.ci === undefined || sel.ii === undefined) return;
    setPlans((prev) =>
      prev.map((p, pi) => {
        if (pi !== sel.pi) return p;
        const categories = p.categories.map((c, ci) => {
          if (ci !== sel.ci) return c;
          return {
            ...c,
            items: c.items.map((it, ii) => (ii === sel.ii ? { ...it, ...patch } : it)),
          };
        });
        return recalcPlan({ ...p, categories });
      })
    );
  };

  const patchCategory = (sel: Selection, patch: Partial<CategoryNode>) => {
    if (sel.ci === undefined) return;
    setPlans((prev) =>
      prev.map((p, pi) => {
        if (pi !== sel.pi) return p;
        const categories = p.categories.map((c, ci) => (ci === sel.ci ? { ...c, ...patch } : c));
        return recalcPlan({ ...p, categories });
      })
    );
  };

  const patchPlan = (pi: number, patch: Partial<PlanNode>) => {
    setPlans((prev) => prev.map((p, i) => (i === pi ? { ...p, ...patch } : p)));
  };

  // 编辑单价/数量：金额 = 单价×数量
  const onPriceQty = (sel: Selection, field: "unitPrice" | "quantity", v: string) => {
    const src = sel.ci !== undefined && sel.ii !== undefined ? getItem(sel) : null;
    if (!src) return;
    const patch: Partial<ItemNode> = { [field]: num(v) };
    let price = field === "unitPrice" ? num(v) : num(src.unitPrice);
    let qty = field === "quantity" ? num(v) : num(src.quantity);
    patch.amount = price * qty;
    patchItem(sel, patch);
  };

  const getItem = (sel: Selection): ItemNode | null => {
    const p = plans[sel.pi];
    if (sel.ci === undefined || sel.ii === undefined || !p) return null;
    return p.categories[sel.ci]?.items[sel.ii] ?? null;
  };

  // —— 按钮动作 ——
  const addBudget = () => {
    setPlans((prev) => [...prev, emptyPlan()]);
  };

  const addSameLevel = () => {
    if (!selected) return;
    const { kind, pi, ci, ii } = selected;
    setPlans((prev) => {
      const next = deepCopyPlans(prev);
      if (kind === "plan") {
        next.splice(pi + 1, 0, emptyPlan());
      } else if (kind === "category" && ci !== undefined) {
        next[pi].categories.splice(ci + 1, 0, emptyCategory("请输入该级预算名称"));
      } else if (kind === "item" && ci !== undefined && ii !== undefined) {
        next[pi].categories[ci].items.splice(ii + 1, 0, emptyItem());
      }
      return next;
    });
  };

  const addSubLevel = () => {
    if (!selected) return;
    const { kind, pi, ci } = selected;
    // 计算当前层级（plan=1, category=2, item=3）
    if (kind === "item") {
      alert("最多只能添加三级预算项！");
      return;
    }
    setPlans((prev) => {
      const next = deepCopyPlans(prev);
      if (kind === "plan") {
        next[pi].categories.push(emptyCategory("请输入该级预算名称"));
        next[pi].expanded = true;
      } else if (kind === "category" && ci !== undefined) {
        next[pi].categories[ci].items.push(emptyItem());
        next[pi].categories[ci].expanded = true;
      }
      return next;
    });
  };

  // 删除该级：先校验/入库，再由确认框统一执行
  const requestDelete = () => {
    if (!selected) {
      alert("请选择要删除的预算项！");
      return;
    }
    // 标准预算类别（第二级）不可删除
    if (selected.kind === "category") {
      const label = plans[selected.pi].categories[selected.ci ?? -1]?.label;
      if (label && BUDGET_CATEGORY_LABELS.includes(label)) {
        alert("预算类别项不可删除！");
        return;
      }
    }
    setConfirmDelete(selected);
  };

  const executeDelete = async () => {
    const sel = confirmDelete;
    if (!sel) return;
    setConfirmDelete(null);
    const { kind, pi, ci, ii } = sel;
    try {
      if (kind === "plan") {
        // 顶层：删除整个计划（按 name）
        await invoke("delete_budget_plan", { name: plans[pi].name });
      } else if (kind === "item" && ci !== undefined && ii !== undefined) {
        const topName = plans[pi].name;
        const catLabel = plans[pi].categories[ci].label;
        const itemName = plans[pi].categories[ci].items[ii].name;
        // 非标准类别行不入库，只删 UI
        if (BUDGET_CATEGORY_LABELS.includes(catLabel)) {
          await invoke("delete_budget_plan_item", {
            planName: topName,
            categoryLabel: catLabel,
            itemName,
          });
        }
      }
    } catch (e) {
      setError(String(e));
      return; // 入库失败则不删 UI
    }
    // 移除 UI 节点
    setPlans((prev) => {
      const next = deepCopyPlans(prev);
      if (kind === "plan") {
        next.splice(pi, 1);
      } else if (kind === "category" && ci !== undefined) {
        next[pi].categories.splice(ci, 1);
      } else if (kind === "item" && ci !== undefined && ii !== undefined) {
        next[pi].categories[ci].items.splice(ii, 1);
      }
      return next;
    });
    setSelected(null);
  };

  // 保存数据：整树一次提交
  const handleSave = async () => {
    try {
      const payload = plans.map((p) => ({
        name: p.name,
        total_amount: num(p.totalAmount),
        remarks: p.remarks.trim() ? p.remarks : null,
        categories: p.categories.map((c) => ({
          category: c.label,
          amount: num(c.amount),
          remarks: c.remarks.trim() ? c.remarks : null,
          items: c.items.map((it) => ({
            name: it.name,
            specification: it.specification.trim() ? it.specification : null,
            unit_price: num(it.unitPrice),
            quantity: Math.round(num(it.quantity)),
            amount: num(it.amount),
            remarks: it.remarks.trim() ? it.remarks : null,
          })),
        })),
      }));
      await invoke("save_budget_plans", { plans: payload });
      emitBudgetOrExpenseUpdated();
      alert("预算数据保存成功！");
    } catch (e) {
      setError(String(e));
    }
  };

  // 导出数据：取选中项所属顶层计划
  const requestExport = () => {
    if (!selected || selected.kind !== "plan") {
      // 选中条目/类别时上溯到顶层；未选中提示
      if (!selected) {
        alert("请先选择要导出的预算项目");
        return;
      }
    }
    setExportDialogOpen(true);
  };

  const getTopPlanIndex = (sel: Selection): number => sel.pi;

  const handleExportConfirm = async (config: BudgetExportConfig) => {
    setExportDialogOpen(false);
    if (!selected) return;
    const pi = getTopPlanIndex(selected);
    const top = plans[pi];

    // 组装 BudgetExportData（对齐 Rust excel::BudgetExportData；类别固定 10 个标准顺序）
    const byLabel = new Map(top.categories.map((c) => [c.label, c]));
    const categories = BUDGET_CATEGORY_LABELS.map((label) => {
      const c = byLabel.get(label);
      return {
        name: label,
        amount: c ? num(c.amount) : 0,
        remarks: c?.remarks ?? "",
        items: (c?.items ?? []).map((it) => ({
          name: it.name,
          specification: it.specification,
          unit_price: num(it.unitPrice),
          quantity: num(it.quantity),
          amount: num(it.amount),
          remarks: it.remarks,
        })),
      };
    });
    const data = {
      project_name: top.name,
      total_amount: num(top.totalAmount),
      categories,
    };

    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(
      now.getHours()
    )}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
    const savePath = await save({
      defaultPath: `预算数据_${ts}.xlsx`,
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
    });
    if (!savePath) return;
    try {
      await invoke("export_budget_data", { savePath, data, config });
      alert(`导出成功：\n${savePath}`);
    } catch (e) {
      alert(`导出失败：${String(e)}`);
    }
  };

  const toggleExpand = (sel: Selection) => {
    if (sel.kind === "plan") {
      patchPlan(sel.pi, { expanded: !plans[sel.pi].expanded });
    } else if (sel.kind === "category") {
      patchCategory(sel, { expanded: !(plans[sel.pi]?.categories[sel.ci ?? -1]?.expanded ?? false) });
    }
  };

  // 树行渲染
  const renderRow = (
    sel: Selection,
    indent: number,
    cells: {
      col0: React.ReactNode;
      col1: React.ReactNode;
      col2?: React.ReactNode;
      col3?: React.ReactNode;
      col4: React.ReactNode;
      col5: React.ReactNode;
      isGroup?: boolean;
    }
  ) => {
    const isSel =
      selected?.kind === sel.kind &&
      selected?.pi === sel.pi &&
      (sel.ci === undefined || selected?.ci === sel.ci) &&
      (sel.ii === undefined || selected?.ii === sel.ii);
    return (
      <div
        className={`bt-row${isSel ? " selected" : ""}`}
        onClick={() => setSelected(sel)}
        style={{ paddingLeft: 8 + indent * 26 }}
      >
        <div className="bt-cell bt-name">{cells.col0}</div>
        <div className="bt-cell bt-spec">{cells.col1}</div>
        <div className="bt-cell bt-num">{cells.col2 ?? ""}</div>
        <div className="bt-cell bt-num">{cells.col3 ?? ""}</div>
        <div className="bt-cell bt-num">{cells.col4}</div>
        <div className="bt-cell bt-note">{cells.col5}</div>
      </div>
    );
  };

  const expandToggle = (sel: Selection, hasChildren: boolean) =>
    hasChildren ? (
      <button
        className="bt-expand"
        onClick={(e) => {
          e.stopPropagation();
          toggleExpand(sel);
        }}
      >
        {isExpanded(sel) ? "▾" : "▸"}
      </button>
    ) : (
      <span className="bt-expand-spacer" />
    );

  const isExpanded = (sel: Selection): boolean => {
    if (sel.pi === -1) return true;
    if (sel.kind === "plan") return plans[sel.pi]?.expanded ?? true;
    if (sel.kind === "category") {
      return plans[sel.pi]?.categories[sel.ci ?? -1]?.expanded ?? true;
    }
    return true;
  };

  const input = (v: string, onChange: (v: string) => void, style?: React.CSSProperties) => (
    <input
      className="bt-input"
      style={style}
      value={v}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => onChange(e.target.value)}
    />
  );

  const numInput = (
    v: string,
    onChange: (v: string) => void,
    style?: React.CSSProperties
  ) => (
    <input
      className="bt-input bt-num-input"
      type="number"
      style={style}
      value={v}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => onChange(e.target.value)}
    />
  );

  return (
    <div className="expense-mgmt">
      <div className="expense-toolbar">
        <h2 className="page-title">预算编制</h2>
        <div className="list-actions">
          <button className="primary-btn" onClick={addBudget}>
            添加预算
          </button>
          <button onClick={addSameLevel} disabled={!selected}>
            增加同级
          </button>
          <button onClick={addSubLevel} disabled={!selected}>
            增加子级
          </button>
          <button className="danger-btn" onClick={requestDelete} disabled={!selected}>
            删除该级
          </button>
          <span className="bt-btn-sep" />
          <button className="primary-btn" onClick={handleSave}>
            保存数据
          </button>
          <button className="primary-btn" onClick={requestExport}>
            导出数据
          </button>
        </div>
      </div>

      {error && (
        <div className="placeholder-card">
          <p className="hint" style={{ color: "#c62828" }}>
            操作失败：{error}
          </p>
        </div>
      )}

      {loading ? (
        <div className="placeholder-card">
          <p className="hint">正在加载预算数据…</p>
        </div>
      ) : (
        <div className="bt-tree">
          {/* 表头 */}
          <div className="bt-row bt-header">
            <div className="bt-cell bt-name">课题/预算名称</div>
            <div className="bt-cell bt-spec">型号规格|简要内容</div>
            <div className="bt-cell bt-num">单价（元）</div>
            <div className="bt-cell bt-num">数量</div>
            <div className="bt-cell bt-num">经费数额（元）</div>
            <div className="bt-cell bt-note">备注</div>
          </div>

          {plans.length === 0 && (
            <div className="bt-empty hint">暂无预算计划，点击「添加预算」创建</div>
          )}

          {plans.map((p, pi) => {
            const planSel: Selection = { kind: "plan", pi };
            return (
              <div key={pi}>
                {renderRow(
                  planSel,
                  0,
                  {
                    isGroup: true,
                    col0: (
                      <>
                        {expandToggle(planSel, p.categories.length > 0)}
                        {input(p.name, (v) => patchPlan(pi, { name: v }), { fontWeight: p.categories.length > 0 ? 700 : 400 })}
                      </>
                    ),
                    col1: <span />,
                    col4: (
                      <span className="bt-amount-read">
                        {fmt2(num(p.totalAmount))}
                      </span>
                    ),
                    col5: input(p.remarks, (v) => patchPlan(pi, { remarks: v })),
                  }
                )}
                {p.expanded &&
                  p.categories.map((c, ci) => {
                    const catSel: Selection = { kind: "category", pi, ci };
                    return (
                      <div key={ci}>
                        {renderRow(
                          catSel,
                          1,
                          {
                            col0: (
                              <>
                                {expandToggle(catSel, c.items.length > 0)}
                                {input(c.label, (v) => patchCategory(catSel, { label: v }))}
                              </>
                            ),
                            col1: <span />,
                            col4: (
                              <span className="bt-amount-read">
                                {fmt2(num(c.amount))}
                              </span>
                            ),
                            col5: input(c.remarks, (v) => patchCategory(catSel, { remarks: v })),
                          }
                        )}
                        {c.expanded &&
                          c.items.map((it, ii) => {
                            const itemSel: Selection = { kind: "item", pi, ci, ii };
                            return renderRow(
                              itemSel,
                              2,
                              {
                                col0: (
                                  <>
                                    {expandToggle(itemSel, false)}
                                    {input(it.name, (v) => patchItem(itemSel, { name: v }))}
                                  </>
                                ),
                                col1: input(it.specification, (v) => patchItem(itemSel, { specification: v })),
                                col2: numInput(
                                  String(num(it.unitPrice) || ""),
                                  (v) => onPriceQty(itemSel, "unitPrice", v)
                                ),
                                col3: numInput(
                                  String(num(it.quantity) || ""),
                                  (v) => onPriceQty(itemSel, "quantity", v)
                                ),
                                col4: (
                                  <span className="bt-amount-read">
                                    {fmt2(num(it.amount))}
                                  </span>
                                ),
                                col5: input(it.remarks, (v) => patchItem(itemSel, { remarks: v })),
                              }
                            );
                          })}
                      </div>
                    );
                  })}
              </div>
            );
          })}
        </div>
      )}

      {/* 该级删除确认（自绘对话框） */}
      {confirmDelete && (
        <div className="dialog-overlay">
          <div className="dialog-container" style={{ width: 400 }}>
            <div className="dialog-header">
              <h2>确认删除</h2>
              <button className="close-btn" onClick={() => setConfirmDelete(null)}>
                &times;
              </button>
            </div>
            <div className="dialog-body">
              <p>确定要删除该预算项吗？此操作不可恢复！</p>
            </div>
            <div className="dialog-footer">
              <button onClick={() => setConfirmDelete(null)}>取消</button>
              <button className="primary-btn" onClick={executeDelete}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 导出配置对话框 */}
      {exportDialogOpen && (
        <BudgetExportDialog onClose={() => setExportDialogOpen(false)} onConfirm={handleExportConfirm} />
      )}
    </div>
  );
}