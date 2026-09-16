// 数据库管理对话框：查看/切换当前数据库文件
// - 默认使用应用自带的 database/database.db（源码模式为项目根，便携模式为 exe 旁）
// - 可手动选择其他 SQLite 数据库文件加载；切换成功后重新加载页面以刷新全部数据

import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open as openFileDialog } from "@tauri-apps/plugin-dialog";

interface DatabaseDialogProps {
  open: boolean;
  onClose: () => void;
}

export default function DatabaseDialog({ open, onClose }: DatabaseDialogProps) {
  const [currentPath, setCurrentPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setBusy(false);
    setError("");
    invoke<string>("db_path")
      .then(setCurrentPath)
      .catch((e) => setError(String(e)));
  }, [open]);

  const switchTo = async (path: string) => {
    setBusy(true);
    setError("");
    try {
      await invoke("open_database", { path });
      // 切换成功后重载页面，让所有页面从新数据库重新拉取数据
      window.location.reload();
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  };

  const pickFile = async () => {
    const selected = await openFileDialog({
      multiple: false,
      directory: false,
      title: "选择数据库文件",
      filters: [{ name: "数据库文件", extensions: ["db", "sqlite", "sqlite3"] }],
    });
    if (typeof selected === "string" && selected) {
      await switchTo(selected);
    }
  };

  const resetDefault = async () => {
    setBusy(true);
    setError("");
    try {
      await invoke("reset_database");
      window.location.reload();
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="dialog-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog-container" style={{ width: 520 }}>
        <div className="dialog-header">
          <h2>数据库管理</h2>
          <button className="close-btn" onClick={onClose} disabled={busy}>
            &times;
          </button>
        </div>
        <div className="dialog-body">
          <p className="form-hint" style={{ lineHeight: 1.8 }}>
            当前数据库：<br />
            <code style={{ wordBreak: "break-all" }}>{currentPath || "加载中…"}</code>
          </p>
          <p className="form-hint" style={{ marginTop: 8 }}>
            提示：切换数据库后页面将自动重新加载；新数据库会自动补建缺失的表并执行迁移。
          </p>
          {error && (
            <div className="form-error" style={{ marginTop: 8 }}>
              {error}
            </div>
          )}
        </div>
        <div className="dialog-footer">
          <button onClick={resetDefault} disabled={busy}>
            恢复默认数据库
          </button>
          <button onClick={pickFile} disabled={busy} className="primary-btn">
            {busy ? "切换中..." : "选择其他数据库文件…"}
          </button>
        </div>
      </div>
    </div>
  );
}
