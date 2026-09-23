// Fluent 风格左侧导航栏
// 9 主项 + 设置置底；图标全部内联 SVG（currentColor 跟随主题），见 tabIcons.tsx / InlineIcon
// 支持折叠/展开（默认折叠）：折叠时仅显示图标，hover 显示名称提示

import { useState } from "react";
import { NAV_ITEMS } from "../data/nav";
import { TAB_ICONS } from "./tabIcons";

interface SidebarProps {
  active: string;
  onSelect: (key: string) => void;
}

// 顶部应用 logo（图标 + 名称）：仅无窗口图标的平台需要（macOS 标题栏无图标），
// Windows 标题栏左上角已显示程序图标，故不渲染
const SHOW_SIDEBAR_LOGO = !navigator.userAgent.includes("Windows");

// 内置 SVG 图标（主页 / 小工具 / 帮助）
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
    case "settings":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="3.2" />
          <path
            d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
            strokeLinejoin="round"
          />
        </svg>
      );
    default:
      return null;
  }
}

function NavIcon({ icon }: { icon: string }) {
  // 图标全部内联（tab_* 图形 + home/tools/settings），currentColor 跟随主题
  return (
    <span className="nav-icon">
      {TAB_ICONS[icon] ?? <InlineIcon name={icon} />}
    </span>
  );
}

export default function Sidebar({ active, onSelect }: SidebarProps) {
  // 默认折叠状态
  const [collapsed, setCollapsed] = useState(true);
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
      <div className="sidebar-section bottom">{bottom.map(renderItem)}</div>
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
    </aside>
  );
}
