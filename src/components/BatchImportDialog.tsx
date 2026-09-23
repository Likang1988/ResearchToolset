// 批量导入支出对话框
// 流程：下载模板 → 选择文件 → 解析预览 → 确认导入（batch_add_expenses）

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";

// 与后端 core::excel::ParsedExpense 对齐
interface ParsedExpense {
  category: string;
  content: string;
  specification: string | null;
  supplier: string | null;
  amount: number;
  date: string;
  remarks: string | null;
}

interface Props {
  projectId: number;
  budgetId: number;
  /** 导入成功后回调（页面负责刷新列表 + emitBudgetOrExpenseUpdated） */
  onImported: (count: number) => void;
  onClose: () => void;
}

function fmt(n: number): string {
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function BatchImportDialog({
  projectId,
  budgetId,
  onImported,
  onClose,
}: Props) {
  const [filePath, setFilePath] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedExpense[] | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  const selectFile = async () => {
    const f = await open({
      multiple: false,
      title: "选择支出导入文件",
      filters: [
        { name: "Excel", extensions: ["xlsx", "xls"] },
        { name: "CSV", extensions: ["csv"] },
      ],
    });
    if (typeof f === "string") {
      setFilePath(f);
      setParsed(null);
      setParseError(null);
    }
  };

  const downloadTemplate = async () => {
    const savePath = await save({
      defaultPath: "支出导入模板.xlsx",
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
    });
    if (!savePath) return;
    try {
      await invoke("download_expense_import_template", { savePath });
      alert(`模板已保存至：${savePath}`);
    } catch (e) {
      alert(`保存模板失败：${String(e)}`);
    }
  };

  // 解析 + 校验（任一校验失败由后端返回首个错误信息）
  const doParse = async () => {
    if (!filePath) {
      alert("请先选择文件！");
      return;
    }
    setIsParsing(true);
    setParseError(null);
    setParsed(null);
    try {
      const items = await invoke<ParsedExpense[]>("parse_expenses_import", {
        filePath,
      });
      setParsed(items);
    } catch (e) {
      setParseError(String(e));
    } finally {
      setIsParsing(false);
    }
  };

  const doImport = async () => {
    if (!parsed || parsed.length === 0) return;
    setIsImporting(true);
    try {
      const n = await invoke<number>("batch_add_expenses", {
        projectId,
        budgetId,
        items: parsed,
      });
      alert(`成功导入 ${n} 条记录！`);
      onImported(n);
    } catch (e) {
      alert(`批量导入支出失败：${String(e)}`);
      setIsImporting(false);
    }
  };

  return (
    <div className="dialog-overlay">
      <div className="dialog-container" style={{ width: 760 }}>
        <div className="dialog-header">
          <h2>批量导入支出信息</h2>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>
        <div className="dialog-body">
          {/* 文件选择 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>选择文件:</span>
            <span style={{ color: filePath ? "#333" : "#999", fontStyle: filePath ? "normal" : "italic", flex: 1, wordBreak: "break-all" }}>
              {filePath ?? "未选择文件"}
            </span>
            <button onClick={selectFile}>选择</button>
          </div>

          {/* 说明 */}
          <div className="hint" style={{ margin: "10px 0", whiteSpace: "pre-line" }}>
            {"注意事项：\n1. 费用类别、开支内容和报账金额为必填项\n2. 费用类别必须是系统预设的类别之一\n3. 报账金额必须大于0\n4. 报账日期格式为YYYY-MM-DD，可为空"}
          </div>

          {parseError && (
            <div className="hint" style={{ color: "#c62828", marginBottom: 8 }}>
              导入文件校验失败：{parseError}
            </div>
          )}

          {/* 解析预览 */}
          {parsed && parsed.length > 0 && (
            <div style={{ maxHeight: 260, overflow: "auto", marginBottom: 8 }}>
              <table className="data-table expense-table">
                <thead>
                  <tr>
                    <th>费用类别</th>
                    <th>开支内容</th>
                    <th>规格型号</th>
                    <th>供应商</th>
                    <th>报账金额(元)</th>
                    <th>报账日期</th>
                    <th>备注</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.map((p, i) => (
                    <tr key={i}>
                      <td>{p.category}</td>
                      <td style={{ textAlign: "left" }}>{p.content}</td>
                      <td>{p.specification ?? ""}</td>
                      <td>{p.supplier ?? ""}</td>
                      <td className="num">{fmt(p.amount)}</td>
                      <td>{p.date}</td>
                      <td>{p.remarks ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="hint">共解析 {parsed.length} 条支出，确认无误后点击「确认导入」。</p>
            </div>
          )}
        </div>
        <div className="dialog-footer">
          <button onClick={downloadTemplate}>下载模板</button>
          <button onClick={doParse} disabled={isParsing}>
            {isParsing ? "解析中…" : "解析预览"}
          </button>
          <button onClick={onClose} disabled={isImporting}>
            取消
          </button>
          <button
            className="primary-btn"
            onClick={doImport}
            disabled={!parsed || parsed.length === 0 || isImporting}
          >
            {isImporting ? "导入中…" : "确认导入"}
          </button>
        </div>
      </div>
    </div>
  );
}