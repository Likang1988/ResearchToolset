// 日期筛选默认范围的空数据兜底（清单/支出/成果/活动四页共用）
// 数据为空（或全无日期字段值）时，日期框显示 2020-01-01 ～ 今天，
// 保持"框里永远是真实日期"，不出现 locale 混杂的空态占位符。

export const EMPTY_RANGE_START = "2020-01-01";

export function todayStr(): string {
  const n = new Date();
  const p = (x: number) => String(x).padStart(2, "0");
  return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}`;
}
