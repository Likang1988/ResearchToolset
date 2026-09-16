// 预算执行饼图：纯 SVG 环形图，展示按类别 / 时间维度聚合的支出分布
// 对应 Python app/components/budget_chart_widget.py：调用方负责聚合，
// 此组件只负责渲染（标题 + 环形图 + 图例：标签/金额/百分比）

import { useMemo, type ReactNode } from "react";

// 单个扇区数据（调用方已聚合：label=类别或时间，value=金额（万元））
export interface PieEntry {
  label: string;
  value: number;
}

interface Props {
  title: string;
  entries: PieEntry[];
  /// 附加工具（如分布切换按钮），渲染在圆角框左上角
  toolbar?: ReactNode;
}

// 配色（对齐 Python BudgetChartBase.colors）
const COLORS = [
  "#FF9999",
  "#66B2FF",
  "#99FF99",
  "#FFCC99",
  "#CC99FF",
  "#FF99CC",
  "#99CCFF",
  "#CCFF99",
  "#FFFF99",
  "#FFB366",
];

// 将数值映射到 SVG path 的弧段（极坐标转笛卡尔）
function describeSlice(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number
): string {
  // 角度从 12 点方向开始，顺时针；转换到标准数学坐标
  const toXY = (angle: number) => {
    const rad = ((angle - 90) * Math.PI) / 180;
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
  };
  const [x1, y1] = toXY(startAngle);
  const [x2, y2] = toXY(endAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  // 完整圆（360°）需拆成两段避免 path 退化
  if (endAngle - startAngle >= 360) {
    const [mx, my] = toXY(startAngle + 180);
    return `M ${cx},${cy} L ${x1},${y1} A ${r},${r} 0 1 1 ${mx},${my} A ${r},${r} 0 1 1 ${x1},${y1} Z`;
  }
  return `M ${cx},${cy} L ${x1},${y1} A ${r},${r} 0 ${largeArc} 1 ${x2},${y2} Z`;
}

export default function BudgetPieChart({ title, entries, toolbar }: Props) {
  // 过滤 0 值并按数值降序
  const slices = useMemo(
    () =>
      entries
        .filter((it) => it.value > 0)
        .sort((a, b) => b.value - a.value),
    [entries]
  );

  const total = slices.reduce((s, x) => s + x.value, 0);

  const size = 260;
  const cx = size / 2;
  const cy = size / 2;
  const r = 105;

  return (
    <div className="pie-chart-card">
      {/* 工具插槽：绝对定位于圆角框左上角（对齐 Python 按钮盖在 chart_view 上） */}
      {toolbar && <div className="pie-chart-toolbar">{toolbar}</div>}
      <div className="pie-chart-title">{title}</div>
      {total <= 0 ? (
        <div className="pie-empty">暂无数据</div>
      ) : (
        <div className="pie-chart-body">
          <svg width={size} height={size} className="pie-svg">
            {(() => {
              let acc = 0;
              return slices.map((s, i) => {
                const start = (acc / total) * 360;
                acc += s.value;
                const end = (acc / total) * 360;
                const color = COLORS[i % COLORS.length];
                const path = describeSlice(cx, cy, r, start, end);
                return (
                  <path key={s.label} d={path} fill={color} stroke="#fff" strokeWidth={1.5}>
                    <title>
                      {s.label}: {s.value.toFixed(2)} 万元 (
                      {((s.value / total) * 100).toFixed(1)}%)
                    </title>
                  </path>
                );
              });
            })()}
            {/* 中心白圈做成环形图 */}
            <circle cx={cx} cy={cy} r={r * 0.55} fill="#fff" />
            <text x={cx} y={cy - 6} textAnchor="middle" className="pie-center-label">
              合计
            </text>
            <text x={cx} y={cy + 14} textAnchor="middle" className="pie-center-value">
              {total.toFixed(2)}
            </text>
          </svg>
          <ul className="pie-legend">
            {slices.map((s, i) => (
              <li key={s.label}>
                <span
                  className="legend-dot"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="legend-label">{s.label}</span>
                <span className="legend-value">{s.value.toFixed(2)}</span>
                <span className="legend-pct">
                  {((s.value / total) * 100).toFixed(1)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}