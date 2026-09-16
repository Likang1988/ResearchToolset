//! 项目文档服务：对应 Python `app/views/projecting_interface/project_document.py`
//!
//! 业务核心：
//! - `doc_type` 在库中以 SQLAlchemy Enum 的枚举名存储（如 `APPLICATION`），
//!   对外统一为中文 label（如「申请材料」），读写时双向转换。
//! - 新增/编辑/删除均写入 actionlogs（type="文档"），对齐 Python 行为。
//! - 附件文件操作（拷贝/删除）由 attachments 模块完成，本服务只负责路径落库。
//! - `file_path` 为可选；删除文档后由调用方（command 层）清理磁盘文件。

use rusqlite::{params, Connection, OptionalExtension};

use crate::models::ProjectDocument;
use crate::DbError;

/// 全部文档类型的中文 label（与 `DocumentType` 枚举顺序一致，前端下拉框用）。
pub const DOCUMENT_TYPES: [&str; 10] = [
    "申请材料",
    "开题材料",
    "合同/任务书",
    "研究数据",
    "进展报告",
    "外协材料",
    "质量管理",
    "结题材料",
    "会议纪要",
    "其他",
];

/// 中文 label → 存储 KEY（SQLAlchemy Enum 名称，如 APPLICATION）。
/// 未识别返回原值（兜底，应不会发生）。
fn to_storage_key(label: &str) -> String {
    match label {
        "申请材料" => "APPLICATION".to_string(),
        "开题材料" => "INITIATION".to_string(),
        "合同/任务书" => "CONTRACT".to_string(),
        "研究数据" => "RESEARCH_DATA".to_string(),
        "进展报告" => "PROGRESS".to_string(),
        "外协材料" => "OUTSOURCING".to_string(),
        "质量管理" => "QUALITY".to_string(),
        "结题材料" => "FINALIZATION".to_string(),
        "会议纪要" => "MEETING".to_string(),
        "其他" => "OTHER".to_string(),
        _ => label.to_string(),
    }
}

/// 存储 KEY → 中文 label。
fn to_label(key: &str) -> String {
    match key {
        "APPLICATION" => "申请材料",
        "INITIATION" => "开题材料",
        "CONTRACT" => "合同/任务书",
        "RESEARCH_DATA" => "研究数据",
        "PROGRESS" => "进展报告",
        "OUTSOURCING" => "外协材料",
        "QUALITY" => "质量管理",
        "FINALIZATION" => "结题材料",
        "MEETING" => "会议纪要",
        "OTHER" => "其他",
        _ => key,
    }
    .to_string()
}

/// 新增/编辑文档输入。
///
/// `doc_type` 从前端传入中文 label（如「申请材料」），service 内转存储 KEY 入库。
/// `file_path` 仅新增时使用（编辑不改附件路径，与 Python 一致）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct DocumentInput {
    pub project_id: i64,
    pub name: String,
    pub doc_type: String,
    pub version: Option<String>,
    pub description: Option<String>,
    pub keywords: Option<String>,
    pub file_path: Option<String>,
}

/// selector 查询用公共列清单（doc_type 读取后转换中文 label）。
const SELECT_COLS: &str = "id, project_id, name, doc_type, version, description, file_path, \
                           upload_time, keywords";

/// 从 row 构造 ProjectDocument（doc_type 存 KEY → 转 label）
fn row_to_document(row: &rusqlite::Row) -> rusqlite::Result<ProjectDocument> {
    let key: String = row.get(3)?;
    Ok(ProjectDocument {
        id: row.get(0)?,
        project_id: row.get(1)?,
        name: row.get(2)?,
        doc_type: to_label(&key),
        version: row.get(4)?,
        description: row.get(5)?,
        file_path: row.get(6)?,
        upload_time: row.get(7)?,
        keywords: row.get(8)?,
    })
}

/// 列出某项目下全部文档（按 upload_time DESC，与 Python `load_documents` 一致）。
pub fn list_documents_by_project(
    conn: &Connection,
    project_id: i64,
) -> Result<Vec<ProjectDocument>, DbError> {
    let mut stmt = conn.prepare(&format!(
        "SELECT {SELECT_COLS} FROM project_documents \
         WHERE project_id = ?1 ORDER BY upload_time DESC"
    ))?;
    let rows = stmt.query_map([project_id], row_to_document)?;
    let mut docs = Vec::new();
    for row in rows {
        docs.push(row?);
    }
    Ok(docs)
}

/// 列出全部项目文档（「全部文档」模式，按 upload_time DESC）。
pub fn list_all_documents(conn: &Connection) -> Result<Vec<ProjectDocument>, DbError> {
    let mut stmt = conn.prepare(&format!(
        "SELECT {SELECT_COLS} FROM project_documents ORDER BY upload_time DESC"
    ))?;
    let rows = stmt.query_map([], row_to_document)?;
    let mut docs = Vec::new();
    for row in rows {
        docs.push(row?);
    }
    Ok(docs)
}

/// 按 id 查文档（编辑回填用）。不存在返回 None。
pub fn get_document_by_id(conn: &Connection, id: i64) -> Result<Option<ProjectDocument>, DbError> {
    let row = conn
        .query_row(
            &format!("SELECT {SELECT_COLS} FROM project_documents WHERE id = ?1"),
            [id],
            row_to_document,
        )
        .optional()?;
    Ok(row)
}

/// 写入操作日志（对齐 Python 内联 Actionlog 写法；operator 暂记「当前用户」）。
#[allow(clippy::too_many_arguments)]
fn log_document_action(
    conn: &Connection,
    project_id: i64,
    doc_id: Option<i64>,
    action: &str,
    name: &str,
    doc_type_label: &str,
    version: Option<&str>,
) -> Result<(), DbError> {
    let description = format!("{action}文档: {name}");
    let related_info = format!("类型: {doc_type_label}, 版本: {}", version.unwrap_or("无"));
    conn.execute(
        "INSERT INTO actionlogs \
         (project_id, project_document_id, type, action, description, operator, related_info) \
         VALUES (?1, ?2, '文档', ?3, ?4, '当前用户', ?5)",
        params![project_id, doc_id, action, description, related_info],
    )?;
    Ok(())
}

/// 新增文档（事务）：INSERT project_documents + 写「新增」日志。返回新文档 id。
pub fn add_document(conn: &Connection, input: DocumentInput) -> Result<i64, DbError> {
    crate::db::begin_tx(conn)?;
    let result = add_document_inner(conn, input);
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

fn add_document_inner(conn: &Connection, input: DocumentInput) -> Result<i64, DbError> {
    let storage_key = to_storage_key(&input.doc_type);
    conn.execute(
        "INSERT INTO project_documents \
         (project_id, name, doc_type, version, description, file_path, keywords) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![
            input.project_id,
            input.name,
            storage_key,
            input.version,
            input.description,
            input.file_path,
            input.keywords,
        ],
    )?;
    let doc_id = conn.last_insert_rowid();
    log_document_action(
        conn,
        input.project_id,
        Some(doc_id),
        "新增",
        &input.name,
        &input.doc_type,
        input.version.as_deref(),
    )?;
    Ok(doc_id)
}

/// 更新文档（事务）：改 name/doc_type/version/description/keywords（不改 file_path），
/// 写「编辑」日志。对齐 Python `edit_document`。
pub fn update_document(conn: &Connection, id: i64, input: DocumentInput) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = update_document_inner(conn, id, input);
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

fn update_document_inner(conn: &Connection, id: i64, input: DocumentInput) -> Result<(), DbError> {
    let storage_key = to_storage_key(&input.doc_type);
    let changed = conn.execute(
        "UPDATE project_documents SET name = ?1, doc_type = ?2, version = ?3, \
         description = ?4, keywords = ?5 WHERE id = ?6",
        params![
            input.name,
            storage_key,
            input.version,
            input.description,
            input.keywords,
            id,
        ],
    )?;
    if changed == 0 {
        return Err(DbError::Other(format!("文档 id={id} 不存在")));
    }
    log_document_action(
        conn,
        input.project_id,
        Some(id),
        "编辑",
        &input.name,
        &input.doc_type,
        input.version.as_deref(),
    )?;
    Ok(())
}

/// 批量删除文档（事务）。返回被删除文档的磁盘文件路径列表，
/// 由调用方在事务提交后执行文件清理（对齐 Python：文件删除失败不致命）。
pub fn delete_documents(conn: &Connection, ids: &[i64]) -> Result<Vec<Option<String>>, DbError> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    crate::db::begin_tx(conn)?;
    let result = delete_documents_inner(conn, ids);
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

fn delete_documents_inner(
    conn: &Connection,
    ids: &[i64],
) -> Result<Vec<Option<String>>, DbError> {
    let mut paths = Vec::new();
    for id in ids {
        // 取记录用于日志与文件清理；不存在则跳过（对齐 Python query.first() 判空）
        let row: Option<(i64, String, String, Option<String>)> = conn
            .query_row(
                "SELECT project_id, name, doc_type, file_path FROM project_documents WHERE id = ?1",
                [id],
                |r| {
                    Ok((
                        r.get(0)?,
                        r.get(1)?,
                        r.get(2)?,
                        r.get(3)?,
                    ))
                },
            )
            .optional()?;
        let Some((project_id, name, doc_type_key, file_path)) = row else {
            continue;
        };
        let version: Option<String> = conn
            .query_row(
                "SELECT version FROM project_documents WHERE id = ?1",
                [id],
                |r| r.get(0),
            )
            .optional()?;
        conn.execute("DELETE FROM project_documents WHERE id = ?1", [id])?;
        // 删除日志不填 project_document_id（对齐 Python：先删文档再记日志）
        log_document_action(
            conn,
            project_id,
            None,
            "删除",
            &name,
            &to_label(&doc_type_key),
            version.as_deref(),
        )?;
        paths.push(file_path);
    }
    Ok(paths)
}

/// 仅更新文档附件路径（附件替换/删除后写库；对齐 `update_expense_voucher`）。
/// 删除附件即传 `None`。
pub fn update_document_file_path(
    conn: &Connection,
    id: i64,
    file_path: Option<String>,
) -> Result<(), DbError> {
    conn.execute(
        "UPDATE project_documents SET file_path = ?1 WHERE id = ?2",
        params![file_path, id],
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

    fn sample_input(pid: i64) -> DocumentInput {
        DocumentInput {
            project_id: pid,
            name: "项目申请书".to_string(),
            doc_type: "申请材料".to_string(),
            version: Some("1.0".to_string()),
            description: Some("描述".to_string()),
            keywords: Some("申请书,立项".to_string()),
            file_path: Some("/tmp/申请书.pdf".to_string()),
        }
    }

    #[test]
    fn add_document_writes_row_and_actionlog() {
        let (conn, pid) = setup_project();
        let doc_id = add_document(&conn, sample_input(pid)).unwrap();
        assert!(doc_id > 0);

        // 落库的 doc_type 应为存储 KEY（APPLICATION）
        let key: String = conn
            .query_row(
                "SELECT doc_type FROM project_documents WHERE id = ?1",
                [doc_id],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(key, "APPLICATION");

        // 读出转换为中文 label
        let doc = get_document_by_id(&conn, doc_id).unwrap().unwrap();
        assert_eq!(doc.doc_type, "申请材料");
        assert_eq!(doc.name, "项目申请书");

        // 日志
        let (t, act): (String, String) = conn
            .query_row(
                "SELECT type, action FROM actionlogs WHERE project_document_id = ?1",
                [doc_id],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(t, "文档");
        assert_eq!(act, "新增");
    }

    #[test]
    fn update_document_keeps_file_path() {
        let (conn, pid) = setup_project();
        let doc_id = add_document(&conn, sample_input(pid)).unwrap();

        let mut input = sample_input(pid);
        input.name = "改名".to_string();
        input.doc_type = "结题材料".to_string();
        input.file_path = Some("/should/not/override.pdf".to_string());
        update_document(&conn, doc_id, input).unwrap();

        let doc = get_document_by_id(&conn, doc_id).unwrap().unwrap();
        assert_eq!(doc.name, "改名");
        assert_eq!(doc.doc_type, "结题材料");
        // file_path 不应被编辑覆盖
        assert_eq!(doc.file_path.as_deref(), Some("/tmp/申请书.pdf"));

        // 日志动作应为「编辑」
        let (t, act): (String, String) = conn
            .query_row(
                "SELECT type, action FROM actionlogs WHERE project_document_id = ?1 ORDER BY id DESC LIMIT 1",
                [doc_id],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(t, "文档");
        assert_eq!(act, "编辑");
    }

    #[test]
    fn delete_documents_returns_paths_and_logs() {
        let (conn, pid) = setup_project();
        let d1 = add_document(&conn, sample_input(pid)).unwrap();
        let mut inp2 = sample_input(pid);
        inp2.name = "课题报告".to_string();
        inp2.doc_type = "开题材料".to_string();
        inp2.file_path = Some("/tmp/报告.docx".to_string());
        let d2 = add_document(&conn, inp2).unwrap();

        let paths = delete_documents(&conn, &[d1, d2]).unwrap();
        assert_eq!(paths.len(), 2);
        assert_eq!(paths[0].as_deref(), Some("/tmp/申请书.pdf"));
        assert_eq!(paths[1].as_deref(), Some("/tmp/报告.docx"));

        let remain: i64 = conn
            .query_row("SELECT COUNT(*) FROM project_documents", [], |r| r.get(0))
            .unwrap();
        assert_eq!(remain, 0);

        // 删除日志（不含 project_document_id）
        let (t, act, pdid): (String, String, Option<i64>) = conn
            .query_row(
                "SELECT type, action, project_document_id FROM actionlogs \
                 WHERE action = '删除' ORDER BY id DESC LIMIT 1",
                [],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(t, "文档");
        assert_eq!(act, "删除");
        assert!(pdid.is_none());
    }

    #[test]
    fn delete_documents_skips_missing_ids() {
        let (conn, pid) = setup_project();
        let d1 = add_document(&conn, sample_input(pid)).unwrap();
        let paths = delete_documents(&conn, &[d1, 9999]).unwrap();
        assert_eq!(paths.len(), 1); // 只删除存在的
    }

    #[test]
    fn document_types_round_trip() {
        for label in DOCUMENT_TYPES {
            assert_eq!(to_label(&to_storage_key(label)), label, "label {label}");
        }
        // 兜底：未识别原样返回
        assert_eq!(to_storage_key("未知"), "未知");
        assert_eq!(to_label("UNKNOWN"), "UNKNOWN");
    }
}