// 支出对话框：新增 / 编辑共用
// 对应 Python app/components/expense_dialog.py::ExpenseDialog
// 本期不实现文件选择，voucher_path 为文本输入

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { BUDGET_CATEGORIES } from "./BudgetFormDialog";

// 与后端 core::services::expense::ExpenseInput 对齐
export interface ExpenseInput {
  project_id: number;
  budget_id: number;
  category: string;
  content: string;
  specification: string | null;
  supplier: string | null;
  amount: number;
  date: string;
  remarks: string | null;
  voucher_path: string | null;
}

export type ExpenseFormMode = "add" | "update";

interface Props {
  projectId: number;
  budgetId: number;
  editingId?: number;
  onSubmit: (input: ExpenseInput, id?: number) => Promise<void>;
  onClose: () => void;
  /** 左下角"批量导入"入口（由父页面打开批量导入对话框） */
  onBatchImport?: () => void;
}

// 与后端 core::models::Expense 对齐（get_expense 返回结构）
interface ExpenseDetail {
  id: number;
  project_id: number;
  budget_id: number;
  category: string;
  content: string;
  specification: string | null;
  supplier: string | null;
  amount: number | null;
  date: string | null;
  remarks: string | null;
  voucher_path: string | null;
}

function todayStr(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export default function ExpenseFormDialog({
  projectId,
  budgetId,
  editingId,
  onSubmit,
  onClose,
  onBatchImport,
}: Props) {
  const isEdit = editingId !== undefined;
  const [isLoadingDetail, setIsLoadingDetail] = useState(isEdit);
  const [category, setCategory] = useState<string>(BUDGET_CATEGORIES[0]);
  const [content, setContent] = useState("");
  const [specification, setSpecification] = useState("");
  const [supplier, setSupplier] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState<string>(todayStr());
  const [remarks, setRemarks] = useState("");
  const [voucherPath, setVoucherPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 编辑模式：打开时调后端回填
  useEffect(() => {
    if (!isEdit || editingId === undefined) return;
    (async () => {
      try {
        const detail = await invoke<ExpenseDetail | null>("get_expense", {
          id: editingId,
        });
        if (!detail) {
          setError("未找到该支出记录，可能已被删除。");
          return;
        }
        setCategory(detail.category);
        setContent(detail.content);
        setSpecification(detail.specification ?? "");
        setSupplier(detail.supplier ?? "");
        setAmount(detail.amount != null ? String(detail.amount) : "");
        setDate(detail.date ?? todayStr());
        setRemarks(detail.remarks ?? "");
        setVoucherPath(detail.voucher_path ?? "");
      } catch (err) {
        setError(String(err));
      } finally {
        setIsLoadingDetail(false);
      }
    })();
  }, [isEdit, editingId]);

  // 选择凭证文件（对齐 Python ExpenseDialog.select_voucher：仅存所选文件路径）
  const selectVoucher = async () => {
    try {
      const file = await open({
        multiple: false,
        title: "选择凭证文件",
        filters: [
          {
            name: "支持的文件",
            extensions: ["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"],
          },
        ],
      });
      if (typeof file === "string") {
        setVoucherPath(file);
        setError(null);
      }
    } catch (err) {
      setError(String(err));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!content.trim()) {
      setError("开支内容不能为空");
      return;
    }
    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setError("报账金额必须大于 0");
      return;
    }
    if (!date) {
      setError("报账日期不能为空");
      return;
    }

    const input: ExpenseInput = {
      project_id: projectId,
      budget_id: budgetId,
      category,
      content: content.trim(),
      specification: specification.trim() || null,
      supplier: supplier.trim() || null,
      amount: amountNum,
      date,
      remarks: remarks.trim() || null,
      voucher_path: voucherPath.trim() || null,
    };

    setIsSubmitting(true);
    try {
      await onSubmit(input, editingId);
      onClose();
    } catch (err) {
      setError(String(err));
      setIsSubmitting(false);
    }
  };

  const anyLoading = isSubmitting || isLoadingDetail;
  const title = isEdit ? "编辑支出信息" : "新增支出信息";

  return (
    <div className="dialog-overlay">
      <div className="dialog-container" style={{ width: 520 }}>
        <div className="dialog-header">
          <h2>{title}</h2>
          <button className="close-btn" onClick={() => !anyLoading && onClose()}>
            &times;
          </button>
        </div>
        <form onSubmit={handleSubmit} className="dialog-body">
          {error && <div className="form-error">{error}</div>}
          {isLoadingDetail && <div className="form-info">正在加载支出数据…</div>}

          <div className="form-group">
            <label htmlFor="cat">费用类别 *</label>
            <select
              id="cat"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              disabled={isLoadingDetail}
            >
              {BUDGET_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="content">开支内容 *</label>
            <input
              id="content"
              type="text"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="请输入开支内容"
              disabled={isLoadingDetail}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="spec">规格型号</label>
            <input
              id="spec"
              type="text"
              value={specification}
              onChange={(e) => setSpecification(e.target.value)}
              placeholder="可选"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="supplier">供应商</label>
            <input
              id="supplier"
              type="text"
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              placeholder="可选"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="amount">报账金额（元） *</label>
            <input
              id="amount"
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              min={0}
              step={0.01}
              placeholder="单位：元"
              disabled={isLoadingDetail}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="date">报账日期 *</label>
            <input
              id="date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              disabled={isLoadingDetail}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="remarks">备注</label>
            <input
              id="remarks"
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="可选"
              disabled={isLoadingDetail}
            />
          </div>

          <div className="form-group">
            <label htmlFor="voucher">支出凭证</label>
            <div className="form-row">
              <button
                type="button"
                onClick={selectVoucher}
                disabled={isLoadingDetail}
                className="file-select-btn"
              >
                {voucherPath ? "重新选择文件" : "选择凭证文件"}
              </button>
              {voucherPath && (
                <span className="file-path-label" title={voucherPath}>
                  {voucherPath.split(/[\\/]/).pop()}
                </span>
              )}
            </div>
            {voucherPath && (
              <div className="hint" style={{ marginTop: 4, wordBreak: "break-all" }}>
                已选: {voucherPath}
              </div>
            )}
          </div>

          <div className="dialog-footer">
            {onBatchImport && (
              <button
                type="button"
                onClick={onBatchImport}
                disabled={anyLoading}
                style={{ marginRight: "auto" }}
              >
                批量导入
              </button>
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
