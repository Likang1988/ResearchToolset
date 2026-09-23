// 主页：项目经费概览 + 项目进度概览
// - 顶部 header.png 背景图 + 「科研工具集」标题（高 340、标题 28px）
// - 经费卡片：财务编号 / 总预算 / 总支出 / 执行率
// - 进度卡片：每项目一级（level==0）甘特任务（任务编码 / 任务名称 / 任务进度）
// - 点击卡片跳转到对应「项目经费」/「项目进度」页并预选该项目
// - 订阅事件总线：项目/预算/支出/甘特变更后自动刷新

import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  onBudgetOrExpenseUpdated,
  onProgressUpdated,
  onProjectUpdated,
} from "../data/events";

// 与 Rust core::services::home::HomeOverview 对齐
interface FundOverviewItem {
  project_id: number;
  financial_code: string | null;
  total_budget: number; // 元
  total_spent: number; // 元
  execution_rate: number; // %
}
interface TaskOverviewItem {
  code: string;
  name: string;
  progress: number; // %
}
interface ProgressOverviewGroup {
  project_id: number;
  financial_code: string | null;
  tasks: TaskOverviewItem[];
}
interface HomeOverview {
  funds: FundOverviewItem[];
  progress: ProgressOverviewGroup[];
}

// 金额：元 → "x.xx 万元"
function fmtWan(yuan: number): string {
  return `${(yuan / 10000).toFixed(2)} 万元`;
}

interface HomePageProps {
  // 点击卡片跳转：page = "project-fund" | "project-progress"，并预选项目
  onNavigate: (page: string, projectId: number) => void;
  // 数据版本号：变化时强制重新加载（预留；事件总线为常态刷新机制）
  refreshKey?: number;
}

export default function HomePage({ onNavigate, refreshKey = 0 }: HomePageProps) {
  const [overview, setOverview] = useState<HomeOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 拉取概览（事件刷新 / 手动刷新共用）
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await invoke<HomeOverview>("home_overview");
      setOverview(data);
      setError(null);
    } catch (e) {
      setError(typeof e === "string" ? e : "加载主页数据失败");
    } finally {
      setLoading(false);
    }
  }, []);

  // 挂载 / refreshKey 变化时加载（避免卸载后 setState）
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    invoke<HomeOverview>("home_overview")
      .then((data) => {
        if (!cancelled) {
          setOverview(data);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(typeof e === "string" ? e : "加载主页数据失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  // 订阅事件总线：项目 / 预算 / 支出 / 甘特变更后自动刷新
  useEffect(() => {
    const unProject = onProjectUpdated(() => {
      void loadData();
    });
    const unBudget = onBudgetOrExpenseUpdated(() => {
      void loadData();
    });
    const unProgress = onProgressUpdated(() => {
      void loadData();
    });
    return () => {
      unProject();
      unBudget();
      unProgress();
    };
  }, [loadData]);

  return (
    <div className="home-page">
      <div className="home-header">
        <div className="home-header-title">科研工具集</div>
        <button
          className="home-refresh-btn"
          title="刷新"
          onClick={() => void loadData()}
          disabled={loading}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path
              d="M20 12a8 8 0 1 1-2.34-5.66M20 4v4h-4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <div className="home-grid">
        {loading && !overview ? (
          <div className="home-loading">正在加载主页数据…</div>
        ) : (
          <>
            <div className="card home-col">
              <div className="home-col-title">项目经费概览</div>
              {error && <div className="home-error">{error}</div>}
              {!error && overview && overview.funds.length === 0 && (
                <div className="empty-state">
                  暂无项目经费信息
                  <br />
                  <span style={{ fontSize: 11 }}>请在「项目清单」中新建项目</span>
                </div>
              )}
              {overview?.funds.map((f) => (
                <div
                  key={f.project_id}
                  className="overview-card fund-card"
                  onClick={() => onNavigate("project-fund", f.project_id)}
                  title="点击进入项目经费页"
                >
                  <div className="ov-financial-code">{f.financial_code ?? "--"}</div>
                  <div className="ov-divider" />
                  <div className="ov-metric">
                    <div className="ov-label">总预算</div>
                    <div className="ov-value">{fmtWan(f.total_budget)}</div>
                  </div>
                  <div className="ov-metric">
                    <div className="ov-label">总支出</div>
                    <div className="ov-value">{fmtWan(f.total_spent)}</div>
                  </div>
                  <div className="ov-metric">
                    <div className="ov-label">执行率</div>
                    <div className="ov-value">
                      {f.execution_rate.toFixed(2)}
                      <span className="ov-unit"> %</span>
                    </div>
                  </div>
                </div>
              ))}
              {overview !== null && overview.funds.length > 0 && (
                <div className="home-hint">点击卡片进入项目经费页查看详情</div>
              )}
            </div>

            <div className="card home-col">
              <div className="home-col-title">项目进度概览</div>
              {error && <div className="home-error">{error}</div>}
              {!error && overview && overview.progress.length === 0 && (
                <div className="empty-state">
                  暂无项目任务信息
                  <br />
                  <span style={{ fontSize: 11 }}>请在「项目进度」中为项目添加甘特任务</span>
                </div>
              )}
              {overview?.progress.map((g) => (
                <div
                  key={g.project_id}
                  className="overview-card progress-card"
                  onClick={() => onNavigate("project-progress", g.project_id)}
                  title="点击进入项目进度页"
                >
                  <div className="ov-financial-code">{g.financial_code ?? "--"}</div>
                  <div className="ov-divider" />
                  <div className="progress-tasks">
                    <div className="progress-head">
                      <span className="pt-code">任务编码</span>
                      <span className="pt-name">任务名称</span>
                      <span className="pt-progress">任务进度</span>
                    </div>
                    {g.tasks.map((t, i) => (
                      <div className="progress-row" key={i}>
                        <span className="pt-code">{t.code || i + 1}</span>
                        <span className="pt-name">{t.name}</span>
                        <span className="pt-progress">
                          {t.progress.toFixed(2)}
                          <span className="ov-unit"> %</span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {overview !== null && overview.progress.length > 0 && (
                <div className="home-hint">点击卡片进入项目进度页查看详情</div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}