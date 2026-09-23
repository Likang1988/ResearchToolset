//! 项目服务：项目列表查询、新增、编辑、删除、JSON 导入导出

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};

use crate::models::{BudgetCategory, Project};
use crate::DbError;

/// 新增/编辑项目的输入结构（Tauri command 参数）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectNew {
    pub name: String,
    pub financial_code: Option<String>,
    pub project_code: Option<String>,
    pub project_type: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub total_budget: Option<f64>,
    pub director: Option<String>,
}

/// 列出全部项目，按 id 升序。
pub fn list_projects(conn: &Connection) -> Result<Vec<Project>, DbError> {
    let mut stmt = conn.prepare(
        "SELECT id, name, financial_code, project_code, project_type, leader, \
         start_date, end_date, total_budget, director \
         FROM projects ORDER BY id ASC",
    )?;
    let projects = stmt
        .query_map([], Project::from_row)?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(projects)
}

/// 新增项目：同时创建总预算 (year IS NULL) 和 10 个预算类别明细，
/// 并写入"新增"操作日志。
pub fn add_project(conn: &Connection, data: ProjectNew) -> Result<i64, DbError> {
    crate::db::begin_tx(conn)?;
    let result = add_project_inner(conn, data);
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

fn add_project_inner(conn: &Connection, data: ProjectNew) -> Result<i64, DbError> {
    conn.execute(
        "INSERT INTO projects (name, financial_code, project_code, project_type, \
         start_date, end_date, total_budget, director) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            data.name,
            data.financial_code,
            data.project_code,
            data.project_type,
            data.start_date,
            data.end_date,
            data.total_budget,
            data.director,
        ],
    )?;
    let project_id = conn.last_insert_rowid();

    // 自动创建总预算 (year IS NULL)
    conn.execute(
        "INSERT INTO budgets (project_id, year, total_amount, spent_amount) VALUES (?1, NULL, ?2, 0)",
        params![project_id, data.total_budget],
    )?;
    let budget_id = conn.last_insert_rowid();

    // 自动创建 10 个预算科目明细 (初始金额 0)
    for category in BudgetCategory::ALL.iter() {
        conn.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) VALUES (?1, ?2, 0, 0)",
            params![budget_id, category.as_str()],
        )?;
    }

    // 记录添加项目的活动
    crate::logging::log_action(
        conn,
        Some(project_id),
        None,
        None,
        None,
        None,
        None,
        "项目",
        "新增",
        &format!(
            "添加项目：{} - {}",
            data.name,
            data.financial_code.as_deref().unwrap_or("")
        ),
        "系统用户",
        None,
        Some(&project_fields_str(
            &data.name,
            &data.financial_code,
            &data.project_code,
            &data.project_type,
            &data.start_date,
            &data.end_date,
            data.total_budget,
            &data.director,
        )),
        None,
        None,
        None,
    )?;

    Ok(project_id)
}

/// 编辑项目：更新项目基本信息，并写入"编辑"操作日志
/// （old_data/new_data 使用完整的旧/新字段集）。
pub fn update_project(conn: &Connection, id: i64, data: ProjectNew) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = update_project_inner(conn, id, data);
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

fn update_project_inner(conn: &Connection, id: i64, data: ProjectNew) -> Result<(), DbError> {
    // 先取编辑前的旧值（用于操作日志 old_data）
    let (old_name, old_financial_code, old_project_code, old_project_type, old_start, old_end, old_budget, old_director): (
        String,
        Option<String>,
        Option<String>,
        Option<String>,
        Option<String>,
        Option<String>,
        Option<f64>,
        Option<String>,
    ) = conn.query_row(
        "SELECT name, financial_code, project_code, project_type, start_date, end_date, \
         total_budget, director FROM projects WHERE id = ?1",
        [id],
        |r| {
            Ok((
                r.get(0)?,
                r.get(1)?,
                r.get(2)?,
                r.get(3)?,
                r.get(4)?,
                r.get(5)?,
                r.get(6)?,
                r.get(7)?,
            ))
        },
    )?;

    conn.execute(
        "UPDATE projects SET \
         name = ?1, \
         financial_code = ?2, \
         project_code = ?3, \
         project_type = ?4, \
         start_date = ?5, \
         end_date = ?6, \
         total_budget = ?7, \
         director = ?8 \
         WHERE id = ?9",
        params![
            data.name,
            data.financial_code,
            data.project_code,
            data.project_type,
            data.start_date,
            data.end_date,
            data.total_budget,
            data.director,
            id,
        ],
    )?;

    // 记录编辑项目的活动
    let old_data = project_fields_str(
        &old_name,
        &old_financial_code,
        &old_project_code,
        &old_project_type,
        &old_start,
        &old_end,
        old_budget,
        &old_director,
    );
    let new_data = project_fields_str(
        &data.name,
        &data.financial_code,
        &data.project_code,
        &data.project_type,
        &data.start_date,
        &data.end_date,
        data.total_budget,
        &data.director,
    );
    crate::logging::log_action(
        conn,
        Some(id),
        None,
        None,
        None,
        None,
        None,
        "项目",
        "编辑",
        &format!(
            "编辑项目：{} - {}",
            data.name,
            data.financial_code.as_deref().unwrap_or("")
        ),
        "系统用户",
        Some(&old_data),
        Some(&new_data),
        None,
        None,
        None,
    )?;
    Ok(())
}

/// 删除项目：级联删除所有关联表记录
///
/// 删除顺序（SQLite 外键关闭，需显式级联）：
/// 1. budget_items（通过 budget_id 子查询关联 budgets）
/// 2. expenses（project_id + budget_id）
/// 3. gantt_dependencies（project_id）
/// 4. gantt_tasks（project_id）
/// 5. project_documents（project_id）
/// 6. project_outcome（project_id）
/// 7. budgets（project_id）
/// 8. projects（id）
///
/// 不删除 actionlogs：保留操作历史。
/// 附件文件清理见 `attachments::clean_project_attachments`，由调用方在事务提交后执行。
pub fn delete_project(conn: &Connection, id: i64) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = delete_project_inner(conn, id);
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

fn delete_project_inner(conn: &Connection, id: i64) -> Result<(), DbError> {
    // 删除前取项目信息，写入"删除"操作日志
    let (name, _financial_code, project_code): (String, Option<String>, Option<String>) = conn
        .query_row(
            "SELECT name, financial_code, project_code FROM projects WHERE id = ?1",
            [id],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
        )?;
    crate::logging::log_action(
        conn,
        Some(id),
        None,
        None,
        None,
        None,
        None,
        "项目",
        "删除",
        &format!(
            "删除项目及其所有关联数据：{} - {}",
            name,
            project_code.as_deref().unwrap_or("")
        ),
        "系统用户",
        None,
        None,
        None,
        None,
        None,
    )?;

    // 1. budget_items（通过 budgets 子查询）
    conn.execute(
        "DELETE FROM budget_items WHERE budget_id IN \
         (SELECT id FROM budgets WHERE project_id = ?1)",
        params![id],
    )?;
    // 2. expenses
    conn.execute("DELETE FROM expenses WHERE project_id = ?1", params![id])?;
    // 3. gantt_dependencies
    conn.execute("DELETE FROM gantt_dependencies WHERE project_id = ?1", params![id])?;
    // 4. gantt_tasks
    conn.execute("DELETE FROM gantt_tasks WHERE project_id = ?1", params![id])?;
    // 5. project_documents
    conn.execute("DELETE FROM project_documents WHERE project_id = ?1", params![id])?;
    // 6. project_outcome（表名为单数）
    conn.execute("DELETE FROM project_outcome WHERE project_id = ?1", params![id])?;
    // 7. budgets
    conn.execute("DELETE FROM budgets WHERE project_id = ?1", params![id])?;
    // 8. projects
    conn.execute("DELETE FROM projects WHERE id = ?1", params![id])?;
    Ok(())
}

/// 操作日志 old_data/new_data 的项目字段串。
/// 金额缺失时输出 `0.0`。
fn project_fields_str(
    name: &str,
    financial_code: &Option<String>,
    project_code: &Option<String>,
    project_type: &Option<String>,
    start_date: &Option<String>,
    end_date: &Option<String>,
    total_budget: Option<f64>,
    director: &Option<String>,
) -> String {
    format!(
        "名称: {}, 财务编号: {}, 项目编号: {}, 类型: {}, 开始日期: {}, 结束日期: {}, 总经费: {}, 负责人: {}",
        name,
        financial_code.as_deref().unwrap_or(""),
        project_code.as_deref().unwrap_or(""),
        project_type.as_deref().unwrap_or(""),
        start_date.as_deref().unwrap_or(""),
        end_date.as_deref().unwrap_or(""),
        total_budget.map(|v| v.to_string()).unwrap_or_else(|| "0.0".to_string()),
        director.as_deref().unwrap_or(""),
    )
}

// ---------------------------------------------------------------------------
// 项目数据 JSON 导出 / 导入
// ---------------------------------------------------------------------------

/// 导出项目数据为 JSON 字符串，结构：
/// `{ project, budgets: [{id, year, total_amount, spent_amount, items}], expenses: [...] }`。
/// 注意：导出有意省略 director 字段，与既有导出格式保持一致以保证互操作。
pub fn export_project_data(conn: &Connection, project_id: i64) -> Result<String, DbError> {
    // 项目基本信息（导出字段子集）
    let project: serde_json::Value = conn
        .query_row(
            "SELECT id, name, financial_code, project_code, project_type, start_date, end_date, \
             total_budget FROM projects WHERE id = ?1",
            [project_id],
            |r| {
                Ok(serde_json::json!({
                    "id": r.get::<_, i64>(0)?,
                    "name": r.get::<_, String>(1)?,
                    "financial_code": r.get::<_, Option<String>>(2)?,
                    "project_code": r.get::<_, Option<String>>(3)?,
                    "project_type": r.get::<_, Option<String>>(4)?,
                    "start_date": r.get::<_, Option<String>>(5)?,
                    "end_date": r.get::<_, Option<String>>(6)?,
                    "total_budget": r.get::<_, Option<f64>>(7)?,
                }))
            },
        )
        .optional()?
        .ok_or_else(|| DbError::Other("项目不存在".to_string()))?;

    // 预算记录 + 明细
    let mut budgets_json: Vec<serde_json::Value> = Vec::new();
    {
        let mut stmt = conn.prepare(
            "SELECT id, year, total_amount, spent_amount FROM budgets \
             WHERE project_id = ?1 ORDER BY id",
        )?;
        let rows = stmt.query_map([project_id], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, Option<i64>>(1)?,
                r.get::<_, f64>(2)?,
                r.get::<_, f64>(3)?,
            ))
        })?;
        for row in rows {
            let (budget_id, year, total_amount, spent_amount) = row?;
            let mut items_json: Vec<serde_json::Value> = Vec::new();
            let mut item_stmt = conn.prepare(
                "SELECT id, category, amount, spent_amount FROM budget_items \
                 WHERE budget_id = ?1 ORDER BY id",
            )?;
            let item_rows = item_stmt.query_map([budget_id], |r| {
                Ok((
                    r.get::<_, i64>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, f64>(2)?,
                    r.get::<_, f64>(3)?,
                ))
            })?;
            for item in item_rows {
                let (item_id, category, amount, item_spent) = item?;
                items_json.push(serde_json::json!({
                    "id": item_id,
                    "category": category,
                    "amount": amount,
                    "spent_amount": item_spent,
                }));
            }
            budgets_json.push(serde_json::json!({
                "id": budget_id,
                "year": year,
                "total_amount": total_amount,
                "spent_amount": spent_amount,
                "items": items_json,
            }));
        }
    }

    // 支出记录（通过 budgets 关联到本项目）
    let mut expenses_json: Vec<serde_json::Value> = Vec::new();
    {
        let mut stmt = conn.prepare(
            "SELECT e.id, e.budget_id, e.category, e.content, e.specification, e.supplier, \
             e.amount, e.date, e.remarks, e.voucher_path \
             FROM expenses e JOIN budgets b ON e.budget_id = b.id \
             WHERE b.project_id = ?1 ORDER BY e.id",
        )?;
        let rows = stmt.query_map([project_id], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, i64>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, String>(3)?,
                r.get::<_, Option<String>>(4)?,
                r.get::<_, Option<String>>(5)?,
                r.get::<_, f64>(6)?,
                r.get::<_, String>(7)?,
                r.get::<_, Option<String>>(8)?,
                r.get::<_, Option<String>>(9)?,
            ))
        })?;
        for row in rows {
            let (id, budget_id, category, content, specification, supplier, amount, date, remarks, voucher_path) = row?;
            expenses_json.push(serde_json::json!({
                "id": id,
                "budget_id": budget_id,
                "category": category,
                "content": content,
                "specification": specification,
                "supplier": supplier,
                "amount": amount,
                "date": date,
                "remarks": remarks,
                "voucher_path": voucher_path,
            }));
        }
    }

    let root = serde_json::json!({
        "project": project,
        "budgets": budgets_json,
        "expenses": expenses_json,
    });
    // 缩进美化输出，非 ASCII 字符原样保留
    serde_json::to_string_pretty(&root).map_err(DbError::Json)
}

/// 从 JSON 文件导入项目数据。
///
/// - `overwrite=false` 且检测到相同财务编号项目时返回
///   `Err(DbError::Other("DUPLICATE_FINANCIAL_CODE"))`，由前端弹覆盖确认后重试。
/// - `overwrite=true` 时先删除旧项目及其关联数据，再导入。
/// - 支出按日期年份重新绑定到新项目的对应年度预算（预算 id 重新分配）。
pub fn import_project_data(conn: &Connection, path: &str, overwrite: bool) -> Result<i64, DbError> {
    let text = std::fs::read_to_string(path).map_err(DbError::Io)?;
    let data: serde_json::Value = serde_json::from_str(&text).map_err(DbError::Json)?;

    // 验证数据格式
    let project_obj = data
        .get("project")
        .ok_or_else(|| DbError::Other("数据格式不正确".to_string()))?;
    let budgets = data
        .get("budgets")
        .ok_or_else(|| DbError::Other("数据格式不正确".to_string()))?;
    let expenses = data
        .get("expenses")
        .ok_or_else(|| DbError::Other("数据格式不正确".to_string()))?;

    crate::db::begin_tx(conn)?;
    let result = import_project_data_inner(conn, project_obj, budgets, expenses, overwrite);
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

fn import_project_data_inner(
    conn: &Connection,
    project_obj: &serde_json::Value,
    budgets: &serde_json::Value,
    expenses: &serde_json::Value,
    overwrite: bool,
) -> Result<i64, DbError> {
    let name = json_required_str(project_obj, "name")?;
    let financial_code = json_opt_str(project_obj, "financial_code");
    let project_code = json_opt_str(project_obj, "project_code");
    let project_type = json_opt_str(project_obj, "project_type");
    let start_date = json_opt_str(project_obj, "start_date");
    let end_date = json_opt_str(project_obj, "end_date");
    let total_budget = project_obj.get("total_budget").and_then(|v| v.as_f64());

    // 检查项目是否已存在（按财务编号）
    let existing_id: Option<i64> = conn
        .query_row(
            "SELECT id FROM projects WHERE financial_code = ?1",
            [&financial_code],
            |r| r.get(0),
        )
        .optional()?;
    if let Some(existing_id) = existing_id {
        if !overwrite {
            return Err(DbError::Other("DUPLICATE_FINANCIAL_CODE".to_string()));
        }
        // 覆盖：删除原有项目数据（含级联预算/支出）
        delete_project_inner(conn, existing_id)?;
    }

    // 创建新项目（导入数据不含 director，写 NULL）
    conn.execute(
        "INSERT INTO projects (name, financial_code, project_code, project_type, \
         start_date, end_date, total_budget, director) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, NULL)",
        params![
            name,
            financial_code,
            project_code,
            project_type,
            start_date,
            end_date,
            total_budget,
        ],
    )?;
    let project_id = conn.last_insert_rowid();

    // 导入预算数据（按 (project_id, year) 匹配：已有则更新并重建明细）
    if let Some(budget_list) = budgets.as_array() {
        for budget_data in budget_list {
            let year: Option<i64> = budget_data.get("year").and_then(|v| v.as_i64());
            let total_amount: f64 = json_f64(budget_data, "total_amount");
            let spent_amount: f64 = json_f64(budget_data, "spent_amount");

            let existing_budget: Option<i64> = conn
                .query_row(
                    "SELECT id FROM budgets WHERE project_id = ?1 AND (year IS ?2)",
                    params![project_id, year],
                    |r| r.get(0),
                )
                .optional()?;
            let budget_id = match existing_budget {
                Some(bid) => {
                    conn.execute(
                        "UPDATE budgets SET total_amount = ?1, spent_amount = ?2 WHERE id = ?3",
                        params![total_amount, spent_amount, bid],
                    )?;
                    bid
                }
                None => {
                    conn.execute(
                        "INSERT INTO budgets (project_id, year, total_amount, spent_amount) \
                         VALUES (?1, ?2, ?3, ?4)",
                        params![project_id, year, total_amount, spent_amount],
                    )?;
                    conn.last_insert_rowid()
                }
            };

            // 清空既有预算明细，按导入数据重建
            conn.execute("DELETE FROM budget_items WHERE budget_id = ?1", params![budget_id])?;
            if let Some(items) = budget_data.get("items").and_then(|v| v.as_array()) {
                for item_data in items {
                    let category = json_required_str(item_data, "category")?;
                    let amount = json_f64(item_data, "amount");
                    let item_spent = json_f64(item_data, "spent_amount");
                    conn.execute(
                        "INSERT INTO budget_items (budget_id, category, amount, spent_amount) \
                         VALUES (?1, ?2, ?3, ?4)",
                        params![budget_id, category, amount, item_spent],
                    )?;
                }
            }
        }
    }

    // 导入支出数据：按支出日期年份查找对应年度预算并绑定新预算 id
    if let Some(expense_list) = expenses.as_array() {
        for expense_data in expense_list {
            let category = json_required_str(expense_data, "category")?;
            let content = json_required_str(expense_data, "content")?;
            let specification = json_opt_str(expense_data, "specification");
            let supplier = json_opt_str(expense_data, "supplier");
            let amount = json_f64(expense_data, "amount");
            let date = json_required_str(expense_data, "date")?;
            let remarks = json_opt_str(expense_data, "remarks");
            let voucher_path = json_opt_str(expense_data, "voucher_path");

            // 年份取自日期字符串前缀
            let expense_year: Option<i64> = date
                .split('-')
                .next()
                .and_then(|s| s.trim().parse::<i64>().ok());
            let budget_id: Option<i64> = match expense_year {
                Some(y) => conn
                    .query_row(
                        "SELECT id FROM budgets WHERE project_id = ?1 AND year = ?2",
                        params![project_id, y],
                        |r| r.get(0),
                    )
                    .optional()?,
                None => None,
            };

            // 找到对应年度预算才创建支出
            if let Some(bid) = budget_id {
                conn.execute(
                    "INSERT INTO expenses (project_id, budget_id, category, content, specification, \
                     supplier, amount, date, remarks, voucher_path) \
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
                    params![
                        project_id,
                        bid,
                        category,
                        content,
                        specification,
                        supplier,
                        amount,
                        date,
                        remarks,
                        voucher_path,
                    ],
                )?;
            }
        }
    }

    Ok(project_id)
}

fn json_required_str(obj: &serde_json::Value, key: &str) -> Result<String, DbError> {
    obj.get(key)
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| DbError::Other(format!("数据缺少必要字段：{key}")))
}

fn json_opt_str(obj: &serde_json::Value, key: &str) -> Option<String> {
    obj.get(key).and_then(|v| v.as_str()).map(|s| s.to_string())
}

fn json_f64(obj: &serde_json::Value, key: &str) -> f64 {
    obj.get(key).and_then(|v| v.as_f64()).unwrap_or(0.0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db;

    fn open_db() -> Connection {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let mut conn = db::open(tmp.path()).unwrap();
        db::init_db(&mut conn).unwrap();
        conn
    }

    fn sample_data() -> ProjectNew {
        ProjectNew {
            name: "测试项目".to_string(),
            financial_code: Some("F001".to_string()),
            project_code: Some("P001".to_string()),
            project_type: Some("国家自然科学基金".to_string()),
            start_date: Some("2024-01-01".to_string()),
            end_date: Some("2025-12-31".to_string()),
            total_budget: Some(100.0),
            director: Some("张三".to_string()),
        }
    }

    #[test]
    fn adds_project_with_budget_and_items() {
        let conn = open_db();
        let id = add_project(&conn, sample_data()).unwrap();
        assert!(id > 0);

        // 验证项目创建
        let mut stmt = conn
            .prepare("SELECT name, financial_code FROM projects WHERE id = ?1")
            .unwrap();
        let row = stmt.query_row([id], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))).unwrap();
        assert_eq!(row.0, "测试项目");
        assert_eq!(row.1, "F001");

        // 验证总预算创建
        let mut stmt = conn
            .prepare("SELECT COUNT(*) FROM budgets WHERE project_id = ?1 AND year IS NULL")
            .unwrap();
        let count: i64 = stmt.query_row([id], |r| r.get(0)).unwrap();
        assert_eq!(count, 1);

        // 验证预算明细创建 (10 条)
        let budget_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year IS NULL",
                [id],
                |r| r.get(0),
            )
            .unwrap();
        let mut stmt = conn
            .prepare("SELECT COUNT(*) FROM budget_items WHERE budget_id = ?1")
            .unwrap();
        let count: i64 = stmt.query_row([budget_id], |r| r.get(0)).unwrap();
        assert_eq!(count, 10);
    }

    #[test]
    fn updates_project_correctly() {
        let conn = open_db();
        let id = add_project(&conn, sample_data()).unwrap();

        let new_data = ProjectNew {
            name: "新名字".to_string(),
            financial_code: Some("F002".to_string()),
            project_code: None,
            project_type: None,
            start_date: None,
            end_date: None,
            total_budget: None,
            director: None,
        };
        update_project(&conn, id, new_data).unwrap();

        let mut stmt = conn
            .prepare("SELECT name, financial_code FROM projects WHERE id = ?1")
            .unwrap();
        let row = stmt
            .query_row([id], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))
            .unwrap();
        assert_eq!(row.0, "新名字");
        assert_eq!(row.1, "F002");
    }

    #[test]
    fn deletes_project_and_cascades_relations() {
        let conn = open_db();

        // 新增项目（会自动创建 1 条总预算 + 10 条预算明细）
        let id = add_project(
            &conn,
            ProjectNew {
                name: "待删除".to_string(),
                financial_code: Some("F999".to_string()),
                project_code: None,
                project_type: None,
                start_date: None,
                end_date: None,
                total_budget: Some(50.0),
                director: None,
            },
        )
        .unwrap();

        // 额外插入一条年度预算 + 该预算的明细 + 一条支出 + 一条甘特任务
        conn.execute(
            "INSERT INTO budgets (project_id, year, total_amount, spent_amount) VALUES (?1, 2024, 10, 0)",
            params![id],
        )
        .unwrap();
        let year_budget_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year = 2024",
                [id],
                |r| r.get(0),
            )
            .unwrap();
        conn.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) VALUES (?1, '材料费', 5, 0)",
            params![year_budget_id],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO expenses (project_id, budget_id, category, content, amount, date) \
             VALUES (?1, ?2, '材料费', '测试支出', 5, '2024-01-01')",
            params![id, year_budget_id],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO gantt_tasks (project_id, gantt_id, name) VALUES (?1, 'g1', '任务1')",
            params![id],
        )
        .unwrap();

        // 删除项目
        delete_project(&conn, id).unwrap();

        // 验证所有关联表均已清空
        for (sql, label) in [
            ("SELECT COUNT(*) FROM projects WHERE id = ?1", "projects"),
            ("SELECT COUNT(*) FROM budgets WHERE project_id = ?1", "budgets"),
            (
                "SELECT COUNT(*) FROM budget_items WHERE budget_id IN \
                 (SELECT id FROM budgets WHERE project_id = ?1)",
                "budget_items",
            ),
            ("SELECT COUNT(*) FROM expenses WHERE project_id = ?1", "expenses"),
            ("SELECT COUNT(*) FROM gantt_tasks WHERE project_id = ?1", "gantt_tasks"),
        ] {
            let count: i64 = conn.query_row(sql, [id], |r| r.get(0)).unwrap();
            assert_eq!(count, 0, "删除后 {label} 仍非空");
        }
    }

    #[test]
    fn crud_writes_actionlog() {
        let conn = open_db();
        let id = add_project(&conn, sample_data()).unwrap();

        // 新增日志
        let (cnt, action, desc): (i64, String, String) = conn
            .query_row(
                "SELECT COUNT(*), action, description FROM actionlogs WHERE project_id = ?1",
                [id],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(cnt, 1);
        assert_eq!(action, "新增");
        assert_eq!(desc, "添加项目：测试项目 - F001");

        // 编辑日志（old_data 用旧值）
        update_project(
            &conn,
            id,
            ProjectNew {
                name: "新名字".to_string(),
                financial_code: Some("F002".to_string()),
                project_code: None,
                project_type: None,
                start_date: None,
                end_date: None,
                total_budget: None,
                director: None,
            },
        )
        .unwrap();
        let (cnt, action, old_data): (i64, String, String) = conn
            .query_row(
                "SELECT COUNT(*), action, old_data FROM actionlogs WHERE project_id = ?1 AND action = '编辑'",
                [id],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(cnt, 1);
        assert!(old_data.contains("名称: 测试项目"));
        assert!(old_data.contains("财务编号: F001"));

        // 删除日志
        delete_project(&conn, id).unwrap();
        let (cnt, action, desc): (i64, String, String) = conn
            .query_row(
                "SELECT COUNT(*), action, description FROM actionlogs WHERE project_id = ?1 AND action = '删除'",
                [id],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(cnt, 1);
        // 删除用删除时刻的 project_code（已被编辑清空），名称应为"新名字"
        assert!(desc.contains("新名字"));
    }

    #[test]
    fn exports_project_json() {
        let conn = open_db();
        let id = add_project(&conn, sample_data()).unwrap();
        // 加一条年度预算 + 支出
        conn.execute(
            "INSERT INTO budgets (project_id, year, total_amount, spent_amount) VALUES (?1, 2024, 10, 2)",
            params![id],
        )
        .unwrap();
        let year_budget_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year = 2024",
                [id],
                |r| r.get(0),
            )
            .unwrap();
        conn.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) VALUES (?1, '材料费', 3, 0)",
            params![year_budget_id],
        )
        .unwrap();
        conn.execute(
            "INSERT INTO expenses (project_id, budget_id, category, content, amount, date) \
             VALUES (?1, ?2, '材料费', '测试支出', 5, '2024-03-01')",
            params![id, year_budget_id],
        )
        .unwrap();

        let json = export_project_data(&conn, id).unwrap();
        let v: serde_json::Value = serde_json::from_str(&json).unwrap();

        assert_eq!(v["project"]["name"], "测试项目");
        assert_eq!(v["project"]["total_budget"], 100.0);
        let budgets = v["budgets"].as_array().unwrap();
        assert_eq!(budgets.len(), 2); // 总预算 + 2024 年度预算
        assert_eq!(budgets[1]["year"], 2024);
        assert_eq!(budgets[1]["items"][0]["category"], "材料费");
        let expenses = v["expenses"].as_array().unwrap();
        assert_eq!(expenses.len(), 1);
        assert_eq!(expenses[0]["content"], "测试支出");
    }

    #[test]
    fn imports_project_json() {
        let conn = open_db();
        let src = tempfile::NamedTempFile::new().unwrap();
        let json = r#"{
            "project": {
                "id": 99,
                "name": "导入项目",
                "financial_code": "IMP001",
                "project_code": "IP001",
                "project_type": "横向课题",
                "start_date": "2024-05-01",
                "end_date": "2025-04-30",
                "total_budget": 200.0
            },
            "budgets": [
                { "id": 1, "year": null, "total_amount": 200.0, "spent_amount": 0.0,
                  "items": [
                      { "id": 1, "category": "材料费", "amount": 20.0, "spent_amount": 0.0 },
                      { "id": 2, "category": "设备费", "amount": 30.0, "spent_amount": 0.0 }
                  ] },
                { "id": 2, "year": 2024, "total_amount": 100.0, "spent_amount": 5.0,
                  "items": [
                      { "id": 3, "category": "材料费", "amount": 10.0, "spent_amount": 0.0 }
                  ] }
            ],
            "expenses": [
                { "id": 1, "budget_id": 2, "category": "材料费", "content": "购买耗材",
                  "specification": null, "supplier": null, "amount": 5.0,
                  "date": "2024-06-01", "remarks": "", "voucher_path": null }
            ]
        }"#;
        std::fs::write(src.path(), json).unwrap();

        let id = import_project_data(&conn, src.path().to_str().unwrap(), false).unwrap();
        assert!(id > 0);

        // 项目创建
        let (name, code): (String, String) = conn
            .query_row("SELECT name, financial_code FROM projects WHERE id = ?1", [id], |r| {
                Ok((r.get(0)?, r.get(1)?))
            })
            .unwrap();
        assert_eq!(name, "导入项目");
        assert_eq!(code, "IMP001");

        // 预算 2 条（总预算 + 年度），明细 3 条
        let budget_cnt: i64 = conn
            .query_row("SELECT COUNT(*) FROM budgets WHERE project_id = ?1", [id], |r| r.get(0))
            .unwrap();
        assert_eq!(budget_cnt, 2);
        let item_cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id IN (SELECT id FROM budgets WHERE project_id = ?1)",
                [id],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(item_cnt, 3);

        // 支出创建并绑定到 2024 年度预算
        let (e_cnt, bid): (i64, i64) = conn
            .query_row(
                "SELECT COUNT(*), budget_id FROM expenses WHERE project_id = ?1",
                [id],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(e_cnt, 1);
        let year: Option<i64> = conn
            .query_row("SELECT year FROM budgets WHERE id = ?1", [bid], |r| r.get(0))
            .unwrap();
        assert_eq!(year, Some(2024));
    }

    #[test]
    fn import_duplicate_requires_overwrite() {
        let conn = open_db();
        let src = tempfile::NamedTempFile::new().unwrap();
        let json = r#"{
            "project": {
                "name": "导入项目",
                "financial_code": "SAME001",
                "project_code": null,
                "project_type": null,
                "start_date": null,
                "end_date": null,
                "total_budget": 100.0
            },
            "budgets": [],
            "expenses": []
        }"#;
        std::fs::write(src.path(), json).unwrap();

        // 首次导入成功（创建项目）
        import_project_data(&conn, src.path().to_str().unwrap(), false).unwrap();

        // 非覆盖模式：返回 DUPLICATE_FINANCIAL_CODE
        let err = import_project_data(&conn, src.path().to_str().unwrap(), false).unwrap_err();
        assert!(matches!(err, DbError::Other(m) if m == "DUPLICATE_FINANCIAL_CODE"));

        // 覆盖模式：替换旧项目（SQLite 非 AUTOINCREMENT，新记录可能复用原 id）
        let id2 = import_project_data(&conn, src.path().to_str().unwrap(), true).unwrap();
        assert!(id2 > 0);
        let cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM projects WHERE financial_code = 'SAME001'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(cnt, 1);
    }
}