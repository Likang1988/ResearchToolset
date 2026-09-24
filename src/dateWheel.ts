// 日期输入框滚轮调节（App.tsx 挂载）
//
// 原生 date 控件虽支持滚轮但行为随版本/平台不一，且常连带滚动页面。
// 这里统一接管悬停在 type=date 上的滚轮：
//   - 按悬停 x 位置估算字段段（年/月/日），滚轮 ±1
//   - Ctrl+滚轮 ±1 月、Shift+滚轮 ±1 年（不分段，快速跳年月）
// 空态滚动时以今天为基准起调。

const SEG_YEAR = 0;
const SEG_MONTH = 1;
const SEG_DAY = 2;

function parse(input: HTMLInputElement): { y: number; m: number; d: number } {
  if (/^\d{4}-\d{2}-\d{2}$/.test(input.value)) {
    const [y, m, d] = input.value.split("-").map(Number);
    return { y, m, d };
  }
  const now = new Date();
  return { y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() };
}

function write(input: HTMLInputElement, v: { y: number; m: number; d: number }): void {
  if (v.y < 1) v.y = 1;
  // 月溢出钳位（1/31 → 2/28）
  v.d = Math.min(v.d, new Date(v.y, v.m, 0).getDate());
  const text =
    String(v.y).padStart(4, "0") +
    "-" +
    String(v.m).padStart(2, "0") +
    "-" +
    String(v.d).padStart(2, "0");
  // 走原型 setter，绕过 React 的 value tracker，使受控组件能感知变化
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  if (setter) setter.call(input, text);
  else input.value = text;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

// zh 显示格式 y/m/d：年段 4 字符 + 分隔 + 月 2 + 分隔 + 日 2，折算成比例边界
function segmentAt(input: HTMLInputElement, clientX: number): number {
  const rect = input.getBoundingClientRect();
  const pad = 6;
  const indicator = 18; // 右侧日历图标
  const content = Math.max(rect.width - pad - indicator, 1);
  const r = (clientX - rect.left - pad) / content;
  return r < 0.45 ? SEG_YEAR : r < 0.65 ? SEG_MONTH : SEG_DAY;
}

function enhance(input: HTMLInputElement): void {
  if (input.dataset.dateWheel) return;
  input.dataset.dateWheel = "1";
  input.addEventListener(
    "wheel",
    (ev) => {
      const e = ev as WheelEvent;
      e.preventDefault(); // 杜绝页面/容器滚动与缩放
      const delta = e.deltaY < 0 ? 1 : e.deltaY > 0 ? -1 : 0;
      if (!delta) return;
      const v = parse(input);
      if (e.ctrlKey) {
        const t = new Date(v.y, v.m - 1 + delta, 1);
        v.y = t.getFullYear();
        v.m = t.getMonth() + 1;
      } else if (e.shiftKey) {
        v.y += delta;
      } else {
        const seg = segmentAt(input, e.clientX);
        if (seg === SEG_YEAR) v.y += delta;
        else if (seg === SEG_MONTH) {
          const t = new Date(v.y, v.m - 1 + delta, 1);
          v.y = t.getFullYear();
          v.m = t.getMonth() + 1;
        } else v.d += delta;
      }
      write(input, v);
      input.focus({ preventScroll: true });
    },
    { passive: false },
  );
}

/** 扫描现有与后续动态添加（页面切换、弹窗）的 date 输入框 */
export function initDateWheelAdjust(): void {
  const scan = (root: ParentNode) =>
    root.querySelectorAll<HTMLInputElement>('input[type="date"]').forEach(enhance);
  scan(document.body);
  new MutationObserver((records) => {
    for (const r of records) {
      for (const n of Array.from(r.addedNodes)) {
        if (n.nodeType !== Node.ELEMENT_NODE) continue;
        const el = n as Element;
        if (el.matches('input[type="date"]')) enhance(el as HTMLInputElement);
        else scan(el);
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
}
