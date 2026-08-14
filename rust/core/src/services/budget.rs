//! 预算服务：预算使用统计、项目创建（对应 database.py 的
//! `get_budget_usage` / `add_project_to_db`）

use rusqlite::{params, Connection, OptionalExtension};

use crate::models::BudgetCategory;
use crate::DbError;

/// 某科目支出金额
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CategorySpend {
    /// 费用类别（中文，与 BudgetCategory 一致）
    pub category: String,
    /// 该科目支出合计
    pub spent: f64,
}

/// 预算使用情况（对应 Python `get_budget_usage` 返回值）
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct BudgetUsage {
    pub total_budget: f64,
    pub total_spent: f64,
    pub remaining: f64,
    /// 按 10 类固定顺序排列的科目支出
    pub category_spent: Vec<CategorySpend>,
}

/// get_budget_usage 等价物：统计项目预算使用情况
///
/// 语义与 Python 版一致：
/// - 无总预算记录时返回全 0 结构
/// - total_spent = 该项目全部支出之和（与预算无关）
/// - category_spent 按 BudgetCategory 的 10 类逐一查询
pub fn get_budget_usage(conn: &Connection, project_id: i64) -> Result<BudgetUsage, DbError> {
    let empty = || BudgetUsage {
        total_budget: 0.0,
        total_spent: 0.0,
        remaining: 0.0,
        category_spent: BudgetCategory::ALL
            .iter()
            .map(|c| CategorySpend {
                category: c.as_str().to_string(),
                spent: 0.0,
            })
            .collect(),
    };

    // 查询总预算（year IS NULL）
    let total_budget: Option<f64> = conn
        .query_row(
            "SELECT total_amount FROM budgets WHERE project_id = ?1 AND year IS NULL",
            [project_id],
            |r| r.get(0),
        )
        .optional()?;

    let Some(total_budget) = total_budget else {
        return Ok(empty());
    };

    // 总支出
    let total_spent: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE project_id = ?1",
        [project_id],
        |r| r.get(0),
    )?;

    // 各科目支出（10 类逐一查询，与 Python 一致）
    let mut category_spent = Vec::with_capacity(10);
    for category in BudgetCategory::ALL {
        let spent: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE project_id = ?1 AND category = ?2",
            params![project_id, category.as_str()],
            |r| r.get(0),
        )?;
        category_spent.push(CategorySpend {
            category: category.as_str().to_string(),
            spent,
        });
    }

    Ok(BudgetUsage {
        total_budget,
        total_spent,
        remaining: total_budget - total_spent,
        category_spent,
    })
}

/// add_project_to_db 等价物：创建项目并自动建立总预算与 10 个科目子项
///
/// 返回新项目 id。全部操作在同一事务内，失败回滚。
pub fn add_project_to_db(
    conn: &mut Connection,
    name: &str,
    financial_code: Option<&str>,
    project_code: Option<&str>,
    project_type: Option<&str>,
    start_date: Option<&str>,
    end_date: Option<&str>,
    total_budget: Option<f64>,
) -> Result<i64, DbError> {
    let tx = conn.transaction()?;

    tx.execute(
        "INSERT INTO projects (name, financial_code, project_code, project_type, start_date, end_date, total_budget)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![
            name,
            financial_code,
            project_code,
            project_type,
            start_date,
            end_date,
            total_budget.unwrap_or(0.0),
        ],
    )?;
    let project_id = tx.last_insert_rowid();

    // 创建总预算记录（year=NULL，初始金额 0）
    tx.execute(
        "INSERT INTO budgets (project_id, year, total_amount, spent_amount) VALUES (?1, NULL, 0.0, 0.0)",
        [project_id],
    )?;
    let budget_id = tx.last_insert_rowid();

    // 创建 10 个总预算子项（初始金额 0）
    for category in BudgetCategory::ALL {
        tx.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) VALUES (?1, ?2, 0.0, 0.0)",
            params![budget_id, category.as_str()],
        )?;
    }

    tx.commit()?;
    Ok(project_id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::schema;
    use crate::models::BudgetItem;
    use rusqlite::Connection;

    /// 与应用行为一致：外键关闭（rusqlite 默认开启，Python/SQLAlchemy 默认关闭）
    fn test_conn() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        conn
    }

    #[test]
    fn add_project_creates_total_budget_with_10_items() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        let pid = add_project_to_db(&mut conn, "测试项目", Some("C001"), None, None, None, None, None)
            .unwrap();

        let budget = conn
            .query_row(
                "SELECT id, year FROM budgets WHERE project_id = ?1",
                [pid],
                |r| Ok((r.get::<_, i64>(0)?, r.get::<_, Option<i64>>(1)?)),
            )
            .unwrap();
        assert_eq!(budget.1, None, "总预算 year 应为 NULL");

        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id = ?1",
                [budget.0],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 10);
    }

    #[test]
    fn budget_usage_returns_zero_structure_without_total_budget() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        let pid = add_project_to_db(&mut conn, "测试项目", None, None, None, None, None, None)
            .unwrap();
        // 删除总预算，模拟无总预算场景
        conn.execute("DELETE FROM budgets", []).unwrap();

        let usage = get_budget_usage(&conn, pid).unwrap();
        assert_eq!(usage.total_budget, 0.0);
        assert_eq!(usage.total_spent, 0.0);
        assert_eq!(usage.remaining, 0.0);
        assert_eq!(usage.category_spent.len(), 10);
        assert!(usage.category_spent.iter().all(|c| c.spent == 0.0));
    }

    #[test]
    fn budget_usage_sums_expenses_per_category() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        let pid = add_project_to_db(&mut conn, "测试项目", None, None, None, None, None, Some(1000.0))
            .unwrap();
        let budget_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        // 注意：add_project_to_db 创建的总预算金额为 0（与 Python 一致，
        // 项目 total_budget 字段与 budgets.total_amount 相互独立）。
        // 这里模拟 UI 编辑总预算后写入的金额
        conn.execute(
            "UPDATE budgets SET total_amount = 1000.0 WHERE id = ?1",
            [budget_id],
        )
        .unwrap();

        // 材料费 100 + 材料费 50 + 设备费 200
        for (cat, amt) in [("材料费", 100.0), ("材料费", 50.0), ("设备费", 200.0)] {
            conn.execute(
                "INSERT INTO expenses (project_id, budget_id, category, content, amount)
                 VALUES (?1, ?2, ?3, '测试', ?4)",
                params![pid, budget_id, cat, amt],
            )
            .unwrap();
        }

        let usage = get_budget_usage(&conn, pid).unwrap();
        assert_eq!(usage.total_budget, 1000.0);
        assert_eq!(usage.total_spent, 350.0);
        assert_eq!(usage.remaining, 650.0);

        let material = usage
            .category_spent
            .iter()
            .find(|c| c.category == "材料费")
            .unwrap();
        assert_eq!(material.spent, 150.0);
        let equipment = usage
            .category_spent
            .iter()
            .find(|c| c.category == "设备费")
            .unwrap();
        assert_eq!(equipment.spent, 200.0);
    }

    #[test]
    fn add_project_uses_0_0_defaults() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();
        let item: BudgetItem = conn
            .query_row(
                "SELECT * FROM budget_items WHERE budget_id = (SELECT id FROM budgets WHERE project_id = ?1 LIMIT 1)",
                [pid],
                |r| Ok(BudgetItem::from_row(r).unwrap()),
            )
            .unwrap();
        assert_eq!(item.amount, Some(0.0));
        assert_eq!(item.spent_amount, Some(0.0));
    }
}
