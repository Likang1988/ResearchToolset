// 日期输入框占位统一（详见 fluent.css .rt-date-wrap 规则）
//
// WebView2 原生 date 控件空态显示跟随系统区域设置，可能出现
// "yyyy/mm/日" 之类的混杂格式。这里给所有 type=date 输入框套一层
// wrapper：空态隐藏原生字段文本（visibility:hidden，含"日"等字面量），
// 叠加自绘的纯格式提示 "yyyy/mm/dd"；一旦有值恢复原生日期显示。
// 与 locale / --lang / Windows 区域设置完全解耦。

function sync(wrap: HTMLElement, input: HTMLInputElement): void {
  wrap.classList.toggle("rt-date-filled", input.value !== "");
}

function enhance(input: HTMLInputElement): void {
  if (input.dataset.dateHint || !input.parentElement) return;
  input.dataset.dateHint = "1";

  const wrap = document.createElement("span");
  wrap.className = "rt-date-wrap";
  input.parentElement.insertBefore(wrap, input);
  wrap.appendChild(input);

  const ghost = document.createElement("span");
  ghost.className = "rt-date-ghost";
  ghost.textContent = "yyyy/mm/dd";
  wrap.appendChild(ghost);

  const update = () => sync(wrap, input);
  input.addEventListener("input", update);
  input.addEventListener("change", update);
  update();
}

/** 扫描现有与后续动态添加（页面切换、弹窗）的 date 输入框 */
export function initDateInputHints(): void {
  const scan = (root: ParentNode) => {
    root.querySelectorAll<HTMLInputElement>('input[type="date"]').forEach(enhance);
  };
  scan(document.body);
  new MutationObserver((records) => {
    for (const r of records) {
      r.addedNodes.forEach((n) => {
        if (n.nodeType !== Node.ELEMENT_NODE) return;
        const el = n as Element;
        if (el.matches?.('input[type="date"]')) enhance(el as HTMLInputElement);
        scan(el);
      });
    }
  }).observe(document.body, { childList: true, subtree: true });
}
