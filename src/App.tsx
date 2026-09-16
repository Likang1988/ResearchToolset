// ResearchToolset Rust 版导航壳
// 对应 Python app/views/main_window.py：左侧 Fluent 导航栏 + 右侧内容区切换
// 当前仅 UI 骨架，未连后端；业务页用占位页展示计划功能

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
import HelpPage from "./pages/HelpPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import { NAV_ITEMS, DEFAULT_PAGE } from "./data/nav";
import "./App.css";
import "./styles/fluent.css";

function App() {
  const [active, setActive] = useState(DEFAULT_PAGE);
  // 项目经费页所选项目：提升到 App 层，标签切换后返回保持（对齐 Python 页面常驻）
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
          ) : active === "help" ? (
            <HelpPage />
          ) : currentItem ? (
            <PlaceholderPage item={currentItem} />
          ) : null}
        </section>
      </main>
    </div>
  );
}

export default App;
