// 设置页：外观主题 / 数据库管理 / 系统维护 / 软件简介 / 使用帮助 / 操作日志
// - 外观主题：浅色/深色/跟随系统（localStorage 持久化，见 src/theme.ts）
// - 数据库：查看当前库文件、切换其他库、恢复默认（原 DatabaseDialog 并入）
// - 系统维护：从支出记录重建预算支出统计（幂等）
// - 帮助内容：软件简介 / 使用帮助 / 操作日志（100 条，JSON 字段级 diff）三个卡片

import { useEffect, useState, type ReactNode } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open as openFileDialog } from "@tauri-apps/plugin-dialog";
import { getThemeMode, setThemeMode, type ThemeMode } from "../theme";

// 与 Rust core::models::Actionlog 对齐
interface ActionLog {
  id: number;
  project_id: number | null;
  budget_id: number | null;
  expense_id: number | null;
  gantt_task_id: number | null;
  project_document_id: number | null;
  project_outcome_id: number | null;
  type: string;
  action: string;
  description: string;
  operator: string;
  timestamp: string | null;
  old_data: string | null;
  new_data: string | null;
  category: string | null;
  amount: number | null;
  related_info: string | null;
}

// 字段级 diff：仅列出两个 JSON 中取值不同的键；单侧为 null 时整侧全量展示。
function findDiff(
  oldData: string | null,
  newData: string | null,
): Record<string, { old: unknown; new: unknown }> {
  let oldObj: unknown = null;
  let newObj: unknown = null;
  try {
    oldObj = oldData ? JSON.parse(oldData) : null;
  } catch {
    oldObj = oldData;
  }
  try {
    newObj = newData ? JSON.parse(newData) : null;
  } catch {
    newObj = newData;
  }

  const diff: Record<string, { old: unknown; new: unknown }> = {};
  if (oldObj === null && newObj === null) return diff;
  if (oldObj === null) {
    if (isRecord(newObj)) {
      for (const [k, v] of Object.entries(newObj)) diff[k] = { old: null, new: v };
    } else {
      diff[""] = { old: null, new: newObj };
    }
    return diff;
  }
  if (newObj === null) {
    if (isRecord(oldObj)) {
      for (const [k, v] of Object.entries(oldObj)) diff[k] = { old: v, new: null };
    } else {
      diff[""] = { old: oldObj, new: null };
    }
    return diff;
  }
  if (isRecord(oldObj) && isRecord(newObj)) {
    const keys = new Set([...Object.keys(oldObj), ...Object.keys(newObj)]);
    for (const key of keys) {
      const ov = oldObj[key];
      const nv = newObj[key];
      if (ov !== nv) diff[key] = { old: ov, new: nv };
    }
    return diff;
  }
  if (oldObj !== newObj) diff[""] = { old: oldObj, new: newObj };
  return diff;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// diff 值格式化：字符串原样，数字/布尔转文本，对象 JSON 紧凑序列化
function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "null";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// 单侧 diff 文本：`key: value` 每行一条
function diffText(side: "old" | "new", diff: Record<string, { old: unknown; new: unknown }>): string {
  const lines: string[] = [];
  for (const [key, values] of Object.entries(diff)) {
    lines.push(`${key}: ${fmtValue(values[side])}`);
  }
  return lines.join("\n");
}

interface ExpandCardProps {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

// 展开卡片：点击标题展开/收起
function ExpandCard({ title, defaultOpen = false, children }: ExpandCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`help-card${open ? " help-card--open" : ""}`}>
      <button className="help-card-header" onClick={() => setOpen(!open)}>
        <span className="help-card-title">{title}</span>
        <span className="help-card-arrow">▾</span>
      </button>
      {open && <div className="help-card-body">{children}</div>}
    </div>
  );
}

// 小节：标题 + 一段文本
function Section({ title, text }: { title: string; text: string }) {
  return (
    <div className="help-section">
      <div className="help-section-title">{title}</div>
      <div className="help-text">{text}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [logs, setLogs] = useState<ActionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // 重建支出统计：确认框 / 执行中 / 结果提示；reloadKey 触发日志重拉
  const [confirmRebuild, setConfirmRebuild] = useState(false);
  const [rebuildBusy, setRebuildBusy] = useState(false);
  const [rebuildMsg, setRebuildMsg] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  // 外观主题
  const [theme, setTheme] = useState<ThemeMode>(getThemeMode());
  // 数据库管理（原 DatabaseDialog 并入）
  const [dbPath, setDbPath] = useState("");
  const [dbBusy, setDbBusy] = useState(false);
  const [dbError, setDbError] = useState("");

  const pickTheme = (mode: ThemeMode) => {
    setTheme(mode);
    setThemeMode(mode);
  };

  const switchDb = async (path: string) => {
    setDbBusy(true);
    setDbError("");
    try {
      await invoke("open_database", { path });
      // 切换成功后重载页面，让所有页面从新数据库重新拉取数据
      window.location.reload();
    } catch (e) {
      setDbError(String(e));
      setDbBusy(false);
    }
  };

  const pickDbFile = async () => {
    const selected = await openFileDialog({
      multiple: false,
      directory: false,
      title: "选择数据库文件",
      filters: [{ name: "数据库文件", extensions: ["db", "sqlite", "sqlite3"] }],
    });
    if (typeof selected === "string" && selected) {
      await switchDb(selected);
    }
  };

  const resetDefaultDb = async () => {
    setDbBusy(true);
    setDbError("");
    try {
      await invoke("reset_database");
      window.location.reload();
    } catch (e) {
      setDbError(String(e));
      setDbBusy(false);
    }
  };

  // 挂载及 rebuild 后重新加载日志；顺带查询当前数据库路径
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    invoke<string>("db_path")
      .then(setDbPath)
      .catch((e) => setDbError(String(e)));
    invoke<ActionLog[]>("list_actionlogs")
      .then((data) => {
        if (!cancelled) {
          setLogs(data);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(typeof e === "string" ? e : "加载操作日志失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const doRebuild = () => {
    setRebuildBusy(true);
    setRebuildMsg(null);
    invoke<[number, number]>("rebuild_expense_stats")
      .then(([items, budgets]) => {
        setRebuildMsg(`重建完成：已重算 budget_items ${items} 行、budgets ${budgets} 行。`);
        setReloadKey((k) => k + 1);
      })
      .catch((e) => setRebuildMsg(`重建失败：${typeof e === "string" ? e : String(e)}`))
      .finally(() => setRebuildBusy(false));
  };

  return (
    <div className="help-page">
      <div className="help-cards">
        <ExpandCard title="外观主题" defaultOpen>
          <Section
            title="显示主题"
            text="选择“跟随系统”时，随操作系统的深浅色设置实时切换。主题偏好保存在本机。"
          />
          <div
            className="dialog-footer"
            style={{ justifyContent: "flex-start", gap: 20, borderTop: "none" }}
          >
            {(
              [
                ["light", "浅色"],
                ["dark", "深色"],
                ["system", "跟随系统"],
              ] as [ThemeMode, string][]
            ).map(([mode, label]) => (
              <label key={mode} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                <input
                  type="radio"
                  name="theme-mode"
                  checked={theme === mode}
                  onChange={() => pickTheme(mode)}
                />
                {label}
              </label>
            ))}
          </div>
        </ExpandCard>

        <ExpandCard title="数据库" defaultOpen>
          <p className="form-hint" style={{ lineHeight: 1.8 }}>
            当前数据库：<br />
            <code style={{ wordBreak: "break-all" }}>{dbPath || "加载中…"}</code>
          </p>
          <p className="form-hint" style={{ marginTop: 8 }}>
            提示：切换数据库后页面将自动重新加载；新数据库会自动补建缺失的表并执行迁移。
          </p>
          {dbError && (
            <div className="form-error" style={{ marginTop: 8 }}>
              {dbError}
            </div>
          )}
          <div className="dialog-footer" style={{ justifyContent: "flex-start" }}>
            <button onClick={resetDefaultDb} disabled={dbBusy}>
              恢复默认数据库
            </button>
            <button onClick={pickDbFile} disabled={dbBusy} className="primary-btn">
              {dbBusy ? "切换中..." : "选择其他数据库文件…"}
            </button>
          </div>
        </ExpandCard>

        <ExpandCard title="系统维护" defaultOpen>
          <Section
            title="重建支出统计"
            text="预算树中各科目显示的“支出额”来自预算表的统计列，个别历史操作可能使其与支出记录不一致（明细弹窗合计与树中数字对不上）。此处按支出记录全量重算所有统计列：操作幂等、不改任何业务数据，可放心执行。"
          />
          <div className="dialog-footer" style={{ justifyContent: "flex-start", borderTop: "none" }}>
            <button onClick={() => setConfirmRebuild(true)} disabled={rebuildBusy}>
              {rebuildBusy ? "正在重建…" : "重建支出统计"}
            </button>
            {rebuildMsg && <span className="hint" style={{ marginLeft: 12 }}>{rebuildMsg}</span>}
          </div>
          {confirmRebuild && (
            <div className="dialog-overlay" onClick={() => setConfirmRebuild(false)}>
              <div
                className="dialog-container"
                style={{ width: 420 }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="dialog-header">
                  <h2>确认重建支出统计</h2>
                  <button className="close-btn" onClick={() => setConfirmRebuild(false)}>
                    &times;
                  </button>
                </div>
                <div className="dialog-body">
                  将按支出记录重算全部项目的预算支出统计列，业务数据不受影响。确定继续？
                </div>
                <div className="dialog-footer">
                  <button onClick={() => setConfirmRebuild(false)}>取消</button>
                  <button
                    className="primary-btn"
                    onClick={() => {
                      setConfirmRebuild(false);
                      doRebuild();
                    }}
                  >
                    重建
                  </button>
                </div>
              </div>
            </div>
          )}
        </ExpandCard>

        <ExpandCard title="软件简介">
          <Section title="科研工具集 - ResearchToolset" text="基于 Rust + Tauri 的跨平台科研工具软件" />
          <Section
            title="项目简介"
            text={
              "目前软件的功能主要为科研经费管理，旨在帮助科研人员高效管理和追踪项目资金使用情况。\n\n" +
              "后续将不断丰富功能模块，目标是形成一个功能多样的工具集。\n\n" +
              "项目源于本人日常科研工作需要，利用VSCode+Cline+DeepSeek进行开发，项目代码还比较混乱，可能有很多重复代码和未知bug，未必适用于所有科研工作者，请谨慎使用。"
            }
          />
          <Section
            title="主要功能"
            text={
              "- 经费追踪\n" +
              "  用于项目实施阶段的经费执行情况追踪的工具\n\n" +
              "  - 项目管理\n" +
              "    - 添加、编辑、删除项目信息\n" +
              "    - 支持多种项目类别（国家自然科学基金、国家重点研发计划等）\n" +
              "    - 项目基本信息维护（项目编号、起止时间、总经费等）\n\n" +
              "  - 预算管理\n" +
              "    - 总预算管理\n" +
              "    - 添加、编辑、删除年度预算信息\n" +
              "    - 直观显示总预算及年度预算的预算额、支出额、结余额、执行率\n" +
              "    - 总预算及年度预算执行情况统计，按类别、时间分布统计饼图\n\n" +
              "  - 支出管理\n" +
              "    - 添加、编辑、删除支出记录\n" +
              "    - 支持批量导入支出信息\n" +
              "    - 支持导入支出凭证\n" +
              "    - 支出记录排序、筛选、导出\n\n" +
              "- 预算编制\n" +
              "  - 用于课题申请阶段的预算编制工具，功能开发中\n\n" +
              "- 小工具\n" +
              "  - 间接经费计算器\n\n" +
              "- 更多功能待添加……"
            }
          />
          <Section
            title="计划"
            text={
              "- [x] UI 全面重构（Fluent 风格）\n" +
              "- [x] 支出信息批量导入\n" +
              "- [x] 支出信息列表排序、筛选、导出\n" +
              "- [x] 支出凭证插入、导出\n" +
              "- [x] 预算管理列表执行率进度条\n" +
              "- [x] 预算管理界面统计图表\n" +
              "  - [x] 按列表支出分布\n" +
              "  - [x] 按时间支出分布\n" +
              "- [x] 预算编制功能模块\n" +
              "- [x] 预算编制数据导出 (明细、汇总、分年度)\n" +
              "- [x] 丰富主页功能 (项目概览、最近活动)"
            }
          />
          <Section title="系统要求" text={"- 跨平台（Windows / macOS / Linux）"} />
          <Section
            title="依赖项"
            text={
              "- Rust + Tauri 2\n- React\n- SQLite (rusqlite)\n- ECharts\n- jQueryGantt (项目进度页)"
            }
          />
          <Section
            title="注意事项"
            text={"- 建议定期备份数据库文件\n- 批量导入数据时请使用系统提供的模板"}
          />
          <Section
            title="许可证"
            text={"ResearchToolset使用 GPLv3 许可证进行授权。\n\n版权所有 © 2025 by Likang1988."}
          />
        </ExpandCard>

        <ExpandCard title="使用帮助">
          <Section
            title="系统介绍"
            text={
              "科研项目经费管理系统是一个帮助科研人员高效管理项目经费的工具。\n" +
              "系统提供项目管理、经费追踪等功能，让您轻松掌控项目资金使用情况。"
            }
          />
          <Section
            title="功能指南"
            text={
              "1. 项目管理：\n" +
              "   - 添加新项目：点击'添加项目'按钮，填写项目信息\n" +
              "   - 编辑项目：选择项目后点击'编辑项目'按钮\n" +
              "   - 删除项目：选择项目后点击'删除项目'按钮\n\n" +
              "2. 经费管理：\n" +
              "   - 点击项目列表中的'经费管理'按钮\n" +
              "   - 可以添加、编辑、删除经费记录\n" +
              "   - 支持批量导入支出记录"
            }
          />
          <Section
            title="常见问题"
            text={
              "Q: 如何批量导入支出记录？\n" +
              "A: 在经费管理页面点击'批量导入'按钮，选择Excel文件即可。\n\n" +
              "Q: 如何查看项目支出明细？\n" +
              "A: 在经费管理页面可以查看所有支出记录。\n\n" +
              "Q: 如何导出经费报表？\n" +
              "A: 目前正在开发导出功能，敬请期待。"
            }
          />
        </ExpandCard>

        <ExpandCard title="操作日志">
          {loading ? (
            <div className="help-log-status">正在加载操作日志…</div>
          ) : error ? (
            <div className="help-log-status" style={{ color: "#c62828" }}>
              {error}
            </div>
          ) : logs.length === 0 ? (
            <div className="help-log-status">暂无操作日志</div>
          ) : (
            <div className="help-log-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>类型</th>
                    <th>动作</th>
                    <th>描述</th>
                    <th>相关信息</th>
                    <th>原数据</th>
                    <th>新数据</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => {
                    const diff = findDiff(log.old_data, log.new_data);
                    return (
                      <tr key={log.id}>
                        <td className="help-log-cell-nowrap">{log.timestamp ?? ""}</td>
                        <td>{log.type}</td>
                        <td>{log.action}</td>
                        <td>{log.description}</td>
                        <td>{log.related_info ?? ""}</td>
                        <td className="help-log-cell-diff">{diffText("old", diff)}</td>
                        <td className="help-log-cell-diff">{diffText("new", diff)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </ExpandCard>
      </div>
    </div>
  );
}