// 年度预算对话框：新增 / 编辑共用
// 新增：年度可编辑、科目金额默认空、总金额实时联动
// 编辑：年度禁用不可改、回填原有 10 科目金额、更新时保留 spent_amount

import { useEffect, useState } from "react";

// 10 个预算科目（顺序与后端 core::models::BudgetCategory::ALL 一致）
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
];

export interface BudgetFormItem {
  category: string;
  amount: number;
}

/// 新增模式的提交数据
export interface AddBudgetPayload {
  mode: "add";
  project_id: number;
  year: number;
  total_amount: number;
  items: BudgetFormItem[];
}

/// 编辑年度预算模式的提交数据（project_id/year 由后端按 id 校验，不随表单改）
export interface UpdateBudgetPayload {
  mode: "update";
  id: number;
  total_amount: number;
  items: BudgetFormItem[];
}

/// 编辑总预算模式的提交数据
export interface TotalBudgetPayload {
  mode: "total";
  id: number;
  total_amount: number;
  items: BudgetFormItem[];
}

export type BudgetFormPayload = AddBudgetPayload | UpdateBudgetPayload | TotalBudgetPayload;

interface Props {
  /// 新增：必填；编辑：忽略（用 editingId 调后端查询）
  projectId: number;
  /// 编辑模式：传预算 id；undefined 为新增
  editingId?: number;
  /// 编辑模式：annual=年度预算，total=总预算。仅当 editingId 存在时有效
  editingMode?: "annual" | "total";
  /// 当前总预算的总结余（万元）：∑(总预算各类金额 - 各类别年度预算累计支出)；
  /// null = 尚未设置总预算（仅年度模式展示）
  totalBalance?: number | null;
  /// 各科目结余（万元）：科目 → 结余；null = 尚未设置总预算
  categoryBalances?: Record<string, number> | null;
  /// 新增模式预填金额（万元）：科目 → 金额
  /// （计划类别金额 `item.amount / 10000` 填入）；仅新增模式生效，编辑靠后端回填
  initialAmounts?: Record<string, number>;
  /// 项目总经费（万元，来源项目清单）；总预算模式用于校验预算总计与总经费一致
  projectTotalBudget?: number | null;
  /// 新增模式：点击右下角「导入预算计划」（打开计划选择对话框，选中后经
  /// initialAmounts 预填表单）；仅新增模式生效
  onImportBudgetPlan?: () => void;
  /// 计划加载中（导入按钮禁用态）
  importBusy?: boolean;
  /// 提交：根据 payload.mode 区分 add / update / total；返回 Promise 让表单显示 loading
  onSubmit: (data: BudgetFormPayload) => Promise<void>;
  onClose: () => void;
}

export default function BudgetFormDialog({
  projectId,
  editingId,
  editingMode = "annual",
  totalBalance,
  categoryBalances,
  initialAmounts,
  projectTotalBudget,
  onImportBudgetPlan,
  importBusy = false,
  onSubmit,
  onClose,
}: Props) {
  const isEdit = editingId !== undefined;
  const isTotal = isEdit && editingMode === "total";
  const [isLoadingDetail, setIsLoadingDetail] = useState(isEdit);
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState<string>(String(currentYear));
  // 新增模式：可被 initialAmounts（从预算编制导入）预填；编辑模式在下方 useEffect 中回填
  const [amounts, setAmounts] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      BUDGET_CATEGORIES.map((c) => [
        c,
        initialAmounts && initialAmounts[c] !== undefined
          ? String(initialAmounts[c])
          : "",
      ])
    )
  );
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 新增模式：打开对话框后再从预算编制导入（initialAmounts 引用变化）时，
  // 把新金额回填进表单字段
  useEffect(() => {
    if (isEdit || initialAmounts === undefined) return;
    setAmounts(
      Object.fromEntries(
        BUDGET_CATEGORIES.map((c) => [
          c,
          initialAmounts[c] !== undefined ? String(initialAmounts[c]) : "",
        ])
      )
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAmounts]);

  // 编辑模式：打开时调后端回填表单
  useEffect(() => {
    if (!isEdit || editingId === undefined) return;
    (async () => {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        // total 模式调 get_total_budget，annual 模式调 get_annual_budget
        const cmd = isTotal ? "get_total_budget" : "get_annual_budget";
        const detail = await invoke<
          | { items: { category: string; amount: number }[] }
          | null
        >(cmd, { id: editingId });
        if (!detail) {
          setError(
            isTotal
              ? "未找到该总预算，可能已被删除。请刷新后重试。"
              : "未找到该年度预算，可能已被删除。请刷新后重试。"
          );
          return;
        }
        // annual 模式才有 year 字段
        if (!isTotal && "year" in detail) {
          setYear(String((detail as { year: number }).year));
        }
        const map: Record<string, string> = Object.fromEntries(
          BUDGET_CATEGORIES.map((c) => [c, ""])
        );
        for (const it of detail.items) {
          map[it.category] = String(it.amount);
        }
        setAmounts(map);
      } catch (err) {
        setError(String(err));
      } finally {
        setIsLoadingDetail(false);
      }
    })();
  }, [isEdit, editingId, isTotal]);

  // 总金额 = 10 个科目之和
  const total = BUDGET_CATEGORIES.reduce((sum, cat) => {
    const v = parseFloat(amounts[cat]);
    return sum + (isNaN(v) ? 0 : v);
  }, 0);

  const handleChange = (category: string, value: string) => {
    setAmounts((prev) => ({ ...prev, [category]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 总预算模式无年度；年度模式编辑时年度被禁用，使用后端加载值
    if (!isTotal) {
      if (isEdit) {
        const y = parseInt(year, 10);
        if (isNaN(y)) {
          setError("年度数据加载异常，请关闭重试");
          return;
        }
      } else {
        const y = parseInt(year, 10);
        if (isNaN(y) || y < 1900 || y > 2100) {
          setError("请输入有效的年度（如 2024）");
          return;
        }
      }
    }

    if (total <= 0) {
      setError("总金额必须大于 0，请至少为一个科目填入金额");
      return;
    }

    // 总预算模式：预算总计必须与项目总经费（项目清单）一致
    if (
      isTotal &&
      projectTotalBudget !== null &&
      projectTotalBudget !== undefined &&
      Math.abs(total - projectTotalBudget) > 1e-6
    ) {
      setError(
        `预算总计 ${total.toFixed(2)} 万元与项目总经费 ${projectTotalBudget.toFixed(
          2
        )} 万元不一致，请调整科目金额`
      );
      return;
    }

    const items: BudgetFormItem[] = BUDGET_CATEGORIES.map((category) => ({
      category,
      amount: parseFloat(amounts[category]) || 0,
    }));

    setIsSubmitting(true);
    try {
      let payload: BudgetFormPayload;
      if (isTotal && editingId !== undefined) {
        payload = {
          mode: "total",
          id: editingId,
          total_amount: Math.round(total * 100) / 100,
          items,
        };
      } else if (isEdit && editingId !== undefined) {
        payload = {
          mode: "update",
          id: editingId,
          total_amount: Math.round(total * 100) / 100,
          items,
        };
      } else {
        payload = {
          mode: "add",
          project_id: projectId,
          year: parseInt(year, 10),
          total_amount: Math.round(total * 100) / 100,
          items,
        };
      }
      await onSubmit(payload);
      onClose();
    } catch (err) {
      setError(String(err));
      setIsSubmitting(false);
    }
  };

  const anyLoading = isSubmitting || isLoadingDetail;
  const title = isTotal
    ? "编辑总预算"
    : isEdit
    ? "编辑年度预算"
    : "新增年度预算";

  return (
    <div className="dialog-overlay">
      <div className="dialog-container" style={{ width: 560 }}>
        <div className="dialog-header">
          <h2>{title}</h2>
          <button
            className="close-btn"
            onClick={() => !anyLoading && onClose()}
          >
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit} className="dialog-body">
          {error && <div className="form-error">{error}</div>}
          {isLoadingDetail && (
            <div className="form-info">正在加载预算数据…</div>
          )}

          <div className="budget-form-top">
            {/* 总预算模式不显示年度字段 */}
            {!isTotal && (
              <div className="form-group" style={{ flex: "0 0 160px" }}>
                <label htmlFor="year">年度 *</label>
                <input
                  type="number"
                  id="year"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                  min={1900}
                  max={2100}
                  step={1}
                  required
                  disabled={isEdit}
                  className={isEdit ? "disabled-input" : ""}
                />
                {isEdit && (
                  <div className="form-hint">编辑时不可修改年度</div>
                )}
              </div>
            )}
            {/* 总预算模式：左侧总预算（随录入实时汇总），右侧项目总经费 */}
            {isTotal && (
              <>
                <div className="budget-current-total">
                  <span>总预算</span>
                  <strong>{total.toFixed(2)} 万元</strong>
                </div>
                <div className="budget-project-total">
                  <span>项目总经费</span>
                  <strong>
                    {projectTotalBudget === null ||
                    projectTotalBudget === undefined
                      ? "未设置"
                      : `${projectTotalBudget.toFixed(2)} 万元`}
                  </strong>
                </div>
              </>
            )}
          </div>

          {/* 年度预算：费用类别 / 预算金额 / 结余金额 3 列表格 */}
          {!isTotal && (
            <div className="budget-table">
              <div className="budget-table-header">
                <span>费用类别</span>
                <span>预算金额</span>
                <span>结余金额</span>
              </div>
              {BUDGET_CATEGORIES.map((cat) => {
                const catBalance =
                  categoryBalances === null || categoryBalances === undefined
                    ? null
                    : categoryBalances[cat] ?? 0;
                return (
                  <div className="budget-table-row" key={cat}>
                    <span className="budget-table-cat">{cat}</span>
                    <input
                      type="number"
                      id={`amt-${cat}`}
                      className="budget-table-input"
                      value={amounts[cat]}
                      onChange={(e) => handleChange(cat, e.target.value)}
                      min={0}
                      step={0.01}
                      placeholder="0.00"
                      disabled={isLoadingDetail}
                    />
                    <span className="budget-table-balance">
                      {catBalance === null
                        ? "未设置总预算"
                        : `${catBalance.toFixed(2)} 万元`}
                    </span>
                  </div>
                );
              })}
              {/* 总计行：总计 / 预算总额 / 总结余 */}
              <div className="budget-table-row budget-table-total">
                <span className="budget-table-cat">总计</span>
                <span className="budget-table-amount">
                  {total.toFixed(2)} 万元
                </span>
                <span className="budget-table-balance">
                  {totalBalance === null || totalBalance === undefined
                    ? "未设置总预算"
                    : `${totalBalance.toFixed(2)} 万元`}
                </span>
              </div>
            </div>
          )}

          {/* 总预算编辑：保持原有科目网格 */}
          {isTotal && (
            <div className="budget-items-grid">
              {BUDGET_CATEGORIES.map((cat) => (
                <div className="form-group budget-item" key={cat}>
                  <label htmlFor={`amt-${cat}`}>{cat}</label>
                  <input
                    type="number"
                    id={`amt-${cat}`}
                    value={amounts[cat]}
                    onChange={(e) => handleChange(cat, e.target.value)}
                    min={0}
                    step={0.01}
                    placeholder="0.00"
                    disabled={isLoadingDetail}
                  />
                </div>
              ))}
            </div>
          )}

          <div className="dialog-footer">
            {!isEdit && onImportBudgetPlan && (
              <>
                <button
                  type="button"
                  onClick={onImportBudgetPlan}
                  disabled={anyLoading || importBusy}
                >
                  {importBusy ? "加载中..." : "导入预算计划"}
                </button>
                <span style={{ flex: 1 }} />
              </>
            )}
            <button type="button" onClick={onClose} disabled={anyLoading}>
              取消
            </button>
            <button type="submit" disabled={anyLoading} className="primary-btn">
              {isSubmitting ? "保存中..." : "保存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
