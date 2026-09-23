//! 树形列表工具：树形数据的导入/导出（JSON/CSV/Excel）
//!
//! 树为纯内存结构（不落库）：
//! - JSON 导出：`{"columns": [""], "children": [...]}` 递归结构（顶层为不可见根节点，
//!   其文本为空串，导入时只取 `children`）
//! - CSV 导出：动态表头「层级1..层级N」，仅叶子节点各输出一行（每层级一列，短路径补空）
//! - Excel 导出：层级列 + 同层级合并单元格 + B8CCE4 填充 + 细边框 + 列宽 15
//! - JSON 导入：读取 `data.children` 递归构建树

use std::path::Path;

use rust_xlsxwriter::{Color, Format, FormatAlign, FormatBorder, Workbook};

use crate::DbError;

/// 树节点（名称 + 子节点）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TreeListNode {
    pub name: String,
    pub children: Vec<TreeListNode>,
}

// ─────────────────────────── 导出 ───────────────────────────

/// 按 `format`（json/csv/xlsx）导出整棵树。`roots` 为顶层节点列表。
pub fn export_tree_list(
    path: &Path,
    roots: &[TreeListNode],
    format: &str,
) -> Result<(), DbError> {
    match format.to_lowercase().as_str() {
        "json" => export_json(path, roots),
        "csv" => export_csv(path, roots),
        "xlsx" => export_excel(path, roots),
        other => Err(DbError::Other(format!("不支持的导出格式: {other}"))),
    }
}

// —— JSON（顶层 columns 为根文本，空串） ——

fn to_json_node(n: &TreeListNode) -> serde_json::Value {
    serde_json::json!({
        "columns": [n.name],
        "children": n.children.iter().map(to_json_node).collect::<Vec<_>>(),
    })
}

fn export_json(path: &Path, roots: &[TreeListNode]) -> Result<(), DbError> {
    let data = serde_json::json!({
        "columns": [""],
        "children": roots.iter().map(to_json_node).collect::<Vec<_>>(),
    });
    let text = serde_json::to_string_pretty(&data)?;
    std::fs::write(path, text)?;
    Ok(())
}

// —— CSV（叶子路径逐行展平导出） ——

/// 子树深度（叶子 = 1）
fn subtree_depth(n: &TreeListNode) -> usize {
    if n.children.is_empty() {
        1
    } else {
        1 + n.children.iter().map(subtree_depth).max().unwrap_or(0)
    }
}

/// 收集所有叶子路径（每条为自根起的完整名称链条）
fn flatten_leaves(n: &TreeListNode, chain: &mut Vec<String>, out: &mut Vec<Vec<String>>) {
    chain.push(n.name.clone());
    if n.children.is_empty() {
        out.push(chain.clone());
    }
    for c in &n.children {
        flatten_leaves(c, chain, out);
    }
    chain.pop();
}

/// CSV 字段转义：含逗号/引号/换行时加引号，内部引号翻倍
fn csv_escape(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') || s.contains('\r') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

fn export_csv(path: &Path, roots: &[TreeListNode]) -> Result<(), DbError> {
    let max_depth = roots.iter().map(subtree_depth).max().unwrap_or(0);

    let mut lines: Vec<String> = Vec::new();
    // 表头
    let headers: Vec<String> = (0..max_depth).map(|i| format!("层级{}", i + 1)).collect();
    lines.push(headers.iter().map(|h| csv_escape(h)).collect::<Vec<_>>().join(","));

    // 叶子行
    let mut leaves: Vec<Vec<String>> = Vec::new();
    for r in roots {
        flatten_leaves(r, &mut Vec::new(), &mut leaves);
    }
    for leaf in &leaves {
        let row: Vec<String> = (0..max_depth)
            .map(|i| csv_escape(leaf.get(i).map(String::as_str).unwrap_or("")))
            .collect();
        lines.push(row.join(","));
    }

    std::fs::write(path, lines.join("\n"))?;
    Ok(())
}

// —— Excel（按层级合并单元格导出） ——

/// 层级树（同名节点合并 children，保持插入序）
struct HierarchyNode {
    name: String,
    children: Vec<HierarchyNode>,
}

/// 由叶子路径构建层级树（空名层级跳过）
fn build_hierarchy(leaves: &[Vec<String>], max_depth: usize) -> Vec<HierarchyNode> {
    let mut roots: Vec<HierarchyNode> = Vec::new();
    for leaf in leaves {
        let mut cur = &mut roots;
        for level in 0..max_depth {
            let name = leaf.get(level).map(String::as_str).unwrap_or("");
            if name.is_empty() {
                break;
            }
            let pos = cur.iter().position(|n| n.name == name);
            let node = match pos {
                Some(i) => &mut cur[i],
                None => {
                    cur.push(HierarchyNode {
                        name: name.to_string(),
                        children: Vec::new(),
                    });
                    let last = cur.len() - 1;
                    &mut cur[last]
                }
            };
            cur = &mut node.children;
        }
    }
    roots
}

/// 节点及其子树占用的行数（叶子 = 1）
fn count_rows(n: &HierarchyNode) -> usize {
    if n.children.is_empty() {
        1
    } else {
        n.children.iter().map(count_rows).sum()
    }
}

/// 递归填充数据并合并同层级单元格
fn fill_excel(
    ws: &mut rust_xlsxwriter::Worksheet,
    nodes: &[HierarchyNode],
    start_row: u32,
    level: u16,
    fmt: &Format,
) -> Result<u32, DbError> {
    let mut current_row = start_row;
    for n in nodes {
        let span = if n.children.is_empty() {
            1
        } else {
            n.children.iter().map(count_rows).sum::<usize>() as u32
        };
        if span > 1 {
            ws.merge_range(
                current_row,
                level - 1,
                current_row + span - 1,
                level - 1,
                &n.name,
                fmt,
            )
            .map_err(|e| DbError::Other(e.to_string()))?;
        } else {
            ws.write_with_format(current_row, level - 1, &n.name, fmt)
                .map_err(|e| DbError::Other(e.to_string()))?;
        }
        if n.children.is_empty() {
            current_row += 1; // span == 1
        } else {
            // 递归填充子节点，返回已推进的游标（子节点总行数即 span）
            current_row = fill_excel(ws, &n.children, current_row, level + 1, fmt)?;
        }
    }
    Ok(current_row)
}

fn export_excel(path: &Path, roots: &[TreeListNode]) -> Result<(), DbError> {
    let max_depth = roots.iter().map(subtree_depth).max().unwrap_or(0);
    let mut leaves: Vec<Vec<String>> = Vec::new();
    for r in roots {
        flatten_leaves(r, &mut Vec::new(), &mut leaves);
    }
    let hierarchy = build_hierarchy(&leaves, max_depth);

    let cell_fmt = Format::new()
        .set_background_color(Color::RGB(0xB8CCE4))
        .set_align(FormatAlign::Center)
        .set_align(FormatAlign::VerticalCenter)
        .set_border(FormatBorder::Thin);

    let mut wb = Workbook::new();
    let sheet = wb.add_worksheet();

    // 表头：层级1..层级N
    for col in 0..max_depth as u16 {
        sheet
            .write_with_format(0, col, format!("层级{}", col + 1), &cell_fmt)
            .map_err(|e| DbError::Other(e.to_string()))?;
        // 列宽统一 15
        sheet
            .set_column_width(col, 15.0)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    if max_depth > 0 {
        fill_excel(&mut *sheet, &hierarchy, 1, 1, &cell_fmt)?;
    }

    wb.save(path)
        .map_err(|e| DbError::Other(format!("保存 Excel 失败: {e}")))?;
    Ok(())
}

// ─────────────────────────── 导入 ───────────────────────────

/// 解析树形列表 JSON：
/// 只取顶层 `children` 递归构建，节点名取 `columns[0]`。
pub fn parse_tree_list_json(path: &Path) -> Result<Vec<TreeListNode>, DbError> {
    let raw = std::fs::read_to_string(path)?;
    let v: serde_json::Value = serde_json::from_str(&raw)?;
    let arr = v
        .get("children")
        .and_then(|c| c.as_array())
        .cloned()
        .unwrap_or_default();
    Ok(arr.iter().map(parse_json_node).collect())
}

fn parse_json_node(v: &serde_json::Value) -> TreeListNode {
    let name = v
        .get("columns")
        .and_then(|c| c.as_array())
        .and_then(|a| a.first())
        .and_then(|x| x.as_str())
        .unwrap_or("")
        .to_string();
    let children = v
        .get("children")
        .and_then(|c| c.as_array())
        .cloned()
        .unwrap_or_default()
        .iter()
        .map(parse_json_node)
        .collect();
    TreeListNode { name, children }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tree(name: &str, children: Vec<TreeListNode>) -> TreeListNode {
        TreeListNode {
            name: name.to_string(),
            children,
        }
    }

    /// 简单三层树：A → (A1, A2)；B
    fn sample_tree() -> Vec<TreeListNode> {
        vec![
            tree(
                "A",
                vec![tree("A1", vec![]), tree("A2", vec![tree("A2x", vec![])])],
            ),
            tree("B", vec![]),
        ]
    }

    #[test]
    fn subtree_depth_matches_expected() {
        // A: 子子树深度 max(A1=1, A2=2)+1 = 3；B = 1 → 整体 max = 3
        let d = sample_tree()
            .iter()
            .map(subtree_depth)
            .max()
            .unwrap_or(0);
        assert_eq!(d, 3);
        // 空树 → 0
        let empty: Vec<TreeListNode> = vec![];
        assert_eq!(empty.iter().map(subtree_depth).max().unwrap_or(0), 0);
    }

    #[test]
    fn flatten_only_leaves() {
        let mut out = Vec::new();
        for r in &sample_tree() {
            flatten_leaves(r, &mut Vec::new(), &mut out);
        }
        assert_eq!(
            out,
            vec![
                vec!["A".to_string(), "A1".to_string()],
                vec!["A".to_string(), "A2".to_string(), "A2x".to_string()],
                vec!["B".to_string()],
            ]
        );
    }

    #[test]
    fn json_round_trip() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("tree.json");
        export_tree_list(&p, &sample_tree(), "json").unwrap();

        let text = std::fs::read_to_string(&p).unwrap();
        let v: serde_json::Value = serde_json::from_str(&text).unwrap();
        // 顶层 children = 2 根；顶层 columns 为空串（不可见根节点文本）
        assert_eq!(v["columns"][0], "");
        assert_eq!(v["children"].as_array().unwrap().len(), 2);

        let roots = parse_tree_list_json(&p).unwrap();
        assert_eq!(roots.len(), 2);
        assert_eq!(roots[0].name, "A");
        assert_eq!(roots[0].children.len(), 2);
        assert_eq!(roots[0].children[1].children[0].name, "A2x");
        assert_eq!(roots[1].name, "B");
    }

    #[test]
    fn csv_leaf_rows() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("tree.csv");
        export_tree_list(&p, &sample_tree(), "csv").unwrap();
        let text = std::fs::read_to_string(&p).unwrap();
        let lines: Vec<&str> = text.lines().collect();
        // 表头 + 2 个叶子（A→A1、A→A2→A2x、B）
        assert_eq!(lines.len(), 4);
        assert_eq!(lines[0], "层级1,层级2,层级3");
        assert_eq!(lines[1], "A,A1,");
        assert_eq!(lines[2], "A,A2,A2x");
        assert_eq!(lines[3], "B,,");
    }

    #[test]
    fn excel_export_ok() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("tree.xlsx");
        export_tree_list(&p, &sample_tree(), "xlsx").unwrap();
        assert!(p.exists());
        // Excel 文件头 PK\x03\x04
        let head = std::fs::read(&p).unwrap();
        assert_eq!(&head[..4], &[0x50, 0x4B, 0x03, 0x04]);
    }

    #[test]
    fn csv_escape_quotes() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("q.csv");
        let roots = vec![tree("含,逗号", vec![tree("含\"引号", vec![])])];
        export_tree_list(&p, &roots, "csv").unwrap();
        let text = std::fs::read_to_string(&p).unwrap();
        let lines: Vec<&str> = text.lines().collect();
        assert_eq!(lines[1], "\"含,逗号\",\"含\"\"引号\"");
    }
}