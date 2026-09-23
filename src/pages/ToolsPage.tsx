// 小工具首页
// 两张工具卡片（间接经费计算器 / 树形列表工具）+ 打开按钮 → 切换子视图
// 子工具为独立视图（IndirectCostCalculatorView / TreeListView），可从顶部返回首页

import { useState } from "react";
import IndirectCostCalculatorView from "./IndirectCostCalculatorView";
import TreeListView from "./TreeListView";

type ToolsView = "home" | "calculator" | "treelist";

interface ToolCard {
  key: ToolsView;
  icon: string;
  name: string;
}

const TOOLS: ToolCard[] = [
  { key: "calculator", icon: "/icons/calculator.svg", name: "间接经费计算器" },
  { key: "treelist", icon: "/icons/treelist.svg", name: "树形列表工具" },
];

export default function ToolsPage() {
  const [view, setView] = useState<ToolsView>("home");

  if (view === "calculator") {
    return <IndirectCostCalculatorView onBack={() => setView("home")} />;
  }
  if (view === "treelist") {
    return <TreeListView onBack={() => setView("home")} />;
  }

  return (
    <div className="tools-home">
      <div className="tools-list">
        {TOOLS.map((t) => (
          <div key={t.key} className="tools-card">
            <div className="tools-card-body">
              <img className="tools-card-icon" src={t.icon} alt={t.name} />
              <span className="tools-card-title">{t.name}</span>
            </div>
            <button className="primary-btn" onClick={() => setView(t.key)}>
              打开
            </button>
          </div>
        ))}
      </div>
      <div className="tools-author">© Likang</div>
    </div>
  );
}