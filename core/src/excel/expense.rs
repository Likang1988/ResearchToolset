//! Excel 读写（支出相关）
//!
//! 对应 Python：
//! - `app/tools/generate_expense_template.py`（模板生成，BatchImportDialog.download_template）
//! - `app/components/batch_import_dialog.py::import_data`（批量导入解析与校验）
//! - `project_expense.py::export_expense_excel`（支出导出）
//!
//! 读：calamine（xlsx/xls）+ csv crate（csv，calamine 0.36 无 CSV 支持）；
//! 写：rust_xlsxwriter。
//! 按 feature-checklist §4：模板与导出均含 DataValidation 下拉校验（Python 模板原实现
//! 未加校验，此处按验收清单补上，属改进项）。

use std::path::Path;

use calamine::{Data, Reader, Sheets};
use rust_xlsxwriter::{DataValidation, Workbook, Worksheet};

use crate::models::BudgetCategory;

/// 批量导入解析出的一条支出记录
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ImportedExpense {
    pub category: String,
    pub content: String,
    /// 报账金额（元，> 0）
    pub amount: f64,
    pub specification: Option<String>,
    pub supplier: Option<String>,
    /// 报账日期 YYYY-MM-DD（缺省时用当天）
    pub date: String,
    pub remarks: Option<String>,
}

/// 支出导出行（7 列，与 Python export_expense_excel 一致）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ExportExpenseRow {
    pub category: String,
    pub content: String,
    pub specification: Option<String>,
    pub supplier: Option<String>,
    pub amount: f64,
    /// 报账日期 YYYY-MM-DD
    pub date: String,
    pub remarks: Option<String>,
}

const HEADERS: [&str; 7] = [
    "费用类别",
    "开支内容",
    "规格型号",
    "供应商",
    "报账金额",
    "报账日期",
    "备注",
];

/// rust_xlsxwriter 错误统一转为 String（便于与中文错误信息拼接）
fn xe(e: rust_xlsxwriter::XlsxError) -> String {
    format!("Excel 写入失败: {e}")
}

/// 生成批量导入模板（3 个 sheet + 类别下拉校验）。
///
/// - `支出信息`：表头 + 2 行示例数据，A2:A100 类别下拉校验
/// - `费用类别`：10 类 + 说明列
/// - `使用说明`：9 行说明（无表头）
pub fn generate_import_template(path: &Path) -> Result<(), String> {
    let mut workbook = Workbook::new();

    // ── 支出信息 ──
    let mut data_sheet = workbook.add_worksheet();
    data_sheet
        .set_name("支出信息")
        .map_err(|e| format!("命名工作表失败: {e}"))?;
    write_headers(&mut data_sheet, 0)?;

    // 示例数据两行（对应 Python example_data）
    let example: [(&str, &str, &str, &str, f64, &str, &str); 2] = [
        ("设备费", "设备A采购", "型号X", "供应商A", 10000.0, "2025-01-01", "示例数据1"),
        ("材料费", "材料B采购", "型号Y", "供应商B", 5000.0, "2025-01-02", "示例数据2"),
    ];
    for (i, (cat, content, spec, sup, amt, date, remark)) in example.iter().enumerate() {
        let row = (i + 1) as u32;
        data_sheet.write_string(row, 0, *cat).map_err(xe)?;
        data_sheet.write_string(row, 1, *content).map_err(xe)?;
        data_sheet.write_string(row, 2, *spec).map_err(xe)?;
        data_sheet.write_string(row, 3, *sup).map_err(xe)?;
        data_sheet.write_number(row, 4, *amt).map_err(xe)?;
        data_sheet.write_string(row, 5, *date).map_err(xe)?;
        data_sheet.write_string(row, 6, *remark).map_err(xe)?;
    }

    // 类别下拉校验（A2:A100，允许空）
    let dv = category_validation()?;
    data_sheet.add_data_validation(1, 0, 99, 0, &dv).map_err(xe)?;
    data_sheet.set_column_width(0, 14).map_err(xe)?;
    data_sheet.set_column_width(1, 20).map_err(xe)?;
    for col in 2..7 {
        data_sheet.set_column_width(col, 14).map_err(xe)?;
    }

    // ── 费用类别 ──
    let cat_sheet = workbook.add_worksheet();
    cat_sheet
        .set_name("费用类别")
        .map_err(|e| format!("命名工作表失败: {e}"))?;
    cat_sheet.write_string(0, 0, "费用类别").map_err(xe)?;
    cat_sheet.write_string(0, 1, "说明").map_err(xe)?;
    for (i, category) in BudgetCategory::ALL.iter().enumerate() {
        let row = (i + 1) as u32;
        cat_sheet.write_string(row, 0, category.as_str()).map_err(xe)?;
        cat_sheet.write_string(row, 1, "").map_err(xe)?;
    }

    // ── 使用说明 ──
    let help_sheet = workbook.add_worksheet();
    help_sheet
        .set_name("使用说明")
        .map_err(|e| format!("命名工作表失败: {e}"))?;
    let instructions = [
        "使用说明：",
        "1. 费用类别、开支内容、报账金额为必填项",
        "2. 费用类别必须是以下之一：",
        &format!(
            "   {}",
            BudgetCategory::ALL
                .iter()
                .map(|c| c.as_str())
                .collect::<Vec<_>>()
                .join("、")
        ),
        "3. 报账金额必须大于0",
        "4. 报账日期支持常见格式（如：YYYY-MM-DD、YYYY/MM/DD、DD/MM/YYYY等），可为空，默认为当前日期",
        "5. 规格型号、供应商、备注为选填项",
        "6. 请勿修改表头名称",
        "7. 请勿删除或修改本说明",
    ];
    for (i, line) in instructions.iter().enumerate() {
        help_sheet.write_string(i as u32, 0, *line).map_err(xe)?;
    }

    workbook
        .save(path)
        .map_err(|e| format!("保存模板失败: {e}"))?;
    Ok(())
}

/// 解析批量导入文件（xlsx/xls/csv），返回记录列表。
///
/// 校验与 Python 一致（缺失必要列 / 必填空值 / 类别非法 / 金额格式 / 金额<=0 /
/// 日期格式），错误时返回带行号的中文提示（比 Python 更细粒度：逐行报错，
/// 符合 checklist §4「逐行报错提示」）。
pub fn parse_import_file(path: &Path) -> Result<Vec<ImportedExpense>, String> {
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_lowercase())
        .unwrap_or_default();

    // 统一读为行×列字符串矩阵（含 BOM 处理），后续共用同一套校验逻辑
    let rows: Vec<Vec<String>> = if ext == "csv" {
        read_csv_rows(path)?
    } else {
        read_sheet_rows(path)?
    };

    parse_rows(rows)
}

/// 读取 CSV 为字符串矩阵（去 BOM）
fn read_csv_rows(path: &Path) -> Result<Vec<Vec<String>>, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("读取文件失败: {e}"))?;
    let bytes = bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(&bytes);
    let mut reader = csv::ReaderBuilder::new()
        .has_headers(false)
        .from_reader(bytes);
    let mut rows = Vec::new();
    for record in reader.records() {
        let record = record.map_err(|e| format!("解析 CSV 失败: {e}"))?;
        rows.push(record.iter().map(|f| f.trim().to_string()).collect());
    }
    Ok(rows)
}

/// 读取 xlsx/xls 第一个有效 sheet 为字符串矩阵
/// （优先「支出信息」sheet，否则取第一个；空单元格转为空串）
fn read_sheet_rows(path: &Path) -> Result<Vec<Vec<String>>, String> {
    let mut sheets =
        calamine::open_workbook_auto(path).map_err(|e| format!("打开文件失败: {e}"))?;

    let range: Option<calamine::Range<Data>> = match &mut sheets {
        Sheets::Xlsx(x) => {
            let names = x.sheet_names().to_vec();
            read_named_sheet(x, &names)
        }
        Sheets::Xls(x) => {
            let names = x.sheet_names().to_vec();
            read_named_sheet(x, &names)
        }
        _ => return Err("文件格式无法识别，请选择 .xlsx / .xls / .csv 文件".to_string()),
    };

    let Some(range) = range else {
        return Err("读取工作表失败".to_string());
    };
    Ok(range
        .rows()
        .map(|row| row.iter().map(cell_to_string).collect())
        .collect())
}

/// 在 workbook 中读取指定 sheet（优先「支出信息」，否则第一个）
fn read_named_sheet<R, RS>(
    reader: &mut R,
    names: &[String],
) -> Option<calamine::Range<Data>>
where
    R: Reader<RS>,
    RS: std::io::Read + std::io::Seek,
{
    let target = names
        .iter()
        .find(|n| n.contains("支出信息"))
        .cloned()
        .or_else(|| names.first().cloned())?;
    reader.worksheet_range(&target).ok()
}

/// 对行矩阵执行列定位与逐行校验，返回记录列表
fn parse_rows(rows: Vec<Vec<String>>) -> Result<Vec<ImportedExpense>, String> {
    if rows.is_empty() || rows.iter().all(|r| r.iter().all(|c| c.is_empty())) {
        return Err("导入的文件为空！".to_string());
    }

    // 定位表头（跳过空行）
    let header_row = rows
        .iter()
        .position(|r| r.iter().any(|c| !c.is_empty()))
        .ok_or_else(|| "导入的文件为空！".to_string())?;
    let header = rows[header_row].clone();

    let col = |name: &str| header.iter().position(|h| h == name);

    // 必要列检查（Python：缺失必要列直接报错）
    let required = ["费用类别", "开支内容", "报账金额"];
    let missing: Vec<&str> = required.iter().filter(|c| col(c).is_none()).copied().collect();
    if !missing.is_empty() {
        return Err(format!(
            "文件缺少必要列！\n缺失列：{}\n必须包含：{}",
            missing.join("、"),
            required.join("、")
        ));
    }
    let cat_col = col("费用类别").unwrap();
    let content_col = col("开支内容").unwrap();
    let amount_col = col("报账金额").unwrap();
    let spec_col = col("规格型号");
    let supplier_col = col("供应商");
    let date_col = col("报账日期");
    let remark_col = col("备注");

    let valid_categories: Vec<&str> = BudgetCategory::ALL.iter().map(|c| c.as_str()).collect();

    let mut expenses = Vec::new();
    let mut errors: Vec<String> = Vec::new();

    for (i, row) in rows.iter().enumerate().skip(header_row + 1) {
        // 空行跳过
        if row.iter().all(|c| c.is_empty()) {
            continue;
        }
        let excel_row_no = i + 1; // 1-based 行号（含表头）

        let category = row.get(cat_col).cloned().unwrap_or_default().trim().to_string();
        let content = row.get(content_col).cloned().unwrap_or_default().trim().to_string();
        let amount_raw = row.get(amount_col).cloned().unwrap_or_default();

        // 必填校验
        if category.is_empty() {
            errors.push(format!("第{excel_row_no}行：费用类别不能为空"));
            continue;
        }
        if content.is_empty() {
            errors.push(format!("第{excel_row_no}行：开支内容不能为空"));
            continue;
        }
        // 类别合法性
        if !valid_categories.contains(&category.as_str()) {
            errors.push(format!(
                "第{excel_row_no}行：无效的费用类别「{category}」\n有效的费用类别包括：{}",
                valid_categories.join("、")
            ));
            continue;
        }
        // 金额格式与范围
        let amount = match amount_raw.trim().parse::<f64>() {
            Ok(v) => v,
            Err(_) => {
                errors.push(format!("第{excel_row_no}行：报账金额「{amount_raw}」不是有效数字"));
                continue;
            }
        };
        if amount <= 0.0 {
            errors.push(format!("第{excel_row_no}行：报账金额必须大于0"));
            continue;
        }

        // 日期（可为空 → 默认当天）
        let date = match date_col.and_then(|c| row.get(c)).map(|s| s.trim()) {
            Some(d) if !d.is_empty() => match parse_date_text(d) {
                Some(parsed) => parsed,
                None => {
                    errors.push(format!(
                        "第{excel_row_no}行：无法识别报账日期，请使用常见格式（如：YYYY-MM-DD、YYYY/MM/DD）"
                    ));
                    continue;
                }
            },
            _ => chrono::Local::now().format("%Y-%m-%d").to_string(),
        };

        expenses.push(ImportedExpense {
            category,
            content,
            amount,
            specification: cell_at(row, spec_col).filter(|s| !s.is_empty()).cloned(),
            supplier: cell_at(row, supplier_col).filter(|s| !s.is_empty()).cloned(),
            date,
            remarks: cell_at(row, remark_col).filter(|s| !s.is_empty()).cloned(),
        });
    }

    if !errors.is_empty() {
        return Err(if errors.len() > 20 {
            format!(
                "发现 {} 处错误，前 20 条如下：\n{}",
                errors.len(),
                errors.iter().take(20).cloned().collect::<Vec<_>>().join("\n")
            )
        } else {
            errors.join("\n")
        });
    }

    Ok(expenses)
}

/// 取行中指定列（Option<usize> 列索引安全访问）
fn cell_at<'a>(row: &'a [String], col: Option<usize>) -> Option<&'a String> {
    col.and_then(|c| row.get(c))
}

/// 导出支出信息到 Excel（含类别下拉校验与说明区，对应 export_expense_excel）。
pub fn export_expenses(path: &Path, rows: &[ExportExpenseRow]) -> Result<(), String> {
    let mut workbook = Workbook::new();
    let mut sheet = workbook.add_worksheet();
    sheet
        .set_name("支出信息")
        .map_err(|e| format!("命名工作表失败: {e}"))?;

    write_headers(&mut sheet, 0)?;

    for (i, row) in rows.iter().enumerate() {
        let r = (i + 1) as u32;
        sheet.write_string(r, 0, row.category.as_str()).map_err(xe)?;
        sheet.write_string(r, 1, row.content.as_str()).map_err(xe)?;
        sheet.write_string(r, 2, row.specification.as_deref().unwrap_or("")).map_err(xe)?;
        sheet.write_string(r, 3, row.supplier.as_deref().unwrap_or("")).map_err(xe)?;
        sheet.write_number(r, 4, row.amount).map_err(xe)?;
        sheet.write_string(r, 5, row.date.as_str()).map_err(xe)?;
        sheet.write_string(r, 6, row.remarks.as_deref().unwrap_or("")).map_err(xe)?;
    }

    // 类别下拉校验（数据行 A2:A{n+1}，允许空）
    let last = rows.len() as u32;
    let dv = category_validation()?;
    sheet.add_data_validation(1, 0, last, 0, &dv).map_err(xe)?;

    // 说明区（数据下方空一行，对应 Python instructions 的 start_row = len(df)+3（1-based））
    let start_row = last + 2;
    let instructions = [
        "说明:",
        "1. 请在“费用类别”列使用下拉列表选择。",
        "2. “开支内容”、“报账金额”、“报账日期”为必填项。",
        "3. “报账金额”请填写数字。",
        "4. “报账日期”请使用 YYYY-MM-DD 格式。",
    ];
    for (i, line) in instructions.iter().enumerate() {
        sheet.write_string(start_row + i as u32, 0, *line).map_err(xe)?;
    }

    sheet.set_column_width(0, 14).map_err(xe)?;
    sheet.set_column_width(1, 20).map_err(xe)?;
    sheet.set_column_width(2, 16).map_err(xe)?;
    sheet.set_column_width(3, 16).map_err(xe)?;
    sheet.set_column_width(4, 12).map_err(xe)?;
    sheet.set_column_width(5, 12).map_err(xe)?;
    sheet.set_column_width(6, 16).map_err(xe)?;

    workbook
        .save(path)
        .map_err(|e| format!("导出Excel文件失败: {e}"))?;
    Ok(())
}

/// 类别下拉校验（允许空，带提示文案，对应 Python DataValidation）
fn category_validation() -> Result<DataValidation, String> {
    let categories: Vec<&str> = BudgetCategory::ALL.iter().map(|c| c.as_str()).collect();
    DataValidation::new()
        .allow_list_strings(&categories)
        .and_then(|dv| dv.set_error_title("无效输入"))
        .and_then(|dv| dv.set_error_message("您的输入不在允许的列表中"))
        .and_then(|dv| dv.set_input_title("选择类别"))
        .and_then(|dv| dv.set_input_message("请从下拉列表中选择一个类别"))
        .map_err(|e| format!("创建数据校验失败: {e}"))
}

fn write_headers(sheet: &mut Worksheet, row: u32) -> Result<(), String> {
    for (col, h) in HEADERS.iter().enumerate() {
        sheet
            .write_string(row, col as u16, *h)
            .map_err(|e| format!("写入表头失败: {e}"))?;
    }
    Ok(())
}

/// 单元格转字符串（保留浮点/整数的字面量，不引入科学计数法）
fn cell_to_string(cell: &Data) -> String {
    match cell {
        Data::String(s) => s.clone(),
        Data::Float(f) => format_number(*f),
        Data::Int(i) => i.to_string(),
        Data::Bool(b) => b.to_string(),
        Data::DateTimeIso(s) => s.clone(),
        Data::DurationIso(s) => s.clone(),
        Data::DateTime(dt) => match dt.as_datetime() {
            Some(d) => d.format("%Y-%m-%d").to_string(),
            None => String::new(),
        },
        Data::Error(e) => format!("错误:{e:?}"),
        Data::Empty => String::new(),
    }
}

/// 数字格式化：整数值不带小数尾缀，其余保留最多 2 位小数（金额场景）
fn format_number(v: f64) -> String {
    if (v - v.round()).abs() < 1e-9 {
        format!("{}", v as i64)
    } else {
        format!("{v:.2}")
    }
}

/// 文本日期解析，覆盖 pandas to_datetime 的常见格式
fn parse_date_text(s: &str) -> Option<String> {
    let s = s.trim();
    if s.is_empty() {
        return None;
    }
    const FORMATS: [&str; 7] = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%d/%m/%Y",
        "%Y%m%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ];
    for fmt in FORMATS {
        if let Ok(d) = chrono::NaiveDate::parse_from_str(s, fmt) {
            return Some(d.format("%Y-%m-%d").to_string());
        }
        if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(s, fmt) {
            return Some(dt.date().format("%Y-%m-%d").to_string());
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generates_import_template() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("模板.xlsx");
        generate_import_template(&path).unwrap();
        assert!(path.exists());

        // 用 calamine 读回验证 3 个 sheet
        let mut sheets = calamine::open_workbook_auto(&path).unwrap();
        let names = match &sheets {
            Sheets::Xlsx(x) => x.sheet_names().to_vec(),
            _ => panic!("应生成 xlsx"),
        };
        assert_eq!(names, vec!["支出信息", "费用类别", "使用说明"]);

        if let Sheets::Xlsx(x) = &mut sheets {
            let r = x.worksheet_range("支出信息").unwrap();
            // 表头 + 2 示例行
            assert_eq!(r.rows().len(), 3);
            assert_eq!(cell_to_string(&r.get_value((0, 0)).unwrap()), "费用类别");
            let cat = cell_to_string(&r.get_value((1, 0)).unwrap());
            assert!(cat == "设备费" || cat == "材料费");
            let amount = cell_to_string(&r.get_value((1, 4)).unwrap());
            assert!(amount.parse::<f64>().unwrap() > 0.0);

            let cat_sheet = x.worksheet_range("费用类别").unwrap();
            // 10 类 + 表头
            assert_eq!(cat_sheet.rows().len(), 11);
        }
    }

    #[test]
    fn parse_import_file_roundtrip() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("导入.xlsx");
        generate_import_template(&path).unwrap();

        let rows = parse_import_file(&path).unwrap();
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].category, "设备费");
        assert_eq!(rows[0].content, "设备A采购");
        assert_eq!(rows[0].amount, 10000.0);
        assert_eq!(rows[0].date, "2025-01-01");
        assert_eq!(rows[1].category, "材料费");
    }

    #[test]
    fn parse_import_rejects_invalid_category() {
        let tmp = tempfile::tempdir().unwrap();
        // 手写一个坏文件：类别非法
        let path = tmp.path().join("bad.xlsx");
        let mut wb = Workbook::new();
        let ws = wb.add_worksheet();
        ws.write_string(0, 0, "费用类别").unwrap();
        ws.write_string(0, 1, "开支内容").unwrap();
        ws.write_string(0, 2, "报账金额").unwrap();
        ws.write_string(1, 0, "不存在的类别").unwrap();
        ws.write_string(1, 1, "内容").unwrap();
        ws.write_number(1, 2, 100.0).unwrap();
        wb.save(&path).unwrap();

        let err = parse_import_file(&path).unwrap_err();
        assert!(err.contains("第2行"), "应含行号: {err}");
        assert!(err.contains("不存在的类别"));
    }

    #[test]
    fn parse_import_rejects_bad_amount_and_missing_required() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("bad2.xlsx");
        let mut wb = Workbook::new();
        let ws = wb.add_worksheet();
        ws.write_string(0, 0, "费用类别").unwrap();
        ws.write_string(0, 1, "开支内容").unwrap();
        ws.write_string(0, 2, "报账金额").unwrap();
        // 行1：金额非数字；行2：金额<=0
        ws.write_string(1, 0, "材料费").unwrap();
        ws.write_string(1, 1, "内容").unwrap();
        ws.write_string(1, 2, "abc").unwrap();
        ws.write_string(2, 0, "材料费").unwrap();
        ws.write_string(2, 1, "内容").unwrap();
        ws.write_number(2, 2, -5.0).unwrap();
        // 行3：开支内容为空
        ws.write_string(3, 0, "材料费").unwrap();
        ws.write_number(3, 2, 100.0).unwrap();
        wb.save(&path).unwrap();

        let err = parse_import_file(&path).unwrap_err();
        assert!(err.contains("不是有效数字"), "{err}");
        assert!(err.contains("必须大于0"), "{err}");
        assert!(err.contains("开支内容不能为空"), "{err}");
    }

    #[test]
    fn parse_import_csv_with_bom() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("data.csv");
        let csv = "\u{feff}费用类别,开支内容,报账金额,规格型号,供应商,报账日期,备注\n材料费,试剂采购,1200,AR级,某公司,2025/03/01,试验用\n";
        std::fs::write(&path, csv).unwrap();

        let rows = parse_import_file(&path).unwrap();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].category, "材料费");
        assert_eq!(rows[0].amount, 1200.0);
        // YYYY/MM/DD 格式应被解析
        assert_eq!(rows[0].date, "2025-03-01");
    }

    #[test]
    fn parse_import_defaults_date_when_missing() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("nodate.csv");
        let csv = "费用类别,开支内容,报账金额\n材料费,内容,100\n";
        std::fs::write(&path, csv).unwrap();
        let rows = parse_import_file(&path).unwrap();
        let today = chrono::Local::now().format("%Y-%m-%d").to_string();
        assert_eq!(rows[0].date, today);
    }

    #[test]
    fn export_expenses_writes_file_with_validation() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("导出.xlsx");
        let rows = vec![
            ExportExpenseRow {
                category: "材料费".to_string(),
                content: "试剂".to_string(),
                specification: None,
                supplier: Some("公司A".to_string()),
                amount: 1234.5,
                date: "2025-01-01".to_string(),
                remarks: None,
            },
            ExportExpenseRow {
                category: "设备费".to_string(),
                content: "设备".to_string(),
                specification: Some("X1".to_string()),
                supplier: None,
                amount: 999.0,
                date: "2025-02-01".to_string(),
                remarks: Some("备注".to_string()),
            },
        ];
        export_expenses(&path, &rows).unwrap();

        let mut sheets = calamine::open_workbook_auto(&path).unwrap();
        if let Sheets::Xlsx(x) = &mut sheets {
            let r = x.worksheet_range("支出信息").unwrap();
            assert_eq!(r.rows().len(), 9); // 表头 + 2 数据 + 空1行 + 5 说明行
            assert_eq!(cell_to_string(&r.get_value((0, 0)).unwrap()), "费用类别");
            assert_eq!(cell_to_string(&r.get_value((1, 4)).unwrap()), "1234.50");
            assert_eq!(cell_to_string(&r.get_value((2, 5)).unwrap()), "2025-02-01");
            assert!(cell_to_string(&r.get_value((4, 0)).unwrap()).contains("说明"));
        } else {
            panic!("应生成 xlsx");
        }
    }

    #[test]
    fn date_text_parsing() {
        assert_eq!(parse_date_text("2025-01-02").unwrap(), "2025-01-02");
        assert_eq!(parse_date_text("2025/1/2").unwrap(), "2025-01-02");
        assert_eq!(parse_date_text("02/01/2025").unwrap(), "2025-01-02");
        assert_eq!(parse_date_text("20250102").unwrap(), "2025-01-02");
        assert_eq!(parse_date_text("2025-01-02 15:30:00").unwrap(), "2025-01-02");
        assert!(parse_date_text("not-a-date").is_none());
    }

    #[test]
    fn cell_to_string_handles_all_types() {
        assert_eq!(cell_to_string(&Data::String("设备费".into())), "设备费");
        assert_eq!(cell_to_string(&Data::Int(42)), "42");
        assert_eq!(cell_to_string(&Data::Float(1234.5)), "1234.50");
        assert_eq!(cell_to_string(&Data::Bool(true)), "true");
        assert_eq!(cell_to_string(&Data::Empty), "");
        assert_eq!(cell_to_string(&Data::DateTimeIso("2025-01-01T00:00:00".into())), "2025-01-01T00:00:00");
    }
}