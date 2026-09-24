// 项目成果页：9 列表格（成果名称/类型/状态/作者/完成人/投稿/申请日期/发表/授权日期/期刊/授权单位/描述/成果附件）
// + 关键词/类型/状态/发表-授权日期范围筛选
// + 新增/编辑/删除（OutcomeFormDialog）+ 附件 5 个操作（查看/路径/下载/替换/删除/上传）
// + Excel 导出（export_outcomes_excel）+ 附件打包导出（成果附件_{financial_code}）

import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { EMPTY_RANGE_START, todayStr } from "../dateDefaults";
import { open, save } from "@tauri-apps/plugin-dialog";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";
import OutcomeFormDialog, {
  type OutcomeFormData,
  OUTCOME_TYPES,
  OUTCOME_STATUSES,
} from "../components/OutcomeFormDialog";

// 与后端 core::models::ProjectOutcome 对齐
interface ProjectOutcome {
  id: number;
  project_id: number;
  name: string;
  type: string;
  status: string | null;
  authors: string | null;
  submit_date: string | null;
  publish_date: string | null;
  journal: string | null;
  description: string | null;
  remarks: string | null;
  attachment_path: string | null;
}

interface Project {
  id: number;
  name: string;
  financial_code: string | null;
}

// 与后端 core::attachments::AttachmentContext 对齐（生成成果附件路径用）
interface OutcomeAttachmentContext {
  financial_code: string | null;
  category: string | null;
  amount: number | null;
  date: string | null;
  base_folder: string | null;
}

export default function ProjectOutcomePage() {
  // 项目下拉（"" = 全部成果）
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectChoice, setProjectChoice] = useState<string>("");

  const [allOutcomes, setAllOutcomes] = useState<ProjectOutcome[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 附件文件缺失集合（DB 有路径但磁盘文件已被程序外删除）
  const [missingFiles, setMissingFiles] = useState<Set<string>>(new Set());

  // 工具栏对话框
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingOutcomeId, setEditingOutcomeId] = useState<number | undefined>(undefined);

  // 多选删除（批量删除用自绘确认框，避免 WKWebView 不支持的 window.confirm）
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // 附件删除确认
  const [confirmAttDelete, setConfirmAttDelete] = useState<ProjectOutcome | null>(null);

  // 行内附件菜单
  const [attachmentMenuFor, setAttachmentMenuFor] = useState<number | null>(null);
  const [attachmentMenuPos, setAttachmentMenuPos] = useState<{
    left: number;
    top: number;
  } | null>(null);

  // 过滤器
  const [keyword, setKeyword] = useState("");
  const [filterType, setFilterType] = useState<string>("全部类型");
  const [filterStatus, setFilterStatus] = useState<string>("全部状态");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // 默认日期范围：现有成果最早/最晚发表·授权日期（直接显示真实日期，
  // 规避 WebView2 空态占位符混排「yyyy/mm/日」，与项目清单页/支出管理页做法一致）
  const dateRange = useMemo(() => {
    let min = "";
    let max = "";
    for (const o of allOutcomes) {
      const d = o.publish_date;
      if (!d) continue;
      if (!min || d < min) min = d;
      if (!max || d > max) max = d;
    }
    return { min, max };
  }, [allOutcomes]);

  // 首次拿到数据时填充默认范围（用户手动清空后不再回填）
  const boundsInitRef = useRef(false);
  useEffect(() => {
    if (boundsInitRef.current) return;
    if (dateRange.min || dateRange.max) {
      boundsInitRef.current = true;
      setStartDate(dateRange.min);
      setEndDate(dateRange.max);
    } else if (!loading) {
      // 数据已加载且为空（或全无日期值）：兜底 2020-01-01 ～ 今天，框内仍显示真实日期
      boundsInitRef.current = true;
      setStartDate(EMPTY_RANGE_START);
      setEndDate(todayStr());
    }
  }, [dateRange, loading]);

  const selectedProject =
    projectChoice === "" ? null : (projects.find((p) => p.id === Number(projectChoice)) ?? null);

  // 加载项目列表
  useEffect(() => {
    invoke<Project[]>("list_projects")
      .then(setProjects)
      .catch((e) => setError(String(e)));
  }, []);

  // 加载成果（"" → 全部；否则按项目）
  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const projectId = projectChoice === "" ? null : Number(projectChoice);
      const outcomes = await invoke<ProjectOutcome[]>("list_project_outcomes", {
        projectId,
      });
      setAllOutcomes(outcomes);
      // 校验附件真实性（不影响列表加载）
      const paths = outcomes
        .map((o) => o.attachment_path)
        .filter((p): p is string => !!p);
      setMissingFiles(new Set());
      if (paths.length > 0) {
        try {
          const exists = await invoke<boolean[]>("check_attachments", { paths });
          const missing = new Set<string>();
          paths.forEach((p, i) => {
            if (!exists[i]) missing.add(p);
          });
          setMissingFiles(missing);
        } catch {
          // 校验失败不阻断列表加载
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectChoice]);

  // 本地筛选：keyword 匹配 name/authors/journal/description，
  // 类型/状态相等，发表/授权日期落在 [start_date, end_date] 闭区间
  const filteredOutcomes = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return allOutcomes.filter((o) => {
      if (filterType !== "全部类型" && o.type !== filterType) return false;
      if (filterStatus !== "全部状态" && o.status !== filterStatus) return false;
      if (kw) {
        const haystack = [o.name, o.authors ?? "", o.journal ?? "", o.description ?? ""]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(kw)) return false;
      }
      if (o.publish_date) {
        if (startDate && o.publish_date < startDate) return false;
        if (endDate && o.publish_date > endDate) return false;
      }
      return true;
    });
  }, [allOutcomes, keyword, filterType, filterStatus, startDate, endDate]);

  const resetFilters = () => {
    setKeyword("");
    setFilterType("全部类型");
    setFilterStatus("全部状态");
    // 重置回默认日期范围（等价于不过滤，同时始终显示真实日期）
    setStartDate(dateRange.min || EMPTY_RANGE_START);
    setEndDate(dateRange.max || todayStr());
  };

  // 行选择
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
      if (prev.size === filteredOutcomes.length) return new Set();
      return new Set(filteredOutcomes.map((o) => o.id));
    });
  };

  // 提交表单：分发新增 / 编辑（新增 attachment_path 为 null；编辑不改附件）
  const handleSubmitOutcome = async (data: OutcomeFormData, id?: number) => {
    if (!selectedProject) throw new Error("请先选择一个项目");
    const input = {
      project_id: selectedProject.id,
      name: data.name,
      type: data.type,
      status: data.status,
      authors: data.authors,
      submit_date: data.submit_date,
      publish_date: data.publish_date,
      journal: data.journal,
      description: data.description,
      attachment_path: null,
    };
    if (id !== undefined) {
      await invoke("update_outcome", { id, input });
    } else {
      await invoke("add_outcome", { input });
    }
    setSelectedIds(new Set());
    await refresh();
  };

  // 批量删除（后端负责删库 + 文件清理）
  const confirmDelete = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    try {
      await invoke("delete_outcomes", { ids });
      setSelectedIds(new Set());
      await refresh();
      setConfirmingDelete(false);
    } catch (e) {
      setError(String(e));
      setConfirmingDelete(false);
    }
  };

  // 导出 Excel（当前项目全部成果 / 全部模式导出全部）
  const handleExportExcel = async () => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(
      now.getHours()
    )}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
    const savePath = await save({
      defaultPath: `成果信息_${selectedProject?.financial_code ?? "全部"}_${ts}.xlsx`,
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
    });
    if (!savePath) return;
    try {
      await invoke("export_outcomes_excel", {
        savePath,
        projectId: selectedProject ? selectedProject.id : null,
      });
      alert(`导出成功：${savePath}`);
    } catch (e) {
      alert(`导出失败：${String(e)}`);
    }
  };

  // 导出附件：拷贝到 成果附件_{financial_code} 目录
  const handleExportAttachments = async () => {
    if (!selectedProject) {
      alert("请先选择一个项目（「全部成果」模式不支持导出附件）");
      return;
    }
    const withFile = filteredOutcomes.filter((o) => o.attachment_path);
    if (withFile.length === 0) {
      alert("当前筛选结果中没有带附件的成果");
      return;
    }
    const dir = await open({
      directory: true,
      title: "选择附件保存位置",
    });
    if (typeof dir !== "string") return;

    const projectDir = `${dir}/成果附件_${selectedProject.financial_code ?? "项目"}`;
    let count = 0;
    let skippedMissing = 0;
    try {
      for (const o of withFile) {
        const p = String(o.attachment_path);
        if (missingFiles.has(p)) {
          skippedMissing += 1; // 源文件已被程序外删除：跳过不中断
          continue;
        }
        const filename = p.split(/[\\/]/).pop() ?? "attachment";
        // 避免文件名冲突（base_1.ext 递增）
        let dest = `${projectDir}/${filename}`;
        let counter = 1;
        while (true) {
          try {
            await invoke("copy_attachment_file", { source: p, dest });
            break;
          } catch (err) {
            // 目标已存在会导致 copy 失败，改用带序号的文件名重试
            const dot = filename.lastIndexOf(".");
            const base = dot > 0 ? filename.slice(0, dot) : filename;
            const ext = dot > 0 ? filename.slice(dot) : "";
            dest = `${projectDir}/${base}_${counter}${ext}`;
            counter += 1;
            if (counter > 999) throw err;
          }
        }
        count += 1;
      }
      let msg = `导出完成，共 ${count} 个成果附件`;
      if (skippedMissing > 0) msg += `\n（${skippedMissing} 个附件文件缺失，已跳过）`;
      if (count > 0) msg += `\n保存位置：${projectDir}`;
      alert(msg);
    } catch (err) {
      alert(`导出附件失败：${String(err)}`);
    }
  };

  // 行内附件操作：查看/下载/路径/替换/删除/上传
  const handleAttachmentAction = async (outcome: ProjectOutcome, action: string) => {
    setAttachmentMenuFor(null);
    const path = outcome.attachment_path;

    // 只读操作前置检查：文件已被程序外删除时给出明确提示
    if (
      path &&
      missingFiles.has(path) &&
      (action === "view" || action === "download" || action === "open_path")
    ) {
      alert(
        "该成果附件文件已被删除（可能为程序外操作）。\n" +
          "可通过「替换」重新上传附件，或「删除」清理此附件记录。"
      );
      return;
    }

    // 查看：系统默认程序打开
    if (action === "view") {
      if (!path) return alert("附件不存在");
      try {
        await openPath(path);
      } catch (err) {
        alert(`无法打开附件：${String(err)}`);
      }
      return;
    }

    // 路径：在文件管理器中定位
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

    // 下载：另存为副本
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

    // 上传 / 替换：选源文件 → 拷到规则路径 → 写库 → 删旧文件（save_attachment 处理 old_path）
    if (action === "replace" || action === "upload") {
      const file = await open({
        multiple: false,
        title: "选择成果文件",
      });
      if (typeof file !== "string") return; // 用户取消
      // 用该成果所属项目的 financial_code + 成果类型中文 label 生成附件存储路径
      const owner = projects.find((p) => p.id === outcome.project_id) ?? selectedProject;
      const context: OutcomeAttachmentContext = {
        financial_code: owner?.financial_code ?? null,
        category: outcome.type,
        amount: null,
        date: null,
        base_folder: "outcomes",
      };
      try {
        const newPath = await invoke<string>("save_attachment", {
          kind: "default",
          sourceFile: file,
          context,
          oldPath: path,
        });
        await invoke("update_outcome_attachment_path", {
          id: outcome.id,
          attachmentPath: newPath,
        });
        await refresh();
      } catch (err) {
        alert(`更新成果附件失败：${String(err)}`);
      }
      return;
    }

    // 删除：删文件 + 数据库置空（自绘确认框，WKWebView 不支持 window.confirm）
    if (action === "delete") {
      if (!path) return alert("没有可删除的附件");
      setConfirmAttDelete(outcome);
    }
  };

  const executeAttachmentDelete = async () => {
    const outcome = confirmAttDelete;
    if (!outcome || !outcome.attachment_path) return;
    setConfirmAttDelete(null);
    try {
      await invoke("delete_attachment", { path: outcome.attachment_path });
      await invoke("update_outcome_attachment_path", {
        id: outcome.id,
        attachmentPath: null,
      });
      await refresh();
    } catch (err) {
      alert(`删除附件失败：${String(err)}`);
    }
  };

  return (
    <div className="expense-mgmt">
      <div className="expense-toolbar">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <label>项目成果 -</label>
          <select
            value={projectChoice}
            onChange={(e) => {
              setProjectChoice(e.target.value);
              setSelectedIds(new Set());
            }}
            style={{ minWidth: 240, padding: "4px 8px" }}
          >
            <option value="">全部成果</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.financial_code ? `${p.financial_code} ` : ""}
                {p.name}
              </option>
            ))}
          </select>
        </span>
        <h2 className="page-title">成果管理</h2>
        <div className="list-actions">
          <button
            className="primary-btn"
            onClick={() => {
              if (!selectedProject) {
                alert("请先选择一个项目，再添加成果");
                return;
              }
              setEditingOutcomeId(undefined);
              setDialogOpen(true);
            }}
          >
            添加成果
          </button>
          <button
            onClick={() => {
              if (!selectedProject) {
                alert("请先选择一个项目，再编辑成果");
                return;
              }
              if (selectedIds.size !== 1) {
                alert("请选中一行成果进行编辑");
                return;
              }
              setEditingOutcomeId(Array.from(selectedIds)[0]);
              setDialogOpen(true);
            }}
            disabled={selectedIds.size !== 1 || !selectedProject}
          >
            编辑成果
          </button>
          <button
            onClick={() => {
              if (!selectedProject) {
                alert("请先选择一个项目，再删除成果");
                return;
              }
              if (selectedIds.size === 0) {
                alert("请先勾选要删除的成果行");
                return;
              }
              setConfirmingDelete(true);
            }}
            disabled={selectedIds.size === 0 || !selectedProject}
            className="danger-btn"
          >
            删除成果
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

      {/* 筛选 + 导出 */}
      <div className="expense-filter">
        <label>关键词:</label>
        <input
          type="text"
          placeholder="按名称/作者/期刊······"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 150 }}
        />
        <label>类型:</label>
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
          <option value="全部类型">全部类型</option>
          {OUTCOME_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label>状态:</label>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="全部状态">全部状态</option>
          {OUTCOME_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label>发表/授权日期:</label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />
        <span>至</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />
        <button onClick={resetFilters}>重置筛选</button>
        <div className="filter-actions">
          <button onClick={handleExportExcel}>导出信息</button>
          <button onClick={handleExportAttachments}>导出附件</button>
        </div>
      </div>

      {loading ? (
        <div className="placeholder-card">
          <p className="hint">正在加载成果数据…</p>
        </div>
      ) : (
        <>
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>
                    <input
                      type="checkbox"
                      checked={
                        filteredOutcomes.length > 0 &&
                        selectedIds.size === filteredOutcomes.length
                      }
                      onChange={toggleSelectAll}
                    />
                </th>
                <th style={{ minWidth: 180 }}>成果名称</th>
                <th style={{ width: 70 }}>类型</th>
                <th style={{ width: 100 }}>状态</th>
                <th style={{ minWidth: 140 }}>作者/完成人</th>
                <th style={{ width: 110 }}>投稿/申请日期</th>
                <th style={{ width: 110 }}>发表/授权日期</th>
                <th style={{ minWidth: 130 }}>期刊/授权单位</th>
                <th>描述</th>
                <th style={{ width: 90 }}>成果附件</th>
              </tr>
            </thead>
            <tbody>
              {filteredOutcomes.length === 0 && (
                <tr>
                  <td colSpan={10} className="hint" style={{ textAlign: "center", padding: 24 }}>
                    暂无成果记录
                  </td>
                </tr>
              )}
              {filteredOutcomes.map((o) => (
                <tr key={o.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(o.id)}
                      onChange={() => toggleSelect(o.id)}
                    />
                  </td>
                  <td style={{ textAlign: "left" }}>{o.name}</td>
                  <td>{o.type}</td>
                  <td>{o.status ?? ""}</td>
                  <td>{o.authors ?? ""}</td>
                  <td>{o.submit_date ?? ""}</td>
                  <td>{o.publish_date ?? ""}</td>
                  <td>{o.journal ?? ""}</td>
                  <td>{o.description ?? ""}</td>
                  <td className="voucher-cell">
                    <button
                      className={`voucher-btn${o.attachment_path ? " has" : ""}${
                        o.attachment_path && missingFiles.has(o.attachment_path)
                          ? " missing"
                          : ""
                      }`}
                      title={
                        o.attachment_path
                          ? missingFiles.has(o.attachment_path)
                            ? "附件文件缺失（点击查看处理）"
                            : "管理附件"
                          : "添加附件"
                      }
                      onClick={(ev) => {
                        if (attachmentMenuFor === o.id) {
                          setAttachmentMenuFor(null);
                          return;
                        }
                        const rect = ev.currentTarget.getBoundingClientRect();
                        setAttachmentMenuPos({
                          left: rect.left + rect.width / 2,
                          top: rect.bottom,
                        });
                        setAttachmentMenuFor(o.id);
                      }}
                    >
                      {o.attachment_path ? (
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                          <path
                            d="M11.5 4.5v6a3.5 3.5 0 0 1-7 0V4a2 2 0 0 1 4 0v6.5a.5.5 0 0 1-1 0V4.5"
                            stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
                          />
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                          <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                      )}
                    </button>
                    {attachmentMenuFor === o.id && (
                      <>
                        <div
                          className="voucher-menu-backdrop"
                          onClick={() => setAttachmentMenuFor(null)}
                        />
                        <div className="voucher-menu" style={attachmentMenuPos ?? undefined}>
                          {o.attachment_path ? (
                            <>
                              <button onClick={() => handleAttachmentAction(o, "view")}>查看</button>
                              <button onClick={() => handleAttachmentAction(o, "open_path")}>路径</button>
                              <button onClick={() => handleAttachmentAction(o, "download")}>下载</button>
                              <button onClick={() => handleAttachmentAction(o, "replace")}>替换</button>
                              <div className="voucher-menu-divider" />
                              <button
                                className="danger"
                                onClick={() => handleAttachmentAction(o, "delete")}
                              >
                                删除
                              </button>
                            </>
                          ) : (
                            <button onClick={() => handleAttachmentAction(o, "upload")}>上传附件</button>
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
        </>
      )}

      {/* 批量删除确认（自绘对话框） */}
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
              <p>
                确定要删除选中的 {selectedIds.size} 条成果记录吗？相关附件也将被删除（如果存在）。此操作不可恢复。
              </p>
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

      {/* 附件删除确认 */}
      {confirmAttDelete && (
        <div className="dialog-overlay">
          <div className="dialog-container" style={{ width: 400 }}>
            <div className="dialog-header">
              <h2>确认删除附件</h2>
              <button className="close-btn" onClick={() => setConfirmAttDelete(null)}>
                &times;
              </button>
            </div>
            <div className="dialog-body">
              <p>确定要删除该成果的附件文件吗？此操作不可恢复。</p>
            </div>
            <div className="dialog-footer">
              <button onClick={() => setConfirmAttDelete(null)}>取消</button>
              <button className="primary-btn" onClick={executeAttachmentDelete}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 新增 / 编辑对话框 */}
      {dialogOpen && (
        <OutcomeFormDialog
          editingId={editingOutcomeId}
          onSubmit={handleSubmitOutcome}
          onClose={() => {
            setDialogOpen(false);
            setEditingOutcomeId(undefined);
          }}
        />
      )}
    </div>
  );
}