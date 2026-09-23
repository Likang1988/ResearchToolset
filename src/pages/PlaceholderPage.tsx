// 通用占位页：导航兜底；未实现的页面统一用此组件展示标题 + 功能要点（来自 nav 配置）

import { NavItem } from "../data/nav";

interface PlaceholderPageProps {
  item: NavItem;
}

export default function PlaceholderPage({ item }: PlaceholderPageProps) {
  const features = item.summary
    .split("；")
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div className="placeholder-card">
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 16, fontWeight: 600 }}>{item.label}</span>
      </div>
      <p className="hint">
        该功能尚未实现，以下为该页面的功能要点：
      </p>
      <ul className="feature-list">
        {features.map((f, i) => (
          <li key={i}>{f}</li>
        ))}
      </ul>
    </div>
  );
}
