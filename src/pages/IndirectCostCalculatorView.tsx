// 间接经费计算器
// 6 个输入（总经费/设备费/外部协作费/三段费率%），调用 Rust 二分算法计算最大间接经费
// 费率阶梯：500 万内 rate1、500-1000 万 rate2、1000 万以上 rate3（默认 20%/15%/13%）

import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

interface Props {
  onBack: () => void;
}

const num = (v: string): number | null => {
  if (v.trim() === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export default function IndirectCostCalculatorView({ onBack }: Props) {
  const [totalFunds, setTotalFunds] = useState("");
  const [equipmentCost, setEquipmentCost] = useState("");
  const [externalCoop, setExternalCoop] = useState("");
  const [rate1, setRate1] = useState("20");
  const [rate2, setRate2] = useState("15");
  const [rate3, setRate3] = useState("13");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const calculate = async () => {
    setError(null);
    setResult(null);
    const total = num(totalFunds);
    const equip = num(equipmentCost);
    const external = num(externalCoop);
    const r1 = num(rate1);
    const r2 = num(rate2);
    const r3 = num(rate3);
    if (total === null || equip === null || external === null || r1 === null || r2 === null || r3 === null) {
      setError("请输入有效的数字");
      return;
    }
    try {
      const value = await invoke<number>("calculate_indirect_cost", {
        totalFunds: total,
        equipmentCost: equip,
        externalCooperationCost: external,
        rate1: r1 / 100,
        rate2: r2 / 100,
        rate3: r3 / 100,
      });
      setResult(value.toFixed(2));
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="expense-mgmt">
      <div className="expense-toolbar">
        <button className="back-btn" onClick={onBack}>
          ← 返回
        </button>
        <h2 className="page-title">间接经费计算器</h2>
      </div>

      <div className="calc-form">
        <div className="calc-form-title">输入参数</div>
        <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div className="form-group">
            <label>总经费（万元）:</label>
            <input value={totalFunds} onChange={(e) => setTotalFunds(e.target.value)} />
          </div>
          <div className="form-group">
            <label>设备费（万元）:</label>
            <input value={equipmentCost} onChange={(e) => setEquipmentCost(e.target.value)} />
          </div>
          <div className="form-group">
            <label>外部协作费（万元）:</label>
            <input value={externalCoop} onChange={(e) => setExternalCoop(e.target.value)} />
          </div>
          <div className="form-group">
            <label>500万元以下比例（%）:</label>
            <input value={rate1} onChange={(e) => setRate1(e.target.value)} />
          </div>
          <div className="form-group">
            <label>500-1000万元比例（%）:</label>
            <input value={rate2} onChange={(e) => setRate2(e.target.value)} />
          </div>
          <div className="form-group">
            <label>1000万元以上比例（%）:</label>
            <input value={rate3} onChange={(e) => setRate3(e.target.value)} />
          </div>
        </div>
      </div>

      <div>
        <button className="primary-btn" onClick={calculate}>
          计算最大间接经费
        </button>
      </div>

      <div className="calc-result">
        {error && (
          <>
            <h3>错误</h3>
            <p style={{ color: "#c62828" }}>{error}</p>
          </>
        )}
        {result !== null && (
          <>
            <h3>计算结果</h3>
            <p>
              最大间接经费：<strong>{result}</strong> 万元
            </p>
          </>
        )}
      </div>
    </div>
  );
}