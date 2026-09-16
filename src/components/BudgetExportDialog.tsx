// 预算导出配置对话框：对应 Python app/components/budget_export_dialog.py
// 导出形式（预算明细/预算汇总）→ 汇总子选项（细分年度 1~10 年默认 3、
// 设置比例 30-40-30 或比例留空平均分配）→ 单位（元/万元，默认元）。

import { useState } from "react";

// 与后端 core::excel::BudgetExportConfig 对齐
export interface BudgetExportConfig {
  export_detail: boolean;
  export_summary: boolean;
  year_detail: boolean;
  year_count: number;
  set_proportion: boolean;
  proportions: number[];
  unit_wan: boolean;
}

interface BudgetExportDialogProps {
  onClose: () => void;
  onConfirm: (config: BudgetExportConfig) => void;
}

export default function BudgetExportDialog({ onClose, onConfirm }: BudgetExportDialogProps) {
  // 默认值对齐 Python：明细/汇总不勾选、细分年度不勾选、比例留空、单位元
  const [exportDetail, setExportDetail] = useState(false);
  const [exportSummary, setExportSummary] = useState(false);
  const [yearDetail, setYearDetail] = useState(false);
  const [yearCount, setYearCount] = useState(3);
  const [setProportion, setSetProportion] = useState(false);
  const [proportions, setProportions] = useState<number[]>([30, 40, 30]);
  const [unitWan, setUnitWan] = useState(false);

  // 汇总未勾选时其下子选项全部失效（Python on_summary_state_changed）
  const summaryOn = exportSummary;
  const yearOn = summaryOn && yearDetail;

  // 年数变化：增删比例输入框（对齐 Python on_year_count_changed，新增默认 30-40-30）
  const handleYearCount = (y: number) => {
    const clamped = Math.min(10, Math.max(1, Math.round(y) || 1));
    setYearCount(clamped);
    setProportions((prev) => {
      const next = [...prev];
      if (clamped > next.length) {
        for (let i = next.length; i < clamped; i++) next.push(i === 1 ? 40 : 30);
      } else {
        next.length = clamped;
      }
      return next;
    });
  };

  const handleProportion = (i: number, v: number) => {
    setProportions((prev) => prev.map((p, idx) => (idx === i ? Math.min(100, Math.max(0, v || 0)) : p)));
  };

  const confirm = () => {
    onConfirm({
      export_detail: exportDetail,
      export_summary: exportSummary,
      year_detail: yearOn,
      year_count: yearOn ? yearCount : 1,
      set_proportion: yearOn && setProportion,
      proportions: yearOn && setProportion ? [...proportions] : [],
      unit_wan: unitWan,
    });
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-container" style={{ width: 460 }} onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>导出预算数据</h2>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="dialog-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* 导出形式 */}
          <div>
            <div className="export-section-label">导出形式：</div>
            <label className="export-check">
              <input
                type="checkbox"
                checked={exportDetail}
                onChange={(e) => setExportDetail(e.target.checked)}
              />
              预算明细
            </label>
            <label className="export-check">
              <input
                type="checkbox"
                checked={exportSummary}
                onChange={(e) => {
                  setExportSummary(e.target.checked);
                  if (!e.target.checked) setYearDetail(false); // 汇总关闭 → 细分年度关闭
                }}
              />
              预算汇总
            </label>
            <div className="export-sub-opts">
              {/* 细分年度 */}
              <label className="export-check">
                <input
                  type="checkbox"
                  checked={yearOn}
                  disabled={!summaryOn}
                  onChange={(e) => setYearDetail(e.target.checked)}
                />
                细分年度：
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={yearCount}
                disabled={!yearOn}
                onChange={(e) => handleYearCount(Number(e.target.value))}
                className="export-spin"
              />
              <span>年</span>
              {/* 比例设置 */}
              <div className="export-sub-opts" style={{ marginLeft: 24 }}>
                <label className="export-check">
                  <input
                    type="radio"
                    name="proportion"
                    checked={yearOn && setProportion}
                    disabled={!yearOn}
                    onChange={() => setSetProportion(true)}
                  />
                  设置比例：
                </label>
                <label className="export-check">
                  <input
                    type="radio"
                    name="proportion"
                    checked={!setProportion}
                    disabled={!yearOn}
                    onChange={() => setSetProportion(false)}
                  />
                  比例留空
                </label>
                <div className="export-proportions">
                  {proportions.slice(0, yearCount).map((p, i) => (
                    <span key={i} className="export-proportion-item">
                      第{i + 1}年
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={p}
                        disabled={!yearOn || !setProportion}
                        onChange={(e) => handleProportion(i, Number(e.target.value))}
                        className="export-spin"
                      />
                      %
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* 单位 */}
          <div>
            <div className="export-section-label">设置单位：</div>
            <div className="export-units">
              <label className="export-check">
                <input
                  type="radio"
                  name="unit"
                  checked={!unitWan}
                  onChange={() => setUnitWan(false)}
                />
                元
              </label>
              <label className="export-check">
                <input
                  type="radio"
                  name="unit"
                  checked={unitWan}
                  onChange={() => setUnitWan(true)}
                />
                万元
              </label>
            </div>
          </div>
        </div>
        <div className="dialog-footer">
          <button onClick={onClose}>取消</button>
          <button className="primary-btn" onClick={confirm}>
            导出
          </button>
        </div>
      </div>
    </div>
  );
}