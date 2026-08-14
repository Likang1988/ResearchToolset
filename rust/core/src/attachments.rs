//! 附件管理（对应 `app/utils/attachment_utils.py`，阶段 1 后期实现）
//!
//! 计划实现：
//! - 附件目录结构生成：`{root}/{财务编号}/{年份}/{类别}/`
//! - 上传（拷贝）、替换、删除、下载、系统打开（Windows `os.startfile` / macOS `open` / Linux `xdg-open`）
//! - 文件名清洗（`sanitize_filename`）

/// 清洗文件名中的 Windows 非法字符（对应 Python `sanitize_filename`：
/// 正则 `[\\/*?:"<>|]` 替换为空）
pub fn sanitize_filename(name: &str) -> String {
    name.chars()
        .filter(|c| !matches!(c, '\\' | '/' | '*' | '?' | ':' | '"' | '<' | '>' | '|'))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strips_windows_illegal_chars() {
        assert_eq!(sanitize_filename("a/b\\c:d*e?f\"g<h>i|j"), "abcdefghij");
        assert_eq!(sanitize_filename("正常文件名.pdf"), "正常文件名.pdf");
    }
}
