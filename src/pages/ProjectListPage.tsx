// 项目清单页：调用 list_projects/add_project/update_project 命令，支持查看、新增和编辑

import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import ProjectFormDialog, { ProjectFormData } from "../components/ProjectFormDialog";
import { emitProjectUpdated } from "../data/events";

// 与 Rust core::models::Project 对齐
interface Project {
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
}

const COLUMNS: { key: keyof Project; label: string; align: "center" | "right" }[] = [
  { key: "financial_code", label: "财务编号", align: "center" },
  { key: "name", label: "项目名称", align: "center" },
  { key: "project_code", label: "项目编号", align: "center" },
  { key: "project_type", label: "项目类别", align: "center" },
  { key: "start_date", label: "开始日期", align: "center" },
  { key: "end_date", label: "结束日期", align: "center" },
  { key: "total_budget", label: "总经费(万元)", align: "right" },
  { key: "director", label: "负责人", align: "center" },
];

function renderCell(col: keyof Project, p: Project): string {
  const v = p[col];
  if (v === null || v === undefined || v === "") return "—";
  if (col === "total_budget") return Number(v).toFixed(2);
  return String(v);
}

export default function ProjectListPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 筛选工具栏（对齐项目成果页 apply_filters：关键词 + 类别 + 开始日期范围）
  const [keyword, setKeyword] = useState("");
  const [filterType, setFilterType] = useState<string>("全部类别");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  // 对话框状态
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  // 删除确认对话框状态
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // 选中项目 ID (用于编辑按钮)
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);

  // 右键菜单：复制单元格内容
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    text: string;
  } | null>(null);

  // 导入项目数据状态
  const [isImporting, setIsImporting] = useState(false);
  // 财务编号重复时待覆盖确认的文件路径
  const [importOverwriteFile, setImportOverwriteFile] = useState<string | null>(null);

  const fetchProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await invoke<Project[]>("list_projects");
      setProjects(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  // 点击任意处关闭右键菜单
  useEffect(() => {
    const close = () => setContextMenu(null);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  // 复制单元格内容到剪贴板（被右键单元格的文本）
  const copyCellContent = async (text: string) => {
    setContextMenu(null);
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // 降级复制（Tauri WebView 剪贴板权限异常时兜底）
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
  };

  // 导出项目数据：选项目 → 存 JSON → 写文件
  const handleExport = async () => {
    if (!selectedProjectId) {
      alert("请先选择要导出的项目");
      return;
    }
    const project = projects.find((p) => p.id === selectedProjectId);
    if (!project) return;

    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const ts = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(
      now.getDate()
    )}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
    const savePath = await save({
      defaultPath: `项目数据_${ts}.json`,
      filters: [{ name: "JSON", extensions: ["json"] }],
    });
    if (!savePath) return;

    try {
      await invoke("export_project_data", { projectId: project.id, path: savePath });
      alert(`项目数据已导出到：\n${savePath}`);
    } catch (e) {
      alert(`导出项目数据失败：${String(e)}`);
    }
  };

  // 导入项目数据：先 overwrite=false，财务编号重复则弹覆盖确认后以 overwrite=true 重试
  const runImport = async (path: string, overwrite: boolean) => {
    try {
      await invoke("import_project_data", { path, overwrite });
      await fetchProjects();
      emitProjectUpdated();
      alert("项目数据导入成功！");
    } catch (e) {
      const msg = String(e);
      if (!overwrite && msg.includes("DUPLICATE_FINANCIAL_CODE")) {
        setImportOverwriteFile(path);
        return;
      }
      alert(`导入项目数据失败：${msg}`);
    }
  };

  const handleImport = async () => {
    const file = await open({
      multiple: false,
      title: "导入项目数据",
      filters: [{ name: "JSON", extensions: ["json"] }],
    });
    if (typeof file !== "string") return;
    setIsImporting(true);
    try {
      await runImport(file, false);
    } finally {
      setIsImporting(false);
    }
  };

  // 确认覆盖：删除原项目后重新导入
  const confirmImportOverwrite = async () => {
    if (!importOverwriteFile) return;
    const path = importOverwriteFile;
    setImportOverwriteFile(null);
    setIsImporting(true);
    try {
      await runImport(path, true);
    } finally {
      setIsImporting(false);
    }
  };

  const handleAdd = () => {
    setEditingProject(null);
    setDialogOpen(true);
  };

  const handleEdit = () => {
    if (!selectedProjectId) {
      alert("请先选择一个项目");
      return;
    }
    const project = projects.find((p) => p.id === selectedProjectId);
    if (project) {
      setEditingProject(project);
      setDialogOpen(true);
    }
  };

  // 点击删除按钮：弹出确认对话框
  const handleDeleteClick = () => {
    if (!selectedProjectId) {
      alert("请先选择一个项目");
      return;
    }
    const project = projects.find((p) => p.id === selectedProjectId);
    if (project) {
      setDeleteTarget(project);
    }
  };

  // 确认删除：调用后端 delete_project 命令
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await invoke("delete_project", { id: deleteTarget.id });
      setDeleteTarget(null);
      setSelectedProjectId(null);
      await fetchProjects();
      emitProjectUpdated();
    } catch (e) {
      alert(`删除失败：${String(e)}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSubmit = async (data: ProjectFormData) => {
    // 转换 total_budget 为数字或 null
    const budget = data.total_budget ? parseFloat(data.total_budget) : null;

    // 构造后端需要的数据结构
    const backendData = {
      name: data.name,
      financial_code: data.financial_code || null,
      project_code: data.project_code || null,
      project_type: data.project_type || null,
      start_date: data.start_date || null,
      end_date: data.end_date || null,
      total_budget: isNaN(budget as number) ? null : budget,
      director: data.director || null,
    };

    if (editingProject) {
      // 编辑模式
      await invoke("update_project", {
        id: editingProject.id,
        data: backendData,
      });
    } else {
      // 新增模式
      await invoke("add_project", { data: backendData });
    }

    // 刷新列表
    await fetchProjects();
    emitProjectUpdated();
  };

  // 类别下拉选项：从现有数据动态去重（项目类别为自由输入，无固定常量）
  const projectTypes = useMemo(
    () =>
      Array.from(
        new Set(projects.map((p) => p.project_type).filter((t): t is string => !!t))
      ),
    [projects]
  );

  // 筛选结果（对齐项目成果页 apply_filters：
  // 关键词匹配名称/编号/负责人等，类别相等，开始日期落在 [startDate, endDate] 闭区间）
  const filteredProjects = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return projects.filter((p) => {
      if (filterType !== "全部类别" && p.project_type !== filterType) return false;
      if (kw) {
        const haystack = [
          p.name,
          p.financial_code,
          p.project_code,
          p.project_type,
          p.leader,
          p.director,
        ]
          .filter((v): v is string => v != null)
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(kw)) return false;
      }
      if (p.start_date) {
        if (startDate && p.start_date < startDate) return false;
        if (endDate && p.start_date > endDate) return false;
      }
      return true;
    });
  }, [projects, keyword, filterType, startDate, endDate]);

  const resetFilters = () => {
    setKeyword("");
    setFilterType("全部类别");
    setStartDate("");
    setEndDate("");
  };

  if (loading) {
    return <div className="placeholder-card"><p className="hint">正在加载项目数据…</p></div>;
  }
  if (error) {
    return (
      <div className="placeholder-card">
        <p className="hint" style={{ color: "#c62828" }}>加载项目失败：{error}</p>
      </div>
    );
  }

  return (
    <div className="project-list">
      <div className="list-toolbar">
        <div className="list-summary">共 {projects.length} 个项目</div>
        <div className="list-actions">
          <button onClick={handleAdd} className="primary-btn">新增项目</button>
          <button onClick={handleEdit} disabled={!selectedProjectId}>编辑项目</button>
          <button
            onClick={handleDeleteClick}
            disabled={!selectedProjectId}
            className="danger-btn"
          >
            删除项目
          </button>
        </div>
      </div>

      {/* 筛选工具栏（对齐项目成果页布局）：关键词 + 类别 + 开始日期范围 + 导入/导出 */}
      <div className="expense-filter">
        <label>关键词:</label>
        <input
          type="text"
          placeholder="按名称/财务编号/项目编号/负责人······"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 200 }}
        />
        <label>类别:</label>
        <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
          <option value="全部类别">全部类别</option>
          {projectTypes.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <label>开始日期:</label>
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
          <button onClick={handleImport} disabled={isImporting}>导入</button>
          <button onClick={handleExport} disabled={!selectedProjectId}>导出</button>
        </div>
      </div>

      {projects.length === 0 ? (
        <div className="placeholder-card">
          <p className="hint">暂无项目数据。点击"新增项目"创建第一个项目。</p>
        </div>
      ) : (
        <div className="table-frame">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "40px" }}>
                  {/* 选择列 */}
                </th>
                {COLUMNS.map((c) => (
                  <th key={c.key} style={{ textAlign: c.align }}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map((p) => (
                <tr
                  key={p.id}
                  className={selectedProjectId === p.id ? "selected-row" : ""}
                  onClick={() => setSelectedProjectId(p.id)}
                >
                  <td onClick={(e) => e.stopPropagation()}>
                    <input
                      type="radio"
                      name="project-select"
                      checked={selectedProjectId === p.id}
                      onChange={() => setSelectedProjectId(p.id)}
                    />
                  </td>
                  {COLUMNS.map((c) => (
                    <td
                      key={c.key}
                      style={{ textAlign: c.align }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setContextMenu({
                          x: e.clientX,
                          y: e.clientY,
                          text: renderCell(c.key, p),
                        });
                      }}
                    >
                      {renderCell(c.key, p)}
                    </td>
                  ))}
                </tr>
              ))}
              {filteredProjects.length === 0 && (
                <tr>
                  <td
                    colSpan={COLUMNS.length + 1}
                    style={{ textAlign: "center", color: "#888", padding: "24px 0" }}
                  >
                    无匹配项目
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 表单对话框 */}
      {dialogOpen && (
        <ProjectFormDialog
          title={editingProject ? "编辑项目" : "新增项目"}
          initialProject={editingProject}
          onSubmit={handleSubmit}
          onClose={() => setDialogOpen(false)}
        />
      )}

      {/* 覆盖确认对话框：财务编号重复的导入 */}
      {importOverwriteFile && (
        <div className="dialog-overlay">
          <div className="dialog-container" style={{ width: 420 }}>
            <div className="dialog-header">
              <h2>项目已存在</h2>
              <button
                className="close-btn"
                onClick={() => setImportOverwriteFile(null)}
              >
                &times;
              </button>
            </div>
            <div className="dialog-body">
              <p style={{ lineHeight: 1.8 }}>
                检测到相同财务编号的项目已存在，是否覆盖？
              </p>
              <p className="hint" style={{ marginTop: 8 }}>
                注意：覆盖将删除原有的所有预算和支出数据！
              </p>
            </div>
            <div className="dialog-footer">
              <button onClick={() => setImportOverwriteFile(null)}>取消</button>
              <button
                onClick={confirmImportOverwrite}
                disabled={isImporting}
                className="danger-btn"
              >
                {isImporting ? "导入中..." : "覆盖"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认对话框 */}
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
                确定要删除项目{" "}
                <strong>{deleteTarget.name || "（未命名）"}</strong>
                {deleteTarget.financial_code
                  ? `（财务编号 ${deleteTarget.financial_code}）`
                  : ""}
                吗？
              </p>
              <p className="hint" style={{ marginTop: 8 }}>
                此操作不可恢复，将级联删除该项目的预算、支出、甘特任务、文档、成果等所有关联数据，
                并清理其附件目录。
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
                onClick={confirmDelete}
                disabled={isDeleting}
                className="danger-btn"
              >
                {isDeleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 右键菜单：复制单元格内容 */}
      {contextMenu && (
        <div
          className="context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="context-menu-item"
            onClick={() => copyCellContent(contextMenu.text)}
          >
            复制
          </button>
        </div>
      )}
    </div>
  );
}
