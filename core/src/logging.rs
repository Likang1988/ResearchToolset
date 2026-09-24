//! 操作日志（actionlogs 表的统一写入与查询）
//!
//! `log_action` 写入 actionlogs 表（type/action/description/operator/
//! old_data/new_data/category/amount/related_info/related ids），时间戳由
//! SQLite 本地时区生成。

use rusqlite::{params, Connection};

use crate::DbError;

/// 写入一条操作日志。
///
/// `type_`/`action` 取值：如 ("项目", "新增") / ("支出", "添加") / ("支出", "批量导入")。
/// 关联 id 参数（project_id 等）无用则传 `None`。
/// `category`/`amount`/`related_info` 为 actionlogs 的扩展字段，
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

/// 操作日志查询条件（None 表示该项不过滤）
#[derive(Debug, Clone, Default)]
pub struct LogQuery {
    pub log_type: Option<String>,
    pub action: Option<String>,
    /// 关键词：描述或相关信息模糊匹配
    pub keyword: Option<String>,
    /// 起始时间（"YYYY-MM-DD" 或完整时间串）
    pub start: Option<String>,
    /// 截止时间（"YYYY-MM-DD" 视为当天 23:59:59）
    pub end: Option<String>,
}

impl LogQuery {
    /// 生成 WHERE 子句与参数（时间串为裸日期时补齐到当天末尾）
    fn clause(&self) -> (String, Vec<Box<dyn rusqlite::types::ToSql>>) {
        let mut conds: Vec<String> = Vec::new();
        let mut args: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();
        if let Some(t) = &self.log_type {
            conds.push("type = ?".to_string());
            args.push(Box::new(t.clone()));
        }
        if let Some(a) = &self.action {
            conds.push("action = ?".to_string());
            args.push(Box::new(a.clone()));
        }
        if let Some(k) = self.keyword.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
            conds.push("(description LIKE ? OR related_info LIKE ?)".to_string());
            let pat = format!("%{k}%");
            args.push(Box::new(pat.clone()));
            args.push(Box::new(pat));
        }
        if let Some(s) = &self.start {
            conds.push("timestamp >= ?".to_string());
            args.push(Box::new(s.clone()));
        }
        if let Some(e) = &self.end {
            // type=date 只给日期时，把边界扩到当天末尾
            let padded = if e.len() == 10 { format!("{e} 23:59:59") } else { e.clone() };
            conds.push("timestamp <= ?".to_string());
            args.push(Box::new(padded));
        }
        let where_sql =
            if conds.is_empty() { String::new() } else { format!(" WHERE {}", conds.join(" AND ")) };
        (where_sql, args)
    }
}

/// 按条件分页查询操作日志，返回 (当页行, 匹配总数)。
pub fn query_actionlogs(
    conn: &Connection,
    q: &LogQuery,
    limit: i64,
    offset: i64,
) -> Result<(Vec<crate::models::Actionlog>, i64), DbError> {
    let (where_sql, args) = q.clause();
    let total: i64 = conn.query_row(
        &format!("SELECT COUNT(*) FROM actionlogs{where_sql}"),
        rusqlite::params_from_iter(args.iter().map(|a| a.as_ref())),
        |r| r.get(0),
    )?;
    let sql = format!(
        "SELECT id, project_id, budget_id, expense_id, gantt_task_id, project_document_id, \
         project_outcome_id, type, action, description, operator, timestamp, old_data, new_data, \
         category, amount, related_info \
         FROM actionlogs{where_sql} \
         ORDER BY timestamp DESC, id DESC \
         LIMIT ? OFFSET ?"
    );
    let mut bind: Vec<&dyn rusqlite::types::ToSql> = args.iter().map(|a| a.as_ref()).collect();
    bind.push(&limit);
    bind.push(&offset);
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(bind.as_slice(), crate::models::Actionlog::from_row)?;
    let mut logs = Vec::new();
    for row in rows {
        logs.push(row?);
    }
    Ok((logs, total))
}

/// 日志中出现过的 类型/动作 枚举（供筛选下拉）。
pub fn actionlog_facets(conn: &Connection) -> Result<(Vec<String>, Vec<String>), DbError> {
    let distinct = |conn: &Connection, col: &str| -> Result<Vec<String>, DbError> {
        let mut stmt =
            conn.prepare(&format!("SELECT DISTINCT {col} FROM actionlogs ORDER BY {col}"))?;
        let rows = stmt.query_map([], |r| r.get::<_, String>(0))?;
        let mut out = Vec::new();
        for row in rows {
            out.push(row?);
        }
        Ok(out)
    };
    Ok((distinct(conn, "type")?, distinct(conn, "action")?))
}

/// 清理 `keep_days` 天之前的操作日志，返回删除条数（清理行为本身也记日志）。
pub fn prune_actionlogs(conn: &Connection, keep_days: i64) -> Result<usize, DbError> {
    let cutoff = format!("-{keep_days} days");
    let deleted = conn.execute(
        "DELETE FROM actionlogs WHERE timestamp < datetime('now','localtime', ?1)",
        [cutoff],
    )?;
    log_action(
        conn,
        None,
        None,
        None,
        None,
        None,
        None,
        "系统维护",
        "清理日志",
        &format!("清理 {keep_days} 天前的操作日志，删除 {deleted} 条"),
        "系统用户",
        None,
        None,
        None,
        None,
        None,
    )?;
    Ok(deleted)
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

    #[test]
    fn query_filters_and_paginates_with_total() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let mut conn = db::open(tmp.path()).unwrap();
        db::init_db(&mut conn).unwrap();

        for i in 0..3 {
            log_action(
                &conn, None, None, None, None, None, None,
                "项目", "新增", &format!("添加项目 甲{i}"), "系统用户",
                None, None, None, None, None,
            )
            .unwrap();
        }
        for i in 0..4 {
            log_action(
                &conn, None, None, None, None, None, None,
                "支出", "添加", &format!("添加支出 乙{i}"), "系统用户",
                None, None, None, None, Some("项目: 围产期, 预算: 材料"),
            )
            .unwrap();
        }

        // 类型过滤
        let q = LogQuery { log_type: Some("项目".to_string()), ..Default::default() };
        let (rows, total) = query_actionlogs(&conn, &q, 10, 0).unwrap();
        assert_eq!(total, 3);
        assert_eq!(rows.len(), 3);
        assert!(rows.iter().all(|r| r.r#type == "项目"));

        // 关键词命中 description 或 related_info
        let q = LogQuery { keyword: Some("围产期".to_string()), ..Default::default() };
        let (rows, total) = query_actionlogs(&conn, &q, 10, 0).unwrap();
        assert_eq!(total, 4);
        assert!(rows.iter().all(|r| r.action == "添加"));
        let q = LogQuery { keyword: Some("乙2".to_string()), ..Default::default() };
        let (_, total) = query_actionlogs(&conn, &q, 10, 0).unwrap();
        assert_eq!(total, 1);

        // 分页：limit 2 offset 4 → 第 5、6 条（新→旧），total 恒为全量
        // 固定时间戳避免跨秒抖动，让 id DESC 兜底排序可断言
        conn.execute("UPDATE actionlogs SET timestamp = '2026-01-01 12:00:00'", [])
            .unwrap();
        let q = LogQuery::default();
        let (rows, total) = query_actionlogs(&conn, &q, 2, 4).unwrap();
        assert_eq!(total, 7);
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].description, "添加项目 甲2"); // 跳过乙3..乙0，第 5 新 → 甲2
        assert_eq!(rows[1].description, "添加项目 甲1");

        // type + action 组合
        let q = LogQuery {
            log_type: Some("支出".to_string()),
            action: Some("添加".to_string()),
            ..Default::default()
        };
        let (_, total) = query_actionlogs(&conn, &q, 10, 0).unwrap();
        assert_eq!(total, 4);
    }

    #[test]
    fn facets_list_distinct_types_and_actions() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let mut conn = db::open(tmp.path()).unwrap();
        db::init_db(&mut conn).unwrap();

        log_action(&conn, None, None, None, None, None, None, "项目", "新增", "a", "u", None, None, None, None, None).unwrap();
        log_action(&conn, None, None, None, None, None, None, "支出", "删除", "b", "u", None, None, None, None, None).unwrap();
        log_action(&conn, None, None, None, None, None, None, "项目", "编辑", "c", "u", None, None, None, None, None).unwrap();

        let (types, actions) = actionlog_facets(&conn).unwrap();
        assert_eq!(types, vec!["支出", "项目"]); // ORDER BY 中文按 BINARY 码序，支出(U+652F) < 项目(U+9879)
        assert_eq!(actions.len(), 3);
    }

    #[test]
    fn prune_removes_old_logs_and_self_logs() {
        let tmp = tempfile::NamedTempFile::new().unwrap();
        let mut conn = db::open(tmp.path()).unwrap();
        db::init_db(&mut conn).unwrap();

        // 造 2 条"很久以前" + 1 条刚刚
        log_action(&conn, None, None, None, None, None, None, "项目", "新增", "old1", "u", None, None, None, None, None).unwrap();
        log_action(&conn, None, None, None, None, None, None, "项目", "新增", "old2", "u", None, None, None, None, None).unwrap();
        conn.execute("UPDATE actionlogs SET timestamp = datetime('now','localtime','-400 days')", [])
            .unwrap();
        log_action(&conn, None, None, None, None, None, None, "项目", "新增", "fresh", "u", None, None, None, None, None).unwrap();

        let deleted = prune_actionlogs(&conn, 30).unwrap();
        assert_eq!(deleted, 2);

        // 剩：fresh + 清理日志自身
        let descs: Vec<String> = conn
            .prepare("SELECT description FROM actionlogs ORDER BY id")
            .unwrap()
            .query_map([], |r| r.get(0))
            .unwrap()
            .collect::<rusqlite::Result<_>>()
            .unwrap();
        assert_eq!(descs.len(), 2);
        assert_eq!(descs[0], "fresh");
        assert!(descs[1].contains("删除 2 条"));
    }
}