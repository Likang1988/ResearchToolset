// 项目进度页：jQueryGantt 甘特图（复用 Python 版静态资源）
// 桥接方式：iframe 加载 /gantt/gantt-tauri.html（postMessage 协议），
// 本组件负责调用后端 load_gantt_data / save_gantt_data 命令。
import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import { readTextFile } from "@tauri-apps/plugin-fs";
import { emitProjectUpdated, emitProgressUpdated } from "../data/events";

interface Project {
  id: number;
  name: string;
}

// 与 Rust core::services::gantt::GanttProjectData 对齐（load/save 同构）
// 后端输出 camelCase（与 jQueryGantt 前端字段一致），如 canWrite/selectedRow
interface GanttProjectData {
  tasks: unknown[];
  selectedRow: number;
  deletedTaskIds: string[];
  resources: unknown[];
  roles: unknown[];
  canWrite: boolean;
  canDelete: boolean;
  canWriteOnParent: boolean;
  canAdd: boolean;
  [key: string]: unknown;
}

export default function ProjectProgressPage({
  selectedProjectId: controlledProjectId,
}: {
  selectedProjectId?: number | null;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [status, setStatus] = useState<string>("就绪");
  // 任务按钮可用状态：由 iframe 内当前选中任务同步（无选中时编辑/删除禁用）
  const [canEdit, setCanEdit] = useState(false);
  const [canDelete, setCanDelete] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const loadedProjectIdRef = useRef<number | null>(null);

  // 受控 prop 优先（主页卡片跳转预选项目）；同步到内部选中态
  useEffect(() => {
    if (controlledProjectId !== undefined) {
      setSelectedProjectId(controlledProjectId);
    }
  }, [controlledProjectId]);

  // 加载项目列表
  useEffect(() => {
    invoke<Project[]>("list_projects")
      .then((data) => {
        setProjects(data);
        // 已有合法选择（含受控预选）时保留，避免覆盖主页卡片跳转的项目；
        // 无选择时才默认第一个项目（data[0]）。
        setSelectedProjectId((prev) => {
          if (prev !== null && data.some((p) => p.id === prev)) return prev;
          if (
            controlledProjectId !== undefined &&
            data.some((p) => p.id === controlledProjectId)
          ) {
            return controlledProjectId;
          }
          return data[0]?.id ?? null;
        });
      })
      .catch((e) => setStatus(`加载项目列表失败：${String(e)}`));
    // 仅需挂载时的受控值快照；后续变化由上方受控 effect 处理
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 向 iframe 发送数据
  const postToIframe = useCallback((type: string, data?: unknown) => {
    iframeRef.current?.contentWindow?.postMessage(
      { type, source: "gantt_parent", data },
      "*"
    );
  }, []);

  // 加载甘特数据
  const loadGanttData = useCallback(
    async (projectId: number) => {
      if (!projectId) return;
      setStatus("正在加载甘特数据…");
      try {
        const data = await invoke<GanttProjectData>("load_gantt_data", {
          projectId,
        });
        postToIframe("load_project", data);
        loadedProjectIdRef.current = projectId;
        setStatus("");
      } catch (e) {
        setStatus(`加载甘特数据失败：${String(e)}`);
      }
    },
    [postToIframe]
  );

  // iframe 消息监听（ready / save / load_error）
  useEffect(() => {
    const handleMessage = (evt: MessageEvent) => {
      const msg = evt.data;
      if (!msg || msg.source !== "gantt") return;

      if (msg.type === "gantt_tauri_ready") {
        if (selectedProjectId && loadedProjectIdRef.current !== selectedProjectId) {
          loadGanttData(selectedProjectId);
        }
      } else if (msg.type === "gantt_tauri_save") {
        setStatus("正在保存甘特数据…");
        (async () => {
          try {
            const parsed = JSON.parse(msg.payload || "{}") as GanttProjectData;
            const projectId = loadedProjectIdRef.current ?? selectedProjectId;
            if (!projectId) throw new Error("未选择项目");
            const idMap = await invoke<Record<string, string>>("save_gantt_data", {
              projectId,
              data: parsed,
            });
            postToIframe("save_result", { id_map: idMap });
            emitProjectUpdated();
            emitProgressUpdated();
            setStatus("保存成功");
          } catch (e) {
            postToIframe("save_result", { error: String(e) });
            setStatus(`保存失败：${String(e)}`);
          }
        })();
      } else if (msg.type === "gantt_tauri_load_error") {
        setStatus(`甘特加载错误：${msg.message ?? ""}`);
      } else if (msg.type === "gantt_action_state") {
        // iframe 同步任务选中状态：无选中任务时禁用编辑/删除按钮
        const st = msg.data ?? {};
        setCanEdit(!!st.canEdit);
        setCanDelete(!!st.canDelete);
      } else if (msg.type === "gantt_tauri_export") {
        // 导出：弹"另存为"对话框（按扩展名支持 XLSX / JSON / CSV / TXT）
        setStatus("正在导出甘特图…");
        (async () => {
          try {
            const parsed = JSON.parse(msg.payload || "{}") as GanttProjectData;
            const project = projects.find(
              (p) => p.id === (loadedProjectIdRef.current ?? selectedProjectId)
            );
            if (!project) throw new Error("未选择项目");
            const now = new Date();
            const stamp =
              `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(
                now.getDate()
              ).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(
                now.getMinutes()
              ).padStart(2, "0")}${String(now.getSeconds()).padStart(2, "0")}`;
            const savePath = await save({
              defaultPath: `项目_${project.name}_甘特图_${stamp}.xlsx`,
              filters: [
                { name: "Excel 文件", extensions: ["xlsx"] },
                { name: "JSON 文件", extensions: ["json"] },
                { name: "CSV 文件", extensions: ["csv"] },
                { name: "文本文档", extensions: ["txt"] },
              ],
            });
            if (!savePath) {
              postToIframe("export_result", { message: "导出已取消" });
              setStatus("导出已取消");
              return;
            }
            await invoke("export_gantt", { savePath, data: parsed });
            postToIframe("export_result", { message: "导出成功" });
            setStatus("导出成功");
          } catch (e) {
            postToIframe("export_result", { error: String(e) });
            setStatus(`导出失败：${String(e)}`);
          }
        })();
      } else if (msg.type === "gantt_tauri_import") {
        // 导入：弹"打开文件"对话框读取 JSON，整体替换当前项目的甘特图数据
        setStatus("正在导入甘特图…");
        (async () => {
          try {
            const filePath = await open({
              multiple: false,
              directory: false,
              filters: [{ name: "JSON 文件", extensions: ["json"] }],
            });
            if (typeof filePath !== "string" || !filePath) {
              postToIframe("import_result", { message: "导入已取消" });
              setStatus("导入已取消");
              return;
            }
            const text = await readTextFile(filePath);
            const parsed = JSON.parse(text) as GanttProjectData;
            if (!parsed || !Array.isArray(parsed.tasks)) {
              throw new Error("文件格式不正确：缺少 tasks 数组（请选择导出的 JSON 文件）");
            }
            const projectId = loadedProjectIdRef.current ?? selectedProjectId;
            if (!projectId) throw new Error("未选择项目");
            // 先清空原数据再写入，保证导入为整体替换
            await invoke("clear_project_gantt", { projectId });
            await invoke("save_gantt_data", { projectId, data: parsed });
            // 重新从数据库加载并回填到甘特图
            const fresh = await invoke<GanttProjectData>("load_gantt_data", {
              projectId,
            });
            postToIframe("load_project", fresh);
            postToIframe("import_result", { message: "导入成功" });
            emitProjectUpdated();
            emitProgressUpdated();
            setStatus("导入成功");
          } catch (e) {
            postToIframe("import_result", { error: String(e) });
            setStatus(`导入失败：${String(e)}`);
          }
        })();
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [selectedProjectId, loadGanttData, postToIframe, projects]);

  // 切换项目：重新加载
  const handleProjectChange = (id: number) => {
    setSelectedProjectId(id);
    if (loadedProjectIdRef.current !== id) {
      loadGanttData(id);
    }
  };

  // 任务按钮：转发到 iframe，由甘特页执行新建/编辑/删除
  const handleTaskAction = (action: "new" | "edit" | "delete") => {
    postToIframe("task_action", { action });
  };

  return (
    <div
      className="progress-page"
      style={{ height: "100%", minHeight: 0, display: "flex", flexDirection: "column" }}
    >
      <div
        className="list-toolbar"
        style={{ marginBottom: 8, flexShrink: 0, display: "flex", alignItems: "center", gap: 8 }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <label>选择项目：</label>
          <select
            value={selectedProjectId ?? ""}
            onChange={(e) => handleProjectChange(Number(e.target.value))}
            style={{ minWidth: 240, padding: "4px 8px" }}
          >
            {projects.length === 0 && <option value="">暂无项目</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </span>
        <span className="hint" style={{ marginLeft: 16, color: "#666" }}>
          {status}
        </span>
        <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 8 }}>
          <button onClick={() => handleTaskAction("new")} className="primary-btn">
            新建任务
          </button>
          <button onClick={() => handleTaskAction("edit")} disabled={!canEdit}>
            编辑任务
          </button>
          <button
            onClick={() => handleTaskAction("delete")}
            disabled={!canDelete}
            className="danger-btn"
          >
            删除任务
          </button>
        </span>
      </div>

      {projects.length === 0 ? (
        <div className="placeholder-card">
          <p className="hint">暂无项目数据。请先在"项目清单"页创建项目。</p>
        </div>
      ) : (
        <iframe
          ref={iframeRef}
          src="/gantt/gantt-tauri.html"
          title="甘特图"
          style={{
            width: "100%",
            flex: 1,
            minHeight: 0,
            border: "1px solid #ddd",
            borderRadius: 8,
            background: "#fff",
          }}
        />
      )}
    </div>
  );
}