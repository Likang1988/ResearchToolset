// 支出管理页：项目经费页子页（双击年度预算行进入）
// 对应 Python app/views/projecting_interface/project_expense.py
// 顶部工具栏（增删改+导出 Excel）+ 过滤器 + 支出列表 + 底部统计表

import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";
import ExpenseFormDialog, {
  type ExpenseInput,
} from "../components/ExpenseFormDialog";
import BatchImportDialog from "../components/BatchImportDialog";
import { BUDGET_CATEGORIES } from "../components/BudgetFormDialog";
import { emitBudgetOrExpenseUpdated } from "../data/events";

// 与后端 core::attachments::AttachmentContext 对齐（生成凭证路径用）
interface VoucherContext {
  financial_code: string | null;
  category: string | null;
  amount: number | null;
  date: string | null;
  base_folder: string | null;
}

// 与后端 core::models::Expense 对齐
interface Expense {
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

// 预算子项（用于底部统计表预算行）
interface BudgetItemNode {
  category: string;
  amount: number;
  spent_amount: number;
}
interface BudgetNode {
  id: number;
  year: number | null;
  total_amount: number;
  spent_amount: number;
  items: BudgetItemNode[];
}
interface BudgetTree {
  total_budget: BudgetNode | null;
  annual_budgets: BudgetNode[];
}

interface Props {
  projectId: number;
  projectFinancialCode: string | null;
  budgetId: number;
  budgetYear: number;
  onBack: () => void;
}

// 金额格式化：千分位 + 2 位小数
function fmt(n: number): string {
  return n.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function ExpenseManagementPage({
  projectId,
  projectFinancialCode,
  budgetId,
  budgetYear,
  onBack,
}: Props) {
  const [allExpenses, setAllExpenses] = useState<Expense[]>([]);
  const [budgetNode, setBudgetNode] = useState<BudgetNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 附件文件缺失集合（DB 有路径但磁盘文件已被程序外删除）
  const [missingVouchers, setMissingVouchers] = useState<Set<string>>(new Set());

  // 工具栏对话框
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingExpenseId, setEditingExpenseId] = useState<number | undefined>(undefined);

  // 批量导入对话框
  const [batchImportOpen, setBatchImportOpen] = useState(false);

  // 多选删除
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // 行内凭证附件菜单（当前展开菜单的支出行 id + 按钮锚点坐标）
  const [voucherMenuFor, setVoucherMenuFor] = useState<number | null>(null);
  const [voucherMenuPos, setVoucherMenuPos] = useState<{
    left: number;
    top: number;
  } | null>(null);

  // 过滤器
  const [filterCategory, setFilterCategory] = useState<string>("全部");
  const [filterMinAmount, setFilterMinAmount] = useState<string>("");
  const [filterMaxAmount, setFilterMaxAmount] = useState<string>("");
  const [filterStartDate, setFilterStartDate] = useState<string>("");
  const [filterEndDate, setFilterEndDate] = useState<string>("");
  const [filterKeyword, setFilterKeyword] = useState<string>("");
  // 导出下拉菜单（导出Excel / 导出附件 合并为「导出」按钮）
  const [exportMenuOpen, setExportMenuOpen] = useState(false);

  // 表头排序（默认按报账日期倒序，与 DB 默认一致）
  type SortKey =
    | "category"
    | "content"
    | "specification"
    | "supplier"
    | "amount"
    | "date"
    | "remarks";
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // 刷新支出列表 + 预算节点
  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [expenses, tree] = await Promise.all([
        invoke<Expense[]>("list_expenses", { budgetId }),
        invoke<BudgetTree>("list_project_budgets", { projectId }),
      ]);
      setAllExpenses(expenses);
      // 校验附件真实性：识别"程序外删除"导致的附件缺失（不影响列表加载）
      const paths = expenses
        .map((e) => e.voucher_path)
        .filter((p): p is string => !!p);
      setMissingVouchers(new Set());
      if (paths.length > 0) {
        try {
          const exists = await invoke<boolean[]>("check_attachments", { paths });
          const missing = new Set<string>();
          paths.forEach((p, i) => {
            if (!exists[i]) missing.add(p);
          });
          setMissingVouchers(missing);
        } catch {
          // 校验失败不阻断列表加载
        }
      }
      const node =
        tree.annual_budgets.find((b) => b.id === budgetId) ?? null;
      setBudgetNode(node);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [budgetId, projectId]);

  // 本地过滤 + 表头排序（与 Python apply_filters 一致：内存过滤，不重查 DB）
  const filteredExpenses = useMemo(() => {
    const min = filterMinAmount ? parseFloat(filterMinAmount) : null;
    const max = filterMaxAmount ? parseFloat(filterMaxAmount) : null;
    const kw = filterKeyword.trim().toLowerCase();
    let list = allExpenses.filter((e) => {
      if (filterCategory !== "全部" && e.category !== filterCategory) return false;
      const amt = e.amount ?? 0;
      if (min !== null && !isNaN(min) && amt < min) return false;
      if (max !== null && !isNaN(max) && amt > max) return false;
      if (filterStartDate && (e.date ?? "") < filterStartDate) return false;
      if (filterEndDate && (e.date ?? "") > filterEndDate) return false;
      // 关键词：匹配开支内容/规格型号/供应商/备注
      if (kw) {
        const hay = [e.content, e.specification ?? "", e.supplier ?? "", e.remarks ?? ""]
          .join(" ")
          .toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });
    // 表头排序：字符串/数字统一比较，id 作为稳定次序兜底
    const dir = sortDir === "asc" ? 1 : -1;
    const getVal = (e: Expense): string | number => {
      switch (sortKey) {
        case "category":
          return e.category;
        case "content":
          return e.content;
        case "specification":
          return e.specification ?? "";
        case "supplier":
          return e.supplier ?? "";
        case "amount":
          return e.amount ?? 0;
        case "date":
          return e.date ?? "";
        case "remarks":
          return e.remarks ?? "";
      }
    };
    list = [...list].sort((a, b) => {
      const va = getVal(a);
      const vb = getVal(b);
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return a.id - b.id;
    });
    return list;
  }, [
    allExpenses,
    filterCategory,
    filterMinAmount,
    filterMaxAmount,
    filterStartDate,
    filterEndDate,
    filterKeyword,
    sortKey,
    sortDir,
  ]);

  const resetFilters = () => {
    setFilterCategory("全部");
    setFilterMinAmount("");
    setFilterMaxAmount("");
    setFilterStartDate("");
    setFilterEndDate("");
    setFilterKeyword("");
    setSortKey("date");
    setSortDir("desc");
  };

  // 点击表头切换排序：同列翻转方向，新列默认升序（日期列默认倒序）
  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "date" ? "desc" : "asc");
    }
  };
  const sortIndicator = (key: SortKey): string =>
    sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  // 行选择切换
  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const toggleSelectAll = () => {
    setSelectedIds((prev) => {
      if (prev.size === filteredExpenses.length) return new Set();
      return new Set(filteredExpenses.map((e) => e.id));
    });
  };

  // 提交表单：分发 add / update
  const handleSubmitExpense = async (input: ExpenseInput, id?: number) => {
    if (id !== undefined) {
      await invoke("update_expense", { id, input });
    } else {
      await invoke("add_expense", { input });
    }
    setSelectedIds(new Set());
    await refresh();
    emitBudgetOrExpenseUpdated();
  };

  // 确认删除：批量
  const confirmDelete = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    try {
      await invoke("delete_expenses", { ids });
      setSelectedIds(new Set());
      await refresh();
      emitBudgetOrExpenseUpdated();
      setConfirmingDelete(false);
    } catch (e) {
      setError(String(e));
      setConfirmingDelete(false);
    }
  };

  // 批量导入成功：刷新列表 + 联动预算事件
  const handleBatchImported = async () => {
    setBatchImportOpen(false);
    await refresh();
    emitBudgetOrExpenseUpdated();
  };

  // 导出 Excel
  const handleExportExcel = async () => {
    const defaultName = `支出记录_${projectFinancialCode ?? "项目"}_${budgetYear}.xlsx`;
    const savePath = await save({
      defaultPath: defaultName,
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
    });
    if (!savePath) return;
    try {
      await invoke("export_expenses_excel", {
        budgetId,
        savePath,
      });
      alert(`导出成功：${savePath}`);
    } catch (e) {
      alert(`导出失败：${String(e)}`);
    }
  };

  // 导出当前筛选结果的凭证附件（对齐 Python export_expense_vouchers）
  const handleExportVouchers = async () => {
    const withVoucher = filteredExpenses.filter((e) => e.voucher_path);
    if (withVoucher.length === 0) {
      alert("当前筛选结果中没有带凭证附件的支出");
      return;
    }
    const dir = await open({
      directory: true,
      title: "选择凭证附件保存位置",
    });
    if (typeof dir !== "string") return;
    const pad = (n: number) => String(n).padStart(2, "0");
    const d = new Date();
    const ts = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(
      d.getDate()
    )}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
    const base = `${dir}/凭证_${projectFinancialCode ?? "项目"}_${budgetYear}_${ts}`;
    let count = 0;
    let skippedMissing = 0;
    try {
      for (const e of withVoucher) {
        const p = String(e.voucher_path);
        if (missingVouchers.has(p)) {
          // 源文件已被程序外删除：跳过并提示，不中断整体导出
          skippedMissing += 1;
          continue;
        }
        const name = p.split(/[\\/]/).pop();
        await invoke("copy_attachment_file", {
          source: p,
          dest: `${base}/${e.id}_${name}`,
        });
        count += 1;
      }
      let msg = `导出完成，共 ${count} 个凭证附件`;
      if (skippedMissing > 0) msg += `\n（${skippedMissing} 个附件文件缺失，已跳过）`;
      msg += `\n保存位置：${base}`;
      alert(msg);
    } catch (err) {
      alert(`导出附件失败：${String(err)}`);
    }
  };

  // 行内凭证附件操作（对齐 Python attachment_utils 的菜单动作）
  const handleVoucherAction = async (e: Expense, action: string) => {
    setVoucherMenuFor(null);
    const path = e.voucher_path;

    // 只读操作（查看/下载/路径）前置检查：文件已被程序外删除时给出明确提示
    if (path && missingVouchers.has(path) && (action === "view" || action === "download" || action === "open_path")) {
      alert(
        "该凭证附件文件已被删除（可能为程序外操作）。\n" +
          "可通过「替换」重新上传附件，或「删除」清理此凭证记录。"
      );
      return;
    }

    // 查看：系统默认程序打开文件
    if (action === "view") {
      if (!path) return alert("附件不存在");
      try {
        await openPath(path);
      } catch (err) {
        alert(`无法打开附件：${String(err)}`);
      }
      return;
    }

    // 路径：在文件管理器中定位附件
    if (action === "open_path") {
      if (!path) return alert("附件不存在");
      try {
        await revealItemInDir(path);
      } catch {
        try {
          await openPath(path.substring(0, path.lastIndexOf("/")));
        } catch (err) {
          alert(`无法打开附件路径：${String(err)}`);
        }
      }
      return;
    }

    // 下载：另存为副本（对应 Python download_attachment 的 shutil.copy2）
    if (action === "download") {
      if (!path) return alert("附件不存在");
      const dest = await save({
        defaultPath: path.split(/[\\/]/).pop() ?? "attachment",
        filters: [{ name: "所有文件", extensions: ["*"] }],
      });
      if (!dest) return;
      try {
        await invoke("copy_attachment_file", { source: path, dest });
        alert(`附件已保存到：\n${dest}`);
      } catch (err) {
        alert(`保存附件失败：${String(err)}`);
      }
      return;
    }

    // 上传 / 替换：选源文件 → 拷到规则路径 → 写库 → 删旧文件
    if (action === "replace" || action === "upload") {
      const file = await open({
        multiple: false,
        title: "选择凭证文件",
      });
      if (typeof file !== "string") return; // 用户取消
      const context: VoucherContext = {
        financial_code: projectFinancialCode,
        category: e.category,
        amount: e.amount,
        date: e.date,
        base_folder: null,
      };
      try {
        const newPath = await invoke<string>("save_attachment", {
          kind: "expense",
          sourceFile: file,
          context,
          oldPath: path,
        });
        await invoke("update_expense_voucher", {
          id: e.id,
          voucherPath: newPath,
        });
        await refresh();
      } catch (err) {
        alert(`更新凭证失败：${String(err)}`);
      }
      return;
    }

    // 删除：删文件 + 数据库置空
    if (action === "delete") {
      if (!path) return alert("没有可删除的附件");
      if (!window.confirm("确定要删除此凭证附件吗？此操作不可恢复！")) return;
      try {
        await invoke("delete_attachment", { path });
        await invoke("update_expense_voucher", {
          id: e.id,
          voucherPath: null,
        });
        await refresh();
      } catch (err) {
        alert(`删除凭证失败：${String(err)}`);
      }
    }
  };

  // 底部统计表：按类别预算额（来自 budgetNode.items）+ 支出小计
  const stats = useMemo(() => {
    const budgetByCat = new Map<string, number>();
    if (budgetNode) {
      for (const it of budgetNode.items) {
        budgetByCat.set(it.category, it.amount);
      }
    }
    // 按类别汇总支出（元 → 万元）
    const spentByCat = new Map<string, number>();
    let totalSpentWan = 0;
    for (const e of allExpenses) {
      const amt = (e.amount ?? 0) / 10000;
      spentByCat.set(e.category, (spentByCat.get(e.category) ?? 0) + amt);
      totalSpentWan += amt;
    }
    const totalBudgetWan = budgetNode?.total_amount ?? 0;
    return {
      budgetByCat,
      spentByCat,
      totalBudgetWan,
      totalSpentWan,
    };
  }, [budgetNode, allExpenses]);

  const title = `支出管理-${projectFinancialCode ?? "项目"}-${budgetYear}`;

  return (
    <div className="expense-mgmt">
      <div className="expense-toolbar">
        <button onClick={onBack} className="back-btn">
          ← 返回预算树
        </button>
        <h2 className="page-title">{title}</h2>
        <div className="list-actions">
          <button
            className="primary-btn"
            onClick={() => {
              setEditingExpenseId(undefined);
              setDialogOpen(true);
            }}
          >
            添加支出
          </button>
          <button
            onClick={() => {
              if (selectedIds.size !== 1) {
                alert("请选中一行支出进行编辑");
                return;
              }
              setEditingExpenseId(Array.from(selectedIds)[0]);
              setDialogOpen(true);
            }}
            disabled={selectedIds.size !== 1}
          >
            编辑支出
          </button>
          <button
            onClick={() => {
              if (selectedIds.size === 0) {
                alert("请先勾选要删除的支出行");
                return;
              }
              setConfirmingDelete(true);
            }}
            disabled={selectedIds.size === 0}
            className="danger-btn"
          >
            删除支出
          </button>
        </div>
      </div>

      {error && (
        <div className="placeholder-card">
          <p className="hint" style={{ color: "#c62828" }}>操作失败：{error}</p>
        </div>
      )}

      {/* 过滤器 */}
      <div className="expense-filter">
        <label>费用类别:</label>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
        >
          <option value="全部">全部</option>
          {BUDGET_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <label>金额范围:</label>
        <input
          type="number"
          placeholder="最小"
          value={filterMinAmount}
          onChange={(e) => setFilterMinAmount(e.target.value)}
          style={{ width: 90 }}
        />
        <span>至</span>
        <input
          type="number"
          placeholder="最大"
          value={filterMaxAmount}
          onChange={(e) => setFilterMaxAmount(e.target.value)}
          style={{ width: 90 }}
        />

        <label>日期范围:</label>
        <input
          type="date"
          value={filterStartDate}
          onChange={(e) => setFilterStartDate(e.target.value)}
        />
        <span>至</span>
        <input
          type="date"
          value={filterEndDate}
          onChange={(e) => setFilterEndDate(e.target.value)}
        />

        <label>关键词:</label>
        <input
          type="text"
          placeholder="开支内容/型号······"
          value={filterKeyword}
          onChange={(e) => setFilterKeyword(e.target.value)}
          style={{ width: 125 }}
        />

        <button onClick={resetFilters}>重置</button>
        <div className="filter-actions" style={{ position: "relative" }}>
          <button onClick={() => setExportMenuOpen((v) => !v)}>导出 ▾</button>
          {exportMenuOpen && (
            <>
              {/* 透明遮罩：点击页面任意处关闭下拉 */}
              <div
                className="dropdown-overlay"
                onClick={() => setExportMenuOpen(false)}
              />
              <div
                className="context-menu"
                style={{ position: "absolute", top: "calc(100% + 4px)", right: 0 }}
              >
                <div
                  className="context-menu-item"
                  onClick={() => {
                    setExportMenuOpen(false);
                    void handleExportExcel();
                  }}
                >
                  导出Excel
                </div>
                <div
                  className="context-menu-item"
                  onClick={() => {
                    setExportMenuOpen(false);
                    void handleExportVouchers();
                  }}
                >
                  导出附件
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {loading ? (
        <div className="placeholder-card">
          <p className="hint">正在加载支出数据…</p>
        </div>
      ) : (
        <>
          {/* 支出列表 */}
          <div className="table-frame">
            <table className="data-table expense-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>
                    <input
                      type="checkbox"
                      checked={
                        filteredExpenses.length > 0 &&
                        selectedIds.size === filteredExpenses.length
                      }
                      onChange={toggleSelectAll}
                    />
                </th>
                <th className="sortable" onClick={() => toggleSort("category")}>
                  费用类别{sortIndicator("category")}
                </th>
                <th className="sortable" onClick={() => toggleSort("content")}>
                  开支内容{sortIndicator("content")}
                </th>
                <th className="sortable" onClick={() => toggleSort("specification")}>
                  规格型号{sortIndicator("specification")}
                </th>
                <th className="sortable" onClick={() => toggleSort("supplier")}>
                  供应商{sortIndicator("supplier")}
                </th>
                <th className="sortable" onClick={() => toggleSort("amount")}>
                  报账金额(元){sortIndicator("amount")}
                </th>
                <th className="sortable" onClick={() => toggleSort("date")}>
                  报账日期{sortIndicator("date")}
                </th>
                <th className="sortable" onClick={() => toggleSort("remarks")}>
                  备注{sortIndicator("remarks")}
                </th>
                <th>凭证附件</th>
              </tr>
            </thead>
            <tbody>
              {filteredExpenses.length === 0 && (
                <tr>
                  <td colSpan={9} className="hint" style={{ textAlign: "center", padding: 24 }}>
                    暂无支出记录
                  </td>
                </tr>
              )}
              {filteredExpenses.map((e) => (
                <tr key={e.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(e.id)}
                      onChange={() => toggleSelect(e.id)}
                    />
                  </td>
                  <td>{e.category}</td>
                  <td style={{ textAlign: "left" }}>{e.content}</td>
                  <td>{e.specification ?? ""}</td>
                  <td>{e.supplier ?? ""}</td>
                  <td className="num">{fmt(e.amount ?? 0)}</td>
                  <td>{e.date ?? ""}</td>
                  <td>{e.remarks ?? ""}</td>
                  <td className="voucher-cell">
                    {/* 行内附件按钮（对齐 Python create_attachment_button：有→attach 图标，无→add 图标） */}
                    <button
                      className={`voucher-btn${e.voucher_path ? " has" : ""}${
                        e.voucher_path && missingVouchers.has(e.voucher_path) ? " missing" : ""
                      }`}
                      title={
                        e.voucher_path
                          ? missingVouchers.has(e.voucher_path)
                            ? "附件文件缺失（点击查看处理）"
                            : "管理附件"
                          : "添加附件"
                      }
                      onClick={(ev) => {
                        if (voucherMenuFor === e.id) {
                          setVoucherMenuFor(null);
                          return;
                        }
                        // 表格有 overflow:hidden，菜单须相对视口 fixed 定位
                        const rect = ev.currentTarget.getBoundingClientRect();
                        setVoucherMenuPos({
                          left: rect.left + rect.width / 2,
                          top: rect.bottom,
                        });
                        setVoucherMenuFor(e.id);
                      }}
                    >
                      {e.voucher_path ? (
                        // 回形针图标（管理附件）
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                          <path
                            d="M11.5 4.5v6a3.5 3.5 0 0 1-7 0V4a2 2 0 0 1 4 0v6.5a.5.5 0 0 1-1 0V4.5"
                            stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
                          />
                        </svg>
                      ) : (
                        // 加号图标（添加附件）
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                          <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                      )}
                    </button>
                    {/* 弹出菜单（对齐 Python create_attachment_menu） */}
                    {voucherMenuFor === e.id && (
                      <>
                        <div
                          className="voucher-menu-backdrop"
                          onClick={() => setVoucherMenuFor(null)}
                        />
                        <div className="voucher-menu" style={voucherMenuPos ?? undefined}>
                          {e.voucher_path ? (
                            <>
                              <button onClick={() => handleVoucherAction(e, "view")}>查看</button>
                              <button onClick={() => handleVoucherAction(e, "download")}>下载</button>
                              <button onClick={() => handleVoucherAction(e, "replace")}>替换</button>
                              <button onClick={() => handleVoucherAction(e, "open_path")}>路径</button>
                              <div className="voucher-menu-divider" />
                              <button
                                className="danger"
                                onClick={() => handleVoucherAction(e, "delete")}
                              >
                                删除
                              </button>
                            </>
                          ) : (
                            <button onClick={() => handleVoucherAction(e, "upload")}>上传附件</button>
                          )}
                        </div>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          {/* 底部统计表 */}
          <table className="data-table expense-stats">
            <thead>
              <tr>
                <th style={{ width: 100 }}>分类统计</th>
                {BUDGET_CATEGORIES.map((c) => (
                  <th key={c}>{c}</th>
                ))}
                <th>合计</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>预算(万元)</td>
                {BUDGET_CATEGORIES.map((c) => (
                  <td key={c} className="num">
                    {fmt(stats.budgetByCat.get(c) ?? 0)}
                  </td>
                ))}
                <td className="num">{fmt(stats.totalBudgetWan)}</td>
              </tr>
              <tr>
                <td>支出(万元)</td>
                {BUDGET_CATEGORIES.map((c) => (
                  <td key={c} className="num">
                    {fmt(stats.spentByCat.get(c) ?? 0)}
                  </td>
                ))}
                <td className="num">{fmt(stats.totalSpentWan)}</td>
              </tr>
            </tbody>
          </table>
        </>
      )}

      {/* 删除确认 */}
      {confirmingDelete && (
        <div className="dialog-overlay">
          <div className="dialog-container" style={{ width: 400 }}>
            <div className="dialog-header">
              <h2>确认删除</h2>
              <button className="close-btn" onClick={() => setConfirmingDelete(false)}>
                &times;
              </button>
            </div>
            <div className="dialog-body">
              <p>确定要删除选中的 {selectedIds.size} 条支出记录吗？此操作不可恢复。</p>
            </div>
            <div className="dialog-footer">
              <button onClick={() => setConfirmingDelete(false)}>取消</button>
              <button className="primary-btn" onClick={confirmDelete}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 新增 / 编辑对话框 */}
      {dialogOpen && (
        <ExpenseFormDialog
          projectId={projectId}
          budgetId={budgetId}
          editingId={editingExpenseId}
          onSubmit={handleSubmitExpense}
          onBatchImport={() => setBatchImportOpen(true)}
          onClose={() => {
            setDialogOpen(false);
            setEditingExpenseId(undefined);
          }}
        />
      )}

      {/* 批量导入对话框 */}
      {batchImportOpen && (
        <BatchImportDialog
          projectId={projectId}
          budgetId={budgetId}
          onImported={handleBatchImported}
          onClose={() => setBatchImportOpen(false)}
        />
      )}
    </div>
  );
}
