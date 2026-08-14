//! migrate_db 等价物：列级数据库迁移
//!
//! 逐字复刻 `app/models/database.py::migrate_db` 的行为（含既有缺陷）：
//! - B2: `project_outcomes`（复数）表名检查永不命中 → 对应分支为 no-op
//! - B3: expenses 重建临时表无外键
//! - B4: actionlogs 临时表外键指向不存在的 `project_outcomes`（SQLite 默认不强制外键，无实际影响）
//! 缺陷详情与处理策略见 `docs/migration/feature-checklist.md` §11。

use rusqlite::{Connection, OptionalExtension};

use crate::DbError;

/// 查询表是否存在（与 Python `SELECT name FROM sqlite_master WHERE type='table' AND name=?` 等价）
fn table_exists(conn: &Connection, name: &str) -> Result<bool, DbError> {
    let exists = conn
        .query_row(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?1",
            [name],
            |_| Ok(()),
        )
        .optional()?
        .is_some();
    Ok(exists)
}

/// 查询表的所有列名（PRAGMA table_info 等价物）
fn table_columns(conn: &Connection, table: &str) -> Result<Vec<(String, String)>, DbError> {
    let mut stmt = conn.prepare(&format!("PRAGMA table_info({table})"))?;
    let cols = stmt
        .query_map([], |row| Ok((row.get::<_, String>(1)?, row.get::<_, String>(2)?)))?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(cols)
}

/// 迁移数据库（Python `migrate_db` 等价物）
pub fn migrate_db(conn: &mut Connection) -> Result<(), DbError> {
    // Python 版在外层开启事务，并在若干节点提交；这里显式 BEGIN/COMMIT 复刻同样语义
    conn.execute_batch("BEGIN")?;
    let result = migrate_inner(conn);
    if result.is_err() {
        // 复刻 Python 的 rollback 行为
        let _ = conn.execute_batch("ROLLBACK");
    }
    result
}

fn migrate_inner(conn: &mut Connection) -> Result<(), DbError> {
    // Python 版在 expenses/actionlogs 重建后各自对同一 Transaction 对象 commit。
    // SQLAlchemy 对已提交事务二次 commit 抛 InvalidRequestError（Python 潜在缺陷 B9：
    // 两表同时需重建时启动崩溃）。Rust 版将后续 commit 降级为 no-op 使迁移可完成。
    // 另：Python 版若全程无 commit 命中点（如仅需给 gantt_tasks/projects 补列），
    // finally 会回滚全部 ALTER，迁移实际无效（Python 缺陷 B10）。
    // Rust 版偏离：结束时若仍有未提交变更则提交，使迁移真正生效。
    let mut committed = false;
    let mut changed = false;
    let commit_noop = |committed: &mut bool, conn: &mut Connection| -> Result<(), DbError> {
        if *committed {
            Ok(()) // 已提交过，no-op（对齐 SQLAlchemy 未命中该路径的等价状态）
        } else {
            conn.execute_batch("COMMIT")?;
            *committed = true;
            Ok(())
        }
    };

    // ── 1. gantt_tasks：补 responsible / "order" 列 ──────────────────────────
    if table_exists(conn, "gantt_tasks")? {
        let columns = table_columns(conn, "gantt_tasks")?;
        if !columns.iter().any(|(name, _)| name == "responsible") {
            conn.execute(
                "ALTER TABLE gantt_tasks ADD COLUMN responsible VARCHAR(50)",
                [],
            )?;
            changed = true;
            println!("成功添加 responsible 列到 gantt_tasks 表");
        }
        if !columns.iter().any(|(name, _)| name == "order") {
            // 注意关键字 order 需加双引号
            conn.execute(
                "ALTER TABLE gantt_tasks ADD COLUMN \"order\" INTEGER DEFAULT 0",
                [],
            )?;
            changed = true;
            println!("成功添加 order 列到 gantt_tasks 表");
        }
    }

    // ── 2. project_outcomes（复数）：Python 缺陷 B2，表不存在，永不命中 ───────
    // 保持 no-op，复刻原行为

    // ── 3. projects：补 director 列 ──────────────────────────────────────────
    if table_exists(conn, "projects")? {
        let columns = table_columns(conn, "projects")?;
        if !columns.iter().any(|(name, _)| name == "director") {
            let result = conn.execute("ALTER TABLE projects ADD COLUMN director VARCHAR(50)", []);
            match result {
                Ok(_) => {
                    changed = true;
                    println!("成功添加 director 列到 projects 表")
                }
                Err(e) => println!("添加 director 列失败: {e}"),
            }
        }
    }

    // ── 4. expenses：缺 voucher_path 时重建表（复刻缺陷 B3：无外键）────────────
    if table_exists(conn, "expenses")? {
        let columns = table_columns(conn, "expenses")?;
        if !columns.iter().any(|(name, _)| name == "voucher_path") {
            conn.execute_batch(
                "CREATE TABLE expenses_temp (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    budget_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    specification TEXT,
                    supplier TEXT,
                    amount FLOAT,
                    date DATE,
                    remarks TEXT,
                    voucher_path TEXT
                )",
            )?;
            conn.execute_batch(
                "INSERT INTO expenses_temp (
                    id, project_id, budget_id, category, content,
                    specification, supplier, amount, date, remarks
                )
                SELECT id, project_id, budget_id, category, content,
                       specification, supplier, amount, date, remarks
                FROM expenses",
            )?;
            conn.execute_batch("DROP TABLE expenses")?;
            conn.execute_batch("ALTER TABLE expenses_temp RENAME TO expenses")?;
            changed = true;
            commit_noop(&mut committed, conn)?;
            println!("成功添加voucher_path列");
        }

        // ── 5. actionlogs：结构不满足需求时全表重建（复刻缺陷 B4）───────────────
        if table_exists(conn, "actionlogs")? {
            let columns = table_columns(conn, "actionlogs")?;
            let col_map: std::collections::HashMap<String, String> =
                columns.into_iter().collect();

            let needs_migration = {
                let ts_ok = col_map
                    .get("timestamp")
                    .map(|t| t == "DATETIME")
                    .unwrap_or(false);
                let has = |c: &str| col_map.contains_key(c);
                !ts_ok
                    || !has("old_data")
                    || !has("new_data")
                    || !has("category")
                    || !has("amount")
                    || !has("related_info")
                    || !has("gantt_task_id")
                    || !has("project_document_id")
                    || !has("project_outcome_id")
            };

            if needs_migration {
                conn.execute_batch(
                    "CREATE TABLE actionlogs_temp (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER,
                        budget_id INTEGER,
                        expense_id INTEGER,
                        gantt_task_id INTEGER,
                        project_document_id INTEGER,
                        project_outcome_id INTEGER,
                        type TEXT NOT NULL,
                        action TEXT NOT NULL,
                        description TEXT NOT NULL,
                        operator TEXT NOT NULL,
                        timestamp DATETIME,
                        old_data TEXT,
                        new_data TEXT,
                        category TEXT,
                        amount FLOAT,
                        related_info TEXT,
                        FOREIGN KEY(project_id) REFERENCES projects (id),
                        FOREIGN KEY(budget_id) REFERENCES budgets (id),
                        FOREIGN KEY(expense_id) REFERENCES expenses (id),
                        FOREIGN KEY(gantt_task_id) REFERENCES gantt_tasks (id),
                        FOREIGN KEY(project_document_id) REFERENCES project_documents (id),
                        FOREIGN KEY(project_outcome_id) REFERENCES project_outcomes (id)
                    )",
                )?;
                conn.execute_batch(
                    "INSERT INTO actionlogs_temp (
                        id, project_id, budget_id, expense_id, type,
                        action, description, operator, timestamp,
                        old_data, new_data, category, amount, related_info,
                        gantt_task_id, project_document_id, project_outcome_id
                    )
                    SELECT
                        id, project_id, budget_id, expense_id, type,
                        action, description, operator, datetime(timestamp),
                        old_data, new_data, category, amount, related_info,
                        NULL, NULL, NULL
                    FROM actionlogs",
                )?;
                conn.execute_batch("DROP TABLE actionlogs")?;
                conn.execute_batch("ALTER TABLE actionlogs_temp RENAME TO actionlogs")?;
                changed = true;
                commit_noop(&mut committed, conn)?;
                println!("成功更新actionlogs表结构，添加了新字段并修正了timestamp列类型");
            } else {
                println!("actionlogs 表结构无需更新");
            }
        }
    }

    // ── 6. project_outcomes（复数）：同缺陷 B2，no-op ─────────────────────────

    // ── 7. budget_plan_items：按 expected_columns 补缺列 ─────────────────────
    if table_exists(conn, "budget_plan_items")? {
        let columns = table_columns(conn, "budget_plan_items")?;
        let mut needs_commit = false;

        // 模型应有的列及其 SQLite 类型（与 Python expected_columns 一致）
        let expected_columns: [(&str, &str); 9] = [
            ("plan_id", "INTEGER"),
            ("parent_id", "INTEGER"),
            ("category", "TEXT"),
            ("name", "TEXT"),
            ("specification", "TEXT"),
            ("unit_price", "FLOAT"),
            ("quantity", "INTEGER"),
            ("amount", "FLOAT"),
            ("remarks", "TEXT"),
        ];

            for (col_name, col_type) in expected_columns {
            if !columns.iter().any(|(name, _)| name == col_name) {
                println!("尝试添加 {col_name} 列 ({col_type}) 到 budget_plan_items 表...");
                conn.execute(
                    &format!("ALTER TABLE budget_plan_items ADD COLUMN {col_name} {col_type}"),
                    [],
                )?;
                needs_commit = true;
                changed = true;
            }
        }

        if needs_commit {
            commit_noop(&mut committed, conn)?;
            println!("budget_plan_items 表结构更新提交成功");
        } else {
            println!("budget_plan_items 表结构无需更新");
        }
    }

    // 偏离 B10：任何未提交的变更（如仅 gantt_tasks/projects 补列）最终提交，
    // 使迁移真正生效
    if !committed && changed {
        conn.execute_batch("COMMIT")?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::schema;
    use std::path::Path;

    fn fixture_path(name: &str) -> std::path::PathBuf {
        // core crate 目录为 rust/core；fixtures 位于 rust/tests/fixtures
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("tests")
            .join("fixtures")
            .join(name)
    }

    /// 与应用的连接语义一致：外键关闭（rusqlite 默认开启，Python/SQLAlchemy 默认关闭。
    /// actionlogs 迁移临时表外键指向不存在的 project_outcomes，FK=ON 时会失败）
    fn migrate_conn(path: &std::path::Path) -> Connection {
        let conn = Connection::open(path).unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        conn
    }

    /// 在内存库中构造"最旧版" schema（缺列、缺表），验证迁移收敛
    fn build_synthetic_legacy(conn: &mut Connection) {
        conn.execute_batch(
            "CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                financial_code VARCHAR(50),
                project_code VARCHAR(50),
                project_type VARCHAR(50),
                leader VARCHAR(50),
                start_date DATE,
                end_date DATE,
                total_budget FLOAT
            );
            CREATE TABLE budgets (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                year INTEGER,
                total_amount FLOAT,
                spent_amount FLOAT,
                UNIQUE (project_id, year)
            );
            CREATE TABLE budget_items (
                id INTEGER PRIMARY KEY,
                budget_id INTEGER NOT NULL,
                category VARCHAR(13) NOT NULL,
                amount FLOAT,
                spent_amount FLOAT
            );
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                budget_id INTEGER NOT NULL,
                category VARCHAR(13) NOT NULL,
                content VARCHAR(200) NOT NULL,
                specification VARCHAR(100),
                supplier VARCHAR(100),
                amount FLOAT,
                date DATE,
                remarks VARCHAR(200)
            );
            CREATE TABLE gantt_tasks (
                id INTEGER PRIMARY KEY,
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
                has_child BOOLEAN
            );
            CREATE TABLE gantt_dependencies (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                predecessor_gantt_id VARCHAR(50) NOT NULL,
                successor_gantt_id VARCHAR(50) NOT NULL,
                type VARCHAR(10)
            );
            CREATE TABLE project_documents (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                doc_type VARCHAR(13) NOT NULL,
                version VARCHAR(20),
                description VARCHAR(500),
                file_path VARCHAR(500),
                upload_time DATETIME,
                keywords VARCHAR(200)
            );
            CREATE TABLE project_outcome (
                id INTEGER PRIMARY KEY,
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
                attachment_path VARCHAR(500)
            );
            CREATE TABLE budget_plans (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                create_date DATE,
                total_amount FLOAT,
                remarks VARCHAR(200)
            );
            CREATE TABLE budget_plan_items (
                id INTEGER PRIMARY KEY,
                plan_id INTEGER NOT NULL
            );
            -- 旧版 actionlogs（缺新字段、timestamp 类型不同）
            CREATE TABLE actionlogs (
                id INTEGER PRIMARY KEY,
                project_id INTEGER,
                budget_id INTEGER,
                expense_id INTEGER,
                type VARCHAR(50) NOT NULL,
                action VARCHAR(50) NOT NULL,
                description VARCHAR(200) NOT NULL,
                operator VARCHAR(50) NOT NULL,
                timestamp VARCHAR(50),
                old_data VARCHAR(500),
                new_data VARCHAR(500),
                category VARCHAR(50),
                amount FLOAT,
                related_info VARCHAR(200)
            );
            INSERT INTO projects (id, name) VALUES (1, '测试项目');
            INSERT INTO expenses (id, project_id, budget_id, category, content, amount, date)
                VALUES (1, 1, 0, '材料费', '测试支出', 100.0, '2025-01-01');
            INSERT INTO actionlogs (id, project_id, budget_id, expense_id, type, action, description, operator, timestamp)
                VALUES (1, 1, NULL, NULL, '项目', '新增', '描述', '测试员', '2025-01-01 10:00:00');",
        )
        .unwrap();
    }

    #[test]
    fn migrate_converges_synthetic_legacy() {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        let mut conn = conn;
        build_synthetic_legacy(&mut conn);
        // 模拟 init_db：先 create_all 补缺失表，再 migrate_db
        schema::create_all(&mut conn).unwrap();
        migrate_db(&mut conn).unwrap();

        // expenses 应已重建并保留数据，voucher_path 存在
        let cols = table_columns(&conn, "expenses").unwrap();
        assert!(
            cols.iter().any(|(n, _)| n == "voucher_path"),
            "expenses 应有 voucher_path"
        );
        let amount: f64 = conn
            .query_row("SELECT amount FROM expenses WHERE id=1", [], |r| r.get(0))
            .unwrap();
        assert_eq!(amount, 100.0);

        // gantt_tasks 应有 responsible / "order"
        let cols = table_columns(&conn, "gantt_tasks").unwrap();
        assert!(cols.iter().any(|(n, _)| n == "responsible"));
        assert!(cols.iter().any(|(n, _)| n == "order"));

        // projects 应有 director
        let cols = table_columns(&conn, "projects").unwrap();
        assert!(cols.iter().any(|(n, _)| n == "director"));

        // actionlogs 应全表重建：timestamp 类型 DATETIME + 新字段 + 数据保留
        let cols = table_columns(&conn, "actionlogs").unwrap();
        assert!(
            cols.iter().any(|(n, t)| n == "timestamp" && t == "DATETIME"),
            "actionlogs.timestamp 应为 DATETIME"
        );
        for c in [
            "old_data",
            "new_data",
            "category",
            "amount",
            "related_info",
            "gantt_task_id",
            "project_document_id",
            "project_outcome_id",
        ] {
            assert!(cols.iter().any(|(n, _)| n == c), "actionlogs 缺列 {c}");
        }
        let (desc, ts): (String, String) = conn
            .query_row(
                "SELECT description, timestamp FROM actionlogs WHERE id=1",
                [],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(desc, "描述");
        assert!(ts.starts_with("2025-01-01"), "timestamp 应被 datetime() 规范化: {ts}");

        // budget_plan_items 应补全所有列
        let cols = table_columns(&conn, "budget_plan_items").unwrap();
        for c in [
            "plan_id",
            "parent_id",
            "category",
            "name",
            "specification",
            "unit_price",
            "quantity",
            "amount",
            "remarks",
        ] {
            assert!(cols.iter().any(|(n, _)| n == c), "budget_plan_items 缺列 {c}");
        }
    }

    /// 使用真实数据 fixtures 的对照测试（本地有 fixtures 时执行；CI 无 fixtures 自动跳过）
    #[test]
    fn migrate_real_fixtures() {
        for fixture in ["golden_data.db", "legacy_data.db"] {
            let path = fixture_path(fixture);
            if !path.exists() {
                eprintln!("跳过 {fixture}（fixtures 未检出，本地手动测试用）");
                continue;
            }
            let tmp = tempfile::tempdir().unwrap();
            let copy = tmp.path().join(fixture);
            std::fs::copy(&path, &copy).unwrap();
            let mut conn = migrate_conn(&copy);
            schema::create_all(&mut conn).unwrap();
            migrate_db(&mut conn).unwrap();
            // 数据必须保留
            let count: i64 = conn
                .query_row("SELECT COUNT(*) FROM projects", [], |r| r.get(0))
                .unwrap();
            assert!(count > 0, "{fixture} 迁移后 projects 不应为空");
        }
    }

    #[test]
    fn migrate_is_noop_on_current_schema() {
        let mut conn = Connection::open_in_memory().unwrap();
        schema::create_all(&mut conn).unwrap();
        migrate_db(&mut conn).unwrap(); // 不应报错、不应改动
        let cols = table_columns(&conn, "expenses").unwrap();
        assert!(cols.iter().any(|(n, _)| n == "voucher_path"));
    }
}
