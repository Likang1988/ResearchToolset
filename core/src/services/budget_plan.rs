//! 预算编制服务：对应 Python `app/views/budgeting_interface.py`
//!
//! 业务核心：
//! - 树结构最多三级（与 Python `add_sub_level` 的「最多只能添加三级预算项！」一致）：
//!   预算计划（`budget_plans`）→ 类别占位节点（`budget_plan_items`，`parent_id IS NULL`，
//!   仅存 amount/remarks，name 等为空）→ 预算条目（`parent_id` = 占位节点 id）。
//!   保存时也只用「占位行 + 一级子项」两层重写（对齐 Python `save_data`）。
//! - `category` 以 SQLAlchemy Enum 的名称（KEY，如 `EQUIPMENT`）落库，
//!   对外统一为中文 label（如「设备费」），读写双向转换（未知 label 不识别则跳过，
//!   对齐 Python `if category:` 分支）。
//! - 保存语义（对齐 Python `save_data`）：按 name 查找或创建 BudgetPlan；
//!   对每个类别按 (plan_id, category, parent_id IS NULL) 查找或创建占位行；
//!   然后 DELETE 占位行的全部旧子项，重新 INSERT 直接子项。
//! - 删除语义（对齐 Python `delete_item`）：顶层删除整棵计划（级联 items）；
//!   条目按 (plan, category, name) 精确匹配删除；类别节点由前端禁止删除。
//! - 与 Python 一致：保存/删除 **不写 actionlogs**。

use std::collections::HashMap;

use rusqlite::{params, Connection, OptionalExtension, Transaction};

use crate::models::BudgetPlan;
use crate::DbError;

/// 10 个预算类别中文 label（顺序与 Python `BudgetCategory` 枚举一致，前端渲染/导出用）。
pub const BUDGET_CATEGORY_LABELS: [&str; 10] = [
    "设备费",
    "材料费",
    "外协费",
    "燃动费",
    "会议差旅费",
    "出版文献费",
    "劳务费",
    "专家咨询费",
    "其他支出",
    "间接费用",
];

/// 10 个预算类别存储 KEY（与 `BUDGET_CATEGORY_LABELS` 顺序一一对应）。
pub const BUDGET_CATEGORY_KEYS: [&str; 10] = [
    "EQUIPMENT",
    "MATERIAL",
    "OUTSOURCING",
    "FUEL",
    "CONFERENCE",
    "PUBLICATION",
    "LABOR",
    "CONSULTING",
    "MISCELLANEOUS",
    "INDIRECT",
];

/// 中文 label → 存储 KEY（SQLAlchemy Enum 名称）。未识别返回 None（对齐 Python 跳过保存）。
fn to_category_key(label: &str) -> Option<&'static str> {
    match label {
        "设备费" => Some("EQUIPMENT"),
        "材料费" => Some("MATERIAL"),
        "外协费" => Some("OUTSOURCING"),
        "燃动费" => Some("FUEL"),
        "会议差旅费" => Some("CONFERENCE"),
        "出版文献费" => Some("PUBLICATION"),
        "劳务费" => Some("LABOR"),
        "专家咨询费" => Some("CONSULTING"),
        "其他支出" => Some("MISCELLANEOUS"),
        "间接费用" => Some("INDIRECT"),
        _ => None,
    }
}

/// 存储 KEY → 中文 label。未识别原样返回。
fn category_to_label(key: &str) -> String {
    match key {
        "EQUIPMENT" => "设备费",
        "MATERIAL" => "材料费",
        "OUTSOURCING" => "外协费",
        "FUEL" => "燃动费",
        "CONFERENCE" => "会议差旅费",
        "PUBLICATION" => "出版文献费",
        "LABOR" => "劳务费",
        "CONSULTING" => "专家咨询费",
        "MISCELLANEOUS" => "其他支出",
        "INDIRECT" => "间接费用",
        _ => key,
    }
    .to_string()
}

/// 预算计划树（顶层节点，对应 Python 的顶级 QTreeWidgetItem）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetPlanNode {
    pub id: i64,
    pub name: String,
    pub total_amount: f64,
    pub remarks: String,
    pub categories: Vec<BudgetCategoryNode>,
}

/// 类别节点（第二级，对应 Python 的类别 QTreeWidgetItem）。
/// `category` 为中文 label；`amount`/`remarks` 来自 DB 占位行（无占位行则为 0 / 空）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetCategoryNode {
    pub category: String,
    pub amount: f64,
    pub remarks: String,
    pub items: Vec<BudgetPlanItemNode>,
}

/// 预算条目（第三级，对应 Python 的叶子 QTreeWidgetItem；金额单位为元）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetPlanItemNode {
    pub id: i64,
    pub name: String,
    pub specification: String,
    pub unit_price: f64,
    pub quantity: i64,
    pub amount: f64,
    pub remarks: String,
}

/// 保存一个顶层预算计划（前端整树序列化传入）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetPlanSave {
    pub name: String,
    pub total_amount: f64,
    pub remarks: Option<String>,
    pub categories: Vec<BudgetCategorySave>,
}

/// 保存一个类别（`category` 为中文 label；amount/remarks 为类别合计与备注）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetCategorySave {
    pub category: String,
    pub amount: f64,
    pub remarks: Option<String>,
    pub items: Vec<BudgetPlanItemSave>,
}

/// 保存一个预算条目。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetPlanItemSave {
    pub name: String,
    pub specification: Option<String>,
    pub unit_price: f64,
    pub quantity: i64,
    pub amount: f64,
    pub remarks: Option<String>,
}

/// 列出全部预算计划树（无显式 ORDER BY，对齐 Python `load_budget_plans`）。
///
/// 每个计划固定包含 10 个类别节点（无占位行的类别金额为 0、备注为空、条目为空），
/// 与 Python 逐 `BudgetCategory` 建行的行为一致；条目仅加载占位行的直接子项
/// （对齐 UI 三级约束与保存语义）。
pub fn list_budget_plans(conn: &Connection) -> Result<Vec<BudgetPlanNode>, DbError> {
    let mut stmt = conn.prepare("SELECT id, name, create_date, total_amount, remarks FROM budget_plans")?;
    let plans = stmt.query_map([], BudgetPlan::from_row)?;
    let mut nodes = Vec::new();
    for plan in plans {
        let plan = plan?;
        let categories = load_categories(conn, plan.id)?;
        nodes.push(BudgetPlanNode {
            id: plan.id,
            name: plan.name,
            total_amount: plan.total_amount.unwrap_or(0.0),
            remarks: plan.remarks.unwrap_or_default(),
            categories,
        });
    }
    Ok(nodes)
}

/// 加载某计划下的 10 个类别节点（含占位行合计/备注与其直接子项条目）。
fn load_categories(conn: &Connection, plan_id: i64) -> Result<Vec<BudgetCategoryNode>, DbError> {
    let mut stmt = conn.prepare(
        "SELECT id, plan_id, parent_id, category, name, specification, unit_price, \
         quantity, amount, remarks FROM budget_plan_items WHERE plan_id = ?1",
    )?;
    let rows = stmt.query_map([plan_id], |r| {
        Ok(crate::models::BudgetPlanItem {
            id: r.get("id")?,
            plan_id: r.get("plan_id")?,
            parent_id: r.get("parent_id")?,
            category: r.get("category")?,
            name: r.get("name")?,
            specification: r.get("specification")?,
            unit_price: r.get("unit_price")?,
            quantity: r.get("quantity")?,
            amount: r.get("amount")?,
            remarks: r.get("remarks")?,
        })
    })?;

    // 按 parent_id 分桶：&None → 类别占位行；&Some(id) → 该占位行的子项
    let mut by_parent: HashMap<Option<i64>, Vec<crate::models::BudgetPlanItem>> = HashMap::new();
    for row in rows {
        let item = row?;
        by_parent.entry(item.parent_id).or_default().push(item);
    }

    let mut categories = Vec::with_capacity(BUDGET_CATEGORY_KEYS.len());
    for key in BUDGET_CATEGORY_KEYS {
        // 类别的占位行（parent_id 为空；Python 取 filter 结果的第一个）
        let placeholder = by_parent
            .get(&None)
            .and_then(|items| items.iter().find(|i| i.category.as_deref() == Some(key)));

        let items = match placeholder {
            Some(p) => build_items(&by_parent, p.id),
            None => Vec::new(),
        };
        let node = BudgetCategoryNode {
            category: category_to_label(key),
            amount: placeholder.map(|p| p.amount.unwrap_or(0.0)).unwrap_or(0.0),
            remarks: placeholder.map(|p| p.remarks.clone().unwrap_or_default()).unwrap_or_default(),
            items,
        };
        categories.push(node);
    }
    Ok(categories)
}

/// 取占位行的直接子项（仅一层，对齐 UI 三级约束；条目字段转为展示用的非空值）。
fn build_items(
    by_parent: &HashMap<Option<i64>, Vec<crate::models::BudgetPlanItem>>,
    parent_id: i64,
) -> Vec<BudgetPlanItemNode> {
    by_parent
        .get(&Some(parent_id))
        .map(|items| {
            items
                .iter()
                .map(|i| BudgetPlanItemNode {
                    id: i.id,
                    name: i.name.clone().unwrap_or_default(),
                    specification: i.specification.clone().unwrap_or_default(),
                    unit_price: i.unit_price.unwrap_or(0.0),
                    quantity: i.quantity.unwrap_or(0),
                    amount: i.amount.unwrap_or(0.0),
                    remarks: i.remarks.clone().unwrap_or_default(),
                })
                .collect()
        })
        .unwrap_or_default()
}

/// 保存全部顶层预算计划（单个事务，对齐 Python `save_data` 的一次 commit）。
///
/// 每个计划按 name 查找或创建；每个类别按 (plan_id, category, parent_id IS NULL)
/// 查找或创建占位行，随后删除占位行的全部旧子项并重新插入新子项。
/// 类别 label 无法识别为内置类别时整类跳过（对齐 Python `if category:`）。
pub fn save_budget_plans(conn: &mut Connection, plans: &[BudgetPlanSave]) -> Result<(), DbError> {
    let tx = conn.transaction()?;
    for plan in plans {
        let plan_id = upsert_plan(&tx, plan)?;
        for cat in &plan.categories {
            let Some(key) = to_category_key(&cat.category) else {
                continue; // 非标准类别行（如「请输入该级预算名称」）跳过，对齐 Python
            };
            let placeholder_id = upsert_placeholder(&tx, plan_id, key, cat)?;
            // 删除占位行的全部旧子项（对齐 Python：filter_by(plan_id, category, parent_id).delete()）
            tx.execute(
                "DELETE FROM budget_plan_items WHERE plan_id = ?1 AND category = ?2 AND parent_id = ?3",
                params![plan_id, key, placeholder_id],
            )?;
            // 重新插入直接子项
            for item in &cat.items {
                tx.execute(
                    "INSERT INTO budget_plan_items \
                     (plan_id, parent_id, category, name, specification, unit_price, quantity, amount, remarks) \
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
                    params![
                        plan_id,
                        placeholder_id,
                        key,
                        item.name,
                        item.specification,
                        item.unit_price,
                        item.quantity,
                        item.amount,
                        item.remarks,
                    ],
                )?;
            }
        }
    }
    tx.commit()?;
    Ok(())
}

/// 按 name 查找或创建预算计划，返回其 id。新建时补 create_date（对齐 Python 默认当天）。
fn upsert_plan(tx: &Transaction, plan: &BudgetPlanSave) -> Result<i64, DbError> {
    let existing: Option<i64> = tx
        .query_row(
            "SELECT id FROM budget_plans WHERE name = ?1",
            [&plan.name],
            |r| r.get(0),
        )
        .optional()?;
    match existing {
        Some(id) => {
            tx.execute(
                "UPDATE budget_plans SET total_amount = ?1, remarks = ?2 WHERE id = ?3",
                params![plan.total_amount, plan.remarks, id],
            )?;
            Ok(id)
        }
        None => {
            let today = chrono::Local::now().format("%Y-%m-%d").to_string();
            tx.execute(
                "INSERT INTO budget_plans (name, create_date, total_amount, remarks) VALUES (?1, ?2, ?3, ?4)",
                params![plan.name, today, plan.total_amount, plan.remarks],
            )?;
            Ok(tx.last_insert_rowid())
        }
    }
}

/// 按 (plan_id, category, parent_id IS NULL) 查找或创建类别占位行，返回其 id。
/// 占位行只写 category/amount/remarks（name 等为空，对齐 Python）。
fn upsert_placeholder(
    tx: &Transaction,
    plan_id: i64,
    key: &str,
    cat: &BudgetCategorySave,
) -> Result<i64, DbError> {
    let existing: Option<i64> = tx
        .query_row(
            "SELECT id FROM budget_plan_items \
             WHERE plan_id = ?1 AND category = ?2 AND parent_id IS NULL",
            params![plan_id, key],
            |r| r.get(0),
        )
        .optional()?;
    match existing {
        Some(id) => {
            tx.execute(
                "UPDATE budget_plan_items SET amount = ?1, remarks = ?2 WHERE id = ?3",
                params![cat.amount, cat.remarks, id],
            )?;
            Ok(id)
        }
        None => {
            tx.execute(
                "INSERT INTO budget_plan_items (plan_id, category, amount, remarks) VALUES (?1, ?2, ?3, ?4)",
                params![plan_id, key, cat.amount, cat.remarks],
            )?;
            Ok(tx.last_insert_rowid())
        }
    }
}

/// 删除整个预算计划（按 name）：级联删除其全部 items 再删计划本身，
/// 对齐 Python `delete_item` 顶层分支（SQLAlchemy cascade="all, delete-orphan"）。
/// 计划不存在时静默成功（对齐 Python：查不到则仅删除 UI 行）。
pub fn delete_budget_plan(conn: &mut Connection, name: &str) -> Result<(), DbError> {
    let tx = conn.transaction()?;
    let id: Option<i64> = tx
        .query_row("SELECT id FROM budget_plans WHERE name = ?1", [name], |r| r.get(0))
        .optional()?;
    if let Some(id) = id {
        tx.execute("DELETE FROM budget_plan_items WHERE plan_id = ?1", [id])?;
        tx.execute("DELETE FROM budget_plans WHERE id = ?1", [id])?;
    }
    tx.commit()?;
    Ok(())
}

/// 删除一条预算条目（第三级）：按 (plan_name, category label, item name) 精确匹配删除，
/// 对齐 Python `delete_item` 条目分支（不级联子项，第三条目无子项）。
/// 计划不存在或类别非内置时静默成功（Python 同：查不到仅删 UI）。
pub fn delete_budget_plan_item(
    conn: &Connection,
    plan_name: &str,
    category_label: &str,
    item_name: &str,
) -> Result<(), DbError> {
    let Some(key) = to_category_key(category_label) else {
        return Ok(());
    };
    let plan_id: Option<i64> = conn
        .query_row(
            "SELECT id FROM budget_plans WHERE name = ?1",
            [plan_name],
            |r| r.get(0),
        )
        .optional()?;
    let Some(plan_id) = plan_id else {
        return Ok(());
    };
    conn.execute(
        "DELETE FROM budget_plan_items WHERE plan_id = ?1 AND category = ?2 AND name = ?3",
        params![plan_id, key, item_name],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::schema;
    use rusqlite::Connection;

    /// 与应用行为一致：外键关闭
    fn test_conn() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        let mut conn = conn;
        schema::create_all(&mut conn).unwrap();
        conn
    }

    fn item(name: &str, price: f64, qty: i64) -> BudgetPlanItemSave {
        BudgetPlanItemSave {
            name: name.to_string(),
            specification: Some("规格X".to_string()),
            unit_price: price,
            quantity: qty,
            amount: price * qty as f64,
            remarks: Some("备注".to_string()),
        }
    }

    fn category(label: &str, amount: f64, items: Vec<BudgetPlanItemSave>) -> BudgetCategorySave {
        BudgetCategorySave {
            category: label.to_string(),
            amount,
            remarks: Some("类别备注".to_string()),
            items,
        }
    }

    fn plan(name: &str, total: f64, categories: Vec<BudgetCategorySave>) -> BudgetPlanSave {
        BudgetPlanSave {
            name: name.to_string(),
            total_amount: total,
            remarks: Some("计划备注".to_string()),
            categories,
        }
    }

    #[test]
    fn save_and_list_tree_round_trip() {
        let mut conn = test_conn();
        let plans = vec![plan(
            "课题A",
            320000.0,
            vec![
                category(
                    "设备费",
                    300000.0,
                    vec![item("设备A", 100000.0, 2), item("设备B", 50000.0, 2)],
                ),
                category("材料费", 20000.0, vec![item("材料C", 1000.0, 20)]),
            ],
        )];
        save_budget_plans(&mut conn, &plans).unwrap();

        let trees = list_budget_plans(&conn).unwrap();
        assert_eq!(trees.len(), 1);
        let t = &trees[0];
        assert_eq!(t.name, "课题A");
        assert_eq!(t.total_amount, 320000.0);
        assert_eq!(t.remarks, "计划备注");

        // 固定 10 个类别，顺序与 Python 枚举一致
        assert_eq!(t.categories.len(), 10);
        assert_eq!(t.categories[0].category, "设备费");
        assert_eq!(t.categories[0].amount, 300000.0);
        assert_eq!(t.categories[0].items.len(), 2);
        let it = &t.categories[0].items[0];
        assert_eq!(it.name, "设备A");
        assert_eq!(it.unit_price, 100000.0);
        assert_eq!(it.quantity, 2);
        assert_eq!(it.amount, 200000.0);
        assert_eq!(t.categories[1].category, "材料费");
        assert_eq!(t.categories[1].items[0].name, "材料C");

        // 未保存类别的节点为空金额/空条目
        assert_eq!(t.categories[2].category, "外协费");
        assert_eq!(t.categories[2].amount, 0.0);
        assert!(t.categories[2].items.is_empty());

        // 落库的 category 应为存储 KEY
        let stored: String = conn
            .query_row(
                "SELECT category FROM budget_plan_items WHERE name = '设备A'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(stored, "EQUIPMENT");
    }

    #[test]
    fn save_updates_existing_plan_and_replaces_children() {
        let mut conn = test_conn();
        let plans = vec![plan(
            "课题B",
            100.0,
            vec![category("设备费", 100.0, vec![item("旧项", 10.0, 10)])],
        )];
        save_budget_plans(&mut conn, &plans).unwrap();

        // 二次保存：改金额 + 类别备注 + 替换子项（去掉旧项、加新项）
        let plans2 = vec![plan(
            "课题B",
            200.0,
            vec![category("设备费", 200.0, vec![item("新项", 20.0, 10)])],
        )];
        save_budget_plans(&mut conn, &plans2).unwrap();

        // plan 仍只有一行（按 name 复用）
        let plan_count: i64 = conn
            .query_row("SELECT COUNT(*) FROM budget_plans WHERE name = '课题B'", [], |r| r.get(0))
            .unwrap();
        assert_eq!(plan_count, 1);

        let trees = list_budget_plans(&conn).unwrap();
        let t = &trees[0];
        assert_eq!(t.total_amount, 200.0);
        let eq = &t.categories[0];
        assert_eq!(eq.amount, 200.0);
        assert_eq!(eq.remarks, "类别备注");
        assert_eq!(eq.items.len(), 1);
        assert_eq!(eq.items[0].name, "新项");
        assert_eq!(eq.items[0].amount, 200.0);

        // 占位行不重复（每个类别仅一行 parent_id IS NULL）
        let ph_count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_plan_items \
                 WHERE plan_id = (SELECT id FROM budget_plans WHERE name = '课题B') \
                   AND category = 'EQUIPMENT' AND parent_id IS NULL",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(ph_count, 1);
    }

    #[test]
    fn save_skips_unknown_category_label() {
        let mut conn = test_conn();
        let plans = vec![plan(
            "课题C",
            50.0,
            vec![
                category("设备费", 30.0, vec![item("实物", 30.0, 1)]),
                category("未知类别", 20.0, vec![item("忽略我", 20.0, 1)]),
            ],
        )];
        save_budget_plans(&mut conn, &plans).unwrap();

        let trees = list_budget_plans(&conn).unwrap();
        let eq = &trees[0].categories[0];
        assert_eq!(eq.items.len(), 1);
        assert_eq!(eq.items[0].name, "实物");

        // 未知类别整类未落库
        let ui_count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_plan_items WHERE name = '忽略我'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(ui_count, 0);
    }

    #[test]
    fn delete_plan_cascades_items() {
        let mut conn = test_conn();
        let plans = vec![plan(
            "课题D",
            300.0,
            vec![category("设备费", 300.0, vec![item("机台", 300.0, 1)])],
        )];
        save_budget_plans(&mut conn, &plans).unwrap();

        delete_budget_plan(&mut conn, "课题D").unwrap();
        let trees = list_budget_plans(&conn).unwrap();
        assert!(trees.is_empty());

        let items: i64 = conn
            .query_row("SELECT COUNT(*) FROM budget_plan_items", [], |r| r.get(0))
            .unwrap();
        assert_eq!(items, 0);

        // 不存在的计划静默成功
        delete_budget_plan(&mut conn, "不存在").unwrap();
    }

    #[test]
    fn delete_item_by_plan_category_name() {
        let mut conn = test_conn();
        let plans = vec![plan(
            "课题E",
            60.0,
            vec![
                category("设备费", 30.0, vec![item("删除项", 30.0, 1)]),
                category("材料费", 30.0, vec![item("保留项", 30.0, 1)]),
            ],
        )];
        save_budget_plans(&mut conn, &plans).unwrap();

        delete_budget_plan_item(&conn, "课题E", "设备费", "删除项").unwrap();

        let t = &list_budget_plans(&conn).unwrap()[0];
        assert_eq!(t.categories[0].items.len(), 0);
        assert_eq!(t.categories[1].items.len(), 1);
        assert_eq!(t.categories[1].items[0].name, "保留项");

        // 计划/类别/条目任意缺失均静默成功
        delete_budget_plan_item(&conn, "不存在", "设备费", "删除项").unwrap();
        delete_budget_plan_item(&conn, "课题E", "未知类别", "删除项").unwrap();
        delete_budget_plan_item(&conn, "课题E", "设备费", "不存在项").unwrap();
    }

    #[test]
    fn category_key_label_round_trip() {
        for label in BUDGET_CATEGORY_LABELS {
            let key = to_category_key(label).unwrap();
            assert_eq!(category_to_label(key), label, "label {label}");
        }
        // 兜底：未识别返回 None / 原样
        assert!(to_category_key("未知").is_none());
        assert_eq!(category_to_label("UNKNOWN"), "UNKNOWN");
    }
}