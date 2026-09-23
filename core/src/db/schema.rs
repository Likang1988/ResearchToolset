//! 建表 DDL：与现有数据库逐字一致（golden 文件 `tests/golden/schema.sql`）
//!
//! 来源：`sqlite3 database/database.db .schema`（v1.5.0），勿手改。
//! 若数据模型变更，需重新导出 golden 文件并同步此文件。

use rusqlite::Connection;
use std::collections::HashSet;

use crate::DbError;

/// 全部建表/索引语句，与目标数据库现有结构逐字一致（由 golden 导出）。
/// 元素：(对象类型, 对象名, DDL)
pub const SCHEMA_OBJECTS: &[(&str, &str, &str)] = &[
    // projects
    (
        "table",
        "projects",
        "CREATE TABLE projects (
        id INTEGER NOT NULL, 
        name VARCHAR(100) NOT NULL, 
        financial_code VARCHAR(50), 
        project_code VARCHAR(50), 
        project_type VARCHAR(50), 
        leader VARCHAR(50), 
        start_date DATE, 
        end_date DATE, 
        total_budget FLOAT, 
        director VARCHAR(50), 
        PRIMARY KEY (id)
    )",
    ),
    // budget_plans
    (
        "table",
        "budget_plans",
        "CREATE TABLE budget_plans (
        id INTEGER NOT NULL, 
        name VARCHAR(100) NOT NULL, 
        create_date DATE, 
        total_amount FLOAT, 
        remarks VARCHAR(200), 
        PRIMARY KEY (id)
    )",
    ),
    // academic_activities
    (
        "table",
        "academic_activities",
        "CREATE TABLE academic_activities (
        id INTEGER NOT NULL, 
        name VARCHAR(200) NOT NULL, 
        type VARCHAR(10) NOT NULL, 
        status VARCHAR(9), 
        organizer VARCHAR(200), 
        start_date DATE, 
        end_date DATE, 
        location VARCHAR(200), 
        participants VARCHAR(500), 
        description VARCHAR(500), 
        attachment_path VARCHAR(500), 
        PRIMARY KEY (id)
    )",
    ),
    // budgets
    (
        "table",
        "budgets",
        "CREATE TABLE budgets (
        id INTEGER NOT NULL, 
        project_id INTEGER NOT NULL, 
        year INTEGER, 
        total_amount FLOAT, 
        spent_amount FLOAT, 
        PRIMARY KEY (id), 
        CONSTRAINT uix_project_year UNIQUE (project_id, year) ON CONFLICT FAIL, 
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )",
    ),
    // budget_plan_items
    (
        "table",
        "budget_plan_items",
        "CREATE TABLE budget_plan_items (
        id INTEGER NOT NULL, 
        plan_id INTEGER NOT NULL, 
        parent_id INTEGER, 
        category VARCHAR(13), 
        name VARCHAR(100), 
        specification VARCHAR(100), 
        unit_price FLOAT, 
        quantity INTEGER, 
        amount FLOAT, 
        remarks VARCHAR(200), 
        PRIMARY KEY (id), 
        FOREIGN KEY(plan_id) REFERENCES budget_plans (id), 
        FOREIGN KEY(parent_id) REFERENCES budget_plan_items (id)
    )",
    ),
    // gantt_tasks
    (
        "table",
        "gantt_tasks",
        "CREATE TABLE gantt_tasks (
        id INTEGER NOT NULL, 
        project_id INTEGER NOT NULL, 
        gantt_id VARCHAR(50) NOT NULL, 
        name VARCHAR(255) NOT NULL, 
        code VARCHAR(50), 
        level INTEGER, 
        status VARCHAR(50), 
        start_date DATETIME, 
        duration INTEGER, 
        end_date DATETIME, 
        start_is_milestone BOOLEAN, 
        end_is_milestone BOOLEAN, 
        progress FLOAT, 
        progress_by_worklog BOOLEAN, 
        description VARCHAR(500), 
        collapsed BOOLEAN, 
        has_child BOOLEAN, 
        responsible VARCHAR(50), 
        \"order\" INTEGER, 
        PRIMARY KEY (id), 
        CONSTRAINT uix_project_gantt_id UNIQUE (project_id, gantt_id), 
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )",
    ),
    (
        "index",
        "ix_gantt_tasks_gantt_id",
        "CREATE INDEX ix_gantt_tasks_gantt_id ON gantt_tasks (gantt_id)",
    ),
    // gantt_dependencies
    (
        "table",
        "gantt_dependencies",
        "CREATE TABLE gantt_dependencies (
        id INTEGER NOT NULL, 
        project_id INTEGER NOT NULL, 
        predecessor_gantt_id VARCHAR(50) NOT NULL, 
        successor_gantt_id VARCHAR(50) NOT NULL, 
        type VARCHAR(10), 
        PRIMARY KEY (id), 
        CONSTRAINT uix_project_dependency UNIQUE (project_id, predecessor_gantt_id, successor_gantt_id), 
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )",
    ),
    // project_documents
    (
        "table",
        "project_documents",
        "CREATE TABLE project_documents (
        id INTEGER NOT NULL, 
        project_id INTEGER NOT NULL, 
        name VARCHAR(100) NOT NULL, 
        doc_type VARCHAR(13) NOT NULL, 
        version VARCHAR(20), 
        description VARCHAR(500), 
        file_path VARCHAR(500), 
        upload_time DATETIME, 
        keywords VARCHAR(200), 
        PRIMARY KEY (id), 
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )",
    ),
    // project_outcome（单数表名，既有结构即如此）
    (
        "table",
        "project_outcome",
        "CREATE TABLE project_outcome (
        id INTEGER NOT NULL, 
        project_id INTEGER NOT NULL, 
        name VARCHAR(200) NOT NULL, 
        type VARCHAR(8) NOT NULL, 
        status VARCHAR(9), 
        authors VARCHAR(200), 
        submit_date DATE, 
        publish_date DATE, 
        journal VARCHAR(200), 
        description VARCHAR(500), 
        remarks VARCHAR(200), 
        attachment_path VARCHAR(500), 
        PRIMARY KEY (id), 
        FOREIGN KEY(project_id) REFERENCES projects (id)
    )",
    ),
    // budget_items
    (
        "table",
        "budget_items",
        "CREATE TABLE budget_items (
        id INTEGER NOT NULL, 
        budget_id INTEGER NOT NULL, 
        category VARCHAR(13) NOT NULL, 
        amount FLOAT, 
        spent_amount FLOAT, 
        PRIMARY KEY (id), 
        FOREIGN KEY(budget_id) REFERENCES budgets (id)
    )",
    ),
    // expenses
    (
        "table",
        "expenses",
        "CREATE TABLE expenses (
        id INTEGER NOT NULL, 
        project_id INTEGER NOT NULL, 
        budget_id INTEGER NOT NULL, 
        category VARCHAR(13) NOT NULL, 
        content VARCHAR(200) NOT NULL, 
        specification VARCHAR(100), 
        supplier VARCHAR(100), 
        amount FLOAT, 
        date DATE, 
        remarks VARCHAR(200), 
        voucher_path VARCHAR(500), 
        PRIMARY KEY (id), 
        FOREIGN KEY(project_id) REFERENCES projects (id), 
        FOREIGN KEY(budget_id) REFERENCES budgets (id)
    )",
    ),
    // actionlogs
    (
        "table",
        "actionlogs",
        "CREATE TABLE actionlogs (
        id INTEGER NOT NULL, 
        project_id INTEGER, 
        budget_id INTEGER, 
        expense_id INTEGER, 
        gantt_task_id INTEGER, 
        project_document_id INTEGER, 
        project_outcome_id INTEGER, 
        type VARCHAR(50) NOT NULL, 
        action VARCHAR(50) NOT NULL, 
        description VARCHAR(200) NOT NULL, 
        operator VARCHAR(50) NOT NULL, 
        timestamp DATETIME, 
        old_data VARCHAR(500), 
        new_data VARCHAR(500), 
        category VARCHAR(50), 
        amount FLOAT, 
        related_info VARCHAR(200), 
        PRIMARY KEY (id), 
        FOREIGN KEY(project_id) REFERENCES projects (id), 
        FOREIGN KEY(budget_id) REFERENCES budgets (id), 
        FOREIGN KEY(expense_id) REFERENCES expenses (id), 
        FOREIGN KEY(gantt_task_id) REFERENCES gantt_tasks (id), 
        FOREIGN KEY(project_document_id) REFERENCES project_documents (id), 
        FOREIGN KEY(project_outcome_id) REFERENCES project_outcome (id)
    )",
    ),
];

/// 补建缺失的表/索引（已存在的不动）。
pub fn create_all(conn: &mut Connection) -> Result<(), DbError> {
    // 查询 sqlite_master 中已存在的对象名
    let existing: HashSet<String> = {
        let mut stmt = conn.prepare(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')",
        )?;
        let names = stmt
            .query_map([], |r| r.get::<_, String>(0))?
            .collect::<Result<HashSet<_>, _>>()?;
        names
    };

    for (kind, name, ddl) in SCHEMA_OBJECTS {
        if existing.contains(*name) {
            continue; // 已存在，跳过
        }
        let _ = kind;
        conn.execute_batch(ddl)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_all_builds_all_12_tables() {
        let mut conn = Connection::open_in_memory().unwrap();
        create_all(&mut conn).unwrap();

        let tables: Vec<String> = conn
            .prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            .unwrap()
            .query_map([], |r| r.get(0))
            .unwrap()
            .collect::<Result<_, _>>()
            .unwrap();

        let expected = [
            "academic_activities",
            "actionlogs",
            "budget_items",
            "budget_plan_items",
            "budget_plans",
            "budgets",
            "expenses",
            "gantt_dependencies",
            "gantt_tasks",
            "project_documents",
            "project_outcome",
            "projects",
        ];
        assert_eq!(tables, expected);
    }

    #[test]
    fn create_all_is_idempotent() {
        let mut conn = Connection::open_in_memory().unwrap();
        create_all(&mut conn).unwrap();
        create_all(&mut conn).unwrap(); // 再次执行不应报错、不应改动
    }

    #[test]
    fn created_schema_matches_golden_file() {
        // golden 文件路径：仓库根 tests/golden/schema.sql（core crate 的上级目录）
        let golden_path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("tests")
            .join("golden")
            .join("schema.sql");
        if !golden_path.exists() {
            eprintln!("跳过：golden schema 文件不存在");
            return;
        }
        let golden = std::fs::read_to_string(&golden_path).unwrap();

        let mut conn = Connection::open_in_memory().unwrap();
        create_all(&mut conn).unwrap();

        // 导出 sqlite_master 中的 DDL，与 golden 文件比对（去空白归一化，
        // 忽略缩进差异，聚焦列名/类型/约束/顺序的真实差异）
        let mut stmt = conn
            .prepare(
                "SELECT sql FROM sqlite_master WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%' ORDER BY name",
            )
            .unwrap();
        let dumped: Vec<String> = stmt
            .query_map([], |r| r.get(0))
            .unwrap()
            .collect::<Result<_, _>>()
            .unwrap();

        let normalize = |s: &str| -> String {
            s.trim_end_matches(';')
                .chars()
                .filter(|c| !c.is_whitespace())
                .collect::<String>()
        };

        // golden 文件按名称排序解析，逐条归一化比对
        let mut golden_named: Vec<(&str, String)> = golden
            .split(';')
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(|s| {
                let name = s.split_whitespace().nth(2).unwrap();
                (name, normalize(s))
            })
            .collect();
        golden_named.sort_by(|a, b| a.0.cmp(b.0));

        assert_eq!(
            dumped.len(),
            golden_named.len(),
            "表/索引数量不一致: dumped={} golden={}",
            dumped.len(),
            golden_named.len()
        );
        for (i, ddl) in dumped.iter().enumerate() {
            assert_eq!(
                normalize(ddl),
                golden_named[i].1,
                "第 {i} 个 DDL 不一致（{}）",
                golden_named[i].0
            );
        }
    }
}
