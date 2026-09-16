//! 主页服务：项目经费概览 + 项目进度概览
//!
//! 对应 Python `app/views/home_interface.py`：
//! - load_funds：每项目经费卡片（财务编号 / 总预算 / 总支出 / 执行率）
//! - load_tasks：每项目一级（level==0）甘特任务的进度卡片
//! 合并为单次 DB 访问输出，避免前端 N+1 查询。

use rusqlite::Connection;

use crate::DbError;

/// 项目经费概览行（单位：元；execution_rate 单位：%）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FundOverviewItem {
    pub project_id: i64,
    pub financial_code: Option<String>,
    pub total_budget: f64,
    pub total_spent: f64,
    pub execution_rate: f64,
}

/// 单个一级任务的进度概览行
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TaskOverviewItem {
    pub code: String,
    pub name: String,
    pub progress: f64,
}

/// 某项目的一级任务进度卡片
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ProgressOverviewGroup {
    pub project_id: i64,
    pub financial_code: Option<String>,
    pub tasks: Vec<TaskOverviewItem>,
}

/// 主页概览（经费 + 进度）一次性返回
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct HomeOverview {
    pub funds: Vec<FundOverviewItem>,
    pub progress: Vec<ProgressOverviewGroup>,
}

/// 加载主页全部概览数据。
///
/// 对齐 Python：
/// - total_spent = 该项目全部支出之和（与预算无关）
/// - 无总预算记录时 total_budget=0、相关字段为 0
/// - 执行率 = total_spent / (total_budget*10000)（Python 中 total_budget 存万元）
///   此处 total_budget 以元计，因此执行率 = total_spent / total_budget
/// - progress 取每项目 level==0 的甘特任务，按 order 排序
pub fn home_overview(conn: &Connection) -> Result<HomeOverview, DbError> {
    let funds = build_fund_overview(conn)?;
    let progress = build_progress_overview(conn)?;
    Ok(HomeOverview { funds, progress })
}

fn build_fund_overview(conn: &Connection) -> Result<Vec<FundOverviewItem>, DbError> {
    let mut stmt =
        conn.prepare("SELECT id, financial_code, total_budget FROM projects ORDER BY id")?;
    let rows = stmt.query_map([], |row| {
        Ok((
            row.get::<_, i64>(0)?,
            row.get::<_, Option<String>>(1)?,
            row.get::<_, Option<f64>>(2)?,
        ))
    })?;

    let mut out = Vec::new();
    for r in rows {
        let (project_id, financial_code, total_budget) = r?;
        // 总预算以元计（项目 total_budget 字段存万元，换算为元）
        let total_budget_yuan = total_budget.unwrap_or(0.0) * 10000.0;
        let total_spent: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE project_id = ?1",
            [project_id],
            |r| r.get(0),
        )?;
        let execution_rate = if total_budget_yuan > 0.0 {
            (total_spent / total_budget_yuan) * 100.0
        } else {
            0.0
        };
        out.push(FundOverviewItem {
            project_id,
            financial_code,
            total_budget: total_budget_yuan,
            total_spent,
            execution_rate,
        });
    }
    Ok(out)
}

fn build_progress_overview(conn: &Connection) -> Result<Vec<ProgressOverviewGroup>, DbError> {
    // 取所有项目的一级任务（level==0），按 project_id、order 排序
    let mut stmt = conn.prepare(
        "SELECT id FROM projects ORDER BY id",
    )?;
    let project_ids: Vec<i64> = stmt
        .query_map([], |r| r.get(0))?
        .collect::<Result<Vec<i64>, _>>()?;

    let financial_codes: std::collections::HashMap<i64, Option<String>> = {
        let mut m = std::collections::HashMap::new();
        let mut stmt = conn.prepare("SELECT id, financial_code FROM projects")?;
        let rows = stmt.query_map([], |r| {
            Ok((r.get::<_, i64>(0)?, r.get::<_, Option<String>>(1)?))
        })?;
        for r in rows {
            let (id, code) = r?;
            m.insert(id, code);
        }
        m
    };

    let mut out = Vec::new();
    for project_id in project_ids {
        let mut stmt = conn.prepare(
            "SELECT gantt_id, name, code, level, progress FROM gantt_tasks \
             WHERE project_id = ?1 ORDER BY \"order\", id",
        )?;
        let tasks = stmt.query_map([project_id], |row| {
            Ok((
                row.get::<_, i64>(3)?,        // level
                row.get::<_, Option<String>>(2)?, // code
                row.get::<_, String>(1)?,     // name
                row.get::<_, Option<f64>>(4)?, // progress
            ))
        })?;

        let mut task_items = Vec::new();
        for t in tasks {
            let (level, code, name, progress) = t?;
            if level == 0 {
                task_items.push(TaskOverviewItem {
                    code: code.unwrap_or_else(|| (task_items.len() + 1).to_string()),
                    name,
                    progress: progress.unwrap_or(0.0),
                });
            }
        }

        if !task_items.is_empty() {
            out.push(ProgressOverviewGroup {
                project_id,
                financial_code: financial_codes.get(&project_id).cloned().flatten(),
                tasks: task_items,
            });
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::schema;
    use crate::services::budget::add_project_to_db;
    use rusqlite::{params, Connection};

    fn test_conn() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        conn
    }

    #[test]
    fn empty_db_returns_empty_overview() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let ov = home_overview(&conn).unwrap();
        assert!(ov.funds.is_empty());
        assert!(ov.progress.is_empty());
    }

    #[test]
    fn fund_overview_sums_expenses() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(
            &mut conn,
            "测试项目",
            Some("C001"),
            None,
            None,
            None,
            None,
            Some(100.0), // 总预算 100 万元
        )
        .unwrap();

        // 总预算记录（year NULL） = 100 万元
        conn.execute(
            "UPDATE budgets SET total_amount = 1000000 WHERE project_id = ?1 AND year IS NULL",
            [pid],
        )
        .unwrap();
        let budget_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year IS NULL",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        // 两笔支出合计 250000 元
        conn.execute(
            "INSERT INTO expenses (project_id, budget_id, category, content, amount, date) \
             VALUES (?1, ?2, 'EQUIPMENT', '设备', 150000, '2026-01-01'), \
                    (?1, ?2, 'MATERIAL', '材料', 100000, '2026-02-01')",
            params![pid, budget_id],
        )
        .unwrap();

        let ov = home_overview(&conn).unwrap();
        assert_eq!(ov.funds.len(), 1);
        let f = &ov.funds[0];
        assert_eq!(f.financial_code.as_deref(), Some("C001"));
        assert_eq!(f.total_budget, 1_000_000.0); // 100 万 -> 元
        assert_eq!(f.total_spent, 250_000.0);
        assert!((f.execution_rate - 25.0).abs() < 1e-6);
    }

    #[test]
    fn progress_groups_only_level_zero_tasks() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(
            &mut conn,
            "测试项目",
            Some("C002"),
            None,
            None,
            None,
            None,
            None,
        )
        .unwrap();

        // 一级任务
        conn.execute(
            "INSERT INTO gantt_tasks (project_id, gantt_id, name, code, level, progress) \
             VALUES (?1, 't1', '总体设计', '1', 0, 60.0), \
                    (?1, 't2', '子任务', '2', 1, 30.0)",
            [pid],
        )
        .unwrap();

        let ov = home_overview(&conn).unwrap();
        assert_eq!(ov.funds.len(), 1);
        assert_eq!(ov.progress.len(), 1);
        let g = &ov.progress[0];
        assert_eq!(g.tasks.len(), 1); // 仅 level==0
        assert_eq!(g.tasks[0].name, "总体设计");
        assert_eq!(g.tasks[0].code, "1");
        assert!((g.tasks[0].progress - 60.0).abs() < 1e-6);
    }
}
