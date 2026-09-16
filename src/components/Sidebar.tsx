// Fluent 风格左侧导航栏（对应 Python MainWindow(FluentWindow) 的导航项）
// 9 主项 + 帮助置底；图标：7 个复用自 Python 的 tab_*.svg，3 个 FluentIcon 用内置 SVG 替代
// 支持折叠/展开（默认折叠）：折叠时仅显示图标，hover 显示名称提示

import { useState } from "react";
import { NAV_ITEMS } from "../data/nav";
import DatabaseDialog from "./DatabaseDialog";

interface SidebarProps {
  active: string;
  onSelect: (key: string) => void;
}

// 顶部应用 logo（图标 + 名称）：仅无窗口图标的平台需要（macOS 标题栏无图标），
// Windows 标题栏左上角已显示程序图标，故不渲染
const SHOW_SIDEBAR_LOGO = !navigator.userAgent.includes("Windows");

// 内置图标（替代 QFluentWidgets 的 FluentIcon.HOME / DEVELOPER_TOOLS / HELP）
function InlineIcon({ name }: { name: string }) {
  switch (name) {
    case "home":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" strokeLinejoin="round" />
        </svg>
      );
    case "tools":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path
            d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.3 2.3-2.7-.7-.7-2.7 2.3-2.3z"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "help":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="9" />
          <path d="M9.5 9a2.5 2.5 0 0 1 4.5 1.5c0 1.5-2 2-2 3.5M12 17h.01" strokeLinecap="round" />
        </svg>
      );
    default:
      return null;
  }
}

function NavIcon({ icon }: { icon: string }) {
  if (icon.startsWith("/icons/")) {
    return (
      <span className="nav-icon">
        <img src={icon} alt="" />
      </span>
    );
  }
  return (
    <span className="nav-icon">
      <InlineIcon name={icon} />
    </span>
  );
}

export default function Sidebar({ active, onSelect }: SidebarProps) {
  // 默认折叠状态
  const [collapsed, setCollapsed] = useState(true);
  const [dbDialogOpen, setDbDialogOpen] = useState(false);
  const top = NAV_ITEMS.filter((n) => n.position === "top");
  const bottom = NAV_ITEMS.filter((n) => n.position === "bottom");

  const renderItem = (item: (typeof NAV_ITEMS)[number]) => (
    <div
      key={item.key}
      className={`nav-item ${active === item.key ? "active" : ""}`}
      title={collapsed ? item.label : undefined}
      onClick={() => onSelect(item.key)}
    >
      <NavIcon icon={item.icon} />
      <span className="nav-label">{item.label}</span>
    </div>
  );

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      {SHOW_SIDEBAR_LOGO && (
        <div className="sidebar-logo">
          <img src="/icons/app.png" alt="logo" />
          <span className="sidebar-logo-text">科研工具集</span>
        </div>
      )}
      <div className="sidebar-section">{top.map(renderItem)}</div>
      <div className="sidebar-section bottom">
        {bottom.map(renderItem)}
        {/* 数据库管理入口（非导航页，点击弹出对话框） */}
        <div
          className="nav-item"
          title={collapsed ? "数据库管理" : undefined}
          onClick={() => setDbDialogOpen(true)}
        >
          <span className="nav-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <ellipse cx="12" cy="5.5" rx="7.5" ry="2.8" />
              <path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13" />
              <path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8" />
            </svg>
          </span>
          <span className="nav-label">数据库</span>
        </div>
      </div>
      <button
        className="sidebar-collapse-btn"
        title={collapsed ? "展开侧边栏" : "折叠侧边栏"}
        onClick={() => setCollapsed((c) => !c)}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          {collapsed ? (
            <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
          ) : (
            <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
          )}
        </svg>
        <span className="nav-label">折叠</span>
      </button>
      <DatabaseDialog open={dbDialogOpen} onClose={() => setDbDialogOpen(false)} />
    </aside>
  );
}
