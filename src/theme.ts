// 显示主题：浅色 / 深色 / 跟随系统
// - 选择持久化在 localStorage("rt-theme-mode")，默认"浅色"
// - 生效方式：<html data-theme="light|dark"> + fluent.css 文末 [data-theme="dark"] 变量覆盖
// - "跟随系统"模式下监听 prefers-color-scheme 变化即时切换

export type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "rt-theme-mode";

function systemIsDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** 把模式解析为实际深浅色并写到 <html data-theme> */
export function applyTheme(mode: ThemeMode): void {
  const dark = mode === "dark" || (mode === "system" && systemIsDark());
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function getThemeMode(): ThemeMode {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "dark" || v === "system" ? v : "light";
}

export function setThemeMode(mode: ThemeMode): void {
  localStorage.setItem(STORAGE_KEY, mode);
  applyTheme(mode);
}

/** 应用启动时调用一次：立即上色 + 跟随系统模式下响应系统切换 */
export function initTheme(): void {
  applyTheme(getThemeMode());
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      if (getThemeMode() === "system") applyTheme("system");
    });
}
