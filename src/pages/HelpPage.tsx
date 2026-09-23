// 帮助页：三个展开卡片 + 操作日志表
// - 软件简介：标题/副标题 + 项目简介 + 主要功能 + 计划 + 系统要求 + 依赖项 + 注意事项 + 许可证
// - 使用帮助：系统介绍 + 功能指南 + 常见问题
// - 操作日志：7 列表格（时间/类型/动作/描述/相关信息/原数据/新数据），
//   按时间倒序最多 100 条；原/新数据列只展示字段级 diff

import { useEffect, useState, type ReactNode } from "react";
import { invoke } from "@tauri-apps/api/core";

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

export default function HelpPage() {
  const [logs, setLogs] = useState<ActionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 页面挂载即加载
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
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
  }, []);

  return (
    <div className="help-page">
      <div className="help-cards">
        <ExpandCard title="软件简介" defaultOpen>
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