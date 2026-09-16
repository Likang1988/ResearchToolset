//! 操作日志（对应 Python 各视图内联的 Actionlog 写入逻辑）
//!
//! `log_action` 写入 actionlogs 表（type/action/description/operator/
//! old_data/new_data/category/amount/related_info/related ids），时间戳由
//! SQLite 本地时区生成，与 Python `datetime.now()` 语义一致。

use rusqlite::{params, Connection};

use crate::DbError;

/// 写入一条操作日志（对应 Python `session.add(Actionlog(...))`）。
///
/// `type_`/`action` 取值：如 ("项目", "新增") / ("支出", "添加") / ("支出", "批量导入")。
/// 关联 id 参数（project_id 等）无用则传 `None`。
/// `category`/`amount`/`related_info` 为 Python Actionlog 的扩展字段，
/// 主要用于支出类日志（类别、金额、"项目: X, 预算: Y"），无用则传 `None`。
#[allow(clippy::too_many_arguments)]
pub fn log_action(
    conn: &Connection,
    project_id: Option<i64>,
    budget_id: Option<i64>,
    expense_id: Option<i64>,
    gantt_task_id: Option<i64>,
    project_document_id: Option<i64>,
    project_outcome_id: Option<i64>,
    type_: &str,
    action: &str,
    description: &str,
    operator: &str,
    old_data: Option<&str>,
    new_data: Option<&str>,
    category: Option<&str>,
    amount: Option<f64>,
    related_info: Option<&str>,
) -> Result<(), DbError> {
    conn.execute(
        "INSERT INTO actionlogs \
         (project_id, budget_id, expense_id, gantt_task_id, project_document_id, \
          project_outcome_id, type, action, description, operator, timestamp, old_data, new_data, \
          category, amount, related_info) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, datetime('now','localtime'), \
                 ?11, ?12, ?13, ?14, ?15)",
        params![
            project_id,
            budget_id,
            expense_id,
            gantt_task_id,
            project_document_id,
            project_outcome_id,
            type_,
            action,
            description,
            operator,
            old_data,
            new_data,
            category,
            amount,
            related_info,
        ],
    )?;
    Ok(())
}

/// 查询最近的操作日志（按时间倒序，最多 `limit` 条）。
///
/// 对应 Python `help_interface.load_actionlogs` 的
/// `order_by(Actionlog.timestamp.desc()).limit(100)`。
/// 时间戳为 `datetime('now','localtime')` 字符串（秒级），可字典序比较；
/// 同秒追加 `id DESC` 兜底保证稳定排序。
pub fn list_actionlogs(
    conn: &Connection,
    limit: i64,
) -> Result<Vec<crate::models::Actionlog>, DbError> {
    let mut stmt = conn.prepare(
        "SELECT id, project_id, budget_id, expense_id, gantt_task_id, project_document_id, \
         project_outcome_id, type, action, description, operator, timestamp, old_data, new_data, \
         category, amount, related_info \
         FROM actionlogs \
         ORDER BY timestamp DESC, id DESC \
         LIMIT ?1",
    )?;
    let rows = stmt.query_map([limit], crate::models::Actionlog::from_row)?;
    let mut logs = Vec::new();
    for row in rows {
        logs.push(row?);
    }
    Ok(logs)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db;

    #[test]
    fn writes_actionlog_row() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let mut conn = db::open(tmp.path()).unwrap();
        db::init_db(&mut conn).unwrap();

        log_action(
            &conn,
            Some(42),
            None,
            None,
            None,
            None,
            None,
            "项目",
            "新增",
            "添加项目：测试 - F001",
            "系统用户",
            None,
            Some("名称: 测试, 财务编号: F001"),
            None,
            None,
            None,
        )
        .unwrap();

        let (cnt, type_, action, ts, old_data) = conn
            .query_row(
                "SELECT COUNT(*), type, action, timestamp, old_data FROM actionlogs",
                [],
                |r| {
                    Ok((
                        r.get::<_, i64>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, String>(2)?,
                        r.get::<_, String>(3)?,
                        r.get::<_, Option<String>>(4)?,
                    ))
                },
            )
            .unwrap();
        assert_eq!(cnt, 1);
        assert_eq!(type_, "项目");
        assert_eq!(action, "新增");
        assert!(!ts.is_empty());
        assert_eq!(old_data, None);
    }

    #[test]
    fn list_actionlogs_newest_first_with_limit() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let mut conn = db::open(tmp.path()).unwrap();
        db::init_db(&mut conn).unwrap();

        for i in 0..5 {
            log_action(
                &conn,
                None,
                None,
                None,
                None,
                None,
                None,
                "测试",
                "动作",
                &format!("描述 {i}"),
                "系统用户",
                None,
                Some(&format!(r#"{{"name":"任务{i}"}}"#)),
                None,
                None,
                None,
            )
            .unwrap();
        }

        // 全部取出：按时间倒序（同秒按 id 倒序兜底）
        let logs = list_actionlogs(&conn, 100).unwrap();
        assert_eq!(logs.len(), 5);
        assert!(logs[0].id > logs[1].id);
        assert_eq!(logs[0].description, "描述 4");

        // limit 生效
        let limited = list_actionlogs(&conn, 2).unwrap();
        assert_eq!(limited.len(), 2);
        assert_eq!(limited[0].description, "描述 4");
        assert_eq!(limited[1].description, "描述 3");

        // 字段透传完整（old_data / related 都为 NULL 时正常）
        assert_eq!(logs[0].r#type, "测试");
        assert_eq!(logs[0].action, "动作");
        assert!(logs[0].timestamp.is_some());
        assert_eq!(logs[0].new_data.as_deref(), Some(r#"{"name":"任务4"}"#));
        assert!(logs[0].old_data.is_none());
        assert!(logs[0].related_info.is_none());
        assert!(logs[0].project_id.is_none());
    }
}