// 科目支出明细弹窗：展示项目某科目支出列表（总预算入口=跨全部年度；年度预算入口=限定该年度）

import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

// 与 Rust expense::ProjectExpenseRow 对齐
export interface ProjectExpenseRow {
  id: number;
  year: number | null; // 所属年度预算年份；挂在总预算行时为 null
  category: string; // 中文 label
  content: string;
  specification: string | null;
  supplier: string | null;
  amount: number | null; // 单位：元
  date: string | null;
  remarks: string | null;
  voucher_path: string | null;
}

// 金额格式化：千分位 + 2 位小数（元）
function fmt(n: number): string {
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

interface CategoryExpensesDialogProps {
  projectId: number;
  /** 科目中文 label，如「材料费」 */
  category: string;
  /** 该科目预算额（万元），头部摘要展示 */
  budgetAmount: number;
  /** 限定预算 id（年度预算行入口）；不传 = 跨全部年度（总预算行入口） */
  budgetId?: number | null;
  /** 头部标题里的范围标注，如「2024年度」 */
  scopeLabel?: string | null;
  onClose: () => void;
}

export default function CategoryExpensesDialog({
  projectId,
  category,
  budgetAmount,
  budgetId,
  scopeLabel,
  onClose,
}: CategoryExpensesDialogProps) {
  const [rows, setRows] = useState<ProjectExpenseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 排序：默认日期倒序（后端即此序）；点击日期/金额表头切换
  const [sortKey, setSortKey] = useState<"date" | "amount">("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const toggleSort = (key: "date" | "amount") => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };
  const sortIndicator = (key: "date" | "amount") =>
    sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  const sortedRows = useMemo(() => {
    if (!rows) return null;
    const mul = sortDir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const cmp =
        sortKey === "date"
          ? (a.date ?? "").localeCompare(b.date ?? "")
          : (a.amount ?? 0) - (b.amount ?? 0);
      return cmp * mul || b.id - a.id; // 同值按 id 倒序稳定
    });
  }, [rows, sortKey, sortDir]);

  useEffect(() => {
    let cancelled = false;
    invoke<ProjectExpenseRow[]>("list_project_expenses_by_category", {
      projectId,
      category,
      budgetId: budgetId ?? null,
    })
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, category, budgetId]);

  // 合计（元）
  const total = (rows ?? []).reduce((s, r) => s + (r.amount ?? 0), 0);

  return (
    <div className="dialog-overlay" onClick={onClose}>
      {/* 阻止冒泡，点击弹窗内部不关闭 */}
      <div
        className="dialog-container"
        style={{ width: 760, maxWidth: "92vw" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog-header">
          <h2>
            {category} · 支出明细
            {scopeLabel ? `（${scopeLabel}）` : ""}
          </h2>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>
        {/* body 不自身滚动：提示文字固定，滚动只发生在表格容器内（表头随之吸顶） */}
        <div className="dialog-body dialog-body-fixed-table">
          <p className="hint" style={{ marginBottom: 8 }}>
            {scopeLabel ? `${scopeLabel}中` : "项目全部年度中"}「{category}」
            科目的支出记录，共 {rows === null ? "…" : rows.length} 笔；科目预算{" "}
            {fmt(budgetAmount)} 万元。
          </p>

          {error && (
            <p className="hint" style={{ color: "#c62828" }}>
              加载失败：{error}
            </p>
          )}

          {!error && rows !== null && rows.length === 0 && (
            <p className="hint" style={{ padding: "16px 0", textAlign: "center" }}>
              该科目暂无支出记录
            </p>
          )}

          {!error && rows !== null && rows.length > 0 && (
            <div className="table-frame">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: 70 }}>年度</th>
                    <th
                      className="sortable"
                      style={{ width: 110 }}
                      onClick={() => toggleSort("date")}
                    >
                      日期{sortIndicator("date")}
                    </th>
                    <th style={{ textAlign: "left" }}>支出内容</th>
                    <th style={{ width: 110 }}>供应商</th>
                    <th
                      className="sortable"
                      style={{ width: 120 }}
                      onClick={() => toggleSort("amount")}
                    >
                      金额(元){sortIndicator("amount")}
                    </th>
                    <th style={{ width: 110 }}>备注</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows!.map((r) => (
                    <tr key={r.id}>
                      <td>{r.year ?? "—"}</td>
                      <td>{r.date ?? "—"}</td>
                      <td style={{ textAlign: "left" }}>{r.content}</td>
                      <td>{r.supplier ?? "—"}</td>
                      <td className="num">{fmt(r.amount ?? 0)}</td>
                      <td>{r.remarks ?? "—"}</td>
                    </tr>
                  ))}
                  <tr className="tree-parent">
                    <td colSpan={4} style={{ textAlign: "right" }}>
                      <strong>合计</strong>
                    </td>
                    <td className="num">
                      <strong>{fmt(total)}</strong>
                    </td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="dialog-footer">
          <button onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  );
}
