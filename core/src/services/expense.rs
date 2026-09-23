//! 支出服务
//!
//! 业务核心：
//! - 支出（expenses.amount）单位是「元」
//! - 预算（budgets.spent_amount / budget_items.spent_amount）单位是「万元」
//! - 联动公式：spent_amount += amount / 10000
//!
//! 所有写操作在事务内完成，保证 expenses 与 budgets/budget_items 一致。

use rusqlite::{params, Connection, OptionalExtension};

use crate::excel::ParsedExpense;
use crate::models::{BudgetCategory, Expense};
use crate::DbError;

/// 新增/编辑支出输入。
///
/// `category` 字段从前端传入中文 label（如「材料费」），service 内转 storage_key（MATERIAL）入库。
/// `amount` 单位为元。`date` 格式 YYYY-MM-DD。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ExpenseInput {
    pub project_id: i64,
    pub budget_id: i64,
    pub category: String,
    pub content: String,
    pub specification: Option<String>,
    pub supplier: Option<String>,
    pub amount: f64,
    pub date: String,
    pub remarks: Option<String>,
    pub voucher_path: Option<String>,
}

/// 中文 label → 英文 storage_key；未识别返回原值（兜底，应不会发生）
fn to_storage_key(label: &str) -> String {
    BudgetCategory::from_label(label)
        .map(|c| c.storage_key().to_string())
        .unwrap_or_else(|| label.to_string())
}

/// 英文 storage_key → 中文 label
fn to_label(key: &str) -> String {
    BudgetCategory::from_storage_key(key)
        .map(|c| c.label().to_string())
        .unwrap_or_else(|| key.to_string())
}

/// 列出某预算下所有支出（按 date DESC）
pub fn list_expenses_by_budget(conn: &Connection, budget_id: i64) -> Result<Vec<Expense>, DbError> {
    let mut stmt = conn.prepare(
        "SELECT id, project_id, budget_id, category, content, specification, supplier, \
         amount, date, remarks, voucher_path \
         FROM expenses WHERE budget_id = ?1 ORDER BY date DESC",
    )?;
    let rows = stmt.query_map([budget_id], |r| {
        let category_key: String = r.get(3)?;
        Ok(Expense {
            id: r.get(0)?,
            project_id: r.get(1)?,
            budget_id: r.get(2)?,
            category: to_label(&category_key),
            content: r.get(4)?,
            specification: r.get(5)?,
            supplier: r.get(6)?,
            amount: r.get(7)?,
            date: r.get(8)?,
            remarks: r.get(9)?,
            voucher_path: r.get(10)?,
        })
    })?;
    let mut expenses = Vec::new();
    for row in rows {
        expenses.push(row?);
    }
    Ok(expenses)
}

/// 项目某科目的支出行（附所属预算年度，供总预算科目跨年度查询）。
#[derive(Debug, Clone, serde::Serialize)]
pub struct ProjectExpenseRow {
    pub id: i64,
    /// 所属年度预算的年份；支出挂在总预算行（year NULL）时为 None
    pub year: Option<i64>,
    /// 中文 label（storage_key 反查）
    pub category: String,
    pub content: String,
    pub specification: Option<String>,
    pub supplier: Option<String>,
    /// 单位：元
    pub amount: Option<f64>,
    pub date: Option<String>,
    pub remarks: Option<String>,
    pub voucher_path: Option<String>,
}

/// 按项目 + 科目列出支出，按日期倒序。
///
/// `category_label` 为中文 label（如「材料费」），内部转 storage_key 匹配库内存储值。
/// `budget_id` 为 Some 时只返回该预算下的支出（年度预算行入口用），None 则跨全部年度（总预算行入口用）。
pub fn list_project_expenses_by_category(
    conn: &Connection,
    project_id: i64,
    category_label: &str,
    budget_id: Option<i64>,
) -> Result<Vec<ProjectExpenseRow>, DbError> {
    let key = to_storage_key(category_label);
    let mut sql = String::from(
        "SELECT e.id, b.year, e.category, e.content, e.specification, e.supplier, \
         e.amount, e.date, e.remarks, e.voucher_path \
         FROM expenses e LEFT JOIN budgets b ON e.budget_id = b.id \
         WHERE e.project_id = ?1 AND e.category = ?2",
    );
    if budget_id.is_some() {
        sql.push_str(" AND e.budget_id = ?3");
    }
    sql.push_str(" ORDER BY e.date DESC, e.id DESC");

    let mut stmt = conn.prepare(&sql)?;
    let map_row = |r: &rusqlite::Row| -> rusqlite::Result<ProjectExpenseRow> {
        let category_key: String = r.get(2)?;
        Ok(ProjectExpenseRow {
            id: r.get(0)?,
            year: r.get(1)?,
            category: to_label(&category_key),
            content: r.get(3)?,
            specification: r.get(4)?,
            supplier: r.get(5)?,
            amount: r.get(6)?,
            date: r.get(7)?,
            remarks: r.get(8)?,
            voucher_path: r.get(9)?,
        })
    };
    let mut expenses = Vec::new();
    match budget_id {
        Some(bid) => {
            let rows = stmt.query_map(params![project_id, key, bid], map_row)?;
            for row in rows {
                expenses.push(row?);
            }
        }
        None => {
            let rows = stmt.query_map(params![project_id, key], map_row)?;
            for row in rows {
                expenses.push(row?);
            }
        }
    }
    Ok(expenses)
}

/// 按 id 查支出（编辑回填用）。返回的 category 是中文 label。
pub fn get_expense_by_id(conn: &Connection, id: i64) -> Result<Option<Expense>, DbError> {
    let row = conn
        .query_row(
            "SELECT id, project_id, budget_id, category, content, specification, supplier, \
             amount, date, remarks, voucher_path \
             FROM expenses WHERE id = ?1",
            [id],
            |r| {
                let category_key: String = r.get(3)?;
                Ok(Expense {
                    id: r.get(0)?,
                    project_id: r.get(1)?,
                    budget_id: r.get(2)?,
                    category: to_label(&category_key),
                    content: r.get(4)?,
                    specification: r.get(5)?,
                    supplier: r.get(6)?,
                    amount: r.get(7)?,
                    date: r.get(8)?,
                    remarks: r.get(9)?,
                    voucher_path: r.get(10)?,
                })
            },
        )
        .optional()?;
    Ok(row)
}

/// 新增支出（事务）：
/// 1. INSERT expenses
/// 2. budgets.spent_amount += amount / 10000
/// 3. budget_items(budget_id + category).spent_amount += amount / 10000
///
/// 返回新支出 id。
pub fn add_expense(conn: &Connection, input: ExpenseInput) -> Result<i64, DbError> {
    crate::db::begin_tx(conn)?;
    let result = add_expense_inner(conn, input);
    match result {
        Ok(id) => {
            conn.execute_batch("COMMIT")?;
            Ok(id)
        }
        Err(e) => {
            let _ = conn.execute_batch("ROLLBACK");
            Err(e)
        }
    }
}

/// 查预算所属项目的 (year, financial_code)，用于拼接支出日志 related_info
/// （"项目: {financial_code}, 预算: {year}"）。
fn budget_year_and_code(conn: &Connection, budget_id: i64) -> Result<(i64, Option<String>), DbError> {
    Ok(conn
        .query_row(
            "SELECT b.year, p.financial_code FROM budgets b \
             JOIN projects p ON p.id = b.project_id WHERE b.id = ?1",
            [budget_id],
            |r| Ok((r.get::<_, i64>(0)?, r.get::<_, Option<String>>(1)?)),
        )
        .optional()?
        .unwrap_or((0, None)))
}

/// 写支出操作日志：
/// type="支出"，operator="系统用户"，含 category/amount/related_info 扩展字段。
fn write_expense_log(
    conn: &Connection,
    input: &ExpenseInput,
    expense_id: Option<i64>,
    action: &str,
    description: &str,
    old_data: Option<&str>,
    new_data: Option<&str>,
) -> Result<(), DbError> {
    let (year, financial_code) = budget_year_and_code(conn, input.budget_id)?;
    let category_label = to_label(&to_storage_key(&input.category));
    crate::logging::log_action(
        conn,
        Some(input.project_id),
        Some(input.budget_id),
        expense_id,
        None,
        None,
        None,
        "支出",
        action,
        description,
        "系统用户",
        old_data,
        new_data,
        Some(&category_label),
        Some(input.amount),
        Some(&format!(
            "项目: {}, 预算: {}",
            financial_code.as_deref().unwrap_or(""),
            year
        )),
    )?;
    Ok(())
}

/// 插入支出行并联动预算（供单条添加与批量导入共用，不写日志）。
fn insert_expense_row(conn: &Connection, input: &ExpenseInput) -> Result<i64, DbError> {
    let storage_key = to_storage_key(&input.category);
    conn.execute(
        "INSERT INTO expenses (project_id, budget_id, category, content, specification, \
         supplier, amount, date, remarks, voucher_path) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
        params![
            input.project_id,
            input.budget_id,
            storage_key,
            input.content,
            input.specification,
            input.supplier,
            input.amount,
            input.date,
            input.remarks,
            input.voucher_path,
        ],
    )?;
    let expense_id = conn.last_insert_rowid();

    let amount_wan = input.amount / 10000.0;
    conn.execute(
        "UPDATE budgets SET spent_amount = COALESCE(spent_amount, 0) + ?1 WHERE id = ?2",
        params![amount_wan, input.budget_id],
    )?;
    conn.execute(
        "UPDATE budget_items SET spent_amount = COALESCE(spent_amount, 0) + ?1 \
         WHERE budget_id = ?2 AND category = ?3",
        params![amount_wan, input.budget_id, storage_key],
    )?;
    Ok(expense_id)
}

/// 新增支出（事务内）：插入 + 联动预算 + "添加"日志。
/// description 为"添加支出：{content}，金额：{amount:.2f}元"。
fn add_expense_inner(conn: &Connection, input: ExpenseInput) -> Result<i64, DbError> {
    let expense_id = insert_expense_row(conn, &input)?;
    let description = format!("添加支出：{}，金额：{:.2}元", input.content, input.amount);
    write_expense_log(conn, &input, Some(expense_id), "添加", &description, None, None)?;
    Ok(expense_id)
}

/// 更新支出（事务）：
/// - 类别变化：旧类别 budget_items.spent_amount -= old_amount/10000，新类别 += new_amount/10000
/// - 类别不变：budget_items.spent_amount += diff/10000
/// - budgets.spent_amount += diff/10000（总与项目级支出联动）
pub fn update_expense(conn: &Connection, id: i64, input: ExpenseInput) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = update_expense_inner(conn, id, input);
    match result {
        Ok(_) => {
            conn.execute_batch("COMMIT")?;
            Ok(())
        }
        Err(e) => {
            let _ = conn.execute_batch("ROLLBACK");
            Err(e)
        }
    }
}

fn update_expense_inner(conn: &Connection, id: i64, input: ExpenseInput) -> Result<(), DbError> {
    // 查旧记录（完整字段，供 old_data 日志）
    let old: Option<(
        String,
        String,
        Option<String>,
        Option<String>,
        f64,
        Option<String>,
        Option<String>,
        Option<String>,
    )> = conn
        .query_row(
            "SELECT category, content, specification, supplier, amount, date, remarks, \
             voucher_path FROM expenses WHERE id = ?1",
            [id],
            |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, Option<String>>(2)?,
                    r.get::<_, Option<String>>(3)?,
                    r.get::<_, f64>(4)?,
                    r.get::<_, Option<String>>(5)?,
                    r.get::<_, Option<String>>(6)?,
                    r.get::<_, Option<String>>(7)?,
                ))
            },
        )
        .optional()?;
    let Some((
        old_cat_key,
        old_content,
        old_spec,
        old_supplier,
        old_amount,
        old_date,
        old_remarks,
        old_voucher,
    )) = old
    else {
        return Err(DbError::Other(format!("支出 id={id} 不存在")));
    };

    let new_cat_key = to_storage_key(&input.category);
    let diff = input.amount - old_amount;
    let category_changed = old_cat_key != new_cat_key;

    // UPDATE expenses
    conn.execute(
        "UPDATE expenses SET category = ?1, content = ?2, specification = ?3, supplier = ?4, \
         amount = ?5, date = ?6, remarks = ?7, voucher_path = ?8 WHERE id = ?9",
        params![
            new_cat_key,
            input.content,
            input.specification,
            input.supplier,
            input.amount,
            input.date,
            input.remarks,
            input.voucher_path,
            id,
        ],
    )?;

    let old_wan = old_amount / 10000.0;
    let new_wan = input.amount / 10000.0;

    if category_changed {
        // 旧类别减旧金额
        conn.execute(
            "UPDATE budget_items SET spent_amount = COALESCE(spent_amount, 0) - ?1 \
             WHERE budget_id = ?2 AND category = ?3",
            params![old_wan, input.budget_id, old_cat_key],
        )?;
        // 新类别加新金额
        conn.execute(
            "UPDATE budget_items SET spent_amount = COALESCE(spent_amount, 0) + ?1 \
             WHERE budget_id = ?2 AND category = ?3",
            params![new_wan, input.budget_id, new_cat_key],
        )?;
        // budgets.spent_amount 调差额（=new-old）
        conn.execute(
            "UPDATE budgets SET spent_amount = COALESCE(spent_amount, 0) + ?1 WHERE id = ?2",
            params![new_wan - old_wan, input.budget_id],
        )?;
    } else {
        // 同类别：budget_items 与 budgets 均按差额调整
        conn.execute(
            "UPDATE budget_items SET spent_amount = COALESCE(spent_amount, 0) + ?1 \
             WHERE budget_id = ?2 AND category = ?3",
            params![diff / 10000.0, input.budget_id, new_cat_key],
        )?;
        conn.execute(
            "UPDATE budgets SET spent_amount = COALESCE(spent_amount, 0) + ?1 WHERE id = ?2",
            params![diff / 10000.0, input.budget_id],
        )?;
    }

    // 写"编辑"操作日志（old_data/new_data 为完整字段 JSON）
    let old_data = serde_json::json!({
        "category": to_label(&old_cat_key),
        "content": old_content,
        "specification": old_spec,
        "supplier": old_supplier,
        "amount": old_amount,
        "date": old_date,
        "remarks": old_remarks,
        "voucher_path": old_voucher,
    });
    let new_data = serde_json::json!({
        "category": input.category,
        "content": input.content,
        "specification": input.specification,
        "supplier": input.supplier,
        "amount": input.amount,
        "date": input.date,
        "remarks": input.remarks,
        "voucher_path": input.voucher_path,
    });
    let description = format!("编辑支出ID {id}：{}，新金额：{:.2}元", input.content, input.amount);
    write_expense_log(
        conn,
        &input,
        Some(id),
        "编辑",
        &description,
        Some(&old_data.to_string()),
        Some(&new_data.to_string()),
    )?;
    Ok(())
}

/// 批量删除支出（事务）：
/// - 按 (category, sum(amount)) 累计回退 budget_items.spent_amount
/// - 总金额回退 budgets.spent_amount
///
/// 返回实际删除条数。
pub fn delete_expenses(conn: &Connection, ids: &[i64]) -> Result<usize, DbError> {
    if ids.is_empty() {
        return Ok(0);
    }
    crate::db::begin_tx(conn)?;
    let result = delete_expenses_inner(conn, ids);
    match result {
        Ok(n) => {
            conn.execute_batch("COMMIT")?;
            Ok(n)
        }
        Err(e) => {
            let _ = conn.execute_batch("ROLLBACK");
            Err(e)
        }
    }
}

/// 仅更新支出凭证路径（不动金额/类别，不触发预算联动）。
///
/// 供附件替换（replace）/删除（delete）后更新 `expense.voucher_path`：
/// 附件文件操作由 attachments 模块完成，
/// 此函数只把最新路径写入数据库（删除即传 `None`）。
pub fn update_expense_voucher(
    conn: &Connection,
    id: i64,
    voucher_path: Option<String>,
) -> Result<(), DbError> {
    conn.execute(
        "UPDATE expenses SET voucher_path = ?1 WHERE id = ?2",
        params![voucher_path, id],
    )?;
    Ok(())
}

fn delete_expenses_inner(conn: &Connection, ids: &[i64]) -> Result<usize, DbError> {
    // 按类别累计金额（同 budget_id，因支出挂在年度预算下）
    let mut category_sum: std::collections::HashMap<(i64, String), f64> = std::collections::HashMap::new();
    let mut total_wan = 0.0_f64;
    let mut deleted = 0_usize;

    for id in ids {
        // 联查预算/项目信息，供日志 related_info 与 old_data 使用
        let row: Option<(i64, i64, String, f64, String, Option<String>, i64, Option<String>)> =
            conn
                .query_row(
                    "SELECT e.budget_id, b.project_id, e.category, e.amount, e.content, \
                            e.date, b.year, p.financial_code \
                     FROM expenses e \
                     JOIN budgets b ON b.id = e.budget_id \
                     JOIN projects p ON p.id = b.project_id \
                     WHERE e.id = ?1",
                    [id],
                    |r| {
                        Ok((
                            r.get::<_, i64>(0)?,
                            r.get::<_, i64>(1)?,
                            r.get::<_, String>(2)?,
                            r.get::<_, f64>(3)?,
                            r.get::<_, String>(4)?,
                            r.get::<_, Option<String>>(5)?,
                            r.get::<_, i64>(6)?,
                            r.get::<_, Option<String>>(7)?,
                        ))
                    },
                )
                .optional()?;
        let Some((budget_id, project_id, cat_key, amount, content, date, year, financial_code)) =
            row
        else {
            continue; // id 不存在则跳过
        };
        *category_sum.entry((budget_id, cat_key.clone())).or_insert(0.0) += amount;
        total_wan += amount / 10000.0;
        deleted += 1;

        // 写"删除"日志（删除前记录，
        // old_data 含 category/content/amount/date，记录被删的 expense_id）
        let old_data = serde_json::json!({
            "category": to_label(&cat_key),
            "content": content,
            "amount": amount,
            "date": date,
        });
        crate::logging::log_action(
            conn,
            Some(project_id),
            Some(budget_id),
            Some(*id),
            None,
            None,
            None,
            "支出",
            "删除",
            &format!("删除支出ID {id}：{content}，金额：{amount:.2}元"),
            "系统用户",
            Some(&old_data.to_string()),
            None,
            Some(&to_label(&cat_key)),
            Some(amount),
            Some(&format!(
                "项目: {}, 预算: {}",
                financial_code.as_deref().unwrap_or(""),
                year
            )),
        )?;
    }

    // 先回退 budget_items 与 budgets（避免外键依赖触发）
    for ((budget_id, cat_key), sum) in &category_sum {
        conn.execute(
            "UPDATE budget_items SET spent_amount = COALESCE(spent_amount, 0) - ?1 \
             WHERE budget_id = ?2 AND category = ?3",
            params![sum / 10000.0, budget_id, cat_key],
        )?;
    }
    // 按 budget_id 累计回退 budgets.spent_amount
    let mut budget_total: std::collections::HashMap<i64, f64> = std::collections::HashMap::new();
    for ((budget_id, _), sum) in &category_sum {
        *budget_total.entry(*budget_id).or_insert(0.0) += sum / 10000.0;
    }
    for (budget_id, wan) in budget_total {
        conn.execute(
            "UPDATE budgets SET spent_amount = COALESCE(spent_amount, 0) - ?1 WHERE id = ?2",
            params![wan, budget_id],
        )?;
    }
    let _ = total_wan; // 仅记录用，不再单独使用

    // 删除 expenses 行
    let placeholders = ids.iter().map(|_| "?").collect::<Vec<_>>().join(",");
    let sql = format!("DELETE FROM expenses WHERE id IN ({placeholders})");
    let params: Vec<&dyn rusqlite::ToSql> = ids.iter().map(|id| id as &dyn rusqlite::ToSql).collect();
    let _ = conn.execute(&sql, params.as_slice())?;

    Ok(deleted)
}

/// 批量导入支出（事务）：逐条插入 + 联动预算，每条写"批量导入"日志。
///
/// description 为"批量导入支出：{content}，金额：{amount:.2f}元"。
/// items 为已解析/校验通过的支出列表（category 为中文 label、amount 单位为元）。
/// 返回实际导入条数。
pub fn batch_add_expenses(
    conn: &Connection,
    project_id: i64,
    budget_id: i64,
    items: &[ParsedExpense],
) -> Result<usize, DbError> {
    if items.is_empty() {
        return Ok(0);
    }
    crate::db::begin_tx(conn)?;
    let result = (|| -> Result<usize, DbError> {
        for item in items {
            let input = ExpenseInput {
                project_id,
                budget_id,
                category: item.category.clone(),
                content: item.content.clone(),
                specification: item.specification.clone(),
                supplier: item.supplier.clone(),
                amount: item.amount,
                date: item.date.clone(),
                remarks: item.remarks.clone(),
                voucher_path: None,
            };
            let expense_id = insert_expense_row(conn, &input)?;
            let description =
                format!("批量导入支出：{}，金额：{:.2}元", input.content, input.amount);
            write_expense_log(
                conn,
                &input,
                Some(expense_id),
                "批量导入",
                &description,
                None,
                None,
            )?;
        }
        Ok(items.len())
    })();
    match result {
        Ok(n) => {
            conn.execute_batch("COMMIT")?;
            Ok(n)
        }
        Err(e) => {
            let _ = conn.execute_batch("ROLLBACK");
            Err(e)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::schema;
    use crate::services::budget::{
        add_annual_budget, add_project_to_db, AnnualBudgetInput, BudgetItemInput,
    };
    use rusqlite::Connection;

    /// 与 budget.rs 测试一致：外键关闭
    fn test_conn() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        conn
    }

    /// 构造一个项目 + 2024 年度预算（总 1000，材料费科目 500）
    fn setup_project_with_annual_budget() -> (Connection, i64, i64) {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(
            &mut conn, "测试项目", None, None, None, None, None, None,
        )
        .unwrap();
        let bid = add_annual_budget(
            &conn,
            AnnualBudgetInput {
                project_id: pid,
                year: 2024,
                total_amount: 1000.0,
                items: BudgetCategory::ALL
                    .iter()
                    .map(|c| BudgetItemInput {
                        category: c.as_str().to_string(),
                        amount: if c.as_str() == "材料费" { 500.0 } else { 0.0 },
                    })
                    .collect(),
            },
        )
        .unwrap();
        (conn, pid, bid)
    }

    #[test]
    fn add_expense_updates_spent_amount() {
        let (conn, pid, bid) = setup_project_with_annual_budget();
        let input = ExpenseInput {
            project_id: pid,
            budget_id: bid,
            category: "材料费".to_string(),
            content: "试剂".to_string(),
            specification: None,
            supplier: None,
            amount: 10000.0, // 1 万元
            date: "2024-05-01".to_string(),
            remarks: None,
            voucher_path: None,
        };
        let expense_id = add_expense(&conn, input).unwrap();
        assert!(expense_id > 0);

        // budgets.spent_amount = 1.0（万元）
        let spent: f64 = conn
            .query_row("SELECT spent_amount FROM budgets WHERE id = ?1", [bid], |r| r.get(0))
            .unwrap();
        assert!((spent - 1.0).abs() < 1e-9);

        // budget_items.spent_amount = 1.0（材料费）
        let bi_spent: f64 = conn
            .query_row(
                "SELECT spent_amount FROM budget_items \
                 WHERE budget_id = ?1 AND category = 'MATERIAL'",
                [bid],
                |r| r.get(0),
            )
            .unwrap();
        assert!((bi_spent - 1.0).abs() < 1e-9);
    }

    #[test]
    fn update_expense_handles_category_change() {
        let (conn, pid, bid) = setup_project_with_annual_budget();
        // 先建一条材料费支出 10000 元（=1 万元）
        let eid = add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "试剂".to_string(),
                specification: None,
                supplier: None,
                amount: 10000.0,
                date: "2024-05-01".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();
        // 改成劳务费 20000 元（=2 万元）
        update_expense(
            &conn,
            eid,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "劳务费".to_string(),
                content: "学生劳务".to_string(),
                specification: None,
                supplier: None,
                amount: 20000.0,
                date: "2024-05-02".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();

        // 材料费 budget_items.spent_amount 应回 0
        let m_spent: f64 = conn
            .query_row(
                "SELECT spent_amount FROM budget_items \
                 WHERE budget_id = ?1 AND category = 'MATERIAL'",
                [bid],
                |r| r.get(0),
            )
            .unwrap();
        assert!(m_spent.abs() < 1e-9);

        // 劳务费 budget_items.spent_amount 应为 2.0
        let l_spent: f64 = conn
            .query_row(
                "SELECT spent_amount FROM budget_items \
                 WHERE budget_id = ?1 AND category = 'LABOR'",
                [bid],
                |r| r.get(0),
            )
            .unwrap();
        assert!((l_spent - 2.0).abs() < 1e-9);

        // budgets.spent_amount 应为 2.0
        let b_spent: f64 = conn
            .query_row("SELECT spent_amount FROM budgets WHERE id = ?1", [bid], |r| r.get(0))
            .unwrap();
        assert!((b_spent - 2.0).abs() < 1e-9);
    }

    #[test]
    fn delete_expenses_reverts_spent() {
        let (conn, pid, bid) = setup_project_with_annual_budget();
        let e1 = add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "试剂".to_string(),
                specification: None,
                supplier: None,
                amount: 10000.0,
                date: "2024-05-01".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();
        let e2 = add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "耗材".to_string(),
                specification: None,
                supplier: None,
                amount: 5000.0,
                date: "2024-05-02".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();

        let n = delete_expenses(&conn, &[e1, e2]).unwrap();
        assert_eq!(n, 2);

        let b_spent: f64 = conn
            .query_row("SELECT spent_amount FROM budgets WHERE id = ?1", [bid], |r| r.get(0))
            .unwrap();
        assert!(b_spent.abs() < 1e-9);

        let bi_spent: f64 = conn
            .query_row(
                "SELECT spent_amount FROM budget_items \
                 WHERE budget_id = ?1 AND category = 'MATERIAL'",
                [bid],
                |r| r.get(0),
            )
            .unwrap();
        assert!(bi_spent.abs() < 1e-9);
    }

    #[test]
    fn update_voucher_path_only_changes_path() {
        let (conn, pid, bid) = setup_project_with_annual_budget();
        let eid = add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "试剂".to_string(),
                specification: None,
                supplier: None,
                amount: 10000.0,
                date: "2024-05-01".to_string(),
                remarks: None,
                voucher_path: Some("/old/voucher.pdf".into()),
            },
        )
        .unwrap();

        // 更新为新的凭证路径
        update_expense_voucher(&conn, eid, Some("/new/voucher.pdf".into())).unwrap();
        let e = get_expense_by_id(&conn, eid).unwrap().unwrap();
        assert_eq!(e.voucher_path.as_deref(), Some("/new/voucher.pdf"));
        // 金额联动不应被破坏
        let spent: f64 = conn
            .query_row("SELECT spent_amount FROM budgets WHERE id = ?1", [bid], |r| r.get(0))
            .unwrap();
        assert!((spent - 1.0).abs() < 1e-9);

        // 删除凭证（置空）
        update_expense_voucher(&conn, eid, None).unwrap();
        let e = get_expense_by_id(&conn, eid).unwrap().unwrap();
        assert!(e.voucher_path.is_none());
    }

    #[test]
    fn list_expenses_orders_by_date_desc() {
        let (conn, pid, bid) = setup_project_with_annual_budget();
        add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "早".to_string(),
                specification: None,
                supplier: None,
                amount: 100.0,
                date: "2024-01-01".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();
        add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "晚".to_string(),
                specification: None,
                supplier: None,
                amount: 100.0,
                date: "2024-12-31".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();
        add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "中".to_string(),
                specification: None,
                supplier: None,
                amount: 100.0,
                date: "2024-06-15".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();

        let list = list_expenses_by_budget(&conn, bid).unwrap();
        assert_eq!(list.len(), 3);
        assert_eq!(list[0].content, "晚");
        assert_eq!(list[1].content, "中");
        assert_eq!(list[2].content, "早");
        // category 应为中文 label
        assert_eq!(list[0].category, "材料费");
    }

    /// 增/改/删/批导四种操作各写一条 actionlogs（type="支出"，
    /// 含 category/amount/related_info 扩展字段），对齐 budget_crud_writes_actionlog。
    #[test]
    fn expense_crud_writes_actionlog() {
        let (conn, pid, bid) = setup_project_with_annual_budget();

        // 1) 添加
        let eid = add_expense(
            &conn,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "试剂".to_string(),
                specification: None,
                supplier: None,
                amount: 10000.0,
                date: "2024-05-01".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();

        // 2) 编辑
        update_expense(
            &conn,
            eid,
            ExpenseInput {
                project_id: pid,
                budget_id: bid,
                category: "材料费".to_string(),
                content: "试剂(修订)".to_string(),
                specification: None,
                supplier: None,
                amount: 12000.0,
                date: "2024-05-02".to_string(),
                remarks: None,
                voucher_path: None,
            },
        )
        .unwrap();

        // 3) 删除
        let n = delete_expenses(&conn, &[eid]).unwrap();
        assert_eq!(n, 1);

        // 4) 批量导入
        let n = batch_add_expenses(
            &conn,
            pid,
            bid,
            &[
                ParsedExpense {
                    category: "材料费".to_string(),
                    content: "耗材A".to_string(),
                    specification: Some("型号A".to_string()),
                    supplier: Some("供应商A".to_string()),
                    amount: 5000.0,
                    date: "2024-05-03".to_string(),
                    remarks: None,
                },
                ParsedExpense {
                    category: "劳务费".to_string(),
                    content: "学生劳务".to_string(),
                    specification: None,
                    supplier: None,
                    amount: 2000.0,
                    date: "2024-05-04".to_string(),
                    remarks: Some("临时".to_string()),
                },
            ],
        )
        .unwrap();
        assert_eq!(n, 2);

        // 共 5 条日志：添加 / 编辑 / 删除 / 批量导入×2（每条支出 1 条）
        let mut stmt = conn
            .prepare(
                "SELECT action, category, amount, related_info, expense_id \
                 FROM actionlogs WHERE type = '支出' ORDER BY id",
            )
            .unwrap();
        let rows: Vec<(String, Option<String>, Option<f64>, Option<String>, Option<i64>)> = stmt
            .query_map([], |r| {
                Ok((
                    r.get(0)?,
                    r.get(1)?,
                    r.get(2)?,
                    r.get(3)?,
                    r.get(4)?,
                ))
            })
            .unwrap()
            .collect::<Result<_, _>>()
            .unwrap();
        assert_eq!(rows.len(), 5);
        assert_eq!(rows[0].0, "添加");
        assert_eq!(rows[1].0, "编辑");
        assert_eq!(rows[2].0, "删除");
        assert_eq!(rows[3].0, "批量导入");
        assert_eq!(rows[4].0, "批量导入");

        for (_action, category, amount, related, _expense_id) in &rows {
            // 扩展字段非空
            assert!(category.is_some(), "{rows:?}");
            assert!(amount.is_some(), "{rows:?}");
            assert!(related.as_deref().is_some_and(|s| s.starts_with("项目: ")), "{rows:?}");
        }
        // 中文 label 入库
        assert_eq!(rows[0].1.as_deref(), Some("材料费"));
        assert_eq!(rows[3].1.as_deref(), Some("材料费"));
        assert_eq!(rows[4].1.as_deref(), Some("劳务费"));
        // related_info 包含项目财务号与预算年份
        assert!(rows[0].3.as_deref().unwrap().contains("项目: "));
        // expense_id 均已记录
        assert!(rows.iter().all(|(_, _, _, _, eid)| eid.is_some()));
    }

    #[test]
    fn list_project_expenses_by_category_spans_years() {
        // 两个年度（2024/2025）各有材料费支出，另掺一条差旅费验证过滤
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(
            &mut conn, "跨年度项目", None, None, None, None, None, None,
        )
        .unwrap();

        let mut budget_ids = Vec::new();
        for year in [2024i64, 2025] {
            let bid = add_annual_budget(
                &conn,
                AnnualBudgetInput {
                    project_id: pid,
                    year,
                    total_amount: 1000.0,
                    items: BudgetCategory::ALL
                        .iter()
                        .map(|c| BudgetItemInput {
                            category: c.as_str().to_string(),
                            amount: 100.0,
                        })
                        .collect(),
                },
            )
            .unwrap();
            budget_ids.push((year, bid));
        }

        let add = |year_bid: (i64, i64), cat: &str, content: &str, date: &str| {
            add_expense(
                &conn,
                ExpenseInput {
                    project_id: pid,
                    budget_id: year_bid.1,
                    category: cat.to_string(),
                    content: content.to_string(),
                    specification: None,
                    supplier: None,
                    amount: 1000.0,
                    date: date.to_string(),
                    remarks: None,
                    voucher_path: None,
                },
            )
            .unwrap();
        };
        add(budget_ids[0], "材料费", "2024试剂", "2024-05-01");
        add(budget_ids[1], "材料费", "2025试剂", "2025-03-01");
        add(budget_ids[1], "差旅费", "会议出差", "2025-04-01");

        // 材料费：跨两个年度共 2 条，按日期倒序，year 回填正确
        let mat = list_project_expenses_by_category(&conn, pid, "材料费", None).unwrap();
        assert_eq!(mat.len(), 2);
        assert_eq!(mat[0].content, "2025试剂");
        assert_eq!(mat[0].year, Some(2025));
        assert_eq!(mat[1].content, "2024试剂");
        assert_eq!(mat[1].year, Some(2024));
        // 返回中文 label
        assert!(mat.iter().all(|r| r.category == "材料费"));

        // 差旅费只有 1 条；无支出科目返回空
        let trip = list_project_expenses_by_category(&conn, pid, "差旅费", None).unwrap();
        assert_eq!(trip.len(), 1);
        assert_eq!(trip[0].year, Some(2025));
        let none = list_project_expenses_by_category(&conn, pid, "出版文献费", None).unwrap();
        assert!(none.is_empty());

        // 限定 budget_id：只看 2024 年度预算
        let mat24 =
            list_project_expenses_by_category(&conn, pid, "材料费", Some(budget_ids[0].1)).unwrap();
        assert_eq!(mat24.len(), 1);
        assert_eq!(mat24[0].content, "2024试剂");
        assert_eq!(mat24[0].year, Some(2024));
        // 差旅费只发生在 2025，2024 预算下为空
        let trip24 =
            list_project_expenses_by_category(&conn, pid, "差旅费", Some(budget_ids[0].1)).unwrap();
        assert!(trip24.is_empty());
    }
}
