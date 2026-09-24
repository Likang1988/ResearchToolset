// ResearchToolset Rust 版导航壳
// 左侧 Fluent 导航栏 + 右侧内容区切换
// 各业务页已接入后端命令；未实现的导航项由 PlaceholderPage 兜底

import { useState } from "react";
import Sidebar from "./components/Sidebar";
import HomePage from "./pages/HomePage";
import ProjectListPage from "./pages/ProjectListPage";
import ProjectFundPage from "./pages/ProjectFundPage";
import ProjectProgressPage from "./pages/ProjectProgressPage";
import ProjectDocumentPage from "./pages/ProjectDocumentPage";
import ProjectOutcomePage from "./pages/ProjectOutcomePage";
import ProjectActivityPage from "./pages/ProjectActivityPage";
import BudgetingPage from "./pages/BudgetingPage";
import ToolsPage from "./pages/ToolsPage";
import SettingsPage from "./pages/SettingsPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import { NAV_ITEMS, DEFAULT_PAGE } from "./data/nav";
import { initTheme } from "./theme";
import { initDateWheelAdjust } from "./dateWheel";
import "./App.css";
import "./styles/fluent.css";

// 启动即上色（模块加载期，早于首帧渲染，避免主题闪烁）
initTheme();
// 日期输入框滚轮调节（全应用统一接管）
initDateWheelAdjust();

function App() {
  const [active, setActive] = useState(DEFAULT_PAGE);
  // 项目经费页所选项目：提升到 App 层，标签切换后返回保持（页面状态常驻）
  const [fundProjectId, setFundProjectId] = useState<number | null>(null);
  // 项目进度页所选项目（主页卡片跳转预选）
  const [progressProjectId, setProgressProjectId] = useState<number | null>(null);
  const currentItem = NAV_ITEMS.find((n) => n.key === active);

  // 主页卡片跳转：切到对应页并预选项目
  const handleHomeNavigate = (page: string, projectId: number) => {
    if (page === "project-fund") {
      setFundProjectId(projectId);
      setActive("project-fund");
    } else if (page === "project-progress") {
      setProgressProjectId(projectId);
      setActive("project-progress");
    }
  };

  return (
    <div className="app-shell">
      <Sidebar active={active} onSelect={setActive} />
      <main className="content">
        {active !== "home" && (
          <header className="content-header">
            <h1>{currentItem?.label ?? ""}</h1>
          </header>
        )}
        <section className={`content-body ${active === "home" ? "content-body--flush" : ""}`}>
          {active === "home" ? (
            <HomePage onNavigate={handleHomeNavigate} />
          ) : active === "project-list" ? (
            <ProjectListPage />
          ) : active === "project-fund" ? (
            <ProjectFundPage
              selectedProjectId={fundProjectId}
              onProjectChange={setFundProjectId}
            />
          ) : active === "project-progress" ? (
            <ProjectProgressPage selectedProjectId={progressProjectId} />
          ) : active === "project-document" ? (
            <ProjectDocumentPage />
          ) : active === "project-outcome" ? (
            <ProjectOutcomePage />
          ) : active === "activity" ? (
            <ProjectActivityPage />
          ) : active === "budgeting" ? (
            <BudgetingPage />
          ) : active === "tools" ? (
            <ToolsPage />
          ) : active === "settings" ? (
            <SettingsPage />
          ) : currentItem ? (
            <PlaceholderPage item={currentItem} />
          ) : null}
        </section>
      </main>
    </div>
  );
}

export default App;
