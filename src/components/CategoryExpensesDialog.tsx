// 科目支出明细弹窗：展示项目某科目跨全部年度的支出列表（总预算科目行点击入口）

import { useEffect, useState } from "react";
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
  /** 该科目总预算额（万元），头部摘要展示 */
  budgetAmount: number;
  onClose: () => void;
}

export default function CategoryExpensesDialog({
  projectId,
  category,
  budgetAmount,
  onClose,
}: CategoryExpensesDialogProps) {
  const [rows, setRows] = useState<ProjectExpenseRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    invoke<ProjectExpenseRow[]>("list_project_expenses_by_category", {
      projectId,
      category,
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
  }, [projectId, category]);

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
          <h2>{category} · 支出明细</h2>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="dialog-body">
          <p className="hint" style={{ marginBottom: 8 }}>
            项目全部年度中「{category}」科目的支出记录，共{" "}
            {rows === null ? "…" : rows.length} 笔；科目预算 {fmt(budgetAmount)}{" "}
            万元。
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
                    <th style={{ width: 100 }}>日期</th>
                    <th style={{ textAlign: "left" }}>支出内容</th>
                    <th style={{ width: 110 }}>供应商</th>
                    <th style={{ width: 110 }}>金额(元)</th>
                    <th style={{ width: 110 }}>备注</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
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
