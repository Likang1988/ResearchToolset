//! 项目成果服务
//!
//! 业务核心：
//! - `type` / `status` 在库中以英文枚举名（KEY）存储（如 `PAPER` / `DRAFT`），
//!   对外统一为中文 label（如「论文」/「草稿」），读写时双向转换。
//! - 新增/编辑/删除均写入 actionlogs（type="成果"）：
//!   新增/编辑携带 `project_outcome_id`，删除时不填（先删成果再记日志）。
//! - 附件文件操作（拷贝/删除）由 attachments 模块完成，本服务只负责路径落库；
//!   成果附件使用 `base_folder: "outcomes"`。
//! - 删除成果后由调用方（command 层）清理磁盘附件。

use rusqlite::{params, Connection, OptionalExtension};

use crate::models::ProjectOutcome;
use crate::DbError;

/// 全部成果类型的中文 label（与 `OutcomeType` 枚举顺序一致，前端下拉框用）。
pub const OUTCOME_TYPES: [&str; 6] = ["论文", "专利", "软著", "标准", "获奖", "其他"];

/// 全部成果状态的中文 label（与 `OutcomeStatus` 枚举顺序一致，前端下拉框用）。
pub const OUTCOME_STATUSES: [&str; 5] = ["草稿", "已提交", "已接收", "已发表/授权", "已拒绝"];

/// 中文 label → 存储 KEY（英文枚举名）。未识别返回原值（兜底）。
fn to_storage_key(label: &str) -> String {
    match label {
        "论文" => "PAPER",
        "专利" => "PATENT",
        "软著" => "SOFTWARE",
        "标准" => "STANDARD",
        "获奖" => "AWARD",
        "其他" => "OTHER",
        _ => label,
    }
    .to_string()
}

/// 存储 KEY → 中文 label。未识别原样返回。
fn to_label(key: &str) -> String {
    match key {
        "PAPER" => "论文",
        "PATENT" => "专利",
        "SOFTWARE" => "软著",
        "STANDARD" => "标准",
        "AWARD" => "获奖",
        "OTHER" => "其他",
        _ => key,
    }
    .to_string()
}

/// 中文状态 label → 存储 KEY。未识别原样返回。
fn to_status_key(label: &str) -> String {
    match label {
        "草稿" => "DRAFT",
        "已提交" => "SUBMITTED",
        "已接收" => "ACCEPTED",
        "已发表/授权" => "PUBLISHED",
        "已拒绝" => "REJECTED",
        _ => label,
    }
    .to_string()
}

/// 存储状态 KEY → 中文 label。未识别原样返回。
fn status_to_label(key: &str) -> String {
    match key {
        "DRAFT" => "草稿",
        "SUBMITTED" => "已提交",
        "ACCEPTED" => "已接收",
        "PUBLISHED" => "已发表/授权",
        "REJECTED" => "已拒绝",
        _ => key,
    }
    .to_string()
}

/// 新增/编辑成果输入。
///
/// `type` / `status` 从前端传入中文 label，service 内转存储 KEY 入库。
/// `attachment_path` 仅新增时由调用方填写（编辑不改附件路径；
/// 附件不进编辑表单，走表格按钮单独管理）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct OutcomeInput {
    pub project_id: i64,
    pub name: String,
    pub r#type: String,
    pub status: Option<String>,
    pub authors: Option<String>,
    pub submit_date: Option<String>,
    pub publish_date: Option<String>,
    pub journal: Option<String>,
    pub description: Option<String>,
    pub attachment_path: Option<String>,
}

/// selector 查询用公共列清单（type/status 读取后转换中文 label）。
const SELECT_COLS: &str = "id, project_id, name, type, status, authors, submit_date, \
                           publish_date, journal, description, attachment_path";

/// 从 row 构造 ProjectOutcome（type/status 存 KEY → 转 label）
fn row_to_outcome(row: &rusqlite::Row) -> rusqlite::Result<ProjectOutcome> {
    let type_key: String = row.get(3)?;
    let status_key: Option<String> = row.get(4)?;
    Ok(ProjectOutcome {
        id: row.get(0)?,
        project_id: row.get(1)?,
        name: row.get(2)?,
        r#type: to_label(&type_key),
        status: status_key.as_deref().map(status_to_label),
        authors: row.get(5)?,
        submit_date: row.get(6)?,
        publish_date: row.get(7)?,
        journal: row.get(8)?,
        description: row.get(9)?,
        remarks: None, // 表格/对话框均不使用 remarks；读出语义无实际用途
        attachment_path: row.get(10)?,
    })
}

/// 列出某项目下全部成果（按 publish_date DESC 排序）。
pub fn list_outcomes_by_project(
    conn: &Connection,
    project_id: i64,
) -> Result<Vec<ProjectOutcome>, DbError> {
    let mut stmt = conn.prepare(&format!(
        "SELECT {SELECT_COLS} FROM project_outcome \
         WHERE project_id = ?1 ORDER BY publish_date DESC"
    ))?;
    let rows = stmt.query_map([project_id], row_to_outcome)?;
    let mut outcomes = Vec::new();
    for row in rows {
        outcomes.push(row?);
    }
    Ok(outcomes)
}

/// 列出全部项目成果（「全部成果」模式，按 publish_date DESC）。
pub fn list_all_outcomes(conn: &Connection) -> Result<Vec<ProjectOutcome>, DbError> {
    let mut stmt = conn.prepare(&format!(
        "SELECT {SELECT_COLS} FROM project_outcome ORDER BY publish_date DESC"
    ))?;
    let rows = stmt.query_map([], row_to_outcome)?;
    let mut outcomes = Vec::new();
    for row in rows {
        outcomes.push(row?);
    }
    Ok(outcomes)
}

/// 按 id 查成果（编辑回填用）。不存在返回 None。
pub fn get_outcome_by_id(conn: &Connection, id: i64) -> Result<Option<ProjectOutcome>, DbError> {
    let row = conn
        .query_row(
            &format!("SELECT {SELECT_COLS} FROM project_outcome WHERE id = ?1"),
            [id],
            row_to_outcome,
        )
        .optional()?;
    Ok(row)
}

/// 写入操作日志（operator 暂记「当前用户」）。
fn log_outcome_action(
    conn: &Connection,
    project_id: i64,
    outcome_id: Option<i64>,
    action: &str,
    name: &str,
    type_label: &str,
    status_label: &str,
) -> Result<(), DbError> {
    let description = format!("{action}成果: {name}");
    // related_info = "类型: X, 状态: Y"（状态可能为空 → “无”）
    let related_info = format!("类型: {type_label}, 状态: {}", if status_label.is_empty() { "无" } else { status_label });
    conn.execute(
        "INSERT INTO actionlogs \
         (project_id, project_outcome_id, type, action, description, operator, related_info) \
         VALUES (?1, ?2, '成果', ?3, ?4, '当前用户', ?5)",
        params![project_id, outcome_id, action, description, related_info],
    )?;
    Ok(())
}

/// 新增成果（事务）：INSERT project_outcome + 写「新增」日志。返回新成果 id。
pub fn add_outcome(conn: &Connection, input: OutcomeInput) -> Result<i64, DbError> {
    crate::db::begin_tx(conn)?;
    let result = add_outcome_inner(conn, input);
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

fn add_outcome_inner(conn: &Connection, input: OutcomeInput) -> Result<i64, DbError> {
    let type_key = to_storage_key(&input.r#type);
    let status_key = input.status.as_deref().map(to_status_key);
    conn.execute(
        "INSERT INTO project_outcome \
         (project_id, name, type, status, authors, submit_date, publish_date, \
          journal, description, attachment_path) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
        params![
            input.project_id,
            input.name,
            type_key,
            status_key,
            input.authors,
            input.submit_date,
            input.publish_date,
            input.journal,
            input.description,
            input.attachment_path,
        ],
    )?;
    let outcome_id = conn.last_insert_rowid();
    log_outcome_action(
        conn,
        input.project_id,
        Some(outcome_id),
        "新增",
        &input.name,
        &input.r#type,
        input.status.as_deref().unwrap_or(""),
    )?;
    Ok(outcome_id)
}

/// 更新成果（事务）：改 name/type/status/authors/日期/journal/description
/// （不改 attachment_path），写「编辑」日志。
pub fn update_outcome(conn: &Connection, id: i64, input: OutcomeInput) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = update_outcome_inner(conn, id, input);
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

fn update_outcome_inner(conn: &Connection, id: i64, input: OutcomeInput) -> Result<(), DbError> {
    let type_key = to_storage_key(&input.r#type);
    let status_key = input.status.as_deref().map(to_status_key);
    let changed = conn.execute(
        "UPDATE project_outcome SET name = ?1, type = ?2, status = ?3, authors = ?4, \
         submit_date = ?5, publish_date = ?6, journal = ?7, description = ?8 \
         WHERE id = ?9",
        params![
            input.name,
            type_key,
            status_key,
            input.authors,
            input.submit_date,
            input.publish_date,
            input.journal,
            input.description,
            id,
        ],
    )?;
    if changed == 0 {
        return Err(DbError::Other(format!("成果 id={id} 不存在")));
    }
    log_outcome_action(
        conn,
        input.project_id,
        Some(id),
        "编辑",
        &input.name,
        &input.r#type,
        input.status.as_deref().unwrap_or(""),
    )?;
    Ok(())
}

/// 批量删除成果（事务）。返回被删除成果的磁盘附件路径列表，
/// 由调用方在事务提交后执行文件清理（文件删除失败不致命，仅记录）。
pub fn delete_outcomes(conn: &Connection, ids: &[i64]) -> Result<Vec<Option<String>>, DbError> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    crate::db::begin_tx(conn)?;
    let result = delete_outcomes_inner(conn, ids);
    match result {
        Ok(paths) => {
            conn.execute_batch("COMMIT")?;
            Ok(paths)
        }
        Err(e) => {
            let _ = conn.execute_batch("ROLLBACK");
            Err(e)
        }
    }
}

fn delete_outcomes_inner(conn: &Connection, ids: &[i64]) -> Result<Vec<Option<String>>, DbError> {
    let mut paths = Vec::new();
    for id in ids {
        // 取记录用于日志与文件清理；不存在则跳过
        let row: Option<(i64, String, String, Option<String>, Option<String>)> = conn
            .query_row(
                "SELECT project_id, name, type, status, attachment_path \
                 FROM project_outcome WHERE id = ?1",
                [id],
                |r| {
                    Ok((
                        r.get(0)?,
                        r.get(1)?,
                        r.get(2)?,
                        r.get(3)?,
                        r.get(4)?,
                    ))
                },
            )
            .optional()?;
        let Some((project_id, name, type_key, status_key, attachment_path)) = row else {
            continue;
        };
        conn.execute("DELETE FROM project_outcome WHERE id = ?1", [id])?;
        // 删除日志不填 project_outcome_id（先删成果再记日志）
        log_outcome_action(
            conn,
            project_id,
            None,
            "删除",
            &name,
            &to_label(&type_key),
            &status_key
                .as_deref()
                .map(status_to_label)
                .unwrap_or_default(),
        )?;
        paths.push(attachment_path);
    }
    Ok(paths)
}

/// 仅更新成果附件路径（附件替换/删除后写库；对齐 `update_expense_voucher`）。
/// 删除附件即传 `None`。
pub fn update_outcome_attachment_path(
    conn: &Connection,
    id: i64,
    attachment_path: Option<String>,
) -> Result<(), DbError> {
    conn.execute(
        "UPDATE project_outcome SET attachment_path = ?1 WHERE id = ?2",
        params![attachment_path, id],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::schema;
    use crate::services::budget::add_project_to_db;
    use rusqlite::Connection;

    /// 与应用行为一致：外键关闭
    fn test_conn() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        conn
    }

    /// 构造一个项目（财务编号 C001）+ 返回 (conn, project_id)
    fn setup_project() -> (Connection, i64) {
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
            None,
        )
        .unwrap();
        (conn, pid)
    }

    fn sample_input(pid: i64) -> OutcomeInput {
        OutcomeInput {
            project_id: pid,
            name: "某期刊论文".to_string(),
            r#type: "论文".to_string(),
            status: Some("已发表/授权".to_string()),
            authors: Some("张三, 李四".to_string()),
            submit_date: Some("2024-01-15".to_string()),
            publish_date: Some("2024-06-01".to_string()),
            journal: Some("某期刊".to_string()),
            description: Some("成果描述".to_string()),
            attachment_path: Some("/tmp/论文.pdf".to_string()),
        }
    }

    #[test]
    fn add_outcome_writes_row_and_actionlog() {
        let (conn, pid) = setup_project();
        let oid = add_outcome(&conn, sample_input(pid)).unwrap();
        assert!(oid > 0);

        // 落库的 type/status 应为存储 KEY
        let (t, s): (String, String) = conn
            .query_row(
                "SELECT type, status FROM project_outcome WHERE id = ?1",
                [oid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(t, "PAPER");
        assert_eq!(s, "PUBLISHED");

        // 读出转换为中文 label
        let outcome = get_outcome_by_id(&conn, oid).unwrap().unwrap();
        assert_eq!(outcome.r#type, "论文");
        assert_eq!(outcome.status.as_deref(), Some("已发表/授权"));
        assert_eq!(outcome.name, "某期刊论文");

        // 日志
        let (t, act): (String, String) = conn
            .query_row(
                "SELECT type, action FROM actionlogs WHERE project_outcome_id = ?1",
                [oid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(t, "成果");
        assert_eq!(act, "新增");
    }

    #[test]
    fn update_outcome_keeps_attachment_path() {
        let (conn, pid) = setup_project();
        let oid = add_outcome(&conn, sample_input(pid)).unwrap();

        let mut input = sample_input(pid);
        input.name = "改名成果".to_string();
        input.r#type = "专利".to_string();
        input.status = Some("已提交".to_string());
        input.attachment_path = Some("/should/not/override.pdf".to_string());
        update_outcome(&conn, oid, input).unwrap();

        let outcome = get_outcome_by_id(&conn, oid).unwrap().unwrap();
        assert_eq!(outcome.name, "改名成果");
        assert_eq!(outcome.r#type, "专利");
        assert_eq!(outcome.status.as_deref(), Some("已提交"));
        // attachment_path 不应被编辑覆盖
        assert_eq!(outcome.attachment_path.as_deref(), Some("/tmp/论文.pdf"));

        // 日志动作应为「编辑」
        let (t, act): (String, String) = conn
            .query_row(
                "SELECT type, action FROM actionlogs WHERE project_outcome_id = ?1 \
                 ORDER BY id DESC LIMIT 1",
                [oid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(t, "成果");
        assert_eq!(act, "编辑");
    }

    #[test]
    fn delete_outcomes_returns_paths_and_logs() {
        let (conn, pid) = setup_project();
        let o1 = add_outcome(&conn, sample_input(pid)).unwrap();
        let mut inp2 = sample_input(pid);
        inp2.name = "软件著作权".to_string();
        inp2.r#type = "软著".to_string();
        inp2.attachment_path = Some("/tmp/软著证书.pdf".to_string());
        let o2 = add_outcome(&conn, inp2).unwrap();

        let paths = delete_outcomes(&conn, &[o1, o2]).unwrap();
        assert_eq!(paths.len(), 2);
        assert_eq!(paths[0].as_deref(), Some("/tmp/论文.pdf"));
        assert_eq!(paths[1].as_deref(), Some("/tmp/软著证书.pdf"));

        let remain: i64 = conn
            .query_row("SELECT COUNT(*) FROM project_outcome", [], |r| r.get(0))
            .unwrap();
        assert_eq!(remain, 0);

        // 删除日志（不含 project_outcome_id）
        let (t, act, poid): (String, String, Option<i64>) = conn
            .query_row(
                "SELECT type, action, project_outcome_id FROM actionlogs \
                 WHERE action = '删除' ORDER BY id DESC LIMIT 1",
                [],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(t, "成果");
        assert_eq!(act, "删除");
        assert!(poid.is_none());
    }

    #[test]
    fn delete_outcomes_skips_missing_ids() {
        let (conn, pid) = setup_project();
        let o1 = add_outcome(&conn, sample_input(pid)).unwrap();
        let paths = delete_outcomes(&conn, &[o1, 9999]).unwrap();
        assert_eq!(paths.len(), 1); // 只删除存在的
    }

    #[test]
    fn outcome_types_and_statuses_round_trip() {
        for label in OUTCOME_TYPES {
            assert_eq!(to_label(&to_storage_key(label)), label, "type {label}");
        }
        for label in OUTCOME_STATUSES {
            assert_eq!(status_to_label(&to_status_key(label)), label, "status {label}");
        }
        // 兜底：未识别原样返回
        assert_eq!(to_storage_key("未知"), "未知");
        assert_eq!(to_label("UNKNOWN"), "UNKNOWN");
        assert_eq!(status_to_label("UNKNOWN"), "UNKNOWN");
    }
}