// 单列可编辑树（内存态，不落库）+ 按钮：创建项目/增加同级/增加子级/多个子级/删除该级
// + 导入(JSON) / 导出(Excel/CSV/JSON，Excel 为层级合并单元格导出)
// 数据模型与 Rust services::tree_list::TreeListNode 对齐（name/children）

import { useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";

interface TreeNode {
  name: string;
  children: TreeNode[];
}

interface Props {
  onBack: () => void;
}

type Path = number[];

const pathKey = (p: Path): string => p.join("-");

export default function TreeListView({ onBack }: Props) {
  const [roots, setRoots] = useState<TreeNode[]>([]);
  // 选中节点路径：[] 表示未选中（空数组会与根路径 [0] 混淆，改用 null）
  const [selected, setSelected] = useState<Path | null>(null);
  // 折叠节点 key 集合（默认展开，增加子级后自动展开）
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  // 多个子级对话框开关
  const [multiOpen, setMultiOpen] = useState(false);
  const [multiText, setMultiText] = useState("");
  // 右键菜单
  const [menu, setMenu] = useState<{ x: number; y: number; path: Path } | null>(null);
  // 导入/导出后的提示
  const [error, setError] = useState<string | null>(null);

  // 每个节点输入框的 ref（右键「重命名」聚焦用）
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // ── 树查询/不可变更新 ──

  const isEmpty = roots.length === 0;

  /** 在指定路径上执行变更：mutate 接收父节点数组，返回是否成功 */
  const updateAt = (path: Path, mutate: (parent: TreeNode[]) => boolean) => {
    setRoots((prev) => {
      const next = prev.map((n) => ({ ...n, children: n.children.map(clone) }));
      if (path.length === 1) {
        return mutate(next) ? next : prev;
      }
      let cur: TreeNode = next[path[0]];
      for (let i = 1; i < path.length - 1; i++) {
        cur = cur.children[path[i]];
      }
      const parent = cur.children;
      return mutate(parent) ? next : prev;
    });
  };

  const clone = (n: TreeNode): TreeNode => ({
    name: n.name,
    children: n.children.map(clone),
  });

  const patchName = (path: Path, name: string) => {
    if (path.length === 1) {
      setRoots((prev) => prev.map((n, i) => (i === path[0] ? { ...n, name } : n)));
      return;
    }
    const idx = path[path.length - 1];
    updateAt(path.slice(0, -1), (parent) => {
      parent[idx] = { ...parent[idx], name };
      return true;
    });
  };

  /** 给指定路径节点追加子节点（同时展开父节点） */
  const appendChildren = (path: Path, children: TreeNode[]) => {
    if (path.length === 1) {
      setRoots((prev) =>
        prev.map((n, i) => (i === path[0] ? { ...n, children: [...n.children, ...children] } : n))
      );
      return;
    }
    const idx = path[path.length - 1];
    updateAt(path.slice(0, -1), (parent) => {
      parent[idx] = { ...parent[idx], children: [...parent[idx].children, ...children] };
      return true;
    });
  };

  // ── 按钮动作 ──

  const createRoot = () => {
    setRoots((prev) => [...prev, { name: "请输入项目名称", children: [] }]);
  };

  const addSibling = () => {
    if (!selected || selected.length < 2) return;
    const idx = selected[selected.length - 1];
    updateAt(selected.slice(0, -1), (parent) => {
      parent.splice(idx + 1, 0, { name: "请输入此级名称", children: [] });
      return true;
    });
  };

  const addChild = () => {
    if (!selected) return;
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.delete(pathKey(selected));
      return next;
    });
    appendChildren(selected, [{ name: "请输入此级名称", children: [] }]);
  };

  const addMultiChild = () => {
    if (!selected) return;
    setMultiOpen(true);
    setMultiText("");
  };

  const confirmMulti = () => {
    const titles = multiText
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    setMultiOpen(false);
    if (!selected || titles.length === 0) return;
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.delete(pathKey(selected));
      return next;
    });
    appendChildren(
      selected,
      titles.map((t) => ({ name: t, children: [] }))
    );
  };

  const deleteSelected = () => {
    if (!selected) return;
    if (selected.length === 1) {
      // 根节点：仅当 >1 个根时可删
      if (roots.length <= 1) return;
      setRoots((prev) => prev.filter((_, i) => i !== selected[0]));
    } else {
      const idx = selected[selected.length - 1];
      updateAt(selected.slice(0, -1), (parent) => {
        parent.splice(idx, 1);
        return true;
      });
    }
    setSelected(null);
  };

  const doRename = (path: Path) => {
    setSelected(path);
    setMenu(null);
    const el = inputRefs.current[pathKey(path)];
    if (el) {
      el.focus();
      el.select();
    }
  };

  // ── 导入 / 导出 ──

  const importData = async () => {
    const file = await open({
      multiple: false,
      title: "导入文件",
      filters: [{ name: "JSON文件", extensions: ["json"] }],
    });
    if (typeof file !== "string") return;
    try {
      const nodes = await invoke<TreeNode[]>("import_tree_list", { filePath: file });
      setRoots(nodes);
      setSelected(null);
      setCollapsed(new Set());
      setError(null);
    } catch (e) {
      setError(`导入文件时发生错误：${String(e)}`);
    }
  };

  const exportData = async () => {
    const savePath = await save({
      defaultPath: "树形列表.xlsx",
      filters: [
        { name: "Excel文件", extensions: ["xlsx"] },
        { name: "CSV文件", extensions: ["csv"] },
        { name: "JSON文件", extensions: ["json"] },
      ],
    });
    if (!savePath) return;
    // 按扩展名判定导出格式，无扩展名默认 Excel
    const ext = (savePath.split(".").pop() ?? "").toLowerCase();
    const format = ext === "json" ? "json" : ext === "csv" ? "csv" : "xlsx";
    try {
      await invoke("export_tree_list", { savePath, roots, format });
      setError(null);
    } catch (e) {
      setError(`导出失败：${String(e)}`);
    }
  };

  // ── 渲染 ──

  const expandable = (n: TreeNode) => n.children.length > 0;
  const isCollapsed = (path: Path) => collapsed.has(pathKey(path));

  const renderNode = (node: TreeNode, path: Path, depth: number) => {
    const key = pathKey(path);
    const isSel =
      selected !== null && selected.length === path.length && selected.every((v, i) => v === path[i]);
    const hasChildren = expandable(node);
    const fold = isCollapsed(path);
    return (
      <div key={key}>
        <div
          className={`tl-row${isSel ? " selected" : ""}`}
          style={{ paddingLeft: 8 + depth * 26 }}
          onClick={() => setSelected(path)}
          onContextMenu={(e) => {
            e.preventDefault();
            setSelected(path);
            setMenu({ x: e.clientX, y: e.clientY, path });
          }}
        >
          {hasChildren ? (
            <button
              className="tl-expand"
              onClick={(e) => {
                e.stopPropagation();
                setCollapsed((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  return next;
                });
              }}
            >
              {fold ? "▸" : "▾"}
            </button>
          ) : (
            <span className="tl-expand-spacer" />
          )}
          <input
            ref={(el) => {
              inputRefs.current[key] = el;
            }}
            className="tl-input"
            value={node.name}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => patchName(path, e.target.value)}
          />
        </div>
        {!fold &&
          node.children.map((c, i) => renderNode(c, [...path, i], depth + 1))}
      </div>
    );
  };

  // 按钮启用状态
  const canSibling = selected !== null && selected.length > 1;
  const canChild = selected !== null;
  const canDelete = selected !== null && (selected.length > 1 || roots.length > 1);

  return (
    <div className="expense-mgmt">
      <div className="expense-toolbar">
        <button className="back-btn" onClick={onBack}>
          ← 返回
        </button>
        <h2 className="page-title">树形列表工具</h2>
      </div>

      <div className="tl-toolbar">
        <div className="list-actions">
          <button className="primary-btn" onClick={createRoot}>
            创建项目
          </button>
          <button onClick={addSibling} disabled={!canSibling}>
            增加同级
          </button>
          <button onClick={addChild} disabled={!canChild}>
            增加子级
          </button>
          <button onClick={addMultiChild} disabled={!canChild}>
            多个子级
          </button>
          <button className="danger-btn" onClick={deleteSelected} disabled={!canDelete}>
            删除该级
          </button>
        </div>
        <div className="list-actions">
          <button onClick={importData}>导入</button>
          <button className="primary-btn" onClick={exportData}>
            导出
          </button>
        </div>
      </div>

      {error && (
        <div className="placeholder-card">
          <p className="hint" style={{ color: "#c62828" }}>
            {error}
          </p>
        </div>
      )}

      <div className="tl-tree">
        <div className="tl-header">名称</div>
        {isEmpty && <div className="tl-empty hint">暂无项目，点击「创建项目」开始</div>}
        {roots.map((n, i) => renderNode(n, [i], 0))}
      </div>

      {/* 多个子级对话框（对齐 MultiChildDialog） */}
      {multiOpen && (
        <div className="dialog-overlay">
          <div className="dialog-container" style={{ width: 420 }}>
            <div className="dialog-header">
              <h2>添加多个标题</h2>
              <button className="close-btn" onClick={() => setMultiOpen(false)}>
                &times;
              </button>
            </div>
            <div className="dialog-body">
              <p className="hint" style={{ margin: "0 0 8px" }}>
                键入标题文本，然后针对每个新标题按 Enter 键(T):
              </p>
              <textarea
                className="tl-multi-input"
                value={multiText}
                onChange={(e) => setMultiText(e.target.value)}
                placeholder={"标题1\n标题2\n标题3"}
                rows={8}
                autoFocus
              />
            </div>
            <div className="dialog-footer">
              <button onClick={() => setMultiOpen(false)}>取消</button>
              <button className="primary-btn" onClick={confirmMulti}>
                确定
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 右键重命名菜单（对齐 TreeList.show_context_menu） */}
      {menu && (
        <div
          className="tl-menu-backdrop"
          onClick={() => setMenu(null)}
          onContextMenu={(e) => {
            e.preventDefault();
            setMenu(null);
          }}
        >
          <div className="tl-menu" style={{ left: menu.x, top: menu.y }}>
            <button onClick={() => doRename(menu.path)}>重命名</button>
          </div>
        </div>
      )}
    </div>
  );
}