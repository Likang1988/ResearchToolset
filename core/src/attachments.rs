//! 附件管理（与 UI 无关的附件路径与文件核心逻辑）
//!
//! 实现：
//! - 文件名清洗 `sanitize_filename`
//! - 目录确保 `ensure_directory_exists`
//! - 时间戳 `get_timestamp_str`
//! - 附件保存路径生成 `generate_attachment_path`（支出凭证 / 活动 / 默认三种）
//! - 上传 / 替换 / 删除的纯文件操作（`save_attachment` / `replace_attachment` / `delete_attachment`）
//! - 删除项目时清理附件目录 `clean_project_attachments`
//!
//! 注：文件选择对话框、系统默认程序打开属 UI 层，
//! 由 Tauri command / 前端负责；本模块只做可复用的路径与文件逻辑。

use std::path::{Path, PathBuf};

use crate::DbError;

/// 清洗文件名中的 Windows 非法字符：先去除首尾空白，
/// 再将 `\ / * ? : " < > |` 替换为下划线。
pub fn sanitize_filename(name: &str) -> String {
    name.trim()
        .chars()
        .map(|c| {
            if matches!(c, '\\' | '/' | '*' | '?' | ':' | '"' | '<' | '>' | '|') {
                '_'
            } else {
                c
            }
        })
        .collect()
}

/// 确保目录存在，必要时递归创建。
pub fn ensure_directory_exists(dir_path: &Path) -> Result<(), DbError> {
    if !dir_path.exists() {
        std::fs::create_dir_all(dir_path)?;
    }
    Ok(())
}

/// 当前时间戳，格式 YYYYMMDDHHMMSS。
pub fn get_timestamp_str() -> String {
    chrono::Local::now().format("%Y%m%d%H%M%S").to_string()
}

/// 从原始文件名拆分出 (清洗后的基本名, 带点扩展名)。
/// 先丢弃路径前缀只取文件名，再按最后一个 `.` 拆分基本名与扩展名。
fn split_base_and_ext(original_filename: &str) -> (String, String) {
    let basename = Path::new(original_filename)
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| original_filename.to_string());
    let (base, ext) = basename
        .rfind('.')
        .map(|i| (&basename[..i], &basename[i..]))
        .unwrap_or((&basename[..], ""));
    (sanitize_filename(base), ext.to_string())
}

/// 附件目标类型：决定路径结构与文件命名。
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AttachmentKind {
    /// 支出凭证：`{root}/vouchers/{财务编号}/{年份}/`，文件名 `{类别}_{金额}_{名}.{ext}`
    Expense,
    /// 活动附件：`{root}/activities/{活动类别}/`，文件名 `{时间戳}_{名}.{ext}`
    Activity,
    /// 默认（文档/成果等）：`{root}/{base_folder}/{财务编号}/{类别}/`，文件名 `{时间戳}_{名}.{ext}`
    Default,
}

/// 生成附件路径所需的上下文。
///
/// 字段按 `kind` 取用（其余可忽略）：
/// - `Expense`：`category/cm`（用于类别与文件名）、`date`（YYYY-MM-DD，取年份）
/// - `Activity`：`category`（活动类别名）
/// - `Default`：`category`（如文档类型名）
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct AttachmentContext {
    /// 项目财务编号（ret 用 `unknown_project`）
    pub financial_code: Option<String>,
    /// 类别名（支出类别/活动类别/文档类型的中文 value）
    pub category: Option<String>,
    /// 支出金额（元），仅 Expense 用
    pub amount: Option<f64>,
    /// 支出日期（YYYY-MM-DD），仅 Expense 用
    pub date: Option<String>,
    /// 默认基础文件夹名（仅 Default 用；缺省 "attachments"）
    pub base_folder: Option<String>,
}

/// 生成附件保存的完整路径（含创建目标目录）。
/// 可空字段均回退为 "unknown_*"。
pub fn generate_attachment_path(
    root_dir: &Path,
    kind: AttachmentKind,
    original_filename: &str,
    ctx: &AttachmentContext,
) -> Result<PathBuf, DbError> {
    if original_filename.trim().is_empty() {
        return Err(DbError::Other("缺少文件名，无法生成附件路径".into()));
    }

    let now = get_timestamp_str();
    let (sanitized_base, ext) = split_base_and_ext(original_filename);
    let project_code = ctx
        .financial_code
        .as_deref()
        .filter(|s| !s.trim().is_empty())
        .unwrap_or("unknown_project");
    let category = ctx
        .category
        .as_deref()
        .filter(|s| !s.trim().is_empty())
        .unwrap_or("unknown");

    let (target_dir, new_filename) = match kind {
        AttachmentKind::Expense => {
            let year = ctx
                .date
                .as_deref()
                .and_then(|d| d.split('-').next())
                .filter(|s| !s.is_empty())
                .unwrap_or("unknown_year")
                .to_string();
            let sanitized_category = sanitize_filename(category);
            let amount_str = format!("{:.2}", ctx.amount.unwrap_or(0.0));
            let dir = root_dir.join("vouchers").join(project_code).join(&year);
            let name = format!("{sanitized_category}_{amount_str}_{sanitized_base}{ext}");
            (dir, name)
        }
        AttachmentKind::Activity => {
            let dir = root_dir.join("activities").join(sanitize_filename(category));
            let name = format!("{now}_{sanitized_base}{ext}");
            (dir, name)
        }
        AttachmentKind::Default => {
            let base = ctx
                .base_folder
                .as_deref()
                .filter(|s| !s.trim().is_empty())
                .unwrap_or("attachments");
            let dir = root_dir
                .join(base)
                .join(project_code)
                .join(sanitize_filename(category));
            let name = format!("{now}_{sanitized_base}{ext}");
            (dir, name)
        }
    };

    ensure_directory_exists(&target_dir)?;
    Ok(target_dir.join(new_filename))
}

/// 上传/替换附件：把 `source` 拷贝到目标路径，返回完整目标路径。
///
/// 处理步骤：
/// 1. 生成目标路径（调用 `generate_attachment_path`）
/// 2. ensure 目录
/// 3. 拷贝源文件到目标
/// 4. 若旧路径存在且不同于新路径，删除旧文件
///
/// `save_attachment` 只做文件操作，不涉及数据库（由调用方在事务外编排）。
pub fn save_attachment(
    root_dir: &Path,
    kind: AttachmentKind,
    source_file: &Path,
    ctx: &AttachmentContext,
    old_path: Option<&Path>,
) -> Result<PathBuf, DbError> {
    let source_name = source_file
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default();
    let new_path = generate_attachment_path(root_dir, kind, &source_name, ctx)?;

    // 拷贝源文件到目标
    std::fs::copy(source_file, &new_path)?;

    // 替换时删除旧附件（路径不同才删，且删除失败不致命，仅记录）
    if let Some(old) = old_path {
        if old.exists() && old != &new_path {
            let _ = std::fs::remove_file(old);
        }
    }

    Ok(new_path)
}

/// 删除附件文件（仅做文件删除，数据库由调用方处理）。
/// 文件不存在视为成功（空操作）。
pub fn delete_attachment(path: &Path) -> Result<(), DbError> {
    if path.exists() {
        std::fs::remove_file(path)?;
    }
    Ok(())
}

/// 批量校验附件文件是否真实存在（应对"程序外删除"等异常情况）。
///
/// SQLite 只记录路径字符串，磁盘文件可能已被用户
/// 在程序外删除。列表加载时代理侧校验，返回与输入等长的布尔数组
/// （`true` 表示文件存在）；路径为空或不可访问一律视为不存在。
/// 仅作展示层提示用，不抛错、不阻塞列表加载。
pub fn check_attachments_exist(paths: &[String]) -> Vec<bool> {
    paths
        .iter()
        .map(|p| !p.is_empty() && Path::new(p).is_file())
        .collect()
}

/// 删除项目时清理其专属附件目录（仅文件清理部分）。
///
/// 清理路径：`root_dir/documents/{project_id}` 与 `root_dir/vouchers/{project_id}`。
/// 目录不存在视为成功（空操作）；目录存在则递归删除。
/// 返回 (doc_deleted, voucher_deleted) 标志，调用方可据此提示用户。
pub fn clean_project_attachments(root_dir: &Path, project_id: i64) -> (bool, bool) {
    let doc_dir = root_dir.join("documents").join(project_id.to_string());
    let voucher_dir = root_dir.join("vouchers").join(project_id.to_string());

    let doc_deleted = rm_dir_if_exists(&doc_dir);
    let voucher_deleted = rm_dir_if_exists(&voucher_dir);
    (doc_deleted, voucher_deleted)
}

/// 目录存在则递归删除，返回是否实际执行了删除。
fn rm_dir_if_exists(path: &Path) -> bool {
    if path.is_dir() {
        match std::fs::remove_dir_all(path) {
            Ok(_) => true,
            // 删除失败不向上抛：数据库已提交，不应因文件清理失败让整体回滚。
            Err(_) => false,
        }
    } else {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_windows_illegal_chars_to_underscore() {
        assert_eq!(sanitize_filename("a/b\\c:d*e?f\"g<h>i|j"), "a_b_c_d_e_f_g_h_i_j");
        assert_eq!(sanitize_filename("正常文件名.pdf"), "正常文件名.pdf");
        assert_eq!(sanitize_filename("  前后空格  "), "前后空格");
    }

    #[test]
    fn timestamp_has_14_digits() {
        let ts = get_timestamp_str();
        assert_eq!(ts.len(), 14);
        assert!(ts.chars().all(|c| c.is_ascii_digit()));
    }

    #[test]
    fn default_path_structure() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();
        let ctx = AttachmentContext {
            financial_code: Some("2023KJ001".into()),
            category: Some("申请材料".into()),
            ..Default::default()
        };
        let path = generate_attachment_path(root, AttachmentKind::Default, "申请书/最终版.pdf", &ctx)
            .unwrap();
        // <root>/attachments/2023KJ001/申请材料/<ts>_最终版.pdf
        // （只取文件名部分 "最终版.pdf"，路径前缀 "申请书/" 被丢弃）
        let rel = path.strip_prefix(root).unwrap();
        let parts: Vec<_> = rel
            .components()
            .map(|c| c.as_os_str().to_string_lossy().into_owned())
            .collect();
        assert_eq!(parts.len(), 4);
        assert_eq!(parts[0], "attachments");
        assert_eq!(parts[1], "2023KJ001");
        assert_eq!(parts[2], "申请材料");
        // 文件名以 ts 开头、以下划线连接清洗后的基本名
        let fname = &parts[3];
        assert!(fname.starts_with(&get_timestamp_str()));
        assert!(fname.ends_with("_最终版.pdf"), "got {fname}");
    }

    #[test]
    fn expense_path_structure_uses_year_and_amount() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();
        let ctx = AttachmentContext {
            financial_code: Some("2023KJ001".into()),
            category: Some("材料费".into()),
            amount: Some(12345.678),
            date: Some("2024-05-01".into()),
            ..Default::default()
        };
        let path = generate_attachment_path(root, AttachmentKind::Expense, "发票.pdf", &ctx).unwrap();
        let rel = path.strip_prefix(root).unwrap();
        let parts: Vec<_> = rel
            .components()
            .map(|c| c.as_os_str().to_string_lossy().into_owned())
            .collect();
        assert_eq!(parts.len(), 4);
        assert_eq!(parts[0], "vouchers");
        assert_eq!(parts[1], "2023KJ001");
        assert_eq!(parts[2], "2024");
        // 文件名为 类别_金额_基本名.ext；金额保留两位小数
        assert_eq!(parts[3], "材料费_12345.68_发票.pdf");
    }

    #[test]
    fn activity_path_structure() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();
        let ctx = AttachmentContext {
            category: Some("学术会议".into()),
            ..Default::default()
        };
        let path = generate_attachment_path(root, AttachmentKind::Activity, "通知.pdf", &ctx).unwrap();
        let rel = path.strip_prefix(root).unwrap();
        let parts: Vec<_> = rel
            .components()
            .map(|c| c.as_os_str().to_string_lossy().into_owned())
            .collect();
        assert_eq!(parts.len(), 3);
        assert_eq!(parts[0], "activities");
        assert_eq!(parts[1], "学术会议");
        assert!(parts[2].starts_with(&get_timestamp_str()));
        assert!(parts[2].ends_with("_通知.pdf"));
    }

    #[test]
    fn save_attachment_copies_and_removes_old() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();

        // 源文件
        let src = tmp.path().join("source_材料.png");
        std::fs::write(&src, b"bytes").unwrap();

        // 预置一个"旧文件"（模拟替换场景）
        let old = root
            .join("attachments")
            .join("2023KJ001")
            .join("申请材料")
            .join("旧文件.pdf");
        std::fs::create_dir_all(old.parent().unwrap()).unwrap();
        std::fs::write(&old, b"old").unwrap();

        let ctx = AttachmentContext {
            financial_code: Some("2023KJ001".into()),
            category: Some("申请材料".into()),
            ..Default::default()
        };
        let new_path = save_attachment(root, AttachmentKind::Default, &src, &ctx, Some(&old)).unwrap();

        assert!(new_path.exists(), "新附件应被拷贝");
        assert_eq!(std::fs::read(&new_path).unwrap(), b"bytes");
        assert!(!old.exists(), "旧附件应被删除");
    }

    #[test]
    fn delete_attachment_missing_is_ok() {
        let tmp = tempfile::tempdir().unwrap();
        let nonexist = tmp.path().join("nope.txt");
        delete_attachment(&nonexist).unwrap(); // 不应报错
    }

    #[test]
    fn check_attachments_exist_reports_missing() {
        let tmp = tempfile::tempdir().unwrap();
        let existing = tmp.path().join("发票.png");
        std::fs::write(&existing, b"x").unwrap();
        let results = check_attachments_exist(&[
            existing.to_string_lossy().into_owned(),
            tmp.path().join("已删除.png").to_string_lossy().into_owned(),
            String::new(), // 空路径视为不存在
        ]);
        assert_eq!(results, vec![true, false, false]);
    }

    #[test]
    fn clean_project_attachments_removes_existing_dirs() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();

        // 预建 documents/42 与 vouchers/42，各放一个文件
        let doc_dir = root.join("documents").join("42");
        let voucher_dir = root.join("vouchers").join("42");
        std::fs::create_dir_all(&doc_dir).unwrap();
        std::fs::create_dir_all(&voucher_dir).unwrap();
        std::fs::write(doc_dir.join("a.txt"), "x").unwrap();
        std::fs::write(voucher_dir.join("b.pdf"), "y").unwrap();

        let (d, v) = clean_project_attachments(root, 42);
        assert!(d, "documents 应被删除");
        assert!(v, "vouchers 应被删除");
        assert!(!doc_dir.exists());
        assert!(!voucher_dir.exists());
    }

    #[test]
    fn clean_project_attachments_missing_dirs_is_noop() {
        let tmp = tempfile::tempdir().unwrap();
        // 不存在该项目的目录，应返回 (false, false) 不报错
        let (d, v) = clean_project_attachments(tmp.path(), 999);
        assert!(!d);
        assert!(!v);
    }
}
