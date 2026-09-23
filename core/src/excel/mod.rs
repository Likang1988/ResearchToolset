//! Excel 导入导出
//!
//! 现状实现：
//! - `export_expenses_to_xlsx`：支出导出，含「费用类别」列下拉数据有效性 + 下方使用说明。
//! - `generate_expense_import_template`：支出批量导入模板 ——
//!   「支出信息」示例数据 + 「费用类别」+「使用说明」三个 sheet。
//! - `parse_expenses_from_xlsx`：读取并校验导入文件，
//!   返回结构化支出数据（不含 project/budget 关联，由调用方填充）。
//! - `export_budget_data`：预算编制导出 —— 预算明细 + 预算汇总（支持分年度比例）。

use std::path::Path;

use calamine::{open_workbook_auto, Data, Reader};
use chrono::NaiveDate;
use rust_xlsxwriter::{DataValidation, Format, Workbook};

use crate::models::{AcademicActivity, BudgetCategory, Expense, ProjectDocument, ProjectOutcome};
use crate::DbError;

/// 支出列表列头（导出与模板共用）
const EXPENSE_HEADERS: [&str; 7] =
    ["费用类别", "开支内容", "规格型号", "供应商", "报账金额", "报账日期", "备注"];

// ─────────────────────────── 项目文档导出 ───────────────────────────

/// 截断上传时间到分钟，即保留 `YYYY-MM-DD HH:MM`。
/// 库中存的是 `YYYY-MM-DD HH:MM:SS.ffffff`，取前 16 字符。
fn truncate_to_minute(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    if chars.len() >= 16 {
        chars[..16].iter().collect()
    } else {
        s.to_string()
    }
}

/// 导出项目文档列表到 xlsx。
///
/// 列顺序：文档名称 | 文档类型 | 版本号 | 关键词 | 上传时间 | 文档描述 | 文件路径
/// （导出列与表格列不同：表格为「文档附件」，导出为「文件路径」完整路径）。
/// `doc_type` 已由调用方转换为中文 label；上传时间截断到分钟。
pub fn export_documents_to_xlsx(path: &Path, docs: &[ProjectDocument]) -> Result<(), DbError> {
    let mut wb = Workbook::new();
    let sheet = wb.add_worksheet();
    sheet.set_name("文档信息").map_err(|e| DbError::Other(e.to_string()))?;

    let headers = ["文档名称", "文档类型", "版本号", "关键词", "上传时间", "文档描述", "文件路径"];
    let header_fmt = Format::new().set_bold();
    for (col, h) in headers.iter().enumerate() {
        sheet
            .write_with_format(0, col as u16, *h, &header_fmt)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    for (row_idx, d) in docs.iter().enumerate() {
        let row = (row_idx + 1) as u32;
        sheet
            .write(row, 0, &d.name)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 1, &d.doc_type)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 2, d.version.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 3, d.keywords.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        let time = d
            .upload_time
            .as_deref()
            .map(truncate_to_minute)
            .unwrap_or_default();
        sheet
            .write(row, 4, time)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 5, d.description.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 6, d.file_path.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    let widths = [30.0, 12.0, 10.0, 18.0, 17.0, 30.0, 45.0];
    for (col, w) in widths.iter().enumerate() {
        sheet
            .set_column_width(col as u16, *w)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    wb.save(path).map_err(|e| DbError::Other(e.to_string()))?;
    Ok(())
}

// ─────────────────────────── 项目成果导出 ───────────────────────────

/// 导出项目成果列表到 xlsx。
///
/// 列顺序：成果名称 | 成果类型 | 成果状态 | 作者/完成人 | 投稿/申请日期 |
/// 发表/授权日期 | 期刊/授权单位 | 成果描述 | 附件路径（9 列）。
/// `type` / `status` 已由调用方转换为中文 label；日期原样写入（YYYY-MM-DD）。
pub fn export_outcomes_to_xlsx(path: &Path, outcomes: &[ProjectOutcome]) -> Result<(), DbError> {
    let mut wb = Workbook::new();
    let sheet = wb.add_worksheet();
    sheet.set_name("成果信息").map_err(|e| DbError::Other(e.to_string()))?;

    let headers = [
        "成果名称",
        "成果类型",
        "成果状态",
        "作者/完成人",
        "投稿/申请日期",
        "发表/授权日期",
        "期刊/授权单位",
        "成果描述",
        "附件路径",
    ];
    let header_fmt = Format::new().set_bold();
    for (col, h) in headers.iter().enumerate() {
        sheet
            .write_with_format(0, col as u16, *h, &header_fmt)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    for (row_idx, o) in outcomes.iter().enumerate() {
        let row = (row_idx + 1) as u32;
        sheet
            .write(row, 0, &o.name)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 1, &o.r#type)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 2, o.status.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 3, o.authors.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 4, o.submit_date.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 5, o.publish_date.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 6, o.journal.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 7, o.description.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 8, o.attachment_path.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    let widths = [30.0, 12.0, 14.0, 22.0, 15.0, 15.0, 24.0, 40.0, 50.0];
    for (col, w) in widths.iter().enumerate() {
        sheet
            .set_column_width(col as u16, *w)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    wb.save(path).map_err(|e| DbError::Other(e.to_string()))?;
    Ok(())
}

/// 导出活动列表到 xlsx。
///
/// 列顺序：活动名称 | 活动类型 | 活动状态 | 主办方 | 开始日期 | 结束日期 |
/// 活动地点 | 参与人员 | 活动描述（9 列，**不含附件列**）。
/// `type` / `status` 已由调用方转换为中文 label；日期原样写入（YYYY-MM-DD）。
pub fn export_activities_to_xlsx(path: &Path, activities: &[AcademicActivity]) -> Result<(), DbError> {
    let mut wb = Workbook::new();
    let sheet = wb.add_worksheet();
    sheet.set_name("活动信息").map_err(|e| DbError::Other(e.to_string()))?;

    let headers = [
        "活动名称",
        "活动类型",
        "活动状态",
        "主办方",
        "开始日期",
        "结束日期",
        "活动地点",
        "参与人员",
        "活动描述",
    ];
    let header_fmt = Format::new().set_bold();
    for (col, h) in headers.iter().enumerate() {
        sheet
            .write_with_format(0, col as u16, *h, &header_fmt)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    for (row_idx, a) in activities.iter().enumerate() {
        let row = (row_idx + 1) as u32;
        sheet
            .write(row, 0, &a.name)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 1, &a.r#type)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 2, a.status.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 3, a.organizer.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 4, a.start_date.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 5, a.end_date.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 6, a.location.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 7, a.participants.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 8, a.description.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    let widths = [30.0, 12.0, 10.0, 22.0, 12.0, 12.0, 16.0, 24.0, 40.0];
    for (col, w) in widths.iter().enumerate() {
        sheet
            .set_column_width(col as u16, *w)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    wb.save(path).map_err(|e| DbError::Other(e.to_string()))?;
    Ok(())
}

/// 导出支出列表到 xlsx。
///
/// - 列序：费用类别 | 开支内容 | 规格型号 | 供应商 | 报账金额 | 报账日期 | 备注
/// - 金额保持元单位；日期原样写入（已是 YYYY-MM-DD 字符串）
/// - 「费用类别」列 A 加下拉数据有效性（10 个预算类别）
/// - 数据下方空一行写使用说明
pub fn export_expenses_to_xlsx(path: &Path, expenses: &[Expense]) -> Result<(), DbError> {
    let mut wb = Workbook::new();
    let sheet = wb.add_worksheet();
    sheet.set_name("支出信息").map_err(|e| DbError::Other(e.to_string()))?;

    let header_fmt = Format::new().set_bold();
    for (col, h) in EXPENSE_HEADERS.iter().enumerate() {
        sheet
            .write_with_format(0, col as u16, *h, &header_fmt)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    // 数据行
    for (row_idx, e) in expenses.iter().enumerate() {
        let row = (row_idx + 1) as u32;
        // category 为中文 label（调用方已通过 service 转换）
        sheet
            .write(row, 0, &e.category)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 1, &e.content)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 2, e.specification.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 3, e.supplier.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 4, e.amount.unwrap_or(0.0))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 5, e.date.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 6, e.remarks.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    // 「费用类别」列下拉数据有效性（对数据行）
    if !expenses.is_empty() {
        let last = expenses.len() as u32 + 1;
        let labels: Vec<&str> = BudgetCategory::ALL.iter().map(|c| c.label()).collect();
        let dv = DataValidation::new()
            .allow_list_strings(&labels)
            .map_err(|e| DbError::Other(e.to_string()))?
            .set_error_title("无效输入")
            .map_err(|e| DbError::Other(e.to_string()))?
            .set_error_message("您的输入不在允许的列表中")
            .map_err(|e| DbError::Other(e.to_string()))?
            .set_input_title("选择类别")
            .map_err(|e| DbError::Other(e.to_string()))?
            .set_input_message("请从下拉列表中选择一个类别")
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .add_data_validation(1, 0, last, 0, &dv)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    // 数据下方空一行写使用说明
    let instructions = [
        "说明:",
        "1. 请在“费用类别”列使用下拉列表选择。",
        "2. “开支内容”、“报账金额”、“报账日期”为必填项。",
        "3. “报账金额”请填写数字。",
        "4. “报账日期”请使用 YYYY-MM-DD 格式。",
    ];
    let start_row = expenses.len() as u32 + 3;
    for (i, ins) in instructions.iter().enumerate() {
        sheet
            .write(start_row + i as u32, 0, *ins)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    // 自适应列宽（简化：固定一组合理宽度）
    let widths = [12.0, 30.0, 18.0, 18.0, 12.0, 12.0, 20.0];
    for (col, w) in widths.iter().enumerate() {
        sheet
            .set_column_width(col as u16, *w)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    wb.save(path).map_err(|e| DbError::Other(e.to_string()))?;
    Ok(())
}

// ─────────────────────────── 批量导入模板 ───────────────────────────

/// 生成支出批量导入模板（3 个 sheet：支出信息示例数据 + 费用类别 + 使用说明）。
///
/// `example_rows` 为可选的示例行
/// （以 `(类别label, 内容, 规格, 供应商, 金额, 日期, 备注)` 表示）；传空则只写表头。
pub fn generate_expense_import_template(
    path: &Path,
    example_rows: &[(&str, &str, &str, &str, f64, &str, &str)],
) -> Result<(), DbError> {
    let mut wb = Workbook::new();

    // —— Sheet 1: 支出信息 ——
    let sheet = wb.add_worksheet();
    sheet.set_name("支出信息").map_err(|e| DbError::Other(e.to_string()))?;
    let header_fmt = Format::new().set_bold();
    for (col, h) in EXPENSE_HEADERS.iter().enumerate() {
        sheet
            .write_with_format(0, col as u16, *h, &header_fmt)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }
    for (row_idx, r) in example_rows.iter().enumerate() {
        let row = (row_idx + 1) as u32;
        sheet
            .write(row, 0, r.0)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 1, r.1)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 2, r.2)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 3, r.3)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 4, r.4)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 5, r.5)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 6, r.6)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }
    let widths = [12.0, 30.0, 18.0, 18.0, 12.0, 12.0, 20.0];
    for (col, w) in widths.iter().enumerate() {
        sheet
            .set_column_width(col as u16, *w)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    // —— Sheet 2: 费用类别（作为类别参考） ——
    let cat_sheet = wb.add_worksheet();
    cat_sheet
        .set_name("费用类别")
        .map_err(|e| DbError::Other(e.to_string()))?;
    cat_sheet
        .write_with_format(0, 0, "费用类别", &Format::new().set_bold())
        .map_err(|e| DbError::Other(e.to_string()))?;
    cat_sheet
        .write_with_format(0, 1, "说明", &Format::new().set_bold())
        .map_err(|e| DbError::Other(e.to_string()))?;
    for (row_idx, c) in BudgetCategory::ALL.iter().enumerate() {
        let row = (row_idx + 1) as u32;
        cat_sheet
            .write(row, 0, c.label())
            .map_err(|e| DbError::Other(e.to_string()))?;
        cat_sheet
            .write(row, 1, "")
            .map_err(|e| DbError::Other(e.to_string()))?;
    }
    cat_sheet
        .set_column_width(0, 16.0)
        .map_err(|e| DbError::Other(e.to_string()))?;

    // —— Sheet 3: 使用说明 ——
    let ins_sheet = wb.add_worksheet();
    ins_sheet
        .set_name("使用说明")
        .map_err(|e| DbError::Other(e.to_string()))?;
    let all_labels: Vec<&str> = BudgetCategory::ALL.iter().map(|c| c.label()).collect();
    let instructions = [
        "使用说明：",
        "1. 费用类别、开支内容、报账金额为必填项",
        "2. 费用类别必须是以下之一：",
        &format!("   {}", all_labels.join("、")),
        "3. 报账金额必须大于0",
        "4. 报账日期格式为YYYY-MM-DD，可为空，默认为当前日期",
        "5. 规格型号、供应商、备注为选填项",
        "6. 请勿修改表头名称",
        "7. 请勿删除或修改本说明",
    ];
    for (row_idx, ins) in instructions.iter().enumerate() {
        ins_sheet
            .write(row_idx as u32, 0, *ins)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }
    ins_sheet
        .set_column_width(0, 45.0)
        .map_err(|e| DbError::Other(e.to_string()))?;

    wb.save(path).map_err(|e| DbError::Other(e.to_string()))?;
    Ok(())
}

// ─────────────────────────── 批量导入解析 ───────────────────────────

/// 从导入文件解析出的一条支出记录（不含 project/budget 关联）。
///
/// `category` 为中文 label；`date` 为 YYYY-MM-DD。
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct ParsedExpense {
    pub category: String,
    pub content: String,
    pub specification: Option<String>,
    pub supplier: Option<String>,
    pub amount: f64,
    pub date: String,
    pub remarks: Option<String>,
}

fn data_to_string(d: &Data) -> String {
    match d {
        Data::String(s) => s.clone(),
        Data::Float(f) => format!("{f}"),
        Data::Int(i) => format!("{i}"),
        Data::Bool(b) => format!("{b}"),
        Data::DateTime(dt) => dt
            .as_datetime()
            .map(|n| n.format("%Y-%m-%d").to_string())
            .unwrap_or_default(),
        Data::DateTimeIso(s) => s.clone(),
        Data::DurationIso(s) => s.clone(),
        Data::Error(_) | Data::Empty => String::new(),
    }
}

fn data_to_f64(d: &Data) -> Option<f64> {
    match d {
        Data::Float(f) => Some(*f),
        Data::Int(i) => Some(*i as f64),
        Data::DateTime(dt) => Some(dt.as_f64()),
        Data::String(s) => s.trim().parse().ok(),
        _ => None,
    }
}

/// 解析日期字符串为 YYYY-MM-DD；支持常见格式。
fn parse_date(raw: &str) -> Option<String> {
    let raw = raw.trim();
    if raw.is_empty() {
        return None;
    }
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y.%m.%d", "%Y-%m"] {
        if let Ok(d) = NaiveDate::parse_from_str(raw, fmt) {
            return Some(d.format("%Y-%m-%d").to_string());
        }
    }
    None
}

/// 从未知/空单元格取可空字符串。
fn opt_string(d: &Data) -> Option<String> {
    let s = data_to_string(d);
    if s.trim().is_empty() {
        None
    } else {
        Some(s.trim().to_string())
    }
}

/// 读取并校验支出导入文件，返回结构化支出数据。
///
/// - 读取 sheet「支出信息」（.csv 不支持，仅 xlsx）
/// - 校验：必要列存在、必要列无空值、费用类别为预设之一、金额>0、日期格式合法
/// - 任一校验失败即返回 `Err`（携带首个错误信息，遇错即中断、不逐行汇总）
pub fn parse_expenses_from_xlsx(path: &Path) -> Result<Vec<ParsedExpense>, DbError> {
    let mut wb = open_workbook_auto(path)
        .map_err(|e| DbError::Other(format!("无法打开 Excel 文件: {e}")))?;

    // 读取「支出信息」sheet；找不到则报错
    let range = wb
        .worksheet_range("支出信息")
        .map_err(|e| DbError::Other(format!("读取「支出信息」sheet 失败: {e}")))?;

    let height = range.height();
    if height < 2 {
        return Err(DbError::Other("导入文件为空".into()));
    }

    // 表头行 → 列名到列索引的映射
    let required = ["费用类别", "开支内容", "报账金额"];
    let optional = ["规格型号", "供应商", "报账日期", "备注"];

    let mut col_map: std::collections::HashMap<String, u32> = std::collections::HashMap::new();
    for col in 0..range.width() {
        let name = data_to_string(&range.get_value((0, col as u32)).unwrap_or(&Data::Empty)).trim().to_string();
        if !name.is_empty() {
            col_map.insert(name, col as u32);
        }
    }

    // 必要列缺失检查
    let missing: Vec<&str> = required
        .iter()
        .filter(|c| !col_map.contains_key(**c))
        .copied()
        .collect();
    if !missing.is_empty() {
        return Err(DbError::Other(format!(
            "文件缺少必要列：{}；必须包含：{}",
            missing.join("、"),
            required.join("、")
        )));
    }

    let valid_categories: Vec<&str> = BudgetCategory::ALL.iter().map(|c| c.label()).collect();
    let mut parsed = Vec::new();

    for row in 1..(height as u32) {
        // 必填列空值检查
        let mut empty_req: Vec<&str> = Vec::new();
        for c in required {
            let val = data_to_string(&range.get_value((row, col_map[c])).unwrap_or(&Data::Empty));
            if val.trim().is_empty() {
                empty_req.push(c);
            }
        }
        if !empty_req.is_empty() {
            return Err(DbError::Other(format!(
                "第 {} 行以下必填列存在空值：{}",
                row + 1,
                empty_req.join("、")
            )));
        }

        // 费用类别
        let cat_raw = data_to_string(&range.get_value((row, col_map["费用类别"])).unwrap_or(&Data::Empty));
        let cat = cat_raw.trim().to_string();
        if !valid_categories.contains(&cat.as_str()) {
            return Err(DbError::Other(format!(
                "第 {} 行存在无效的费用类别：{cat}\n有效的费用类别包括：{}",
                row + 1,
                valid_categories.join("、")
            )));
        }

        // 金额
        let amount_d = range.get_value((row, col_map["报账金额"])).unwrap_or(&Data::Empty);
        let amount = data_to_f64(amount_d)
            .ok_or_else(|| DbError::Other(format!("第 {} 行报账金额列包含无效的数字格式", row + 1)))?;
        if amount <= 0.0 {
            return Err(DbError::Other(format!("第 {} 行报账金额必须大于0", row + 1)));
        }

        // 内容
        let content = data_to_string(&range.get_value((row, col_map["开支内容"])).unwrap_or(&Data::Empty))
            .trim()
            .to_string();

        // 可选字段
        let specification = optional
            .get(0)
            .and_then(|c| col_map.get(*c))
            .map(|&col| range.get_value((row, col)).unwrap_or(&Data::Empty))
            .and_then(opt_string);
        let supplier = optional
            .get(1)
            .and_then(|c| col_map.get(*c))
            .map(|&col| range.get_value((row, col)).unwrap_or(&Data::Empty))
            .and_then(opt_string);
        let remarks = optional
            .get(3)
            .and_then(|c| col_map.get(*c))
            .map(|&col| range.get_value((row, col)).unwrap_or(&Data::Empty))
            .and_then(opt_string);

        // 日期：空 → 当前日期；非空则须能解析
        let date_raw = optional
            .get(2)
            .and_then(|c| col_map.get(*c))
            .map(|&col| data_to_string(&range.get_value((row, col)).unwrap_or(&Data::Empty)).trim().to_string())
            .unwrap_or_default();
        let date = if date_raw.is_empty() {
            chrono::Local::now().format("%Y-%m-%d").to_string()
        } else {
            parse_date(&date_raw).ok_or_else(|| {
                DbError::Other(format!(
                    "第 {} 行无法识别报账日期格式：{date_raw}，请使用常见格式（YYYY-MM-DD、YYYY/MM/DD、DD/MM/YYYY）",
                    row + 1
                ))
            })?
        };

        parsed.push(ParsedExpense {
            category: cat,
            content,
            specification,
            supplier,
            amount,
            date,
            remarks,
        });
    }

    Ok(parsed)
}

// ─────────────────────────── 预算编制导出 ───────────────────────────

/// 预算导出中一个预算项（对应 budget_plan_items 的叶子项；金额单位为元）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetExportItem {
    pub name: String,
    pub specification: String,
    pub unit_price: f64,
    pub quantity: f64,
    pub amount: f64,
    pub remarks: String,
}

/// 预算导出中一个类别（对应一个 budget 类别节点；金额单位为元）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetExportCategory {
    pub name: String,
    pub amount: f64,
    pub remarks: String,
    pub items: Vec<BudgetExportItem>,
}

/// 预算导出数据（对应一个预算计划树）。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetExportData {
    pub project_name: String,
    pub total_amount: f64,
    pub categories: Vec<BudgetExportCategory>,
}

/// 预算导出配置。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetExportConfig {
    pub export_detail: bool,
    pub export_summary: bool,
    pub year_detail: bool,
    pub year_count: usize,
    /// 是否手动设置年度比例；false 则平均分配
    pub set_proportion: bool,
    /// 各年度比例（%），长度应与 year_count 相符
    pub proportions: Vec<u32>,
    /// true = 万元，false = 元
    pub unit_wan: bool,
}

/// 单位换算：万元 / 元。
fn conv(amount: f64, wan: bool) -> f64 {
    if wan {
        amount / 10000.0
    } else {
        amount
    }
}

/// 导出预算数据到 xlsx（预算明细 + 预算汇总 sheet）。
///
/// - 预算明细：列 = 项目名称 | 预算类别 | 预算项 | 规格型号 | 单价(unit) | 数量 |
///   金额(unit) | 备注 | 类别合计(unit) | 类别备注
/// - 预算汇总：列 = 序号 | 费用类别 | 经费数额(unit) [| 第1年 | 第2年 | ...]，
///   含「合计」行；分年度按比例或平均分配
pub fn export_budget_data(
    path: &Path,
    data: &BudgetExportData,
    cfg: &BudgetExportConfig,
) -> Result<(), DbError> {
    let unit = if cfg.unit_wan { "万元" } else { "元" };
    let mut wb = Workbook::new();

    // —— 预算明细 ——
    if cfg.export_detail {
        let sheet = wb.add_worksheet();
        sheet.set_name("预算明细").map_err(|e| DbError::Other(e.to_string()))?;
        let headers = [
            "项目名称",
            "预算类别",
            "预算项",
            "规格型号",
            &format!("单价({unit})"),
            "数量",
            &format!("金额({unit})"),
            "备注",
            &format!("类别合计({unit})"),
            "类别备注",
        ];
        let header_fmt = Format::new().set_bold();
        for (col, h) in headers.iter().enumerate() {
            sheet
                .write_with_format(0, col as u16, *h, &header_fmt)
                .map_err(|e| DbError::Other(e.to_string()))?;
        }

        let mut row: u32 = 1;
        for cat in &data.categories {
            if cat.items.is_empty() {
                // 类别无预算项 → 空行
                sheet
                    .write(row, 0, &data.project_name)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 1, &cat.name)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 8, 0.0)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                row += 1;
                continue;
            }
            for item in &cat.items {
                sheet
                    .write(row, 0, &data.project_name)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 1, &cat.name)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 2, &item.name)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 3, &item.specification)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 4, conv(item.unit_price, cfg.unit_wan))
                    .map_err(|e| DbError::Other(e.to_string()))?;
                // 数量单位不换算
                sheet
                    .write(row, 5, item.quantity)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 6, conv(item.amount, cfg.unit_wan))
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 7, &item.remarks)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 8, conv(cat.amount, cfg.unit_wan))
                    .map_err(|e| DbError::Other(e.to_string()))?;
                sheet
                    .write(row, 9, &cat.remarks)
                    .map_err(|e| DbError::Other(e.to_string()))?;
                row += 1;
            }
        }
    }

    // —— 预算汇总 ——
    if cfg.export_summary {
        let sheet = wb.add_worksheet();
        sheet.set_name("预算汇总").map_err(|e| DbError::Other(e.to_string()))?;

        let mut headers: Vec<String> = vec![
            "序号".to_string(),
            "费用类别".to_string(),
            format!("经费数额({unit})"),
        ];
        if cfg.year_detail {
            for y in 1..=cfg.year_count {
                headers.push(format!("第{y}年"));
            }
        }
        let header_fmt = Format::new().set_bold();
        for (col, h) in headers.iter().enumerate() {
            sheet
                .write_with_format(0, col as u16, h.as_str(), &header_fmt)
                .map_err(|e| DbError::Other(e.to_string()))?;
        }

        let mut row: u32 = 1;
        for (j, cat) in data.categories.iter().enumerate() {
            sheet
                .write(row, 0, (j + 1) as u32)
                .map_err(|e| DbError::Other(e.to_string()))?;
            sheet
                .write(row, 1, &cat.name)
                .map_err(|e| DbError::Other(e.to_string()))?;
            sheet
                .write(row, 2, conv(cat.amount, cfg.unit_wan))
                .map_err(|e| DbError::Other(e.to_string()))?;

            if cfg.year_detail {
                let year_amounts = year_amounts(cat.amount, cfg);
                for (y, amt) in year_amounts.iter().enumerate() {
                    sheet
                        .write(row, (3 + y) as u16, conv(*amt, cfg.unit_wan))
                        .map_err(|e| DbError::Other(e.to_string()))?;
                }
            }
            row += 1;
        }

        // 合计行
        sheet
            .write(row, 1, "合计")
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 2, conv(data.total_amount, cfg.unit_wan))
            .map_err(|e| DbError::Other(e.to_string()))?;
        if cfg.year_detail {
            let total_years = year_amounts(data.total_amount, cfg);
            for (y, amt) in total_years.iter().enumerate() {
                sheet
                    .write(row, (3 + y) as u16, conv(*amt, cfg.unit_wan))
                    .map_err(|e| DbError::Other(e.to_string()))?;
            }
        }
    }

    wb.save(path).map_err(|e| DbError::Other(e.to_string()))?;
    Ok(())
}

/// 按配置将某金额分配到各年度（元）。比例模式取 `proportions[:year_count]`，
/// 否则平均分配。均按百分比计算（比例×金额/100）。
fn year_amounts(amount: f64, cfg: &BudgetExportConfig) -> Vec<f64> {
    let n = cfg.year_count.max(1);
    if cfg.set_proportion && !cfg.proportions.is_empty() {
        cfg.proportions
            .iter()
            .take(n)
            .map(|p| amount * (*p as f64) / 100.0)
            .collect()
    } else {
        vec![amount / n as f64; n]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_document() -> ProjectDocument {
        ProjectDocument {
            id: 1,
            project_id: 1,
            name: "项目申请书".to_string(),
            doc_type: "申请材料".to_string(),
            version: Some("1.0".to_string()),
            description: Some("立项申请书".to_string()),
            file_path: Some(r"d:\docs\申请书.pdf".to_string()),
            upload_time: Some("2025-04-28 16:45:50.123456".to_string()),
            keywords: Some("申请,立项".to_string()),
        }
    }

    #[test]
    fn export_documents_creates_xlsx_with_7_columns() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("documents.xlsx");

        export_documents_to_xlsx(&path, &[sample_document()]).unwrap();
        assert!(path.exists());
        assert!(path.metadata().unwrap().len() > 0);

        let mut wb = open_workbook_auto(&path).unwrap();
        let range = wb.worksheet_range("文档信息").unwrap();
        // 表头 7 列
        assert_eq!(data_to_string(&range.get_value((0, 0)).unwrap()), "文档名称");
        assert_eq!(data_to_string(&range.get_value((0, 6)).unwrap()), "文件路径");
        // 数据行：类型为中文 label、时间为截断到分钟格式
        assert_eq!(data_to_string(&range.get_value((1, 1)).unwrap()), "申请材料");
        assert_eq!(data_to_string(&range.get_value((1, 4)).unwrap()), "2025-04-28 16:45");
        assert_eq!(data_to_string(&range.get_value((1, 6)).unwrap()), r"d:\docs\申请书.pdf");
    }

    #[test]
    fn truncate_time_to_minute() {
        assert_eq!(truncate_to_minute("2025-01-02 03:04:05.000000"), "2025-01-02 03:04");
        assert_eq!(truncate_to_minute("2025-01-02"), "2025-01-02");
    }

    fn sample_outcome() -> ProjectOutcome {
        ProjectOutcome {
            id: 1,
            project_id: 1,
            name: "某期刊论文".to_string(),
            r#type: "论文".to_string(),
            status: Some("已发表/授权".to_string()),
            authors: Some("张三, 李四".to_string()),
            submit_date: Some("2024-01-15".to_string()),
            publish_date: Some("2024-06-01".to_string()),
            journal: Some("某期刊".to_string()),
            description: Some("成果描述".to_string()),
            remarks: None,
            attachment_path: Some(r"d:\docs\论文.pdf".to_string()),
        }
    }

    #[test]
    fn export_outcomes_creates_xlsx_with_9_columns() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("outcomes.xlsx");

        export_outcomes_to_xlsx(&path, &[sample_outcome()]).unwrap();
        assert!(path.exists());
        assert!(path.metadata().unwrap().len() > 0);

        let mut wb = open_workbook_auto(&path).unwrap();
        let range = wb.worksheet_range("成果信息").unwrap();
        // 表头 9 列
        assert_eq!(data_to_string(&range.get_value((0, 0)).unwrap()), "成果名称");
        assert_eq!(data_to_string(&range.get_value((0, 8)).unwrap()), "附件路径");
        // 数据行：类型/状态为中文 label、日期原样写入
        assert_eq!(data_to_string(&range.get_value((1, 1)).unwrap()), "论文");
        assert_eq!(data_to_string(&range.get_value((1, 2)).unwrap()), "已发表/授权");
        assert_eq!(data_to_string(&range.get_value((1, 5)).unwrap()), "2024-06-01");
        assert_eq!(data_to_string(&range.get_value((1, 8)).unwrap()), r"d:\docs\论文.pdf");
    }

    fn sample_activity() -> AcademicActivity {
        AcademicActivity {
            id: 1,
            name: "某学术会议".to_string(),
            r#type: "学术会议".to_string(),
            status: Some("已结束".to_string()),
            organizer: Some("某大学".to_string()),
            start_date: Some("2024-05-10".to_string()),
            end_date: Some("2024-05-12".to_string()),
            location: Some("北京".to_string()),
            participants: Some("张三, 李四".to_string()),
            description: Some("会议描述".to_string()),
            attachment_path: Some(r"d:\docs\会议通知.pdf".to_string()),
        }
    }

    #[test]
    fn export_activities_creates_xlsx_with_9_columns() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("activities.xlsx");

        export_activities_to_xlsx(&path, &[sample_activity()]).unwrap();
        assert!(path.exists());
        assert!(path.metadata().unwrap().len() > 0);

        let mut wb = open_workbook_auto(&path).unwrap();
        let range = wb.worksheet_range("活动信息").unwrap();
        // 表头 9 列，末列为「活动描述」（不含附件列）
        assert_eq!(data_to_string(&range.get_value((0, 0)).unwrap()), "活动名称");
        assert_eq!(data_to_string(&range.get_value((0, 8)).unwrap()), "活动描述");
        // 数据行：类型/状态为中文 label、日期原样写入
        assert_eq!(data_to_string(&range.get_value((1, 1)).unwrap()), "学术会议");
        assert_eq!(data_to_string(&range.get_value((1, 2)).unwrap()), "已结束");
        assert_eq!(data_to_string(&range.get_value((1, 4)).unwrap()), "2024-05-10");
        assert_eq!(data_to_string(&range.get_value((1, 8)).unwrap()), "会议描述");
    }

    fn sample_expense() -> Expense {
        Expense {
            id: 1,
            project_id: 1,
            budget_id: 1,
            category: "材料费".to_string(),
            content: "试剂A".to_string(),
            specification: Some("500g".to_string()),
            supplier: Some("Sigma".to_string()),
            amount: Some(10000.0),
            date: Some("2024-05-01".to_string()),
            remarks: None,
            voucher_path: None,
        }
    }

    #[test]
    fn export_expenses_creates_xlsx_file() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("expenses.xlsx");

        let expenses = vec![sample_expense()];
        export_expenses_to_xlsx(&path, &expenses).unwrap();
        assert!(path.exists());
        assert!(path.metadata().unwrap().len() > 0);
    }

    #[test]
    fn template_generation_creates_3_sheets() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("template.xlsx");

        let examples = [
            ("设备费", "设备A", "X1", "供应商A", 10000.0, "2024-01-01", "示例"),
            ("材料费", "材料B", "", "", 5000.0, "", ""),
        ];
        generate_expense_import_template(&path, &examples).unwrap();
        assert!(path.exists());

        // 用 calamine 读回验证 sheet 数量与首行表头
        let mut wb = open_workbook_auto(&path).unwrap();
        let range = wb.worksheet_range("支出信息").unwrap();
        assert_eq!(data_to_string(&range.get_value((0, 0)).unwrap()), "费用类别");
        assert_eq!(data_to_string(&range.get_value((0, 6)).unwrap()), "备注");
        // 示例第一行
        assert_eq!(data_to_string(&range.get_value((1, 0)).unwrap()), "设备费");
        assert_eq!(data_to_string(&range.get_value((1, 4)).unwrap()), "10000");
        // 类别 sheet 存在
        assert!(wb.worksheet_range("费用类别").is_ok());
        assert!(wb.worksheet_range("使用说明").is_ok());
    }

    #[test]
    fn parse_expenses_round_trips_template() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("template.xlsx");

        let examples = [
            ("设备费", "设备A采购", "型号X", "供应商A", 10000.0, "2024-01-15", "示例数据1"),
            ("材料费", "材料B采购", "型号Y", "供应商B", 5000.0, "", ""), // 空日期 → 当前日期
        ];
        generate_expense_import_template(&path, &examples).unwrap();

        let parsed = parse_expenses_from_xlsx(&path).unwrap();
        assert_eq!(parsed.len(), 2);
        assert_eq!(parsed[0].category, "设备费");
        assert_eq!(parsed[0].content, "设备A采购");
        assert_eq!(parsed[0].amount, 10000.0);
        assert_eq!(parsed[0].date, "2024-01-15");
        assert_eq!(parsed[1].specification, Some("型号Y".to_string()));

        // 空日期应补为当前日期（YYYY-MM-DD 格式）
        assert_eq!(parsed[1].date.len(), 10);
    }

    #[test]
    fn parse_rejects_invalid_category() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("bad.xlsx");

        let examples = [("不存在类别", "内容", "", "", 100.0, "", "")];
        generate_expense_import_template(&path, &examples).unwrap();

        let err = parse_expenses_from_xlsx(&path).unwrap_err();
        assert!(err.to_string().contains("无效的费用类别"), "got {err}");
    }

    #[test]
    fn parse_rejects_nonpositive_amount() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("neg.xlsx");

        let examples = [("设备费", "内容", "", "", -5.0, "", "")];
        generate_expense_import_template(&path, &examples).unwrap();

        let err = parse_expenses_from_xlsx(&path).unwrap_err();
        assert!(err.to_string().contains("必须大于0"), "got {err}");
    }

    #[test]
    fn parse_rejects_bad_date() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("date.xlsx");

        let examples = [("设备费", "内容", "", "", 100.0, "2024年1月", "")];
        generate_expense_import_template(&path, &examples).unwrap();

        let err = parse_expenses_from_xlsx(&path).unwrap_err();
        assert!(err.to_string().contains("无法识别报账日期"), "got {err}");
    }

    #[test]
    fn budget_export_detail_and_summary() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("budget.xlsx");

        let data = BudgetExportData {
            project_name: "测试项目".to_string(),
            total_amount: 150000.0,
            categories: vec![
                BudgetExportCategory {
                    name: "设备费".to_string(),
                    amount: 100000.0,
                    remarks: String::new(),
                    items: vec![BudgetExportItem {
                        name: "服务器".to_string(),
                        specification: "X".to_string(),
                        unit_price: 50000.0,
                        quantity: 2.0,
                        amount: 100000.0,
                        remarks: String::new(),
                    }],
                },
                BudgetExportCategory {
                    name: "材料费".to_string(),
                    amount: 50000.0,
                    remarks: String::new(),
                    items: vec![],
                },
            ],
        };

        let cfg = BudgetExportConfig {
            export_detail: true,
            export_summary: true,
            year_detail: true,
            year_count: 3,
            set_proportion: false,
            proportions: vec![],
            unit_wan: true,
        };

        export_budget_data(&path, &data, &cfg).unwrap();
        assert!(path.exists());

        // 验证汇总 sheet 存在且万元单位换算正确
        let mut wb = open_workbook_auto(&path).unwrap();
        let summary = wb.worksheet_range("预算汇总").unwrap();
        // 表头第 3 列应为 经费数额(万元)
        assert_eq!(
            data_to_string(&summary.get_value((0, 2)).unwrap()),
            "经费数额(万元)"
        );
        // 第 1 行数据：序号1, 设备费, 10（万元）
        assert_eq!(data_to_string(&summary.get_value((1, 0)).unwrap()), "1");
        assert_eq!(data_to_string(&summary.get_value((1, 2)).unwrap()), "10");

        let detail = wb.worksheet_range("预算明细").unwrap();
        // 表头应含 单价(万元)
        assert_eq!(
            data_to_string(&detail.get_value((0, 4)).unwrap()),
            "单价(万元)"
        );
    }

    #[test]
    fn budget_summary_proportion_mode() {
        // 比例模式：30/40/30，验证每年金额
        let cfg = BudgetExportConfig {
            export_detail: false,
            export_summary: true,
            year_detail: true,
            year_count: 3,
            set_proportion: true,
            proportions: vec![30, 40, 30],
            unit_wan: false,
        };
        let amts = year_amounts(10000.0, &cfg);
        assert_eq!(amts, vec![3000.0, 4000.0, 3000.0]);
    }
}
