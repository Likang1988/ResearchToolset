// 通用占位页：未迁移的业务页统一用此组件展示标题 + 阶段徽标 + 计划功能要点

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
        该模块尚未迁移，当前为占位页。按计划将实现以下功能（对照 feature-checklist）：
      </p>
      <ul className="feature-list">
        {features.map((f, i) => (
          <li key={i}>{f}</li>
        ))}
      </ul>
    </div>
  );
}
