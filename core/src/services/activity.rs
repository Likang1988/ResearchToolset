//! 学术活动服务
//!
//! 业务核心：
//! - `type` / `status` 在库中以英文枚举名（KEY）存储（如 `CONFERENCE` / `PLANNED`），
//!   对外统一为中文 label（如「学术会议」/「未开始」），读写时双向转换。
//! - 活动的新增/编辑/删除 **不写 actionlogs**（actionlogs 表无活动外键）。
//! - 表 `academic_activities` 为全局表（无 project_id），不做项目维度筛选。
//! - 附件文件操作（拷贝/删除）由 attachments 模块完成，本服务只负责附件路径落库；
//!   新附件路径由调用方先通过 `save_attachment(kind="activity")` 生成并拷贝，再随
//!   新增/编辑一并写入（附件的 add/replace/delete 操作均会修改 attachment_path）。
//! - 删除活动后由调用方（command 层）清理磁盘附件。
//!
//! 排序：`ORDER BY start_date DESC`。

use rusqlite::{params, Connection, OptionalExtension};

use crate::models::AcademicActivity;
use crate::DbError;

/// 全部活动类型的中文 label（与 `ActivityType` 枚举顺序一致，前端下拉框用）。
pub const ACTIVITY_TYPES: [&str; 7] = [
    "学术会议",
    "学术讲座",
    "培训活动",
    "研讨会",
    "工作坊",
    "学术交流",
    "其他",
];

/// 全部活动状态的中文 label（与 `ActivityStatus` 枚举顺序一致，前端下拉框用）。
pub const ACTIVITY_STATUSES: [&str; 4] = ["未开始", "进行中", "已结束", "已取消"];

/// 中文类型 label → 存储 KEY（英文枚举名）。未识别返回原值（兜底）。
fn to_storage_key(label: &str) -> String {
    match label {
        "学术会议" => "CONFERENCE",
        "学术讲座" => "LECTURE",
        "培训活动" => "TRAINING",
        "研讨会" => "SEMINAR",
        "工作坊" => "WORKSHOP",
        "学术交流" => "EXCHANGE",
        "其他" => "OTHER",
        _ => label,
    }
    .to_string()
}

/// 存储 KEY → 中文类型 label。未识别原样返回。
fn to_label(key: &str) -> String {
    match key {
        "CONFERENCE" => "学术会议",
        "LECTURE" => "学术讲座",
        "TRAINING" => "培训活动",
        "SEMINAR" => "研讨会",
        "WORKSHOP" => "工作坊",
        "EXCHANGE" => "学术交流",
        "OTHER" => "其他",
        _ => key,
    }
    .to_string()
}

/// 中文状态 label → 存储 KEY。未识别原样返回。
fn to_status_key(label: &str) -> String {
    match label {
        "未开始" => "PLANNED",
        "进行中" => "ONGOING",
        "已结束" => "COMPLETED",
        "已取消" => "CANCELLED",
        _ => label,
    }
    .to_string()
}

/// 存储状态 KEY → 中文 label。未识别原样返回。
fn status_to_label(key: &str) -> String {
    match key {
        "PLANNED" => "未开始",
        "ONGOING" => "进行中",
        "COMPLETED" => "已结束",
        "CANCELLED" => "已取消",
        _ => key,
    }
    .to_string()
}

/// 新增/编辑活动输入。
///
/// `type` / `status` 从前端传入中文 label，service 内转存储 KEY 入库。
/// `attachment_path` 为对话框处理后的最终附件路径：
/// - 新增选择文件 → 调用方已拷贝到规则目录，传新路径；
/// - 编辑不变 → 传原路径；替换 → 传新路径；移除 → 传 `None`。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ActivityInput {
    pub name: String,
    pub r#type: String,
    pub status: Option<String>,
    pub organizer: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub location: Option<String>,
    pub participants: Option<String>,
    pub description: Option<String>,
    pub attachment_path: Option<String>,
}

/// 查询用公共列清单（type/status 读取后转换中文 label）。
const SELECT_COLS: &str = "id, name, type, status, organizer, start_date, \
                           end_date, location, participants, description, attachment_path";

/// 从 row 构造 AcademicActivity（type/status 存 KEY → 转 label）
fn row_to_activity(row: &rusqlite::Row) -> rusqlite::Result<AcademicActivity> {
    let type_key: String = row.get(2)?;
    let status_key: Option<String> = row.get(3)?;
    Ok(AcademicActivity {
        id: row.get(0)?,
        name: row.get(1)?,
        r#type: to_label(&type_key),
        status: status_key.as_deref().map(status_to_label),
        organizer: row.get(4)?,
        start_date: row.get(5)?,
        end_date: row.get(6)?,
        location: row.get(7)?,
        participants: row.get(8)?,
        description: row.get(9)?,
        attachment_path: row.get(10)?,
    })
}

/// 列出全部活动（按 start_date DESC，NULL 在 SQLite DESC 排序下自然落末）。
pub fn list_activities(conn: &Connection) -> Result<Vec<AcademicActivity>, DbError> {
    let mut stmt = conn.prepare(&format!(
        "SELECT {SELECT_COLS} FROM academic_activities ORDER BY start_date DESC"
    ))?;
    let rows = stmt.query_map([], row_to_activity)?;
    let mut activities = Vec::new();
    for row in rows {
        activities.push(row?);
    }
    Ok(activities)
}

/// 按 id 查活动（编辑回填用）。不存在返回 None。
pub fn get_activity_by_id(conn: &Connection, id: i64) -> Result<Option<AcademicActivity>, DbError> {
    let row = conn
        .query_row(
            &format!("SELECT {SELECT_COLS} FROM academic_activities WHERE id = ?1"),
            [id],
            row_to_activity,
        )
        .optional()?;
    Ok(row)
}

/// 新增活动。返回新活动 id。不写 actionlogs。
pub fn add_activity(conn: &Connection, input: ActivityInput) -> Result<i64, DbError> {
    let type_key = to_storage_key(&input.r#type);
    let status_key = input.status.as_deref().map(to_status_key);
    conn.execute(
        "INSERT INTO academic_activities \
         (name, type, status, organizer, start_date, end_date, location, \
          participants, description, attachment_path) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
        params![
            input.name,
            type_key,
            status_key,
            input.organizer,
            input.start_date,
            input.end_date,
            input.location,
            input.participants,
            input.description,
            input.attachment_path,
        ],
    )?;
    Ok(conn.last_insert_rowid())
}

/// 更新活动：改全部字段（含 attachment_path）。
///
/// 与成果不同，编辑时对话框的附件状态（add/replace/delete）会改写 attachment_path，
/// 故这里必须支持写附件路径；
/// 附件文件拷贝/删除由调用方先完成，`None` 表示移除附件。
pub fn update_activity(conn: &Connection, id: i64, input: ActivityInput) -> Result<(), DbError> {
    let type_key = to_storage_key(&input.r#type);
    let status_key = input.status.as_deref().map(to_status_key);
    let changed = conn.execute(
        "UPDATE academic_activities SET name = ?1, type = ?2, status = ?3, organizer = ?4, \
         start_date = ?5, end_date = ?6, location = ?7, participants = ?8, \
         description = ?9, attachment_path = ?10 \
         WHERE id = ?11",
        params![
            input.name,
            type_key,
            status_key,
            input.organizer,
            input.start_date,
            input.end_date,
            input.location,
            input.participants,
            input.description,
            input.attachment_path,
            id,
        ],
    )?;
    if changed == 0 {
        return Err(DbError::Other(format!("活动 id={id} 不存在")));
    }
    Ok(())
}

/// 批量删除活动。返回被删除活动的磁盘附件路径列表，
/// 由调用方在删除后执行文件清理（文件删除失败不致命，仅记录）。不写 actionlogs；不存在的 id 跳过。
pub fn delete_activities(conn: &Connection, ids: &[i64]) -> Result<Vec<Option<String>>, DbError> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    let mut paths = Vec::new();
    for id in ids {
        let attachment_path: Option<String> = conn
            .query_row(
                "SELECT attachment_path FROM academic_activities WHERE id = ?1",
                [id],
                |r| r.get(0),
            )
            .optional()?;
        if attachment_path.is_none() {
            continue;
        }
        conn.execute("DELETE FROM academic_activities WHERE id = ?1", [id])?;
        paths.push(attachment_path);
    }
    Ok(paths)
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

    fn sample_input() -> ActivityInput {
        ActivityInput {
            name: "某学术会议".to_string(),
            r#type: "学术会议".to_string(),
            status: Some("已结束".to_string()),
            organizer: Some("某大学".to_string()),
            start_date: Some("2024-05-10".to_string()),
            end_date: Some("2024-05-12".to_string()),
            location: Some("北京".to_string()),
            participants: Some("张三, 李四".to_string()),
            description: Some("会议描述".to_string()),
            attachment_path: Some("/tmp/会议通知.pdf".to_string()),
        }
    }

    #[test]
    fn add_activity_writes_row_without_actionlog() {
        let conn = test_conn();
        let aid = add_activity(&conn, sample_input()).unwrap();
        assert!(aid > 0);

        // 落库的 type/status 应为存储 KEY
        let (t, s): (String, String) = conn
            .query_row(
                "SELECT type, status FROM academic_activities WHERE id = ?1",
                [aid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(t, "CONFERENCE");
        assert_eq!(s, "COMPLETED");

        // 读出转换为中文 label
        let activity = get_activity_by_id(&conn, aid).unwrap().unwrap();
        assert_eq!(activity.r#type, "学术会议");
        assert_eq!(activity.status.as_deref(), Some("已结束"));
        assert_eq!(activity.name, "某学术会议");
        assert_eq!(activity.organizer.as_deref(), Some("某大学"));

        // 活动不写 actionlogs
        let n: i64 = conn
            .query_row("SELECT COUNT(*) FROM actionlogs", [], |r| r.get(0))
            .unwrap();
        assert_eq!(n, 0);
    }

    #[test]
    fn update_activity_updates_fields_and_attachment_path() {
        let conn = test_conn();
        let aid = add_activity(&conn, sample_input()).unwrap();

        // 编辑：改字段 + 换附件路径
        let mut input = sample_input();
        input.name = "改名活动".to_string();
        input.r#type = "工作坊".to_string();
        input.status = Some("进行中".to_string());
        input.attachment_path = Some("/tmp/新附件.doc".to_string());
        update_activity(&conn, aid, input).unwrap();

        let activity = get_activity_by_id(&conn, aid).unwrap().unwrap();
        assert_eq!(activity.name, "改名活动");
        assert_eq!(activity.r#type, "工作坊");
        assert_eq!(activity.status.as_deref(), Some("进行中"));
        assert_eq!(activity.attachment_path.as_deref(), Some("/tmp/新附件.doc"));

        // 编辑：移除附件（attachment_path = None）
        let mut input2 = sample_input();
        input2.name = "改名活动".to_string();
        input2.attachment_path = None;
        update_activity(&conn, aid, input2).unwrap();
        let activity = get_activity_by_id(&conn, aid).unwrap().unwrap();
        assert!(activity.attachment_path.is_none());

        // 编辑不存在的 id 报错
        let err = update_activity(&conn, 9999, sample_input()).unwrap_err();
        assert!(err.to_string().contains("不存在"));
    }

    #[test]
    fn list_activities_sorted_by_start_date_desc() {
        let conn = test_conn();
        let mut a1 = sample_input();
        a1.name = "较早活动".to_string();
        a1.start_date = Some("2024-01-01".to_string());
        add_activity(&conn, a1).unwrap();
        let mut a2 = sample_input();
        a2.name = "较晚活动".to_string();
        a2.start_date = Some("2024-09-01".to_string());
        add_activity(&conn, a2).unwrap();

        let list = list_activities(&conn).unwrap();
        assert_eq!(list.len(), 2);
        assert_eq!(list[0].name, "较晚活动");
        assert_eq!(list[1].name, "较早活动");
    }

    #[test]
    fn delete_activities_returns_paths_and_skips_missing() {
        let conn = test_conn();
        let a1 = add_activity(&conn, sample_input()).unwrap();
        let mut inp2 = sample_input();
        inp2.name = "学术讲座".to_string();
        inp2.r#type = "学术讲座".to_string();
        inp2.attachment_path = Some("/tmp/讲座材料.pptx".to_string());
        let a2 = add_activity(&conn, inp2).unwrap();

        // 只删 a1 + 不存在的 id：跳过缺失项
        let paths = delete_activities(&conn, &[a1, 9999]).unwrap();
        assert_eq!(paths.len(), 1);
        assert_eq!(paths[0].as_deref(), Some("/tmp/会议通知.pdf"));

        // a2 仍存在
        let remain: i64 = conn
            .query_row("SELECT COUNT(*) FROM academic_activities", [], |r| r.get(0))
            .unwrap();
        assert_eq!(remain, 1);

        // 删 a2，返回其附件路径
        let paths = delete_activities(&conn, &[a2]).unwrap();
        assert_eq!(paths[0].as_deref(), Some("/tmp/讲座材料.pptx"));

        // 全部删完，仍无 actionlog
        let n: i64 = conn
            .query_row("SELECT COUNT(*) FROM actionlogs", [], |r| r.get(0))
            .unwrap();
        assert_eq!(n, 0);
    }

    #[test]
    fn activity_types_and_statuses_round_trip() {
        for label in ACTIVITY_TYPES {
            assert_eq!(to_label(&to_storage_key(label)), label, "type {label}");
        }
        for label in ACTIVITY_STATUSES {
            assert_eq!(status_to_label(&to_status_key(label)), label, "status {label}");
        }
        // 兜底：未识别原样返回
        assert_eq!(to_storage_key("未知"), "未知");
        assert_eq!(to_label("UNKNOWN"), "UNKNOWN");
        assert_eq!(status_to_label("UNKNOWN"), "UNKNOWN");
    }
}