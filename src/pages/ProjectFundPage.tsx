// 项目经费页：项目下拉 + 三级预算树表格 + 右侧科目占比饼图

import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import BudgetPieChart, { type PieEntry } from "../components/BudgetPieChart";
import BudgetFormDialog, {
  BUDGET_CATEGORIES,
  type BudgetFormPayload,
} from "../components/BudgetFormDialog";
import CategoryExpensesDialog from "../components/CategoryExpensesDialog";
import ExpenseManagementPage from "./ExpenseManagementPage";
import { emitBudgetOrExpenseUpdated } from "../data/events";

// 后端 Project 类型（仅用于下拉加载，字段与 core::models::Project 对齐）
type Project = {
  id: number;
  name: string;
  financial_code: string | null;
  project_code: string | null;
  project_type: string | null;
  leader: string | null;
  start_date: string | null;
  end_date: string | null;
  total_budget: number | null;
  director: string | null;
};

// 与 Rust core::services::budget::BudgetTree 对齐
interface BudgetItemNode {
  category: string;
  amount: number;
  spent_amount: number;
}
interface BudgetNode {
  id: number;
  year: number | null; // null = 总预算
  total_amount: number;
  spent_amount: number;
  items: BudgetItemNode[];
}
interface BudgetTree {
  total_budget: BudgetNode | null;
  annual_budgets: BudgetNode[];
}

// 图表数据源：支出记录子集（对应 expense::Expense）
interface ChartExpense {
  id: number;
  category: string; // 中文 label，如「材料费」
  amount: number; // 单位：元
  date: string | null; // YYYY-MM-DD
}

// 项目列表项（轻量，只取下拉所需字段）
interface ProjectOption {
  id: number;
  name: string;
  financial_code: string | null;
  total_budget: number | null; // 项目总经费（万元，项目清单数据源）
}

// 预算编制返回的预算计划树（与 Rust core::services::budget_plan::BudgetPlanNode 对齐）
interface BudgetPlanNode {
  id: number;
  name: string;
  total_amount: number;
  remarks: string;
  categories: { category: string; amount: number; remarks: string; items: unknown[] }[];
}

// 金额格式化：千分位 + 2 位小数
function fmt(n: number): string {
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

interface ProjectFundPageProps {
  /** 由 App 层持有：切换标签页后返回仍保持所选项目 */
  selectedProjectId?: number | null;
  onProjectChange?: (id: number | null) => void;
}

export default function ProjectFundPage({
  selectedProjectId,
  onProjectChange,
}: ProjectFundPageProps) {
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  // 无受控 props 时的兜底内部状态
  const [localSelectedId, setLocalSelectedId] = useState<number | null>(null);
  const selectedId =
    selectedProjectId !== undefined ? selectedProjectId : localSelectedId;
  // 切换选中：本地状态 + 通知 App 层持久化
  const changeSelectedId = (id: number | null) => {
    setLocalSelectedId(id);
    onProjectChange?.(id);
  };
  const [tree, setTree] = useState<BudgetTree | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 饼图联动：当前选中预算节点 id + 视图（类别分布 / 时间分布）
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  // 默认类别视图，可切到时间视图
  const [pieView, setPieView] = useState<"category" | "time">("category");

  // 当前选中节点的支出记录（图表数据源）
  const [nodeExpenses, setNodeExpenses] = useState<ChartExpense[]>([]);
  // 支出管理返回后手动触发图表数据重拉
  const [chartReloadKey, setChartReloadKey] = useState(0);

  // 新增 / 编辑年度预算对话框（editingId 有值=编辑；undefined=新增）
  const [budgetDialogOpen, setBudgetDialogOpen] = useState(false);
  const [editingBudgetId, setEditingBudgetId] = useState<number | undefined>(undefined);
  const [editingBudgetMode, setEditingBudgetMode] = useState<"annual" | "total">("annual");

  // 删除预算确认对话框（按钮与样式对齐项目清单页）
  const [deleteTarget, setDeleteTarget] = useState<{
    type: "annual" | "total";
    id: number;
    label: string;
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // "从预算编制导入"：计划列表 + 选择对话框 + 预填金额（万元）
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [budgetPlans, setBudgetPlans] = useState<BudgetPlanNode[]>([]);
  const [importPlanId, setImportPlanId] = useState<number | null>(null);
  const [isLoadingPlans, setIsLoadingPlans] = useState(false);
  const [importPrefill, setImportPrefill] = useState<Record<string, number> | null>(null);

  // 支出管理子页：非空时切换到支出管理，覆盖预算树区域
  const [expenseView, setExpenseView] = useState<{ budgetId: number; year: number } | null>(null);

  // 预算科目行点击 → 弹窗展示该科目支出明细（总预算=跨全部年度；年度预算=限定该年度）
  const [categoryDetail, setCategoryDetail] = useState<{
    category: string;
    amount: number;
    budgetId: number | null;
    scopeLabel: string | null;
  } | null>(null);

  // 当前选中的项目（用于支出管理子页传 props）
  const selectedProject = projects.find((p) => p.id === selectedId) ?? null;

  // 首次加载项目列表
  useEffect(() => {
    invoke<Project[]>("list_projects")
      .then((data) => {
        setProjects(
          data.map((p) => ({
            id: p.id,
            name: p.name,
            financial_code: p.financial_code,
            total_budget: p.total_budget ?? null,
          }))
        );
      })
      .catch((e) => setError(String(e)));
  }, []);

  // 选中项目变化时加载预算树
  useEffect(() => {
    if (selectedId === null) {
      setTree(null);
      setSelectedNodeId(null);
      return;
    }
    setLoading(true);
    setError(null);
    invoke<BudgetTree>("list_project_budgets", { projectId: selectedId })
      .then((data) => {
        setTree(data);
        // 默认选中总预算节点（若无则取第一个年度预算）
        const defaultNode =
          data.total_budget ?? data.annual_budgets[0] ?? null;
        setSelectedNodeId(defaultNode?.id ?? null);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [selectedId]);

  // 当前选中的预算节点（用于驱动饼图）
  const selectedNode = (() => {
    if (!tree || selectedNodeId === null) return null;
    const all = [
      ...(tree.total_budget ? [tree.total_budget] : []),
      ...tree.annual_budgets,
    ];
    return all.find((n) => n.id === selectedNodeId) ?? null;
  })();

  // 选中节点变化 → 拉取该节点支出作为图表数据源
  useEffect(() => {
    if (!selectedNode) {
      setNodeExpenses([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      if (selectedNode.year === null) {
        // 总预算：合并所有年度预算的支出（按 id 去重）
        const years = tree?.annual_budgets ?? [];
        const lists = await Promise.all(
          years.map((b) =>
            invoke<ChartExpense[]>("list_expenses", { budgetId: b.id }).catch(
              () => [] as ChartExpense[]
            )
          )
        );
        const merged = Array.from(
          new Map(lists.flat().map((e) => [e.id, e])).values()
        );
        if (!cancelled) setNodeExpenses(merged);
      } else {
        const list = await invoke<ChartExpense[]>("list_expenses", {
          budgetId: selectedNode.id,
        }).catch(() => [] as ChartExpense[]);
        if (!cancelled) setNodeExpenses(list);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [selectedId, selectedNodeId, tree, chartReloadKey]);

  // 按类别 / 时间维度聚合支出（单位换算：元 → 万元）
  const pieEntries: PieEntry[] = useMemo(() => {
    if (!selectedNode || nodeExpenses.length === 0) return [];
    const sums = new Map<string, number>();
    for (const exp of nodeExpenses) {
      let key: string;
      if (pieView === "category") {
        key = exp.category;
      } else {
        // 时间维度：总预算按年度，年度预算按月度
        const parts = (exp.date ?? "").split("-");
        key =
          selectedNode.year === null
            ? `${parts[0] ?? ""}年`
            : `${Number(parts[1] ?? 0)}月`;
        if (key === "年" || key === "0月") {
          key = selectedNode.year === null ? "未知年" : "未知月";
        }
      }
      sums.set(key, (sums.get(key) ?? 0) + exp.amount / 10000);
    }
    return Array.from(sums.entries())
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value);
  }, [nodeExpenses, pieView, selectedNode]);

  const pieTitle = selectedNode
    ? selectedNode.year === null
      ? `总预算支出 - ${pieView === "category" ? "类别分布" : "年度分布"}`
      : `${selectedNode.year}年度预算支出 - ${pieView === "category" ? "类别分布" : "月度分布"}`
    : "请选择项目以查看图表";

  // 总预算各科目结余 + 总结余（万元）：
  // 各类结余 = 总预算该类金额 - 该类所有年度预算累计支出；
  // 总结余 = Σ各类结余。
  // null = 尚未设置总预算
  const budgetBalances: {
    total: number;
    byCategory: Record<string, number>;
  } | null = useMemo(() => {
    if (!tree?.total_budget) return null;
    const spentByCat = new Map<string, number>();
    for (const ab of tree.annual_budgets) {
      for (const it of ab.items) {
        spentByCat.set(
          it.category,
          (spentByCat.get(it.category) ?? 0) + it.spent_amount
        );
      }
    }
    const byCategory: Record<string, number> = {};
    let total = 0;
    for (const item of tree.total_budget.items) {
      const balance = item.amount - (spentByCat.get(item.category) ?? 0);
      byCategory[item.category] = Math.round(balance * 100) / 100;
      total += balance;
    }
    return { total: Math.round(total * 100) / 100, byCategory };
  }, [tree]);

  // 点击"添加预算"：前置校验
  const handleAddBudget = () => {
    if (selectedId === null) {
      alert("请先选择一个项目");
      return;
    }
    if (!tree?.total_budget || tree.total_budget.total_amount <= 0) {
      alert("请先设置总预算（在总预算行编辑金额）后再添加年度预算");
      return;
    }
    setEditingBudgetId(undefined);
    setBudgetDialogOpen(true);
  };

  // 点击删除预算：弹出确认对话框
  const handleDeleteBudget = () => {
    if (!selectedNode) {
      alert("请先选中要删除的预算行");
      return;
    }
    setDeleteTarget({
      type: selectedNode.year === null ? "total" : "annual",
      id: selectedNode.id,
      label:
        selectedNode.year === null
          ? "总预算"
          : `${selectedNode.year}年度预算`,
    });
  };

  // 确认删除：级联删除预算（及关联支出）
  const confirmDeleteBudget = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      if (deleteTarget.type === "annual") {
        await invoke("delete_annual_budget", { id: deleteTarget.id });
      } else {
        // 总预算：删除整个项目的预算/支出（delete_total_budget 按 projectId）
        await invoke("delete_total_budget", { projectId: selectedId });
      }
      setDeleteTarget(null);
      emitBudgetOrExpenseUpdated();
      const fresh = await refreshBudgetTree();
      if (fresh) {
        const defaultNode =
          fresh.total_budget ?? fresh.annual_budgets[0] ?? null;
        setSelectedNodeId(defaultNode?.id ?? null);
      }
    } catch (e) {
      alert(`删除预算失败：${String(e)}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // 点击"编辑预算"：根据选中节点分流到总预算 / 年度预算编辑
  const handleEditBudget = () => {
    if (!selectedNode) {
      alert("请在表格中先选中一行预算进行编辑");
      return;
    }
    setEditingBudgetId(selectedNode.id);
    setEditingBudgetMode(selectedNode.year === null ? "total" : "annual");
    setBudgetDialogOpen(true);
  };

  // 点击"导入预算计划"：前置校验后加载计划列表
  const handleImportBudgetPlan = async () => {
    if (selectedId === null) {
      alert("请先选择一个项目");
      return;
    }
    if (!tree?.total_budget || tree.total_budget.total_amount <= 0) {
      alert("请先设置总预算（在总预算行编辑金额）后再导入年度预算");
      return;
    }
    setIsLoadingPlans(true);
    try {
      const plans = await invoke<BudgetPlanNode[]>("list_budget_plans");
      if (!plans || plans.length === 0) {
        alert("没有可用的预算计划。");
        return;
      }
      setBudgetPlans(plans);
      setImportPlanId(plans[0].id);
      setImportDialogOpen(true);
    } catch (e) {
      alert(`获取预算计划失败：${String(e)}`);
    } finally {
      setIsLoadingPlans(false);
    }
  };

  // 确认导入：选定计划的类别金额（元）÷ 10000 填万元 → 预填进新增预算对话框
  const confirmImportPlan = () => {
    const plan = budgetPlans.find((p) => p.id === importPlanId);
    if (!plan) return;
    const prefill: Record<string, number> = {};
    for (const cat of BUDGET_CATEGORIES) {
      const node = plan.categories.find((c) => c.category === cat);
      // 在计划中的填金额（万元），不在的填 0
      prefill[cat] =
        node && node.amount > 0
          ? Math.round((node.amount / 10000) * 100) / 100
          : 0;
    }
    setImportPrefill(prefill);
    setImportDialogOpen(false);
    // 打开新增年度预算对话框并预填
    setEditingBudgetId(undefined);
    setEditingBudgetMode("annual");
    setBudgetDialogOpen(true);
  };

  // 刷新预算树并保持当前选中（返回 fresh 供调用方使用）
  const refreshBudgetTree = async () => {
    if (selectedId === null) return null;
    const fresh = await invoke<BudgetTree>("list_project_budgets", {
      projectId: selectedId,
    });
    setTree(fresh);
    return fresh;
  };

  // 提交表单：根据 payload.mode 分发 add / update / total
  const handleSubmitBudget = async (payload: BudgetFormPayload) => {
    if (payload.mode === "add") {
      await invoke("add_annual_budget", { input: payload });
      const fresh = await refreshBudgetTree();
      if (fresh) {
        const newNode =
          fresh.annual_budgets.find((b) => b.year === payload.year) ?? null;
        setSelectedNodeId(newNode?.id ?? selectedNodeId);
      }
    } else if (payload.mode === "update") {
      await invoke("update_annual_budget", {
        id: payload.id,
        totalAmount: payload.total_amount,
        items: payload.items,
      });
      const fresh = await refreshBudgetTree();
      if (fresh) {
        // 保持当前选中节点（若仍存在）
        const stillThere =
          fresh.annual_budgets.find((b) => b.id === payload.id) ?? null;
        setSelectedNodeId(stillThere?.id ?? selectedNodeId);
      }
    } else {
      // total 模式：更新总预算
      await invoke("update_total_budget", {
        id: payload.id,
        totalAmount: payload.total_amount,
        items: payload.items,
      });
      const fresh = await refreshBudgetTree();
      if (fresh && fresh.total_budget) {
        setSelectedNodeId(fresh.total_budget.id);
      }
    }
    emitBudgetOrExpenseUpdated();
  };

  return (
    <div className="project-fund">
      {/* 支出管理子页激活时隐藏顶部工具栏（标题/项目下拉/添加与编辑预算在子页无作用） */}
      {expenseView === null && (
        <div className="fund-toolbar">
          <div className="fund-toolbar-left">
            <h2 className="page-title">经费预算</h2>
            <select
              className="project-selector"
              value={selectedId ?? ""}
              onChange={(e) =>
                changeSelectedId(e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">请选择项目...</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.financial_code ? `${p.financial_code} ` : ""}
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="list-actions">
            <button
              onClick={handleAddBudget}
              disabled={selectedId === null}
              className="primary-btn"
            >
              添加预算
            </button>
            <button
              onClick={handleEditBudget}
              disabled={!selectedNode}
            >
              编辑预算
            </button>
            <button
              onClick={handleDeleteBudget}
              disabled={!selectedNode}
              className="danger-btn"
            >
              删除预算
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="placeholder-card">
          <p className="hint" style={{ color: "#c62828" }}>加载失败：{error}</p>
        </div>
      )}

      {selectedId === null && !error && (
        <div className="placeholder-card">
          <p className="hint">请选择一个项目以查看经费预算</p>
        </div>
      )}

      {loading && (
        <div className="placeholder-card">
          <p className="hint">正在加载预算数据…</p>
        </div>
      )}

      {/* 支出管理子页：覆盖预算树区域 */}
      {!loading && expenseView !== null && selectedId !== null && selectedProject && (
        <ExpenseManagementPage
          projectId={selectedId}
          projectFinancialCode={selectedProject.financial_code}
          budgetId={expenseView.budgetId}
          budgetYear={expenseView.year}
          onBack={async () => {
            setExpenseView(null);
            // 返回预算树时刷新一次，反映支出/删除对 spent_amount 的改动
            await refreshBudgetTree();
            // 图表数据（支出记录）也同步重拉
            setChartReloadKey((k) => k + 1);
          }}
        />
      )}

      {!loading && tree && expenseView === null && (
        <div className="fund-split">
          <div className="fund-left">
            <div className="table-frame">
              <table className="data-table fund-tree">
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", width: "146px" }}>预算年度</th>
                    <th>预算额(万元)</th>
                    <th>支出额(万元)</th>
                    <th>结余额(万元)</th>
                    <th style={{ width: 160 }}>执行率</th>
                    <th style={{ width: 100 }}>操作</th>
                  </tr>
                </thead>
              <tbody>
                {/* 总预算行 + 10 科目子项 */}
                {tree.total_budget && (
                  <BudgetRows
                    key={`${selectedId}-total`}
                    node={tree.total_budget}
                    label="总预算"
                    isTotal
                    selectedNodeId={selectedNodeId}
                    onSelect={setSelectedNodeId}
                    onManageExpenses={null}
                    onShowCategoryExpenses={(category, amount) =>
                      setCategoryDetail({
                        category,
                        amount,
                        budgetId: null,
                        scopeLabel: null,
                      })
                    }
                  />
                )}
                {/* 年度预算行 + 各自 10 科目子项 */}
                {tree.annual_budgets.map((b) => (
                  <BudgetRows
                    key={`${selectedId}-${b.id}`}
                    node={b}
                    label={`${b.year}年度`}
                    isTotal={false}
                    selectedNodeId={selectedNodeId}
                    onSelect={setSelectedNodeId}
                    onManageExpenses={
                      b.year !== null
                        ? () =>
                            setExpenseView({ budgetId: b.id, year: b.year as number })
                        : null
                    }
                    onShowCategoryExpenses={(category, amount) =>
                      setCategoryDetail({
                        category,
                        amount,
                        budgetId: b.id,
                        scopeLabel: b.year !== null ? `${b.year}年度` : null,
                      })
                    }
                  />
                ))}
                {!tree.total_budget && tree.annual_budgets.length === 0 && (
                  <tr>
                    <td colSpan={6} className="hint" style={{ textAlign: "center", padding: 24 }}>
                      该项目暂无预算数据
                    </td>
                  </tr>
                )}
              </tbody>
              </table>
              </div>
          </div>

          {/* 右侧饼图区 */}
          <div className="fund-right">
            <BudgetPieChart
              title={pieTitle}
              entries={pieEntries}
              toolbar={
                /* 分布切换图标按钮 */
                <div className="pie-view-switch">
                  <button
                    className={`icon-btn ${pieView === "category" ? "active" : ""}`}
                    title="类别分布"
                    onClick={() => setPieView("category")}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      width="18"
                      height="18"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
                      <path d="M22 12A10 10 0 0 0 12 2v10z" />
                    </svg>
                  </button>
                  <button
                    className={`icon-btn ${pieView === "time" ? "active" : ""}`}
                    title="时间分布"
                    onClick={() => setPieView("time")}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      width="18"
                      height="18"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                      <line x1="16" y1="2" x2="16" y2="6" />
                      <line x1="8" y1="2" x2="8" y2="6" />
                      <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                  </button>
                </div>
              }
            />
          </div>
        </div>
      )}

      {/* 新增 / 编辑年度预算对话框 */}
      {budgetDialogOpen && selectedId !== null && (
        <BudgetFormDialog
          projectId={selectedId}
          editingId={editingBudgetId}
          editingMode={editingBudgetMode}
          // 仅新增模式带入导入预填（万元）；编辑模式靠后端回填
          initialAmounts={
            editingBudgetId === undefined ? importPrefill ?? undefined : undefined
          }
          onImportBudgetPlan={
            editingBudgetId === undefined ? handleImportBudgetPlan : undefined
          }
          importBusy={isLoadingPlans}
          totalBalance={budgetBalances?.total ?? null}
          categoryBalances={budgetBalances?.byCategory ?? null}
          projectTotalBudget={
            projects.find((p) => p.id === selectedId)?.total_budget ?? null
          }
          onSubmit={handleSubmitBudget}
          onClose={() => {
            setBudgetDialogOpen(false);
            setEditingBudgetId(undefined);
            setImportPrefill(null);
          }}
        />
      )}

      {/* 删除预算确认对话框（样式对齐项目清单页） */}
      {deleteTarget && (
        <div className="dialog-overlay">
          <div className="dialog-container" style={{ width: 420 }}>
            <div className="dialog-header">
              <h2>确认删除</h2>
              <button
                className="close-btn"
                onClick={() => !isDeleting && setDeleteTarget(null)}
              >
                &times;
              </button>
            </div>
            <div className="dialog-body">
              <p style={{ lineHeight: 1.8 }}>
                确定要删除选中的预算{" "}
                <strong>{deleteTarget.label}</strong> 及其所有相关数据
                （包括支出记录）吗？
              </p>
              <p className="hint" style={{ marginTop: 8 }}>
                此操作不可恢复！
              </p>
            </div>
            <div className="dialog-footer">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
              >
                取消
              </button>
              <button
                onClick={confirmDeleteBudget}
                disabled={isDeleting}
                className="danger-btn"
              >
                {isDeleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    {/* 从预算编制导入：计划选择对话框 */}
      {importDialogOpen && (
        <div className="dialog-overlay">
          <div className="dialog-container" style={{ width: 420 }}>
            <div className="dialog-header">
              <h2>选择预算计划导入</h2>
              <button
                className="close-btn"
                onClick={() => setImportDialogOpen(false)}
              >
                &times;
              </button>
            </div>
            <div className="dialog-body">
              <p style={{ lineHeight: 1.8 }}>请选择要导入的预算计划：</p>
              <select
                className="project-selector"
                style={{ width: "100%", marginTop: 8 }}
                value={importPlanId ?? ""}
                onChange={(e) =>
                  setImportPlanId(e.target.value ? Number(e.target.value) : null)
                }
              >
                {budgetPlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="dialog-footer">
              <button onClick={() => setImportDialogOpen(false)}>取消</button>
              <button onClick={confirmImportPlan} className="primary-btn">
                确定
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 预算科目支出明细弹窗 */}
      {categoryDetail && selectedId !== null && (
        <CategoryExpensesDialog
          projectId={selectedId}
          category={categoryDetail.category}
          budgetAmount={categoryDetail.amount}
          budgetId={categoryDetail.budgetId}
          scopeLabel={categoryDetail.scopeLabel}
          onClose={() => setCategoryDetail(null)}
        />
      )}
    </div>
  );
}

// 渲染一个预算节点行 + 其 10 个科目子项行（可折叠，默认折叠）
function BudgetRows({
  node,
  label,
  isTotal,
  selectedNodeId,
  onSelect,
  onManageExpenses,
  onShowCategoryExpenses,
}: {
  node: BudgetNode;
  label: string;
  isTotal: boolean;
  selectedNodeId: number | null;
  onSelect: (id: number) => void;
  onManageExpenses: (() => void) | null;
  /** 传入时（总预算行）科目子项行可点击，弹出该科目跨年度支出明细 */
  onShowCategoryExpenses?: (category: string, amount: number) => void;
}) {
  const balance = node.total_amount - node.spent_amount;
  const isSelected = selectedNodeId === node.id;
  // 默认折叠：科目子项不展示，点击行首箭头展开
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr
        className={
          (isTotal ? "tree-parent tree-total" : "tree-parent") +
          (isSelected ? " row-selected" : "")
        }
        onClick={() => onSelect(node.id)}
        style={{ cursor: "pointer" }}
      >
        <td className="tree-label">
          <button
            type="button"
            className="tree-toggle"
            title={expanded ? "折叠" : "展开"}
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
          >
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              style={{
                transform: expanded ? "rotate(90deg)" : undefined,
                transition: "transform 0.15s",
              }}
            >
              <path
                d="M2 1l4 4-4 4"
                stroke="currentColor"
                strokeWidth="1.5"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
          {label}
        </td>
        <td className="num">{fmt(node.total_amount)}</td>
        <td className="num">{fmt(node.spent_amount)}</td>
        <td className="num">{fmt(balance)}</td>
        <td>
          <ProgressBar amount={node.total_amount} spent={node.spent_amount} />
        </td>
        <td className="fund-ops-cell">
          {onManageExpenses && (
            <button
              className="fund-ops-btn"
              title="支出管理"
              onClick={(e) => {
                e.stopPropagation();
                onManageExpenses();
              }}
            >
              <img src="/icons/expense.svg" alt="支出管理" />
            </button>
          )}
        </td>
      </tr>
      {expanded &&
        node.items.map((item) => {
          const itemBalance = item.amount - item.spent_amount;
          const clickable = Boolean(onShowCategoryExpenses);
          return (
            <tr
              key={item.category}
              className="tree-child"
              style={clickable ? { cursor: "pointer" } : undefined}
              title={clickable ? "点击查看该科目支出明细" : undefined}
              onClick={
                clickable
                  ? () => onShowCategoryExpenses!(item.category, item.amount)
                  : undefined
              }
            >
              <td className="tree-label child-label">{item.category}</td>
              <td className="num">{fmt(item.amount)}</td>
              <td className="num">{fmt(item.spent_amount)}</td>
              <td className="num">{fmt(itemBalance)}</td>
              <td>
                <ProgressBar amount={item.amount} spent={item.spent_amount} />
              </td>
              <td></td>
            </tr>
          );
        })}
    </>
  );
}

// 执行率进度条
// 颜色逻辑：RGB 在浅绿 (153,255,153) 与浅红 (255,153,153) 之间
// 按执行率线性插值；执行率 >=100% 固定为浅红
function pctColor(pct: number): string {
  const ratio = Math.min(pct / 100, 1); // 0..1
  const r = Math.round(153 + (255 - 153) * ratio);
  const g = Math.round(255 + (153 - 255) * ratio);
  return `rgb(${r}, ${g}, 153)`;
}

function ProgressBar({ amount, spent }: { amount: number; spent: number }) {
  if (amount <= 0) {
    return <span className="hint">—</span>;
  }
  const pct = Math.min((spent / amount) * 100, 100);
  const color = pctColor(pct);
  return (
    <div className="progress-cell">
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="progress-text">{pct.toFixed(2)}%</span>
    </div>
  );
}
