// ResearchToolset Rust 版入口
//
// 当前：注册 list_projects, add_project, update_project, delete_project 命令，
// 启动时打开/初始化/迁移 database/database.db，
// 通过 Mutex<Connection> 在命令间同步共享。

use std::path::{Path, PathBuf};
use std::sync::Mutex;

use rusqlite::Connection;
use tauri::{Manager, State};

use research_toolset_core::attachments::{self, AttachmentContext, AttachmentKind};
use research_toolset_core::db;
use research_toolset_core::excel::{self, BudgetExportConfig, BudgetExportData, ParsedExpense};
use research_toolset_core::logging;
use research_toolset_core::models::{
    AcademicActivity, Actionlog, Expense, Project, ProjectDocument, ProjectOutcome,
};
use research_toolset_core::services::activity::{self, ActivityInput};
use research_toolset_core::services::budget::{
    self, AnnualBudgetDetail, AnnualBudgetInput, BudgetItemInput, TotalBudgetDetail,
};
use research_toolset_core::services::budget_plan::{
    self, BudgetPlanNode, BudgetPlanSave,
};
use research_toolset_core::services::document::{self, DocumentInput};
use research_toolset_core::services::expense::{self, ExpenseInput};
use research_toolset_core::services::gantt::{self, GanttProjectData};
use research_toolset_core::services::home;
use research_toolset_core::services::indirect_cost;
use research_toolset_core::services::outcome::{self, OutcomeInput};
use research_toolset_core::services::project::{self, ProjectNew};
use research_toolset_core::services::tree_list::{self, TreeListNode};

/// 应用共享的数据库连接状态（rusqlite Connection 非线程安全，用 Mutex 包裹）
/// `path` 记录当前打开的数据库路径，供 db_path 查询与切换后展示
pub struct DbState {
    conn: Mutex<Connection>,
    path: Mutex<PathBuf>,
}

/// 解析 database.db 路径。
///
/// - 调试模式：源码项目根 `database/database.db`
/// - 发布（打包/便携）模式：可执行文件旁 `database/database.db`
fn resolve_db_path() -> PathBuf {
    // 调试模式：源码项目根
    if cfg!(debug_assertions) {
        return PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("database")
            .join("database.db");
    }
    // 发布（打包/便携）模式：可执行文件旁的 database/database.db，
    // 数据跟随 exe 位置，与源码隔离，便于绿色分发。
    std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|dir| dir.join("database").join("database.db")))
        .unwrap_or_else(|| PathBuf::from("database").join("database.db"))
}

/// 项目根目录（documents/ 与 vouchers/ 等附件目录的父级）。
/// 与 `resolve_db_path` 同源——database.db 在 `<root>/database/` 下。
fn root_dir() -> PathBuf {
    resolve_db_path()
        .parent()
        .and_then(|p| p.parent()) // 去掉 database/database.db 两层
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

/// 上次打开的数据库路径记录文件（`database/last_db.txt`，与 resolve_db_path 同规则：
/// 源码模式在项目根，便携模式在 exe 旁），用于启动时恢复用户上次选择的数据库。
fn last_db_path_file() -> PathBuf {
    let mut p = resolve_db_path();
    p.set_file_name("last_db.txt");
    p
}

/// 启动时解析数据库路径：优先使用上次打开的数据库（文件仍存在时），否则回退默认。
fn resolve_startup_db_path() -> PathBuf {
    let default = resolve_db_path();
    match std::fs::read_to_string(last_db_path_file()) {
        Ok(s) => {
            let saved = PathBuf::from(s.trim());
            if saved.exists() {
                saved
            } else {
                default
            }
        }
        Err(_) => default,
    }
}

/// 记住当前数据库：非默认路径写入 last_db.txt，等于默认路径则清除记录。
fn remember_db_path(path: &Path) {
    let file = last_db_path_file();
    if path == resolve_db_path() {
        if file.exists() && std::fs::remove_file(&file).is_err() {
            eprintln!("清除上次数据库路径失败");
        }
        return;
    }
    if let Some(dir) = file.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    if let Err(e) = std::fs::write(&file, path.to_string_lossy().as_bytes()) {
        eprintln!("保存上次数据库路径失败: {e}");
    }
}

/// 基础连通性命令：前端可调用以确认 IPC 正常
#[tauri::command]
fn ping() -> String {
    "pong".to_string()
}

/// 返回当前打开的数据库路径（默认= resolve_db_path；用户切换后为自定义路径）
#[tauri::command]
fn db_path(state: State<'_, DbState>) -> String {
    state
        .path
        .lock()
        .map(|p| p.display().to_string())
        .unwrap_or_else(|_| resolve_db_path().display().to_string())
}

/// 切换数据库文件：打开并初始化指定路径的数据库后替换当前连接。
/// 任一步失败都会保持原连接不变，不影响当前使用。
#[tauri::command]
fn open_database(state: State<'_, DbState>, path: String) -> Result<(), String> {
    let new_path = PathBuf::from(&path);
    // 先独立打开 + 建表 + 迁移（失败不触碰现有连接）
    let mut conn = db::open(&new_path).map_err(|e| format!("打开数据库失败: {e}"))?;
    db::init_db(&mut conn).map_err(|e| format!("初始化数据库失败: {e}"))?;
    db::migrate::migrate_db(&mut conn).map_err(|e| format!("迁移数据库失败: {e}"))?;
    // 全部成功后替换连接与路径
    let mut guard = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    *guard = conn;
    *state
        .path
        .lock()
        .map_err(|e| format!("路径锁失败: {e}"))? = new_path.clone();
    remember_db_path(&new_path);
    Ok(())
}

/// 恢复默认数据库（按 resolve_db_path 规则解析，源码/便携模式各归其位）
#[tauri::command]
fn reset_database(state: State<'_, DbState>) -> Result<(), String> {
    let path = resolve_db_path();
    open_database(state, path.display().to_string())
}

/// 列出全部项目（按 id 升序）
#[tauri::command]
fn list_projects(state: State<'_, DbState>) -> Result<Vec<Project>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    project::list_projects(&conn).map_err(|e| format!("查询项目失败: {e}"))
}

/// 主页概览：项目经费 + 项目进度（一次性返回，避免 N+1 查询）
#[tauri::command]
fn home_overview(state: State<'_, DbState>) -> Result<home::HomeOverview, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    home::home_overview(&conn).map_err(|e| format!("加载主页概览失败: {e}"))
}

/// 新增项目
#[tauri::command]
fn add_project(state: State<'_, DbState>, data: ProjectNew) -> Result<i64, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    project::add_project(&conn, data).map_err(|e| format!("新增项目失败: {e}"))
}

/// 编辑项目
#[tauri::command]
fn update_project(state: State<'_, DbState>, id: i64, data: ProjectNew) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    project::update_project(&conn, id, data).map_err(|e| format!("更新项目失败: {e}"))
}

/// 删除项目：级联删除关联记录 + 清理 documents/vouchers 附件目录。
/// 附件清理失败不回滚数据库：数据库已提交，文件错误仅记录。
#[tauri::command]
fn delete_project(state: State<'_, DbState>, id: i64) -> Result<(), String> {
    // 1. 数据库级联删除（在事务内）
    {
        let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
        project::delete_project(&conn, id).map_err(|e| format!("删除项目失败: {e}"))?;
    }
    // 2. 附件目录清理（数据库已提交后执行）
    let _ = attachments::clean_project_attachments(&root_dir(), id);
    Ok(())
}

/// 导出项目数据为 JSON 文件
#[tauri::command]
fn export_project_data(
    state: State<'_, DbState>,
    project_id: i64,
    path: String,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let json = project::export_project_data(&conn, project_id)
        .map_err(|e| format!("导出项目数据失败: {e}"))?;
    std::fs::write(&path, json).map_err(|e| format!("写入导出文件失败: {e}"))
}

/// 导入项目数据。
/// `overwrite=false` 且财务编号重复时返回错误"DUPLICATE_FINANCIAL_CODE"，
/// 前端捕获后弹覆盖确认，再以 `overwrite=true` 重试。
#[tauri::command]
fn import_project_data(
    state: State<'_, DbState>,
    path: String,
    overwrite: bool,
) -> Result<i64, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    project::import_project_data(&conn, &path, overwrite)
        .map_err(|e| format!("导入项目数据失败: {e}"))
}

/// 生成附件保存路径。
/// `kind` 取值：`expense` / `activity` / `default`（serde snake_case）。
/// 返回完整目标路径字符串；目标目录会被创建。
#[tauri::command]
fn generate_attachment_path(
    kind: AttachmentKind,
    original_filename: String,
    context: AttachmentContext,
) -> Result<String, String> {
    attachments::generate_attachment_path(&root_dir(), kind, &original_filename, &context)
        .map(|p| p.display().to_string())
        .map_err(|e| format!("生成附件路径失败: {e}"))
}

/// 上传/替换附件：把 `source_file` 拷贝到按规则生成的目标路径，
/// 若 `old_path`（数据库中的旧附件）存在且不同于新路径则删除旧文件。
/// 返回新附件的完整路径（调用方应保存到数据库）。
#[tauri::command]
fn save_attachment(
    kind: AttachmentKind,
    source_file: String,
    context: AttachmentContext,
    old_path: Option<String>,
) -> Result<String, String> {
    let old = old_path.as_deref().map(std::path::Path::new);
    attachments::save_attachment(
        &root_dir(),
        kind,
        std::path::Path::new(&source_file),
        &context,
        old,
    )
    .map(|p| p.display().to_string())
    .map_err(|e| format!("保存附件失败: {e}"))
}

/// 删除附件文件。
/// 文件不存在时视为成功（空操作）。数据库中的路径置空由调用方负责。
#[tauri::command]
fn delete_attachment(path: String) -> Result<(), String> {
    attachments::delete_attachment(std::path::Path::new(&path))
        .map_err(|e| format!("删除附件失败: {e}"))
}

/// 批量校验附件文件是否真实存在（列表加载时识别"程序外删除"导致的附件缺失）。
#[tauri::command]
fn check_attachments(paths: Vec<String>) -> Result<Vec<bool>, String> {
    Ok(attachments::check_attachments_exist(&paths))
}

/// 列出项目预算树（三级：总预算 + 年度预算 + 各 10 科目子项）
#[tauri::command]
fn list_project_budgets(
    state: State<'_, DbState>,
    project_id: i64,
) -> Result<budget::BudgetTree, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::list_project_budgets(&conn, project_id)
        .map_err(|e| format!("加载预算树失败: {e}"))
}

/// 新增年度预算
#[tauri::command]
fn add_annual_budget(
    state: State<'_, DbState>,
    input: AnnualBudgetInput,
) -> Result<i64, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::add_annual_budget(&conn, input).map_err(|e| format!("新增年度预算失败: {e}"))
}

/// 按 id 查询年度预算详情（回填编辑表单用）
/// 若 id 非年度预算（如总预算）则返回 null
#[tauri::command]
fn get_annual_budget(
    state: State<'_, DbState>,
    id: i64,
) -> Result<Option<AnnualBudgetDetail>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::get_annual_budget_by_id(&conn, id).map_err(|e| format!("查询年度预算失败: {e}"))
}

/// 更新年度预算：修改总金额 + 10 科目金额；科目 spent_amount 保留
#[tauri::command]
fn update_annual_budget(
    state: State<'_, DbState>,
    id: i64,
    total_amount: f64,
    items: Vec<BudgetItemInput>,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::update_annual_budget(&conn, id, total_amount, &items)
        .map_err(|e| format!("更新年度预算失败: {e}"))
}

/// 查询总预算详情（year IS NULL）。非总预算返回 null。
#[tauri::command]
fn get_total_budget(
    state: State<'_, DbState>,
    id: i64,
) -> Result<Option<TotalBudgetDetail>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::get_total_budget_by_id(&conn, id)
        .map_err(|e| format!("查询总预算失败: {e}"))
}

/// 更新总预算：改总金额 + 10 科目金额；科目 spent_amount 保留
#[tauri::command]
fn update_total_budget(
    state: State<'_, DbState>,
    id: i64,
    total_amount: f64,
    items: Vec<BudgetItemInput>,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::update_total_budget(&conn, id, total_amount, &items)
        .map_err(|e| format!("更新总预算失败: {e}"))
}

/// 删除年度预算：级联删除子项与关联支出
#[tauri::command]
fn delete_annual_budget(state: State<'_, DbState>, id: i64) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::delete_annual_budget(&conn, id).map_err(|e| format!("删除年度预算失败: {e}"))
}

/// 删除项目总预算：级联删除该项目全部预算、子项与关联支出
#[tauri::command]
fn delete_total_budget(state: State<'_, DbState>, project_id: i64) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget::delete_total_budget(&conn, project_id).map_err(|e| format!("删除总预算失败: {e}"))
}

/// 列出某预算下所有支出（按日期倒序）
#[tauri::command]
fn list_expenses(
    state: State<'_, DbState>,
    budget_id: i64,
) -> Result<Vec<Expense>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::list_expenses_by_budget(&conn, budget_id)
        .map_err(|e| format!("查询支出列表失败: {e}"))
}

/// 按科目列出项目支出（budget_id 有值时限定该年度预算，否则跨全部年度；按日期倒序）
#[tauri::command]
fn list_project_expenses_by_category(
    state: State<'_, DbState>,
    project_id: i64,
    category: String,
    budget_id: Option<i64>,
) -> Result<Vec<expense::ProjectExpenseRow>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::list_project_expenses_by_category(&conn, project_id, &category, budget_id)
        .map_err(|e| format!("查询科目支出失败: {e}"))
}

/// 维护：从支出记录全量重算预算支出统计（修复统计漂移，幂等）
#[tauri::command]
fn rebuild_expense_stats(state: State<'_, DbState>) -> Result<(usize, usize), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::rebuild_spent_amounts(&conn).map_err(|e| format!("重建支出统计失败: {e}"))
}

/// 按 id 查询支出（编辑回填用）。不存在返回 null。
#[tauri::command]
fn get_expense(state: State<'_, DbState>, id: i64) -> Result<Option<Expense>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::get_expense_by_id(&conn, id).map_err(|e| format!("查询支出失败: {e}"))
}

/// 新增支出：INSERT + 联动更新 budgets/budget_items 的 spent_amount
#[tauri::command]
fn add_expense(state: State<'_, DbState>, input: ExpenseInput) -> Result<i64, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::add_expense(&conn, input).map_err(|e| format!("新增支出失败: {e}"))
}

/// 更新支出：UPDATE + 类别变化时迁移 budget_items.spent_amount + 调 budgets 差额
#[tauri::command]
fn update_expense(
    state: State<'_, DbState>,
    id: i64,
    input: ExpenseInput,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::update_expense(&conn, id, input).map_err(|e| format!("更新支出失败: {e}"))
}

/// 仅更新支出凭证路径（附件上传/替换/删除后写库；不触发金额联动）。
#[tauri::command]
fn update_expense_voucher(
    state: State<'_, DbState>,
    id: i64,
    voucher_path: Option<String>,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::update_expense_voucher(&conn, id, voucher_path)
        .map_err(|e| format!("更新凭证路径失败: {e}"))
}

/// 复制附件到目标位置（下载凭证副本/导出文档附件用）。
/// 若目标父目录不存在则自动创建。
#[tauri::command]
fn copy_attachment_file(source: String, dest: String) -> Result<(), String> {
    let dest_path = std::path::Path::new(&dest);
    if let Some(parent) = dest_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("创建目标目录失败（{}）: {e}", parent.display()))?;
    }
    std::fs::copy(&source, dest_path)
        .map(|_| ())
        .map_err(|e| format!("复制文件失败（{source} → {dest}）: {e}"))
}

/// 批量删除支出：DELETE + 按类别回退 budget_items + 回退 budgets.spent_amount
#[tauri::command]
fn delete_expenses(state: State<'_, DbState>, ids: Vec<i64>) -> Result<usize, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::delete_expenses(&conn, &ids).map_err(|e| format!("删除支出失败: {e}"))
}

/// 导出某预算下的支出列表到 xlsx 文件
#[tauri::command]
fn export_expenses_excel(
    state: State<'_, DbState>,
    budget_id: i64,
    save_path: String,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let expenses = expense::list_expenses_by_budget(&conn, budget_id)
        .map_err(|e| format!("查询支出失败: {e}"))?;
    excel::export_expenses_to_xlsx(std::path::Path::new(&save_path), &expenses)
        .map_err(|e| format!("导出 Excel 失败: {e}"))
}

/// 生成支出批量导入模板（支出信息示例数据 + 费用类别 + 使用说明三个 sheet）。
#[tauri::command]
fn download_expense_import_template(save_path: String) -> Result<(), String> {
    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    let example_rows: [(&str, &str, &str, &str, f64, &str, &str); 2] = [
        ("设备费", "设备A采购", "型号X", "供应商A", 10000.0, today.as_str(), "示例数据1"),
        ("材料费", "材料B采购", "型号Y", "供应商B", 5000.0, "", "示例数据2"),
    ];
    excel::generate_expense_import_template(std::path::Path::new(&save_path), &example_rows)
        .map_err(|e| format!("生成导入模板失败: {e}"))
}

/// 解析并校验支出批量导入文件。
/// 返回结构化支出列表，类别为中文 label、日期为 YYYY-MM-DD。
/// 任一校验失败即返回错误（首个错误信息）。
#[tauri::command]
fn parse_expenses_import(file_path: String) -> Result<Vec<ParsedExpense>, String> {
    excel::parse_expenses_from_xlsx(std::path::Path::new(&file_path))
        .map_err(|e| format!("解析导入文件失败: {e}"))
}

/// 批量导入支出（事务）：对解析校验通过的支出列表逐条插入，
/// 联动预算（budgets/budget_items.spent_amount += amount/10000），
/// 每条写"批量导入"操作日志。返回导入条数。
#[tauri::command]
fn batch_add_expenses(
    state: State<'_, DbState>,
    project_id: i64,
    budget_id: i64,
    items: Vec<ParsedExpense>,
) -> Result<usize, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    expense::batch_add_expenses(&conn, project_id, budget_id, &items)
        .map_err(|e| format!("批量导入支出失败: {e}"))
}

/// 导出预算数据到 xlsx：预算明细 + 预算汇总（支持分年度比例/平均分配、万元换算）。
#[tauri::command]
fn export_budget_data(
    save_path: String,
    data: BudgetExportData,
    config: BudgetExportConfig,
) -> Result<(), String> {
    excel::export_budget_data(std::path::Path::new(&save_path), &data, &config)
        .map_err(|e| format!("导出预算失败: {e}"))
}

// ─────────────────────────── 预算编制 ───────────────────────────

/// 列出全部预算计划树（计划 → 10 个类别占位节点 → 条目叶子；类别为中文 label）。
#[tauri::command]
fn list_budget_plans(
    state: State<'_, DbState>,
) -> Result<Vec<BudgetPlanNode>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget_plan::list_budget_plans(&conn).map_err(|e| format!("加载预算编制失败: {e}"))
}

/// 保存全部顶层预算计划：按 name 查找或创建计划，
/// 类别占位行 upsert + 删除旧子项 + 重插新子项，单事务；不写 actionlogs。
#[tauri::command]
fn save_budget_plans(
    state: State<'_, DbState>,
    plans: Vec<BudgetPlanSave>,
) -> Result<(), String> {
    let mut conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget_plan::save_budget_plans(&mut conn, &plans)
        .map_err(|e| format!("保存预算编制失败: {e}"))
}

/// 删除整个预算计划（按 name 级联删除）。
#[tauri::command]
fn delete_budget_plan(state: State<'_, DbState>, name: String) -> Result<(), String> {
    let mut conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget_plan::delete_budget_plan(&mut conn, &name)
        .map_err(|e| format!("删除预算计划失败: {e}"))
}

/// 删除一条预算条目（按 计划名 + 类别(中文) + 条目名 精确匹配删除）。
#[tauri::command]
fn delete_budget_plan_item(
    state: State<'_, DbState>,
    plan_name: String,
    category_label: String,
    item_name: String,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    budget_plan::delete_budget_plan_item(&conn, &plan_name, &category_label, &item_name)
        .map_err(|e| format!("删除预算条目失败: {e}"))
}

/// 加载某项目的甘特图数据
#[tauri::command]
fn load_gantt_data(
    state: State<'_, DbState>,
    project_id: i64,
) -> Result<gantt::GanttProjectData, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    gantt::load_gantt_data(&conn, project_id).map_err(|e| format!("加载甘特图失败: {e}"))
}

/// 保存甘特图数据（整单事务）
/// 返回新任务临时 id → 持久化 gantt_id 的映射
#[tauri::command]
fn save_gantt_data(
    state: State<'_, DbState>,
    project_id: i64,
    data: GanttProjectData,
) -> Result<std::collections::HashMap<String, String>, String> {
    let mut conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    gantt::save_gantt_data(&mut conn, project_id, &data)
        .map_err(|e| format!("保存甘特图失败: {e}"))
}

/// 清理某项目下全部甘特数据（删除项目级联时调用）
#[tauri::command]
fn clear_project_gantt(state: State<'_, DbState>, project_id: i64) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    gantt::clear_project_gantt(&conn, project_id)
        .map_err(|e| format!("清理甘特图失败: {e}"))
}

/// 导出甘特图数据为文件：
/// 按 `save_path` 扩展名输出 XLSX / JSON / CSV / TXT
#[tauri::command]
fn export_gantt(save_path: String, data: GanttProjectData) -> Result<(), String> {
    gantt::export_gantt_file(std::path::Path::new(&save_path), &data)
        .map_err(|e| format!("导出甘特图失败: {e}"))
}

// ─────────────────────────── 项目文档 ───────────────────────────

/// 列出项目文档：
/// - `project_id` 为 Some 时只列该项目；为 None 时列全部（「全部文档」模式）。
/// `upload_time` 按 DESC 排序；`doc_type` 已转换为中文 label。
#[tauri::command]
fn list_project_documents(
    state: State<'_, DbState>,
    project_id: Option<i64>,
) -> Result<Vec<ProjectDocument>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let docs = match project_id {
        Some(pid) => document::list_documents_by_project(&conn, pid),
        None => document::list_all_documents(&conn),
    };
    docs.map_err(|e| format!("查询项目文档失败: {e}"))
}

/// 按 id 查文档（编辑回填用）。不存在返回 null。
#[tauri::command]
fn get_document(state: State<'_, DbState>, id: i64) -> Result<Option<ProjectDocument>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    document::get_document_by_id(&conn, id).map_err(|e| format!("查询文档失败: {e}"))
}

/// 新增文档：INSERT + 写「新增」actionlog
#[tauri::command]
fn add_document(state: State<'_, DbState>, input: DocumentInput) -> Result<i64, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    document::add_document(&conn, input).map_err(|e| format!("新增文档失败: {e}"))
}

/// 更新文档：UPDATE + 写「编辑」actionlog（不改附件路径）。
#[tauri::command]
fn update_document(state: State<'_, DbState>, id: i64, input: DocumentInput) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    document::update_document(&conn, id, input).map_err(|e| format!("更新文档失败: {e}"))
}

/// 批量删除文档：先删库（事务回填 actionlog），再清理磁盘附件
/// （文件删除失败不致命，仅记录）。
#[tauri::command]
fn delete_documents(state: State<'_, DbState>, ids: Vec<i64>) -> Result<(), String> {
    let paths = {
        let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
        document::delete_documents(&conn, &ids).map_err(|e| format!("删除文档失败: {e}"))?
    };
    for p in paths.iter().flatten() {
        let _ = attachments::delete_attachment(std::path::Path::new(p));
    }
    Ok(())
}

/// 仅更新文档附件路径（附件上传替换/删除后写库；对齐 `update_expense_voucher`）。
#[tauri::command]
fn update_document_file_path(
    state: State<'_, DbState>,
    id: i64,
    file_path: Option<String>,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    document::update_document_file_path(&conn, id, file_path)
        .map_err(|e| format!("更新附件路径失败: {e}"))
}

/// 导出文档列表到 xlsx：
/// 7 列 = 文档名称 | 文档类型 | 版本号 | 关键词 | 上传时间 | 文档描述 | 文件路径。
/// `project_id` 为 None 时导出全部文档。
#[tauri::command]
fn export_documents_excel(
    state: State<'_, DbState>,
    save_path: String,
    project_id: Option<i64>,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let docs = match project_id {
        Some(pid) => document::list_documents_by_project(&conn, pid),
        None => document::list_all_documents(&conn),
    }
    .map_err(|e| format!("查询文档失败: {e}"))?;
    excel::export_documents_to_xlsx(std::path::Path::new(&save_path), &docs)
        .map_err(|e| format!("导出 Excel 失败: {e}"))
}

// ─────────────────────────── 项目成果 ───────────────────────────

/// 列出项目成果：
/// - `project_id` 为 Some 时只列该项目；为 None 时列全部（「全部成果」模式）。
/// `publish_date` 按 DESC 排序；`type` / `status` 已转换为中文 label。
#[tauri::command]
fn list_project_outcomes(
    state: State<'_, DbState>,
    project_id: Option<i64>,
) -> Result<Vec<ProjectOutcome>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let outcomes = match project_id {
        Some(pid) => outcome::list_outcomes_by_project(&conn, pid),
        None => outcome::list_all_outcomes(&conn),
    };
    outcomes.map_err(|e| format!("查询项目成果失败: {e}"))
}

/// 按 id 查成果（编辑回填用）。不存在返回 null。
#[tauri::command]
fn get_outcome(state: State<'_, DbState>, id: i64) -> Result<Option<ProjectOutcome>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    outcome::get_outcome_by_id(&conn, id).map_err(|e| format!("查询成果失败: {e}"))
}

/// 新增成果：INSERT + 写「新增」actionlog
#[tauri::command]
fn add_outcome(state: State<'_, DbState>, input: OutcomeInput) -> Result<i64, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    outcome::add_outcome(&conn, input).map_err(|e| format!("新增成果失败: {e}"))
}

/// 更新成果：UPDATE + 写「编辑」actionlog（不改附件路径）。
#[tauri::command]
fn update_outcome(state: State<'_, DbState>, id: i64, input: OutcomeInput) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    outcome::update_outcome(&conn, id, input).map_err(|e| format!("更新成果失败: {e}"))
}

/// 批量删除成果：先删库（事务回填 actionlog），再清理磁盘附件
/// （文件删除失败不致命，仅记录）。
#[tauri::command]
fn delete_outcomes(state: State<'_, DbState>, ids: Vec<i64>) -> Result<(), String> {
    let paths = {
        let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
        outcome::delete_outcomes(&conn, &ids).map_err(|e| format!("删除成果失败: {e}"))?
    };
    for p in paths.iter().flatten() {
        let _ = attachments::delete_attachment(std::path::Path::new(p));
    }
    Ok(())
}

/// 仅更新成果附件路径（附件上传替换/删除后写库；对齐 `update_expense_voucher`）。
#[tauri::command]
fn update_outcome_attachment_path(
    state: State<'_, DbState>,
    id: i64,
    attachment_path: Option<String>,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    outcome::update_outcome_attachment_path(&conn, id, attachment_path)
        .map_err(|e| format!("更新附件路径失败: {e}"))
}

/// 导出成果列表到 xlsx：
/// 9 列 = 成果名称 | 成果类型 | 成果状态 | 作者/完成人 | 投稿/申请日期 |
/// 发表/授权日期 | 期刊/授权单位 | 成果描述 | 附件路径。
/// `project_id` 为 None 时导出全部成果。
#[tauri::command]
fn export_outcomes_excel(
    state: State<'_, DbState>,
    save_path: String,
    project_id: Option<i64>,
) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let outcomes = match project_id {
        Some(pid) => outcome::list_outcomes_by_project(&conn, pid),
        None => outcome::list_all_outcomes(&conn),
    }
    .map_err(|e| format!("查询成果失败: {e}"))?;
    excel::export_outcomes_to_xlsx(std::path::Path::new(&save_path), &outcomes)
        .map_err(|e| format!("导出 Excel 失败: {e}"))
}

// ─────────────────────────── 学术活动 ───────────────────────────

/// 列出全部学术活动（全局表，无项目维度，按 start_date DESC 排序；type / status 已转换为中文 label）。
#[tauri::command]
fn list_activities(state: State<'_, DbState>) -> Result<Vec<AcademicActivity>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    activity::list_activities(&conn).map_err(|e| format!("查询学术活动失败: {e}"))
}

/// 按 id 查活动（编辑回填用）。不存在返回 null。
#[tauri::command]
fn get_activity(
    state: State<'_, DbState>,
    id: i64,
) -> Result<Option<AcademicActivity>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    activity::get_activity_by_id(&conn, id).map_err(|e| format!("查询学术活动失败: {e}"))
}

/// 新增活动（不写 actionlogs）。
#[tauri::command]
fn add_activity(state: State<'_, DbState>, input: ActivityInput) -> Result<i64, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    activity::add_activity(&conn, input).map_err(|e| format!("新增学术活动失败: {e}"))
}

/// 更新活动（可一并改写 attachment_path，
/// add/replace/delete 均由对话框状态决定后传入；不写 actionlogs）。
#[tauri::command]
fn update_activity(state: State<'_, DbState>, id: i64, input: ActivityInput) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    activity::update_activity(&conn, id, input).map_err(|e| format!("更新学术活动失败: {e}"))
}

/// 批量删除活动：先删库，再清理磁盘附件（文件删除失败不致命）。
#[tauri::command]
fn delete_activities(state: State<'_, DbState>, ids: Vec<i64>) -> Result<(), String> {
    let paths = {
        let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
        activity::delete_activities(&conn, &ids).map_err(|e| format!("删除学术活动失败: {e}"))?
    };
    for p in paths.iter().flatten() {
        let _ = attachments::delete_attachment(std::path::Path::new(p));
    }
    Ok(())
}

/// 导出活动列表到 xlsx：
/// 9 列 = 活动名称 | 活动类型 | 活动状态 | 主办方 | 开始日期 | 结束日期 |
/// 活动地点 | 参与人员 | 活动描述（不含附件列）。导出全部活动。
#[tauri::command]
fn export_activities_excel(state: State<'_, DbState>, save_path: String) -> Result<(), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let activities = activity::list_activities(&conn).map_err(|e| format!("查询学术活动失败: {e}"))?;
    excel::export_activities_to_xlsx(std::path::Path::new(&save_path), &activities)
        .map_err(|e| format!("导出 Excel 失败: {e}"))
}

// ─────────────────────────── 小工具 ───────────────────────────

/// 间接经费计算。
/// 费率以小数传入（如 20% 传 0.20），返回最大间接经费（万元）。
#[tauri::command]
fn calculate_indirect_cost(
    total_funds: f64,
    equipment_cost: f64,
    external_cooperation_cost: f64,
    rate1: f64,
    rate2: f64,
    rate3: f64,
) -> f64 {
    indirect_cost::calculate_max_indirect_cost(
        total_funds,
        equipment_cost,
        external_cooperation_cost,
        rate1,
        rate2,
        rate3,
    )
}

/// 导出树形列表到 json/csv/xlsx（含层级合并单元格的 Excel 导出）。
/// `roots` 为顶层节点。
#[tauri::command]
fn export_tree_list(
    save_path: String,
    roots: Vec<TreeListNode>,
    format: String,
) -> Result<(), String> {
    tree_list::export_tree_list(std::path::Path::new(&save_path), &roots, &format)
        .map_err(|e| format!("导出失败: {e}"))
}

/// 从 JSON 文件导入树形列表（只取顶层 children 递归构建）。
#[tauri::command]
fn import_tree_list(file_path: String) -> Result<Vec<TreeListNode>, String> {
    tree_list::parse_tree_list_json(std::path::Path::new(&file_path))
        .map_err(|e| format!("导入失败: {e}"))
}

/// 操作日志列表（按时间倒序，最多 limit 条，默认 100）。
#[tauri::command]
fn list_actionlogs(
    state: State<'_, DbState>,
    limit: Option<i64>,
) -> Result<Vec<Actionlog>, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let limit = limit.unwrap_or(100).clamp(1, 100);
    logging::list_actionlogs(&conn, limit).map_err(|e| format!("查询操作日志失败: {e}"))
}

/// 操作日志条件查询：返回 (当页行, 匹配总数)。
#[tauri::command]
fn query_action_logs(
    state: State<'_, DbState>,
    log_type: Option<String>,
    action: Option<String>,
    keyword: Option<String>,
    start: Option<String>,
    end: Option<String>,
    limit: Option<i64>,
    offset: Option<i64>,
) -> Result<(Vec<Actionlog>, i64), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    let q = logging::LogQuery { log_type, action, keyword, start, end };
    logging::query_actionlogs(
        &conn,
        &q,
        limit.unwrap_or(200).clamp(1, 500),
        offset.unwrap_or(0).max(0),
    )
    .map_err(|e| format!("查询操作日志失败: {e}"))
}

/// 操作日志筛选选项（类型、动作的去重列表）。
#[tauri::command]
fn action_log_facets(state: State<'_, DbState>) -> Result<(Vec<String>, Vec<String>), String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    logging::actionlog_facets(&conn).map_err(|e| format!("查询日志筛选项失败: {e}"))
}

/// 清理 keep_days 天之前的操作日志，返回删除条数。
#[tauri::command]
fn prune_action_logs(state: State<'_, DbState>, keep_days: i64) -> Result<usize, String> {
    let conn = state.conn.lock().map_err(|e| format!("数据库锁失败: {e}"))?;
    logging::prune_actionlogs(&conn, keep_days.max(0))
        .map_err(|e| format!("清理操作日志失败: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let database_path = resolve_startup_db_path();

    // 确保数据库目录存在
    if let Some(dir) = database_path.parent() {
        if let Err(e) = std::fs::create_dir_all(dir) {
            eprintln!("创建数据库目录失败 {}: {e}", dir.display());
        }
    }

    // 首次迁移：本地数据库不存在时，从旧位置（项目根云盘 database.db）复制
    if !database_path.exists() {
        let legacy = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("database")
            .join("database.db");
        if legacy.exists() {
            eprintln!(
                "首次启动：从 {} 复制数据库到 {}",
                legacy.display(),
                database_path.display()
            );
            if let Err(e) = std::fs::copy(&legacy, &database_path) {
                eprintln!("数据库迁移失败（将使用空库启动）: {e}");
            }
        }
    }

    // 打开 + 补建缺失表 + 列级迁移
    let mut conn = db::open(&database_path).expect("打开数据库失败");
    db::init_db(&mut conn).expect("init_db（补建缺失表）失败");
    db::migrate::migrate_db(&mut conn).expect("migrate_db 失败");

    tauri::Builder::default()
        // 显式设置窗口图标（任务栏/标题栏图标）。
        // dev 模式不读取 bundle 图标，需在此注入；macOS Dock 图标仍由打包的 .icns 决定。
        .setup(|app| {
            let icon = tauri::image::Image::from_bytes(include_bytes!("../icons/icon.png"))
                .expect("加载窗口图标失败");
            for window in app.webview_windows().values() {
                window.set_icon(icon.clone())?;
            }
            Ok(())
        })
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .manage(DbState {
            conn: Mutex::new(conn),
            path: Mutex::new(database_path),
        })
        .invoke_handler(tauri::generate_handler![
            ping,
            db_path,
            open_database,
            reset_database,
            home_overview,
            list_projects,
            add_project,
            update_project,
            delete_project,
            export_project_data,
            import_project_data,
            generate_attachment_path,
            save_attachment,
            delete_attachment,
            check_attachments,
            list_project_budgets,
            add_annual_budget,
            get_annual_budget,
            update_annual_budget,
            get_total_budget,
            update_total_budget,
            delete_annual_budget,
            delete_total_budget,
            list_expenses,
            list_project_expenses_by_category,
            rebuild_expense_stats,
            get_expense,
            add_expense,
            update_expense,
            delete_expenses,
            update_expense_voucher,
            copy_attachment_file,
            export_expenses_excel,
            download_expense_import_template,
            parse_expenses_import,
            batch_add_expenses,
            export_budget_data,
            list_budget_plans,
            save_budget_plans,
            delete_budget_plan,
            delete_budget_plan_item,
            load_gantt_data,
            save_gantt_data,
            clear_project_gantt,
            export_gantt,
            list_project_documents,
            get_document,
            add_document,
            update_document,
            delete_documents,
            update_document_file_path,
            export_documents_excel,
            list_project_outcomes,
            get_outcome,
            add_outcome,
            update_outcome,
            delete_outcomes,
            update_outcome_attachment_path,
            export_outcomes_excel,
            list_activities,
            get_activity,
            add_activity,
            update_activity,
            delete_activities,
            export_activities_excel,
            list_actionlogs,
            query_action_logs,
            action_log_facets,
            prune_action_logs,
            calculate_indirect_cost,
            export_tree_list,
            import_tree_list
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
