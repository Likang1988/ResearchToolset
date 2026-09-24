// 学术活动页：9 列表格（活动名称/类型/状态/主办方/开始日期/结束日期/活动地点/参与人员/活动附件）
// + 关键词(name/description/participants/location)/类型/状态/开始日期范围筛选
// + 新增/编辑/删除（ActivityFormDialog，对话框内可改附件）
// + 行内附件 5 个操作（查看/路径/下载/替换/删除，无附件时显示「上传附件」）
// + Excel 导出（export_activities_excel，9 列不含附件列）+ 附件打包导出（无子目录）
// 注意：academic_activities 为全局表（无 project_id），本页无项目下拉。

import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";
import ActivityFormDialog, {
  type ActivityFormData,
  type ActivityAttachmentState,
  ACTIVITY_TYPES,
  ACTIVITY_STATUSES,
} from "../components/ActivityFormDialog";

// 与后端 core::models::AcademicActivity 对齐
interface AcademicActivity {
  id: number;
  name: string;
  type: string;
  status: string | null;
  organizer: string | null;
  start_date: string | null;
  end_date: string | null;
  location: string | null;
  participants: string | null;
  description: string | null;
  attachment_path: string | null;
}

// 与后端 core::attachments::AttachmentContext 对齐（生成活动附件路径用：
// Activity 类型只取 category = 活动类型中文 label，目录为 {root}/activities/{类别}）
interface ActivityAttachmentContext {
  financial_code: string | null;
  category: string | null;
  amount: number | null;
  date: string | null;
  base_folder: string | null;
}

export default function ProjectActivityPage() {
  const [allActivities, setAllActivities] = useState<AcademicActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 附件文件缺失集合（DB 有路径但磁盘文件已被程序外删除）
  const [missingFiles, setMissingFiles] = useState<Set<string>>(new Set());

  // 工具栏对话框
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingActivityId, setEditingActivityId] = useState<number | undefined>(undefined);

  // 多选删除（批量删除用自绘确认框，避免 WKWebView 不支持的 window.confirm）
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // 附件删除确认
  const [confirmAttDelete, setConfirmAttDelete] = useState<AcademicActivity | null>(null);

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

  // 默认日期范围：现有活动最早/最晚开始日期（直接显示真实日期，
  // 规避 WebView2 空态占位符混排「yyyy/mm/日」，与项目清单页/支出管理页做法一致）
  const dateRange = useMemo(() => {
    let min = "";
    let max = "";
    for (const a of allActivities) {
      const d = a.start_date;
      if (!d) continue;
      if (!min || d < min) min = d;
      if (!max || d > max) max = d;
    }
    return { min, max };
  }, [allActivities]);

  // 首次拿到数据时填充默认范围（用户手动清空后不再回填）
  const boundsInitRef = useRef(false);
  useEffect(() => {
    if (boundsInitRef.current) return;
    if (!dateRange.min && !dateRange.max) return;
    boundsInitRef.current = true;
    setStartDate(dateRange.min);
    setEndDate(dateRange.max);
  }, [dateRange]);

  // 加载活动列表
  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const activities = await invoke<AcademicActivity[]>("list_activities");
      setAllActivities(activities);
      // 校验附件真实性（不影响列表加载）
      const paths = activities
        .map((a) => a.attachment_path)
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
  }, []);

  // 本地筛选：keyword 匹配 name/description/participants/location，
  // 类型/状态相等，start_date 落在 [start, end] 闭区间——无 start_date 的记录不满足日期条件被筛除
  const filteredActivities = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return allActivities.filter((a) => {
      if (filterType !== "全部类型" && a.type !== filterType) return false;
      if (filterStatus !== "全部状态" && a.status !== filterStatus) return false;
      if (kw) {
        const haystack = [a.name, a.description ?? "", a.participants ?? "", a.location ?? ""]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(kw)) return false;
      }
      if (!a.start_date) return false;
      if (startDate && a.start_date < startDate) return false;
      if (endDate && a.start_date > endDate) return false;
      return true;
    });
  }, [allActivities, keyword, filterType, filterStatus, startDate, endDate]);

  const resetFilters = () => {
    setKeyword("");
    setFilterType("全部类型");
    setFilterStatus("全部状态");
    // 重置回默认日期范围（同时始终显示真实日期）
    setStartDate(dateRange.min);
    setEndDate(dateRange.max);
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
      if (prev.size === filteredActivities.length) return new Set();
      return new Set(filteredActivities.map((a) => a.id));
    });
  };

  // 提交表单：先按附件状态处理文件（新增/替换/删除），再入库
  const applyAttachment = async (
    att: ActivityAttachmentState,
    typeLabel: string
  ): Promise<string | null> => {
    if (att.action === "none") return att.oldPath; // 编辑未改动 → 保留原路径；新增 → null
    if (att.action === "delete") {
      if (att.oldPath) await invoke("delete_attachment", { path: att.oldPath });
      return null;
    }
    // add / replace：拷到 {root}/activities/{类型}/（save_attachment 在 replace 时删除旧文件）
    const context: ActivityAttachmentContext = {
      financial_code: null,
      category: typeLabel,
      amount: null,
      date: null,
      base_folder: null,
    };
    return invoke<string>("save_attachment", {
      kind: "activity",
      sourceFile: att.newFile,
      context,
      oldPath: att.action === "replace" ? att.oldPath : null,
    });
  };

  const handleSubmitActivity = async (data: ActivityFormData, id?: number) => {
    const attachmentPath = await applyAttachment(data.attachment, data.type);
    const input = {
      name: data.name,
      type: data.type,
      status: data.status,
      organizer: data.organizer,
      start_date: data.start_date,
      end_date: data.end_date,
      location: data.location,
      participants: data.participants,
      description: data.description,
      attachment_path: attachmentPath,
    };
    if (id !== undefined) {
      await invoke("update_activity", { id, input });
    } else {
      await invoke("add_activity", { input });
    }
    setSelectedIds(new Set());
    await refresh();
  };

  // 批量删除（后端负责删库 + 文件清理）
  const confirmDelete = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    try {
      await invoke("delete_activities", { ids });
      setSelectedIds(new Set());
      await refresh();
      setConfirmingDelete(false);
    } catch (e) {
      setError(String(e));
      setConfirmingDelete(false);
    }
  };

  // 导出 Excel：9 列数据，不含附件列
  const handleExportExcel = async () => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(
      now.getHours()
    )}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
    const savePath = await save({
      defaultPath: `活动信息_${ts}.xlsx`,
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
    });
    if (!savePath) return;
    try {
      await invoke("export_activities_excel", { savePath });
      alert(`导出成功：${savePath}`);
    } catch (e) {
      alert(`导出失败：${String(e)}`);
    }
  };

  // 导出附件：直接拷入所选目录，无子目录；
  // 目标已存在时文件名加 {name}_{时间戳}{ext}
  const handleExportAttachments = async () => {
    const withFile = filteredActivities.filter((a) => a.attachment_path);
    if (withFile.length === 0) {
      alert("当前筛选结果中没有带附件的活动");
      return;
    }
    const dir = await open({
      directory: true,
      title: "选择附件保存位置",
    });
    if (typeof dir !== "string") return;

    let count = 0;
    let skippedMissing = 0;
    try {
      for (const a of withFile) {
        const p = String(a.attachment_path);
        if (missingFiles.has(p)) {
          skippedMissing += 1; // 源文件已被程序外删除：跳过不中断
          continue;
        }
        const filename = p.split(/[\\/]/).pop() ?? "attachment";
        const dot = filename.lastIndexOf(".");
        const base = dot > 0 ? filename.slice(0, dot) : filename;
        const ext = dot > 0 ? filename.slice(dot) : "";
        // 目标已存在（copy 失败）→ 用时间戳后缀重试，仍冲突再递增序号
        const attempts = [filename, `${base}_${Date.now()}${ext}`];
        let dest = `${dir}/${attempts[0]}`;
        let ok = false;
        for (let i = 0; i < attempts.length; i++) {
          try {
            await invoke("copy_attachment_file", { source: p, dest });
            ok = true;
            break;
          } catch {
            dest = `${dir}/${attempts[i + 1] ?? `${base}_${i + 2}${ext}`}`;
          }
        }
        if (!ok) throw new Error(`无法复制附件 ${filename}`);
        count += 1;
      }
      let msg = `导出完成，共 ${count} 个活动附件`;
      if (skippedMissing > 0) msg += `\n（${skippedMissing} 个附件文件缺失，已跳过）`;
      if (count > 0) msg += `\n保存位置：${dir}`;
      alert(msg);
    } catch (err) {
      alert(`导出附件失败：${String(err)}`);
    }
  };

  // 行内附件操作：查看/下载/路径/替换/删除/上传
  const handleAttachmentAction = async (activity: AcademicActivity, action: string) => {
    setAttachmentMenuFor(null);
    const path = activity.attachment_path;

    // 只读操作前置检查：文件已被程序外删除时给出明确提示
    if (
      path &&
      missingFiles.has(path) &&
      (action === "view" || action === "download" || action === "open_path")
    ) {
      alert(
        "该活动附件文件已被删除（可能为程序外操作）。\n" +
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

    // 上传 / 替换：选源文件 → 拷到规则路径（{root}/activities/{类型}/）→ 写库 → 删旧文件
    if (action === "replace" || action === "upload") {
      const file = await open({
        multiple: false,
        title: "选择活动附件文件",
      });
      if (typeof file !== "string") return; // 用户取消
      const context: ActivityAttachmentContext = {
        financial_code: null,
        category: activity.type,
        amount: null,
        date: null,
        base_folder: null,
      };
      try {
        const newPath = await invoke<string>("save_attachment", {
          kind: "activity",
          sourceFile: file,
          context,
          oldPath: path,
        });
        // 写库：换新路径 / 置空路径
        await invoke("update_activity", {
          id: activity.id,
          input: {
            name: activity.name,
            type: activity.type,
            status: activity.status,
            organizer: activity.organizer,
            start_date: activity.start_date,
            end_date: activity.end_date,
            location: activity.location,
            participants: activity.participants,
            description: activity.description,
            attachment_path: newPath,
          },
        });
        await refresh();
      } catch (err) {
        alert(`更新活动附件失败：${String(err)}`);
      }
      return;
    }

    // 删除：删文件 + 数据库置空（自绘确认框，WKWebView 不支持 window.confirm）
    if (action === "delete") {
      if (!path) return alert("没有可删除的附件");
      setConfirmAttDelete(activity);
    }
  };

  const executeAttachmentDelete = async () => {
    const activity = confirmAttDelete;
    if (!activity || !activity.attachment_path) return;
    setConfirmAttDelete(null);
    try {
      await invoke("delete_attachment", { path: activity.attachment_path });
      await invoke("update_activity", {
        id: activity.id,
        input: {
          name: activity.name,
          type: activity.type,
          status: activity.status,
          organizer: activity.organizer,
          start_date: activity.start_date,
          end_date: activity.end_date,
          location: activity.location,
          participants: activity.participants,
          description: activity.description,
          attachment_path: null,
        },
      });
      await refresh();
    } catch (err) {
      alert(`删除附件失败：${String(err)}`);
    }
  };

  return (
    <div className="expense-mgmt">
      <div className="expense-toolbar">
        <h2 className="page-title">活动管理</h2>
        <div className="list-actions">
          <button
            className="primary-btn"
            onClick={() => {
              setEditingActivityId(undefined);
              setDialogOpen(true);
            }}
          >
            添加活动
          </button>
          <button
            onClick={() => {
              if (selectedIds.size !== 1) {
                alert("请选中一行活动进行编辑");
                return;
              }
              setEditingActivityId(Array.from(selectedIds)[0]);
              setDialogOpen(true);
            }}
            disabled={selectedIds.size !== 1}
          >
            编辑活动
          </button>
          <button
            onClick={() => {
              if (selectedIds.size === 0) {
                alert("请先勾选要删除的活动行");
                return;
              }
              setConfirmingDelete(true);
            }}
            disabled={selectedIds.size === 0}
            className="danger-btn"
          >
            删除活动
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
          placeholder="按名称/描述/参与人员/地点搜索"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 200 }}
        />
        <label>类型:</label>
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
          <option value="全部类型">全部类型</option>
          {ACTIVITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label>状态:</label>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="全部状态">全部状态</option>
          {ACTIVITY_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label>活动日期:</label>
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
          <button onClick={handleExportAttachments}>导出材料</button>
        </div>
      </div>

      {loading ? (
        <div className="placeholder-card">
          <p className="hint">正在加载活动数据…</p>
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
                        filteredActivities.length > 0 &&
                        selectedIds.size === filteredActivities.length
                      }
                      onChange={toggleSelectAll}
                    />
                </th>
                <th style={{ minWidth: 180 }}>活动名称</th>
                <th style={{ width: 80 }}>类型</th>
                <th style={{ width: 80 }}>状态</th>
                <th style={{ minWidth: 140 }}>主办方</th>
                <th style={{ width: 110 }}>开始日期</th>
                <th style={{ width: 110 }}>结束日期</th>
                <th style={{ minWidth: 130 }}>活动地点</th>
                <th>参与人员</th>
                <th style={{ width: 90 }}>活动附件</th>
              </tr>
            </thead>
            <tbody>
              {filteredActivities.length === 0 && (
                <tr>
                  <td colSpan={10} className="hint" style={{ textAlign: "center", padding: 24 }}>
                    暂无活动记录
                  </td>
                </tr>
              )}
              {filteredActivities.map((a) => (
                <tr key={a.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(a.id)}
                      onChange={() => toggleSelect(a.id)}
                    />
                  </td>
                  <td style={{ textAlign: "left" }}>{a.name}</td>
                  <td>{a.type}</td>
                  <td>{a.status ?? ""}</td>
                  <td>{a.organizer ?? ""}</td>
                  <td>{a.start_date ?? ""}</td>
                  <td>{a.end_date ?? ""}</td>
                  <td>{a.location ?? ""}</td>
                  <td>{a.participants ?? ""}</td>
                  <td className="voucher-cell">
                    <button
                      className={`voucher-btn${a.attachment_path ? " has" : ""}${
                        a.attachment_path && missingFiles.has(a.attachment_path)
                          ? " missing"
                          : ""
                      }`}
                      title={
                        a.attachment_path
                          ? missingFiles.has(a.attachment_path)
                            ? "附件文件缺失（点击查看处理）"
                            : "管理附件"
                          : "添加附件"
                      }
                      onClick={(ev) => {
                        if (attachmentMenuFor === a.id) {
                          setAttachmentMenuFor(null);
                          return;
                        }
                        const rect = ev.currentTarget.getBoundingClientRect();
                        setAttachmentMenuPos({
                          left: rect.left + rect.width / 2,
                          top: rect.bottom,
                        });
                        setAttachmentMenuFor(a.id);
                      }}
                    >
                      {a.attachment_path ? (
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
                    {attachmentMenuFor === a.id && (
                      <>
                        <div
                          className="voucher-menu-backdrop"
                          onClick={() => setAttachmentMenuFor(null)}
                        />
                        <div className="voucher-menu" style={attachmentMenuPos ?? undefined}>
                          {a.attachment_path ? (
                            <>
                              <button onClick={() => handleAttachmentAction(a, "view")}>查看</button>
                              <button onClick={() => handleAttachmentAction(a, "open_path")}>路径</button>
                              <button onClick={() => handleAttachmentAction(a, "download")}>下载</button>
                              <button onClick={() => handleAttachmentAction(a, "replace")}>替换</button>
                              <div className="voucher-menu-divider" />
                              <button
                                className="danger"
                                onClick={() => handleAttachmentAction(a, "delete")}
                              >
                                删除
                              </button>
                            </>
                          ) : (
                            <button onClick={() => handleAttachmentAction(a, "upload")}>上传附件</button>
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
                确定要删除选中的 {selectedIds.size} 条活动记录吗？相关附件也将被删除（如果存在）。此操作不可恢复。
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
              <p>确定要删除该活动的附件文件吗？此操作不可恢复。</p>
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
        <ActivityFormDialog
          editingId={editingActivityId}
          onSubmit={handleSubmitActivity}
          onClose={() => {
            setDialogOpen(false);
            setEditingActivityId(undefined);
          }}
        />
      )}
    </div>
  );
}