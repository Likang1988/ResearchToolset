// 项目文档页：对应 Python app/views/projecting_interface/project_document.py
// 7 列表格（文档名称/类型/版本/关键词/上传时间/描述/文档附件）+ 关键词/类型筛选
// + 新增/编辑/删除（DocumentFormDialog）+ 附件 5 个操作（查看/下载/替换/路径/删除）
// + Excel 导出（export_documents_excel）+ 附件打包导出

import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";
import DocumentFormDialog, {
  type DocumentFormData,
  DOCUMENT_TYPES,
} from "../components/DocumentFormDialog";

// 与后端 core::models::ProjectDocument 对齐
interface ProjectDocument {
  id: number;
  project_id: number;
  name: string;
  doc_type: string;
  version: string | null;
  description: string | null;
  file_path: string | null;
  upload_time: string | null;
  keywords: string | null;
}

interface Project {
  id: number;
  name: string;
  financial_code: string | null;
}

// 与后端 core::attachments::AttachmentContext 对齐（生成文档附件路径用）
interface DocAttachmentContext {
  financial_code: string | null;
  category: string | null;
  amount: number | null;
  date: string | null;
  base_folder: string | null;
}

// Python 表头："文档名称/类型/版本/关键词/上传时间/描述/文档附件"
const UPLOAD_TIME_LEN = 16; // "YYYY-MM-DD HH:MM"（对齐 Python strftime("%Y-%m-%d %H:%M")）

export default function ProjectDocumentPage() {
  // 项目下拉（"" = 全部文档，对齐 Python "全部文档" 选项）
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectChoice, setProjectChoice] = useState<string>("");

  const [allDocs, setAllDocs] = useState<ProjectDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 附件文件缺失集合（DB 有路径但磁盘文件已被程序外删除）
  const [missingFiles, setMissingFiles] = useState<Set<string>>(new Set());

  // 工具栏对话框
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingDocId, setEditingDocId] = useState<number | undefined>(undefined);

  // 多选删除（批量删除用自绘确认框，避免 WKWebView 不支持的 window.confirm）
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // 附件删除确认
  const [confirmAttDelete, setConfirmAttDelete] = useState<ProjectDocument | null>(null);

  // 行内附件菜单
  const [attachmentMenuFor, setAttachmentMenuFor] = useState<number | null>(null);
  const [attachmentMenuPos, setAttachmentMenuPos] = useState<{
    left: number;
    top: number;
  } | null>(null);

  // 过滤器
  const [keyword, setKeyword] = useState("");
  const [filterType, setFilterType] = useState<string>("全部类型");

  const selectedProject =
    projectChoice === "" ? null : (projects.find((p) => p.id === Number(projectChoice)) ?? null);

  // 加载项目列表
  useEffect(() => {
    invoke<Project[]>("list_projects")
      .then(setProjects)
      .catch((e) => setError(String(e)));
  }, []);

  // 加载文档（"" → 全部；否则按项目）
  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const projectId = projectChoice === "" ? null : Number(projectChoice);
      const docs = await invoke<ProjectDocument[]>("list_project_documents", {
        projectId,
      });
      setAllDocs(docs);
      // 校验附件真实性（不影响列表加载）
      const paths = docs
        .map((d) => d.file_path)
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

  // 本地筛选（对齐 Python apply_filters：keyword 匹配 name/description/keywords，doc_type 相等）
  const filteredDocs = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return allDocs.filter((d) => {
      if (filterType !== "全部类型" && d.doc_type !== filterType) return false;
      if (kw) {
        const haystack = [d.name, d.description ?? "", d.keywords ?? ""]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(kw)) return false;
      }
      return true;
    });
  }, [allDocs, keyword, filterType]);

  const resetFilters = () => {
    setKeyword("");
    setFilterType("全部类型");
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
      if (prev.size === filteredDocs.length) return new Set();
      return new Set(filteredDocs.map((d) => d.id));
    });
  };

  // 新增文档：拷贝源文件到规则路径 → add_document（对齐 Python add_document）
  const addDocument = async (data: DocumentFormData) => {
    if (!selectedProject) throw new Error("请先选择一个项目");
    if (!data.file_path) throw new Error("请选择要上传的文件");
    const context: DocAttachmentContext = {
      financial_code: selectedProject.financial_code,
      category: data.doc_type,
      amount: null,
      date: null,
      base_folder: "documents",
    };
    const newPath = await invoke<string>("save_attachment", {
      kind: "default",
      sourceFile: data.file_path,
      context,
      oldPath: null,
    });
    await invoke("add_document", {
      input: {
        project_id: selectedProject.id,
        name: data.name,
        doc_type: data.doc_type,
        version: data.version,
        description: data.description,
        keywords: data.keywords,
        file_path: newPath,
      },
    });
  };

  // 提交表单：分发新增 / 编辑（编辑不改附件路径，后端忽略 file_path）
  const handleSubmitDocument = async (data: DocumentFormData, id?: number) => {
    if (id !== undefined) {
      if (!selectedProject) throw new Error("请先选择一个项目");
      await invoke("update_document", {
        id,
        input: {
          project_id: selectedProject.id,
          name: data.name,
          doc_type: data.doc_type,
          version: data.version,
          description: data.description,
          keywords: data.keywords,
          file_path: null,
        },
      });
    } else {
      await addDocument(data);
    }
    setSelectedIds(new Set());
    await refresh();
  };

  // 批量删除（后端负责删库 + 文件清理）
  const confirmDelete = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    try {
      await invoke("delete_documents", { ids });
      setSelectedIds(new Set());
      await refresh();
      setConfirmingDelete(false);
    } catch (e) {
      setError(String(e));
      setConfirmingDelete(false);
    }
  };

  // 导出 Excel（当前项目全部文档 / 全部模式导出全部）
  const handleExportExcel = async () => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(
      now.getHours()
    )}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
    const savePath = await save({
      defaultPath: `文档信息_${selectedProject?.financial_code ?? "全部"}_${ts}.xlsx`,
      filters: [{ name: "Excel", extensions: ["xlsx"] }],
    });
    if (!savePath) return;
    try {
      await invoke("export_documents_excel", {
        savePath,
        projectId: selectedProject ? selectedProject.id : null,
      });
      alert(`导出成功：${savePath}`);
    } catch (e) {
      alert(`导出失败：${String(e)}`);
    }
  };

  // 导出附件（对齐 Python export_document_attachments：拷贝到 文档附件_{financial_code} 目录）
  const handleExportAttachments = async () => {
    if (!selectedProject) {
      alert("请先选择一个项目（「全部文档」模式不支持导出附件）");
      return;
    }
    const withFile = filteredDocs.filter((d) => d.file_path);
    if (withFile.length === 0) {
      alert("当前筛选结果中没有带附件的文档");
      return;
    }
    const dir = await open({
      directory: true,
      title: "选择附件保存位置",
    });
    if (typeof dir !== "string") return;

    const projectDir = `${dir}/文档附件_${selectedProject.financial_code ?? "项目"}`;
    let count = 0;
    let skippedMissing = 0;
    try {
      for (const d of withFile) {
        const p = String(d.file_path);
        if (missingFiles.has(p)) {
          skippedMissing += 1; // 源文件已被程序外删除：跳过不中断
          continue;
        }
        const filename = p.split(/[\\/]/).pop() ?? "attachment";
        // 避免文件名冲突（对齐 Python：base_1.ext 递增）
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
      let msg = `导出完成，共 ${count} 个文档附件`;
      if (skippedMissing > 0) msg += `\n（${skippedMissing} 个附件文件缺失，已跳过）`;
      if (count > 0) msg += `\n保存位置：${projectDir}`;
      alert(msg);
    } catch (err) {
      alert(`导出附件失败：${String(err)}`);
    }
  };

  // 行内附件操作（对齐 Python attachment_utils 菜单动作：查看/下载/路径/替换/删除/上传）
  const handleAttachmentAction = async (doc: ProjectDocument, action: string) => {
    setAttachmentMenuFor(null);
    const path = doc.file_path;

    // 只读操作前置检查：文件已被程序外删除时给出明确提示
    if (
      path &&
      missingFiles.has(path) &&
      (action === "view" || action === "download" || action === "open_path")
    ) {
      alert(
        "该文档附件文件已被删除（可能为程序外操作）。\n" +
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
        title: "选择文档文件",
      });
      if (typeof file !== "string") return; // 用户取消
      // 用该文档所属项目的 financial_code 生成路径（对齐 generate_attachment_path context）
      const owner = projects.find((p) => p.id === doc.project_id) ?? selectedProject;
      const context: DocAttachmentContext = {
        financial_code: owner?.financial_code ?? null,
        category: doc.doc_type,
        amount: null,
        date: null,
        base_folder: "documents",
      };
      try {
        const newPath = await invoke<string>("save_attachment", {
          kind: "default",
          sourceFile: file,
          context,
          oldPath: path,
        });
        await invoke("update_document_file_path", {
          id: doc.id,
          filePath: newPath,
        });
        await refresh();
      } catch (err) {
        alert(`更新文档附件失败：${String(err)}`);
      }
      return;
    }

    // 删除：删文件 + 数据库置空（自绘确认框，WKWebView 不支持 window.confirm）
    if (action === "delete") {
      if (!path) return alert("没有可删除的附件");
      setConfirmAttDelete(doc);
    }
  };

  const executeAttachmentDelete = async () => {
    const doc = confirmAttDelete;
    if (!doc || !doc.file_path) return;
    setConfirmAttDelete(null);
    try {
      await invoke("delete_attachment", { path: doc.file_path });
      await invoke("update_document_file_path", { id: doc.id, filePath: null });
      await refresh();
    } catch (err) {
      alert(`删除附件失败：${String(err)}`);
    }
  };

  // 上传时间显示：截断到分钟（对齐 Python strftime("%Y-%m-%d %H:%M")）
  const fmtUploadTime = (t: string | null) =>
    t ? t.slice(0, UPLOAD_TIME_LEN) : "";

  return (
    <div className="expense-mgmt">
      <div className="expense-toolbar">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <label>项目文档 -</label>
          <select
            value={projectChoice}
            onChange={(e) => {
              setProjectChoice(e.target.value);
              setSelectedIds(new Set());
            }}
            style={{ minWidth: 240, padding: "4px 8px" }}
          >
            <option value="">全部文档</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.financial_code ? `${p.financial_code} ` : ""}
                {p.name}
              </option>
            ))}
          </select>
        </span>
        <h2 className="page-title">文档管理</h2>
        <div className="list-actions">
          <button
            className="primary-btn"
            onClick={() => {
              if (!selectedProject) {
                alert("请先选择一个项目，再添加文档");
                return;
              }
              setEditingDocId(undefined);
              setDialogOpen(true);
            }}
          >
            添加文档
          </button>
          <button
            onClick={() => {
              if (!selectedProject) {
                alert("请先选择一个项目，再编辑文档");
                return;
              }
              if (selectedIds.size !== 1) {
                alert("请选中一行文档进行编辑");
                return;
              }
              setEditingDocId(Array.from(selectedIds)[0]);
              setDialogOpen(true);
            }}
            disabled={selectedIds.size !== 1 || !selectedProject}
          >
            编辑文档
          </button>
          <button
            onClick={() => {
              if (!selectedProject) {
                alert("请先选择一个项目，再删除文档");
                return;
              }
              if (selectedIds.size === 0) {
                alert("请先勾选要删除的文档行");
                return;
              }
              setConfirmingDelete(true);
            }}
            disabled={selectedIds.size === 0 || !selectedProject}
            className="danger-btn"
          >
            删除文档
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

      {/* 筛选 + 导出（对齐 Python 搜索栏布局） */}
      <div className="expense-filter">
        <label>关键词:</label>
        <input
          type="text"
          placeholder="按名称/描述/关键词搜索"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 200 }}
        />
        <label>类型:</label>
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
          <option value="全部类型">全部类型</option>
          {DOCUMENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button onClick={resetFilters}>重置筛选</button>
        <div className="filter-actions">
          <button onClick={handleExportExcel}>导出信息</button>
          <button onClick={handleExportAttachments}>导出附件</button>
        </div>
      </div>

      {loading ? (
        <div className="placeholder-card">
          <p className="hint">正在加载文档数据…</p>
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
                      checked={filteredDocs.length > 0 && selectedIds.size === filteredDocs.length}
                      onChange={toggleSelectAll}
                    />
                </th>
                <th style={{ minWidth: 200 }}>文档名称</th>
                <th style={{ width: 90 }}>类型</th>
                <th style={{ width: 70 }}>版本</th>
                <th style={{ minWidth: 140 }}>关键词</th>
                <th style={{ width: 140 }}>上传时间</th>
                <th>描述</th>
                <th style={{ width: 90 }}>文档附件</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.length === 0 && (
                <tr>
                  <td colSpan={8} className="hint" style={{ textAlign: "center", padding: 24 }}>
                    暂无文档记录
                  </td>
                </tr>
              )}
              {filteredDocs.map((d) => (
                <tr key={d.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(d.id)}
                      onChange={() => toggleSelect(d.id)}
                    />
                  </td>
                  <td style={{ textAlign: "left" }}>{d.name}</td>
                  <td>{d.doc_type}</td>
                  <td>{d.version ?? ""}</td>
                  <td>{d.keywords ?? ""}</td>
                  <td>{fmtUploadTime(d.upload_time)}</td>
                  <td>{d.description ?? ""}</td>
                  <td className="voucher-cell">
                    <button
                      className={`voucher-btn${d.file_path ? " has" : ""}${
                        d.file_path && missingFiles.has(d.file_path) ? " missing" : ""
                      }`}
                      title={
                        d.file_path
                          ? missingFiles.has(d.file_path)
                            ? "附件文件缺失（点击查看处理）"
                            : "管理附件"
                          : "添加附件"
                      }
                      onClick={(ev) => {
                        if (attachmentMenuFor === d.id) {
                          setAttachmentMenuFor(null);
                          return;
                        }
                        const rect = ev.currentTarget.getBoundingClientRect();
                        setAttachmentMenuPos({
                          left: rect.left + rect.width / 2,
                          top: rect.bottom,
                        });
                        setAttachmentMenuFor(d.id);
                      }}
                    >
                      {d.file_path ? (
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
                    {attachmentMenuFor === d.id && (
                      <>
                        <div
                          className="voucher-menu-backdrop"
                          onClick={() => setAttachmentMenuFor(null)}
                        />
                        <div className="voucher-menu" style={attachmentMenuPos ?? undefined}>
                          {d.file_path ? (
                            <>
                              <button onClick={() => handleAttachmentAction(d, "view")}>查看</button>
                              <button onClick={() => handleAttachmentAction(d, "open_path")}>路径</button>
                              <button onClick={() => handleAttachmentAction(d, "download")}>下载</button>
                              <button onClick={() => handleAttachmentAction(d, "replace")}>替换</button>
                              <div className="voucher-menu-divider" />
                              <button
                                className="danger"
                                onClick={() => handleAttachmentAction(d, "delete")}
                              >
                                删除
                              </button>
                            </>
                          ) : (
                            <button onClick={() => handleAttachmentAction(d, "upload")}>上传附件</button>
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
                确定要删除选中的 {selectedIds.size} 条文档记录吗？相关文件也将被删除。此操作不可恢复。
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
              <p>确定要删除该文档的附件文件吗？此操作不可恢复。</p>
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
        <DocumentFormDialog
          editingId={editingDocId}
          onSubmit={handleSubmitDocument}
          onClose={() => {
            setDialogOpen(false);
            setEditingDocId(undefined);
          }}
        />
      )}
    </div>
  );
}