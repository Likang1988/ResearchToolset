//! 预算服务：预算使用统计、项目创建（对应 database.py 的
//! `get_budget_usage` / `add_project_to_db`）

use rusqlite::{params, Connection, OptionalExtension};

use crate::models::BudgetCategory;
use crate::DbError;

/// 某科目支出金额
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CategorySpend {
    /// 费用类别（中文，与 BudgetCategory 一致）
    pub category: String,
    /// 该科目支出合计
    pub spent: f64,
}

/// 预算使用情况（对应 Python `get_budget_usage` 返回值）
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct BudgetUsage {
    pub total_budget: f64,
    pub total_spent: f64,
    pub remaining: f64,
    /// 按 10 类固定顺序排列的科目支出
    pub category_spent: Vec<CategorySpend>,
}

/// get_budget_usage 等价物：统计项目预算使用情况
///
/// 语义与 Python 版一致：
/// - 无总预算记录时返回全 0 结构
/// - total_spent = 该项目全部支出之和（与预算无关）
/// - category_spent 按 BudgetCategory 的 10 类逐一查询
pub fn get_budget_usage(conn: &Connection, project_id: i64) -> Result<BudgetUsage, DbError> {
    let empty = || BudgetUsage {
        total_budget: 0.0,
        total_spent: 0.0,
        remaining: 0.0,
        category_spent: BudgetCategory::ALL
            .iter()
            .map(|c| CategorySpend {
                category: c.label().to_string(),
                spent: 0.0,
            })
            .collect(),
    };

    // 查询总预算（year IS NULL）
    let total_budget: Option<f64> = conn
        .query_row(
            "SELECT total_amount FROM budgets WHERE project_id = ?1 AND year IS NULL",
            [project_id],
            |r| r.get(0),
        )
        .optional()?;

    let Some(total_budget) = total_budget else {
        return Ok(empty());
    };

    // 总支出
    let total_spent: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE project_id = ?1",
        [project_id],
        |r| r.get(0),
    )?;

    // 各科目支出（10 类逐一查询，与 Python 一致）
    // DB 存储的是英文 KEY（EQUIPMENT/...），WHERE 条件用 storage_key；
    // 返回结构体用中文 label 给前端展示
    let mut category_spent = Vec::with_capacity(10);
    for category in BudgetCategory::ALL {
        let spent: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE project_id = ?1 AND category = ?2",
            params![project_id, category.storage_key()],
            |r| r.get(0),
        )?;
        category_spent.push(CategorySpend {
            category: category.label().to_string(),
            spent,
        });
    }

    Ok(BudgetUsage {
        total_budget,
        total_spent,
        remaining: total_budget - total_spent,
        category_spent,
    })
}

// ===== 项目经费页：三级预算树（对应 project_fund.py::load_budgets） =====

/// 单个预算科目节点（树叶子）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetItemNode {
    pub category: String,
    pub amount: f64,
    pub spent_amount: f64,
}

/// 单个预算节点（总预算或某年度预算，含 10 个科目子项）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetNode {
    pub id: i64,
    /// None = 总预算；Some(year) = 年度预算
    pub year: Option<i64>,
    pub total_amount: f64,
    /// 支出额。总预算节点填「所有年度预算 spent_amount 之和」，
    /// 年度预算节点填自身 spent_amount（与 Python load_budgets 一致）。
    pub spent_amount: f64,
    pub items: Vec<BudgetItemNode>,
}

/// 项目预算树：一个总预算 + 若干年度预算（按 id 升序）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetTree {
    pub total_budget: Option<BudgetNode>,
    pub annual_budgets: Vec<BudgetNode>,
}

/// 列出项目的预算树（三级结构），对齐 Python `load_budgets` 的查询与汇总语义：
///
/// - 总预算节点的 spent_amount = 所有年度预算 spent_amount 之和
/// - 总预算每个科目子项的 spent_amount = 该科目在所有年度预算中的 spent_amount 之和
/// - 年度预算节点及其子项的 spent_amount = 自身字段（budgets.spent_amount / budget_items.spent_amount）
///
/// 若无总预算记录返回 `total_budget=None`（前端可据此提示「请先设置总预算」）。
pub fn list_project_budgets(conn: &Connection, project_id: i64) -> Result<BudgetTree, DbError> {
    // ---- 总预算 ----
    let total_row: Option<(i64, f64)> = conn
        .query_row(
            "SELECT id, total_amount FROM budgets WHERE project_id = ?1 AND year IS NULL",
            [project_id],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .optional()?;

    let total_budget = match total_row {
        Some((tb_id, tb_amount)) => {
            // 所有年度预算 spent_amount 之和（对应 Python total_spent）
            let total_spent: f64 = conn.query_row(
                "SELECT COALESCE(SUM(spent_amount), 0) FROM budgets \
                 WHERE project_id = ?1 AND year IS NOT NULL",
                [project_id],
                |r| r.get(0),
            )?;

            // 总预算自身的科目子项（amount 字段）
            let mut stmt = conn.prepare(
                "SELECT category, amount FROM budget_items WHERE budget_id = ?1",
            )?;
            let total_items: Vec<(String, f64)> = stmt
                .query_map([tb_id], |r| Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?)))?
                .collect::<Result<Vec<_>, _>>()?;

            // 每个科目在所有年度预算中的 spent_amount 之和
            // 注意：DB 存储 budget_items.category 为英文 KEY（EQUIPMENT/...），
            // WHERE 条件用 storage_key()，HashMap 的 key 也用 storage_key
            let mut category_spent_map = std::collections::HashMap::new();
            for category in BudgetCategory::ALL {
                let spent: f64 = conn.query_row(
                    "SELECT COALESCE(SUM(bi.spent_amount), 0) FROM budget_items bi \
                     JOIN budgets b ON bi.budget_id = b.id \
                     WHERE b.project_id = ?1 AND b.year IS NOT NULL AND bi.category = ?2",
                    params![project_id, category.storage_key()],
                    |r| r.get(0),
                )?;
                category_spent_map.insert(category.storage_key().to_string(), spent);
            }

            // 按 BudgetCategory 固定顺序组装 10 个子项：
            // - 从 DB 读出的 total_items / category_spent_map key 是英文 KEY
            // - BudgetItemNode.category 用中文 label 给前端展示
            let items = BudgetCategory::ALL
                .iter()
                .map(|c| {
                    let amount = total_items
                        .iter()
                        .find(|(cat, _)| cat == c.storage_key())
                        .map(|(_, a)| *a)
                        .unwrap_or(0.0);
                    let spent = category_spent_map
                        .get(c.storage_key())
                        .copied()
                        .unwrap_or(0.0);
                    BudgetItemNode {
                        category: c.label().to_string(),
                        amount,
                        spent_amount: spent,
                    }
                })
                .collect();

            Some(BudgetNode {
                id: tb_id,
                year: None,
                total_amount: tb_amount,
                spent_amount: total_spent,
                items,
            })
        }
        None => None,
    };

    // ---- 年度预算（按 id 升序，与 Python ORDER BY id ASC 一致）----
    let mut stmt = conn.prepare(
        "SELECT id, year, total_amount, spent_amount FROM budgets \
         WHERE project_id = ?1 AND year IS NOT NULL ORDER BY id ASC",
    )?;
    let annual_rows: Vec<(i64, i64, f64, f64)> = stmt
        .query_map([project_id], |r| {
            Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?))
        })?
        .collect::<Result<Vec<_>, _>>()?;

    let mut annual_budgets = Vec::with_capacity(annual_rows.len());
    for (b_id, year, amount, spent) in annual_rows {
        // 该年度预算自身的科目子项
        let mut item_stmt = conn.prepare(
            "SELECT category, amount, spent_amount FROM budget_items WHERE budget_id = ?1",
        )?;
        let row_items: Vec<(String, f64, f64)> = item_stmt
            .query_map([b_id], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, f64>(1)?,
                    r.get::<_, f64>(2)?,
                ))
            })?
            .collect::<Result<Vec<_>, _>>()?;

        // 年度预算自身的子项：DB key 是英文 storage_key，展示用中文 label
        let items = BudgetCategory::ALL
            .iter()
            .map(|c| {
                let (amount, spent) = row_items
                    .iter()
                    .find(|(cat, _, _)| cat == c.storage_key())
                    .map(|(_, a, s)| (*a, *s))
                    .unwrap_or((0.0, 0.0));
                BudgetItemNode {
                    category: c.label().to_string(),
                    amount,
                    spent_amount: spent,
                }
            })
            .collect();

        annual_budgets.push(BudgetNode {
            id: b_id,
            year: Some(year),
            total_amount: amount,
            spent_amount: spent,
            items,
        });
    }

    Ok(BudgetTree {
        total_budget,
        annual_budgets,
    })
}

// ===== 新增年度预算（对应 project_fund.py::add_budget 的数据库部分） =====

/// 单个科目金额输入
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BudgetItemInput {
    pub category: String,
    pub amount: f64,
}

/// 新增年度预算的输入
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AnnualBudgetInput {
    pub project_id: i64,
    pub year: i64,
    pub total_amount: f64,
    pub items: Vec<BudgetItemInput>, // 应含 10 个科目
}

/// 新增年度预算：创建 budgets 记录 + 10 个 budget_items 子项
///
/// 对齐 Python `add_budget` 的数据库写入部分：
/// - 查重：若 (project_id, year) 已存在，返回错误
/// - 事务内创建 budgets（spent_amount=0）+ 10 个 budget_items（spent_amount=0）
/// - 写"新增"操作日志（type=预算, action=新增，关联 budget_id）；
///   预算编辑/删除同样写日志（对齐 Python project_fund.py 各处 Actionlog）
///
/// 注：Python 在写入前还有「总预算是否设置」「超出剩余金额」等校验，
/// 这些放在前端对话框层处理；此处只做核心查重与写入。
pub fn add_annual_budget(conn: &Connection, input: AnnualBudgetInput) -> Result<i64, DbError> {
    crate::db::begin_tx(conn)?;
    let result = add_annual_budget_inner(conn, input);
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

fn add_annual_budget_inner(conn: &Connection, input: AnnualBudgetInput) -> Result<i64, DbError> {
    // 查重：(project_id, year) 是否已存在
    let exists: i64 = conn.query_row(
        "SELECT COUNT(*) FROM budgets WHERE project_id = ?1 AND year = ?2",
        params![input.project_id, input.year],
        |r| r.get(0),
    )?;
    if exists > 0 {
        return Err(DbError::Other(format!(
            "{}年度的预算已存在，请勿重复添加",
            input.year
        )));
    }

    // 创建 budgets 记录
    conn.execute(
        "INSERT INTO budgets (project_id, year, total_amount, spent_amount) \
         VALUES (?1, ?2, ?3, 0)",
        params![input.project_id, input.year, input.total_amount],
    )?;
    let budget_id = conn.last_insert_rowid();

    // 创建 10 个 budget_items（spent_amount 初始 0）。
    // BudgetItemInput.category 来自前端是中文 label（"设备费"/…），
    // 存库需转成英文 storage_key（EQUIPMENT/…）。
    for item in &input.items {
        let storage_key = BudgetCategory::from_label(&item.category)
            .map(|c| c.storage_key().to_string())
            .unwrap_or_else(|| item.category.clone()); // 兜底：不识别则原样（应不会发生）
        conn.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) \
             VALUES (?1, ?2, ?3, 0)",
            params![budget_id, storage_key, item.amount],
        )?;
    }

    // 写"新增"操作日志（对齐 Python add_budget 的 Actionlog）
    crate::logging::log_action(
        conn,
        Some(input.project_id),
        Some(budget_id),
        None,
        None,
        None,
        None,
        "预算",
        "新增",
        &format!("添加了 {} 年度预算", input.year),
        "系统用户",
        None,
        None,
        None,
        None,
        None,
    )?;

    Ok(budget_id)
}

// ===== 编辑年度预算 =====

/// 编辑年度预算的返回结构（前端回填用：year + 10 科目金额）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AnnualBudgetDetail {
    pub id: i64,
    pub project_id: i64,
    pub year: i64,
    pub total_amount: f64,
    pub items: Vec<BudgetItemInput>,
}

/// 按 id 查询年度预算详情（含 10 科目子项，按 BudgetCategory 固定顺序）。
/// 仅返回 year IS NOT NULL 的年度预算；若 id 不存在或为总预算节点返回 None。
pub fn get_annual_budget_by_id(
    conn: &Connection,
    id: i64,
) -> Result<Option<AnnualBudgetDetail>, DbError> {
    let row: Option<(i64, i64, f64)> = conn
        .query_row(
            "SELECT project_id, year, total_amount FROM budgets \
             WHERE id = ?1 AND year IS NOT NULL",
            [id],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
        )
        .optional()?;
    let (project_id, year, total_amount) = match row {
        Some(r) => r,
        None => return Ok(None),
    };

    let mut stmt = conn.prepare(
        "SELECT category, amount FROM budget_items WHERE budget_id = ?1",
    )?;
    let rows: std::collections::HashMap<String, f64> = stmt
        .query_map([id], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, f64>(1).unwrap_or(0.0),
            ))
        })?
        .collect::<Result<_, _>>()?;

    // 从 DB 读出的 key 是英文 storage_key，回填给前端时用中文 label
    let items = BudgetCategory::ALL
        .iter()
        .map(|c| BudgetItemInput {
            category: c.label().to_string(),
            amount: rows.get(c.storage_key()).copied().unwrap_or(0.0),
        })
        .collect();

    Ok(Some(AnnualBudgetDetail {
        id,
        project_id,
        year,
        total_amount,
        items,
    }))
}

/// 更新年度预算：改 budgets.total_amount，并按类别覆盖 10 个 budget_items.amount
///
/// 对齐 Python BudgetDialog：
/// - 年度字段不可改（避免破坏与已有支出/甘特等的关联）
/// - 子项 spent_amount 不变（保留已有支出数据）
/// - 事务：先 UPDATE budgets，再逐类别 UPSERT budget_items（存在则改金额，不存在则补一条）
pub fn update_annual_budget(
    conn: &Connection,
    id: i64,
    total_amount: f64,
    items: &[BudgetItemInput],
) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = update_annual_budget_inner(conn, id, total_amount, items);
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

fn update_annual_budget_inner(
    conn: &Connection,
    id: i64,
    total_amount: f64,
    items: &[BudgetItemInput],
) -> Result<(), DbError> {
    // 校验 id 确为年度预算（不是总预算）
    let exists: i64 = conn.query_row(
        "SELECT COUNT(*) FROM budgets WHERE id = ?1 AND year IS NOT NULL",
        [id],
        |r| r.get(0),
    )?;
    if exists == 0 {
        return Err(DbError::Other(format!(
            "年度预算 id={id} 不存在或不是年度预算"
        )));
    }

    // 提取旧值用于"编辑"操作日志（对齐 Python update_budget 的 old_data/new_data）
    let (project_id, year, old_amount) = conn.query_row(
        "SELECT project_id, year, total_amount FROM budgets WHERE id = ?1",
        [id],
        |r| Ok((r.get::<_, i64>(0)?, r.get::<_, i64>(1)?, r.get::<_, f64>(2)?)),
    )?;
    // rusqlite 的 Option<String> 会把 NULL 解成 None（避免 financial_code 为空时报 InvalidColumnType）
    let financial_code: Option<String> = conn.query_row(
        "SELECT p.financial_code FROM projects p JOIN budgets b ON b.project_id = p.id \
         WHERE b.id = ?1",
        [id],
        |r| r.get(0),
    )?;

    // 更新 budgets.total_amount
    conn.execute(
        "UPDATE budgets SET total_amount = ?1 WHERE id = ?2",
        params![total_amount, id],
    )?;

    // 先查当前每类的 spent_amount（避免删除后丢失已有支出数据）。
    // key = 英文 storage_key（因为 DB 存的是英文）。
    let spent_map: std::collections::HashMap<String, f64> = conn
        .prepare("SELECT category, COALESCE(spent_amount, 0) FROM budget_items WHERE budget_id = ?1")
        .map_err(|e| DbError::Sqlite(e))?
        .query_map([id], |r| {
            Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?))
        })?
        .collect::<Result<_, _>>()?;

    // 先 DELETE 该预算的所有旧 budget_items，再 INSERT 10 个新的（保证 10 类齐全）。
    // 原表无 (budget_id, category) 唯一索引，因此不能用 UPSERT。
    conn.execute("DELETE FROM budget_items WHERE budget_id = ?1", [id])?;
    for item in items {
        // BudgetItemInput.category 是前端传入的中文 label
        let cat = BudgetCategory::from_label(&item.category);
        let storage_key = cat
            .map(|c| c.storage_key().to_string())
            .unwrap_or_else(|| item.category.clone());
        let spent = spent_map.get(&storage_key).copied().unwrap_or(0.0);
        conn.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) \
             VALUES (?1, ?2, ?3, ?4)",
            params![id, storage_key, item.amount, spent],
        )?;
    }

    // 写"编辑"操作日志（对齐 Python 编辑年度预算的 Actionlog）
    crate::logging::log_action(
        conn,
        Some(project_id),
        Some(id),
        None,
        None,
        None,
        None,
        "预算",
        "编辑",
        &format!(
            "编辑了项目 {} 的 {} 年度预算",
            financial_code.as_deref().unwrap_or(""),
            year
        ),
        "系统用户",
        Some(&format!("年度: {year}, 预算额: {old_amount}")),
        Some(&format!("年度: {year}, 预算额: {total_amount}")),
        None,
        None,
        None,
    )?;
    Ok(())
}

// ===== 编辑总预算 =====

/// 总预算详情（前端回填用：仅 10 科目金额，无年度字段）
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TotalBudgetDetail {
    pub id: i64,
    pub project_id: i64,
    pub total_amount: f64,
    pub items: Vec<BudgetItemInput>,
}

/// 按 id 查询总预算详情（含 10 科目子项，按 BudgetCategory 固定顺序）。
/// 仅返回 year IS NULL 的总预算；若 id 不存在或为年度预算返回 None。
pub fn get_total_budget_by_id(
    conn: &Connection,
    id: i64,
) -> Result<Option<TotalBudgetDetail>, DbError> {
    let row: Option<(i64, f64)> = conn
        .query_row(
            "SELECT project_id, total_amount FROM budgets \
             WHERE id = ?1 AND year IS NULL",
            [id],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .optional()?;
    let (project_id, total_amount) = match row {
        Some(r) => r,
        None => return Ok(None),
    };

    let mut stmt = conn.prepare(
        "SELECT category, amount FROM budget_items WHERE budget_id = ?1",
    )?;
    let rows: std::collections::HashMap<String, f64> = stmt
        .query_map([id], |r| {
            Ok((
                r.get::<_, String>(0)?,
                r.get::<_, f64>(1).unwrap_or(0.0),
            ))
        })?
        .collect::<Result<_, _>>()?;

    // 从 DB 读出的 key 是英文 storage_key，回填给前端时用中文 label
    let items = BudgetCategory::ALL
        .iter()
        .map(|c| BudgetItemInput {
            category: c.label().to_string(),
            amount: rows.get(c.storage_key()).copied().unwrap_or(0.0),
        })
        .collect();

    Ok(Some(TotalBudgetDetail {
        id,
        project_id,
        total_amount,
        items,
    }))
}

/// 更新总预算：改 budgets.total_amount + 10 科目 amount（保留 spent_amount）
///
/// 对齐 Python `TotalBudgetDialog.get_data`：
/// - 校验 id 确为总预算（year IS NULL）
/// - 事务：先 UPDATE budgets，再 DELETE+INSERT 10 个 budget_items
///   （保留旧 spent_amount，模式同 update_annual_budget_inner）
pub fn update_total_budget(
    conn: &Connection,
    id: i64,
    total_amount: f64,
    items: &[BudgetItemInput],
) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = update_total_budget_inner(conn, id, total_amount, items);
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

fn update_total_budget_inner(
    conn: &Connection,
    id: i64,
    total_amount: f64,
    items: &[BudgetItemInput],
) -> Result<(), DbError> {
    // 校验 id 确为总预算（year IS NULL）
    let exists: i64 = conn.query_row(
        "SELECT COUNT(*) FROM budgets WHERE id = ?1 AND year IS NULL",
        [id],
        |r| r.get(0),
    )?;
    if exists == 0 {
        return Err(DbError::Other(format!(
            "总预算 id={id} 不存在或不是总预算"
        )));
    }

    // 提取旧值用于"编辑"操作日志（对齐 Python 编辑总预算的 old_data/new_data）
    let (project_id, old_amount) = conn.query_row(
        "SELECT project_id, total_amount FROM budgets WHERE id = ?1",
        [id],
        |r| Ok((r.get::<_, i64>(0)?, r.get::<_, f64>(1)?)),
    )?;

    // 更新 budgets.total_amount
    conn.execute(
        "UPDATE budgets SET total_amount = ?1 WHERE id = ?2",
        params![total_amount, id],
    )?;

    // 先查当前每类的 spent_amount（保留已有支出数据）
    let spent_map: std::collections::HashMap<String, f64> = conn
        .prepare("SELECT category, COALESCE(spent_amount, 0) FROM budget_items WHERE budget_id = ?1")
        .map_err(|e| DbError::Sqlite(e))?
        .query_map([id], |r| {
            Ok((r.get::<_, String>(0)?, r.get::<_, f64>(1)?))
        })?
        .collect::<Result<_, _>>()?;

    // DELETE+INSERT 保证 10 类齐全
    conn.execute("DELETE FROM budget_items WHERE budget_id = ?1", [id])?;
    for item in items {
        let cat = BudgetCategory::from_label(&item.category);
        let storage_key = cat
            .map(|c| c.storage_key().to_string())
            .unwrap_or_else(|| item.category.clone());
        let spent = spent_map.get(&storage_key).copied().unwrap_or(0.0);
        conn.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) \
             VALUES (?1, ?2, ?3, ?4)",
            params![id, storage_key, item.amount, spent],
        )?;
    }

    // 写"编辑"操作日志（对齐 Python 编辑总预算的 Actionlog）
    crate::logging::log_action(
        conn,
        Some(project_id),
        Some(id),
        None,
        None,
        None,
        None,
        "预算",
        "编辑",
        "编辑了项目总预算",
        "系统用户",
        Some(&format!("总预算额: {old_amount}")),
        Some(&format!("总预算额: {total_amount}")),
        None,
        None,
        None,
    )?;
    Ok(())
}

// ===== 删除预算（对应 project_fund.py::delete_budget 的数据库部分） =====

/// 删除年度预算：级联删除其子项与关联支出（对齐 Python 年度预算分支）。
///
/// 操作顺序与 Python 一致：先 expenses，再 budget_items，最后 budgets。
pub fn delete_annual_budget(conn: &Connection, id: i64) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = (|| -> Result<(), DbError> {
        // 校验 id 确为年度预算
        let exists: i64 = conn.query_row(
            "SELECT COUNT(*) FROM budgets WHERE id = ?1 AND year IS NOT NULL",
            [id],
            |r| r.get(0),
        )?;
        if exists == 0 {
            return Err(DbError::Other(format!(
                "年度预算 id={id} 不存在或不是年度预算"
            )));
        }
        // 删除前取 project_id/year 写"删除"日志（对齐 Python 年度预算分支：log 在删库前写入）
        let (project_id, year): (i64, i64) = conn.query_row(
            "SELECT project_id, year FROM budgets WHERE id = ?1",
            [id],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )?;
        crate::logging::log_action(
            conn,
            Some(project_id),
            Some(id),
            None,
            None,
            None,
            None,
            "预算",
            "删除",
            &format!("删除了 {year} 年度预算"),
            "系统用户",
            None,
            None,
            None,
            None,
            None,
        )?;
        conn.execute("DELETE FROM expenses WHERE budget_id = ?1", [id])?;
        conn.execute("DELETE FROM budget_items WHERE budget_id = ?1", [id])?;
        conn.execute("DELETE FROM budgets WHERE id = ?1", [id])?;
        Ok(())
    })();
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

/// 删除项目总预算：级联删除该项目全部预算、子项与关联支出
/// （对齐 Python 总预算分支：删除整个项目的 budgets / budget_items / expenses）。
pub fn delete_total_budget(conn: &Connection, project_id: i64) -> Result<(), DbError> {
    crate::db::begin_tx(conn)?;
    let result = (|| -> Result<(), DbError> {
        // 写"删除"日志（对齐 Python 总预算分支：log 在删库前写入，仅关联 project_id）
        crate::logging::log_action(
            conn,
            Some(project_id),
            None,
            None,
            None,
            None,
            None,
            "预算",
            "删除",
            "删除了项目总预算",
            "系统用户",
            None,
            None,
            None,
            None,
            None,
        )?;
        conn.execute("DELETE FROM expenses WHERE project_id = ?1", [project_id])?;
        conn.execute(
            "DELETE FROM budget_items WHERE budget_id IN \
             (SELECT id FROM budgets WHERE project_id = ?1)",
            [project_id],
        )?;
        conn.execute("DELETE FROM budgets WHERE project_id = ?1", [project_id])?;
        Ok(())
    })();
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

/// add_project_to_db 等价物：创建项目并自动建立总预算与 10 个科目子项
pub fn add_project_to_db(
    conn: &mut Connection,
    name: &str,
    financial_code: Option<&str>,
    project_code: Option<&str>,
    project_type: Option<&str>,
    start_date: Option<&str>,
    end_date: Option<&str>,
    total_budget: Option<f64>,
) -> Result<i64, DbError> {
    let tx = conn.transaction()?;

    tx.execute(
        "INSERT INTO projects (name, financial_code, project_code, project_type, start_date, end_date, total_budget)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![
            name,
            financial_code,
            project_code,
            project_type,
            start_date,
            end_date,
            total_budget.unwrap_or(0.0),
        ],
    )?;
    let project_id = tx.last_insert_rowid();

    // 创建总预算记录（year=NULL，初始金额 0）
    tx.execute(
        "INSERT INTO budgets (project_id, year, total_amount, spent_amount) VALUES (?1, NULL, 0.0, 0.0)",
        [project_id],
    )?;
    let budget_id = tx.last_insert_rowid();

    // 创建 10 个总预算子项（初始金额 0）。存库用英文 storage_key。
    for category in BudgetCategory::ALL {
        tx.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) VALUES (?1, ?2, 0.0, 0.0)",
            params![budget_id, category.storage_key()],
        )?;
    }

    tx.commit()?;
    Ok(project_id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::schema;
    use crate::models::BudgetItem;
    use rusqlite::Connection;

    /// 与应用行为一致：外键关闭（rusqlite 默认开启，Python/SQLAlchemy 默认关闭）
    fn test_conn() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        conn
    }

    #[test]
    fn add_project_creates_total_budget_with_10_items() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        let pid = add_project_to_db(&mut conn, "测试项目", Some("C001"), None, None, None, None, None)
            .unwrap();

        let budget = conn
            .query_row(
                "SELECT id, year FROM budgets WHERE project_id = ?1",
                [pid],
                |r| Ok((r.get::<_, i64>(0)?, r.get::<_, Option<i64>>(1)?)),
            )
            .unwrap();
        assert_eq!(budget.1, None, "总预算 year 应为 NULL");

        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id = ?1",
                [budget.0],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 10);
    }

    #[test]
    fn budget_usage_returns_zero_structure_without_total_budget() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        let pid = add_project_to_db(&mut conn, "测试项目", None, None, None, None, None, None)
            .unwrap();
        // 删除总预算，模拟无总预算场景
        conn.execute("DELETE FROM budgets", []).unwrap();

        let usage = get_budget_usage(&conn, pid).unwrap();
        assert_eq!(usage.total_budget, 0.0);
        assert_eq!(usage.total_spent, 0.0);
        assert_eq!(usage.remaining, 0.0);
        assert_eq!(usage.category_spent.len(), 10);
        assert!(usage.category_spent.iter().all(|c| c.spent == 0.0));
    }

    #[test]
    fn budget_usage_sums_expenses_per_category() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        let pid = add_project_to_db(&mut conn, "测试项目", None, None, None, None, None, Some(1000.0))
            .unwrap();
        let budget_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        // 注意：add_project_to_db 创建的总预算金额为 0（与 Python 一致，
        // 项目 total_budget 字段与 budgets.total_amount 相互独立）。
        // 这里模拟 UI 编辑总预算后写入的金额
        conn.execute(
            "UPDATE budgets SET total_amount = 1000.0 WHERE id = ?1",
            [budget_id],
        )
        .unwrap();

        // 材料费 100 + 材料费 50 + 设备费 200
        // expenses.category 存英文 KEY（MATERIAL / EQUIPMENT / …）
        for (cat, amt) in [("MATERIAL", 100.0), ("MATERIAL", 50.0), ("EQUIPMENT", 200.0)] {
            conn.execute(
                "INSERT INTO expenses (project_id, budget_id, category, content, amount)
                 VALUES (?1, ?2, ?3, '测试', ?4)",
                params![pid, budget_id, cat, amt],
            )
            .unwrap();
        }

        let usage = get_budget_usage(&conn, pid).unwrap();
        assert_eq!(usage.total_budget, 1000.0);
        assert_eq!(usage.total_spent, 350.0);
        assert_eq!(usage.remaining, 650.0);

        let material = usage
            .category_spent
            .iter()
            .find(|c| c.category == "材料费")
            .unwrap();
        assert_eq!(material.spent, 150.0);
        let equipment = usage
            .category_spent
            .iter()
            .find(|c| c.category == "设备费")
            .unwrap();
        assert_eq!(equipment.spent, 200.0);
    }

    #[test]
    fn add_project_uses_0_0_defaults() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();
        let item: BudgetItem = conn
            .query_row(
                "SELECT * FROM budget_items WHERE budget_id = (SELECT id FROM budgets WHERE project_id = ?1 LIMIT 1)",
                [pid],
                |r| Ok(BudgetItem::from_row(r).unwrap()),
            )
            .unwrap();
        assert_eq!(item.amount, Some(0.0));
        assert_eq!(item.spent_amount, Some(0.0));
    }

    /// 验证 list_project_budgets 的三级结构与跨年度汇总语义
    #[test]
    fn list_project_budgets_aggregates_across_years() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        let pid = add_project_to_db(
            &mut conn, "测试", None, None, None, None, None, Some(1000.0),
        )
        .unwrap();

        // 设置总预算金额（add_project_to_db 创建时为 0，这里模拟 UI 编辑后写入）
        let total_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year IS NULL",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        conn.execute(
            "UPDATE budgets SET total_amount = 1000.0 WHERE id = ?1",
            [total_id],
        )
        .unwrap();
        // 总预算的「材料费」科目设 200（DB 存英文 KEY）
        conn.execute(
            "UPDATE budget_items SET amount = 200.0 WHERE budget_id = ?1 AND category = 'MATERIAL'",
            [total_id],
        )
        .unwrap();

        // 新增 2024 年度预算（总 600，材料费科目 400，已支出 100）
        conn.execute(
            "INSERT INTO budgets (project_id, year, total_amount, spent_amount) VALUES (?1, 2024, 600.0, 100.0)",
            [pid],
        )
        .unwrap();
        let y2024_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year = 2024",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        conn.execute(
            "INSERT INTO budget_items (budget_id, category, amount, spent_amount) VALUES (?1, 'MATERIAL', 400.0, 100.0)",
            [y2024_id],
        )
        .unwrap();
        // 其余 9 个科目也要建（用 storage_key：EQUIPMENT/OUTSOURCING/FUEL/CONFERENCE/PUBLICATION/LABOR/CONSULTING/MISCELLANEOUS/INDIRECT）
        for cat in ["EQUIPMENT", "OUTSOURCING", "FUEL", "CONFERENCE", "PUBLICATION",
                    "LABOR", "CONSULTING", "MISCELLANEOUS", "INDIRECT"] {
            conn.execute(
                "INSERT INTO budget_items (budget_id, category, amount, spent_amount) VALUES (?1, ?2, 0.0, 0.0)",
                params![y2024_id, cat],
            )
                .unwrap();
        }

        let tree = list_project_budgets(&conn, pid).unwrap();

        // 总预算存在
        let total = tree.total_budget.expect("应有总预算");
        assert_eq!(total.total_amount, 1000.0);
        // 总预算 spent = 年度预算 spent 之和 = 100
        assert_eq!(total.spent_amount, 100.0);

        // 总预算「材料费」子项：amount=200, spent=该科目年度之和=100
        let m_total = total
            .items
            .iter()
            .find(|i| i.category == "材料费")
            .unwrap();
        assert_eq!(m_total.amount, 200.0);
        assert_eq!(m_total.spent_amount, 100.0);

        // 年度预算 1 条
        assert_eq!(tree.annual_budgets.len(), 1);
        let y = &tree.annual_budgets[0];
        assert_eq!(y.year, Some(2024));
        assert_eq!(y.total_amount, 600.0);
        assert_eq!(y.spent_amount, 100.0);
        // 年度预算「材料费」子项：amount=400, spent=100（自身字段）
        let m_y = y.items.iter().find(|i| i.category == "材料费").unwrap();
        assert_eq!(m_y.amount, 400.0);
        assert_eq!(m_y.spent_amount, 100.0);
        // 10 个科目齐全
        assert_eq!(y.items.len(), 10);
    }

    #[test]
    fn list_project_budgets_no_total_returns_none() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();
        // 删除所有预算（含总预算）
        conn.execute("DELETE FROM budget_items", []).unwrap();
        conn.execute("DELETE FROM budgets", []).unwrap();

        let tree = list_project_budgets(&conn, pid).unwrap();
        assert!(tree.total_budget.is_none());
        assert!(tree.annual_budgets.is_empty());
    }

    /// 验证新增年度预算：创建 budgets + 10 个 budget_items，并查重
    #[test]
    fn add_annual_budget_creates_budget_and_items() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();

        let input = AnnualBudgetInput {
            project_id: pid,
            year: 2024,
            total_amount: 600.0,
            items: BudgetCategory::ALL
                .iter()
                .map(|c| BudgetItemInput {
                    category: c.as_str().to_string(),
                    amount: 60.0,
                })
                .collect(),
        };
        let bid = add_annual_budget(&conn, input).unwrap();
        assert!(bid > 0);

        // 验证 budgets 记录
        let (year, total, spent): (i64, f64, f64) = conn
            .query_row(
                "SELECT year, total_amount, spent_amount FROM budgets WHERE id = ?1",
                [bid],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(year, 2024);
        assert_eq!(total, 600.0);
        assert_eq!(spent, 0.0);

        // 验证 10 个 budget_items
        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id = ?1",
                [bid],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 10);
    }

    #[test]
    fn add_annual_budget_rejects_duplicate_year() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();

        let make_input = |year: i64| AnnualBudgetInput {
            project_id: pid,
            year,
            total_amount: 100.0,
            items: BudgetCategory::ALL
                .iter()
                .map(|c| BudgetItemInput {
                    category: c.as_str().to_string(),
                    amount: 10.0,
                })
                .collect(),
        };

        // 第一次添加 2024 成功
        add_annual_budget(&conn, make_input(2024)).unwrap();
        // 第二次添加 2024 应失败（查重）
        let err = add_annual_budget(&conn, make_input(2024)).unwrap_err();
        assert!(matches!(err, DbError::Other(_)));
        assert!(format!("{err}").contains("已存在"));
    }

    /// 验证 get_annual_budget_by_id 正确回填 10 个科目 + 总预算
    #[test]
    fn get_annual_budget_round_trips_items() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();
        let bid = add_annual_budget(
            &conn,
            AnnualBudgetInput {
                project_id: pid,
                year: 2024,
                total_amount: 100.0,
                items: BudgetCategory::ALL
                    .iter()
                    .enumerate()
                    .map(|(i, c)| BudgetItemInput {
                        category: c.as_str().to_string(),
                        amount: i as f64,
                    })
                    .collect(),
            },
        )
        .unwrap();

        let detail = get_annual_budget_by_id(&conn, bid).unwrap().unwrap();
        assert_eq!(detail.year, 2024);
        assert_eq!(detail.total_amount, 100.0);
        assert_eq!(detail.items.len(), 10);
        assert_eq!(detail.items[0].category, "设备费");
        assert_eq!(detail.items[0].amount, 0.0);
        assert_eq!(detail.items[1].category, "材料费");
        assert_eq!(detail.items[1].amount, 1.0);
    }

    /// 验证 update_annual_budget：amount 被更新、spent_amount 保留不变
    #[test]
    fn update_preserves_spent_amount_and_updates_amount() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();
        let bid = add_annual_budget(
            &conn,
            AnnualBudgetInput {
                project_id: pid,
                year: 2024,
                total_amount: 100.0,
                items: BudgetCategory::ALL
                    .iter()
                    .map(|c| BudgetItemInput {
                        category: c.as_str().to_string(),
                        amount: 10.0,
                    })
                    .collect(),
            },
        )
        .unwrap();

        // 模拟已发生支出：材料费 spent_amount = 3.5（DB 存英文 KEY MATERIAL）
        conn.execute(
            "UPDATE budget_items SET spent_amount = 3.5 \
             WHERE budget_id = ?1 AND category = 'MATERIAL'",
            [bid],
        )
        .unwrap();

        // 更新：材料费 amount 改成 20，其他改为 0，总金额改 20
        let new_items: Vec<BudgetItemInput> = BudgetCategory::ALL
            .iter()
            .map(|c| BudgetItemInput {
                category: c.as_str().to_string(),
                amount: if c.as_str() == "材料费" { 20.0 } else { 0.0 },
            })
            .collect();
        update_annual_budget(&conn, bid, 20.0, &new_items).unwrap();

        // budgets 行已更新
        let total: f64 = conn
            .query_row("SELECT total_amount FROM budgets WHERE id = ?1", [bid], |r| r.get(0))
            .unwrap();
        assert_eq!(total, 20.0);

        // 材料费 amount=20，spent_amount 保留 3.5（DB 存英文 KEY MATERIAL）
        let (amt, spent): (f64, f64) = conn
            .query_row(
                "SELECT amount, spent_amount FROM budget_items \
                 WHERE budget_id = ?1 AND category = 'MATERIAL'",
                [bid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(amt, 20.0);
        assert_eq!(spent, 3.5);

        // 10 个子项齐全（空类别也写入了 0.0 的 amount）
        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id = ?1",
                [bid],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 10);
    }

    /// 验证 get_total_budget_by_id 正确回填 10 个科目 + total_amount
    #[test]
    fn get_total_budget_round_trips_items() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();
        // add_project_to_db 已建总预算（year=NULL，金额 0，10 子项 amount=0）
        let total_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year IS NULL",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        // 模拟 UI 编辑后写入：总金额 100，材料费科目 50（DB 存英文 KEY）
        conn.execute(
            "UPDATE budgets SET total_amount = 100.0 WHERE id = ?1",
            [total_id],
        )
        .unwrap();
        conn.execute(
            "UPDATE budget_items SET amount = 50.0 WHERE budget_id = ?1 AND category = 'MATERIAL'",
            [total_id],
        )
        .unwrap();

        let detail = get_total_budget_by_id(&conn, total_id).unwrap().unwrap();
        assert_eq!(detail.id, total_id);
        assert_eq!(detail.project_id, pid);
        assert_eq!(detail.total_amount, 100.0);
        assert_eq!(detail.items.len(), 10);
        // 顺序与 BudgetCategory::ALL 一致
        assert_eq!(detail.items[0].category, "设备费");
        assert_eq!(detail.items[0].amount, 0.0);
        assert_eq!(detail.items[1].category, "材料费");
        assert_eq!(detail.items[1].amount, 50.0);
    }

    /// 验证 update_total_budget：amount 被更新、spent_amount 保留、10 子项齐全
    #[test]
    fn update_total_budget_preserves_spent_and_updates_amount() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();
        let total_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year IS NULL",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        // 模拟已发生支出：材料费 spent_amount = 3.5（DB 存英文 KEY MATERIAL）
        conn.execute(
            "UPDATE budget_items SET spent_amount = 3.5 \
             WHERE budget_id = ?1 AND category = 'MATERIAL'",
            [total_id],
        )
        .unwrap();

        // 编辑总预算：材料费 amount 改 100，其他改 0，总金额 100
        let new_items: Vec<BudgetItemInput> = BudgetCategory::ALL
            .iter()
            .map(|c| BudgetItemInput {
                category: c.as_str().to_string(),
                amount: if c.as_str() == "材料费" { 100.0 } else { 0.0 },
            })
            .collect();
        update_total_budget(&conn, total_id, 100.0, &new_items).unwrap();

        // budgets.total_amount 已更新
        let total: f64 = conn
            .query_row("SELECT total_amount FROM budgets WHERE id = ?1", [total_id], |r| r.get(0))
            .unwrap();
        assert_eq!(total, 100.0);

        // 材料费 amount=100，spent_amount 保留 3.5
        let (amt, spent): (f64, f64) = conn
            .query_row(
                "SELECT amount, spent_amount FROM budget_items \
                 WHERE budget_id = ?1 AND category = 'MATERIAL'",
                [total_id],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(amt, 100.0);
        assert_eq!(spent, 3.5);

        // 10 个子项齐全
        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id = ?1",
                [total_id],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(count, 10);

        // 非总预算 id 应返回错误
        let err = update_total_budget(&conn, 99999, 1.0, &new_items).unwrap_err();
        assert!(matches!(err, DbError::Other(_)));
    }

    /// 验证删除年度预算：级联删子项与关联支出，其他年度不受影响
    #[test]
    fn delete_annual_budget_cascades_items_and_expenses() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();

        // 建两个年度预算（2024/2025）
        let make = |year: i64| {
            add_annual_budget(
                &conn,
                AnnualBudgetInput {
                    project_id: pid,
                    year,
                    total_amount: 100.0,
                    items: BudgetCategory::ALL
                        .iter()
                        .map(|c| BudgetItemInput {
                            category: c.as_str().to_string(),
                            amount: 10.0,
                        })
                        .collect(),
                },
            )
            .unwrap()
        };
        let b2024 = make(2024);
        let b2025 = make(2025);

        // 各年度各插入一笔支出
        for (bid, amt) in [(b2024, 30.0), (b2025, 40.0)] {
            conn.execute(
                "INSERT INTO expenses (project_id, budget_id, category, content, amount) \
                 VALUES (?1, ?2, 'MATERIAL', '测试', ?3)",
                params![pid, bid, amt],
            )
            .unwrap();
        }

        delete_annual_budget(&conn, b2024).unwrap();

        // 2024 的 budget/items/expenses 全部删除
        let cnt: i64 = conn
            .query_row("SELECT COUNT(*) FROM budgets WHERE id = ?1", [b2024], |r| r.get(0))
            .unwrap();
        assert_eq!(cnt, 0);
        let cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id = ?1",
                [b2024],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(cnt, 0);
        let cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM expenses WHERE budget_id = ?1",
                [b2024],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(cnt, 0);

        // 2025 不受影响
        let cnt: i64 = conn
            .query_row("SELECT COUNT(*) FROM budgets WHERE id = ?1", [b2025], |r| r.get(0))
            .unwrap();
        assert_eq!(cnt, 1);
        let cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM expenses WHERE budget_id = ?1",
                [b2025],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(cnt, 1);
    }

    /// 验证删除总预算：清空该项目全部预算、子项与支出
    #[test]
    fn delete_total_budget_clears_all_budgets_and_expenses() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();

        // 总预算 + 一个年度预算 + 各一笔支出
        let total_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year IS NULL",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        let b2024 = add_annual_budget(
            &conn,
            AnnualBudgetInput {
                project_id: pid,
                year: 2024,
                total_amount: 100.0,
                items: BudgetCategory::ALL
                    .iter()
                    .map(|c| BudgetItemInput {
                        category: c.as_str().to_string(),
                        amount: 10.0,
                    })
                    .collect(),
            },
        )
        .unwrap();
        for (bid, amt) in [(total_id, 5.0), (b2024, 8.0)] {
            conn.execute(
                "INSERT INTO expenses (project_id, budget_id, category, content, amount) \
                 VALUES (?1, ?2, 'MATERIAL', '测试', ?3)",
                params![pid, bid, amt],
            )
            .unwrap();
        }

        delete_total_budget(&conn, pid).unwrap();

        let cnt: i64 = conn
            .query_row("SELECT COUNT(*) FROM budgets WHERE project_id = ?1", [pid], |r| r.get(0))
            .unwrap();
        assert_eq!(cnt, 0);
        let cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM budget_items WHERE budget_id IN \
                 (SELECT id FROM budgets WHERE project_id = ?1)",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(cnt, 0);
        let cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM expenses WHERE project_id = ?1",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(cnt, 0);
    }

    /// 验证预算增/改/删均写 Actionlog（对齐 project.rs::crud_writes_actionlog）
    #[test]
    fn budget_crud_writes_actionlog() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();
        let pid = add_project_to_db(&mut conn, "P", None, None, None, None, None, None).unwrap();

        // 10 个科目统一金额的 items 构造器
        let items_all = |amt: f64| {
            BudgetCategory::ALL
                .iter()
                .map(|c| BudgetItemInput {
                    category: c.as_str().to_string(),
                    amount: amt,
                })
                .collect::<Vec<_>>()
        };

        // 新增年度预算 → 1 条"新增"日志，budget_id 关联正确
        let bid = add_annual_budget(
            &conn,
            AnnualBudgetInput {
                project_id: pid,
                year: 2024,
                total_amount: 100.0,
                items: items_all(10.0),
            },
        )
        .unwrap();
        let (typ, act, desc, log_budget_id): (String, String, String, Option<i64>) = conn
            .query_row(
                "SELECT type, action, description, budget_id FROM actionlogs \
                 WHERE project_id = ?1 ORDER BY id",
                [pid],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
            )
            .unwrap();
        assert_eq!(typ, "预算");
        assert_eq!(act, "新增");
        assert_eq!(desc, "添加了 2024 年度预算");
        assert_eq!(log_budget_id, Some(bid));

        // 编辑年度预算 → 1 条"编辑"，old_data/new_data 非空且含新旧预算额
        update_annual_budget(&conn, bid, 200.0, &items_all(20.0)).unwrap();
        let (act, old_data, new_data): (String, Option<String>, Option<String>) = conn
            .query_row(
                "SELECT action, old_data, new_data FROM actionlogs \
                 WHERE project_id = ?1 AND action = '编辑' AND budget_id = ?2",
                params![pid, bid],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(act, "编辑");
        assert!(old_data.as_deref().unwrap_or("").contains("预算额: 100"));
        assert!(new_data.as_deref().unwrap_or("").contains("预算额: 200"));

        // 编辑总预算 → 1 条"编辑"（old_data 为原 0 总额）
        let total_id: i64 = conn
            .query_row(
                "SELECT id FROM budgets WHERE project_id = ?1 AND year IS NULL",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        update_total_budget(&conn, total_id, 50.0, &items_all(5.0)).unwrap();
        let (act, old_data, new_data): (String, Option<String>, Option<String>) = conn
            .query_row(
                "SELECT action, old_data, new_data FROM actionlogs \
                 WHERE project_id = ?1 AND action = '编辑' AND budget_id = ?2",
                params![pid, total_id],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(act, "编辑");
        assert!(old_data.as_deref().unwrap_or("").contains("总预算额: 0"));
        assert!(new_data.as_deref().unwrap_or("").contains("总预算额: 50"));

        // 删除年度预算 → 1 条"删除"（budget_id 关联）
        delete_annual_budget(&conn, bid).unwrap();
        let (act, desc): (String, String) = conn
            .query_row(
                "SELECT action, description FROM actionlogs \
                 WHERE project_id = ?1 AND action = '删除' AND budget_id = ?2",
                params![pid, bid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(act, "删除");
        assert_eq!(desc, "删除了 2024 年度预算");

        // 删除总预算 → 1 条"删除"（仅关联 project_id）
        delete_total_budget(&conn, pid).unwrap();
        let (act, desc): (String, String) = conn
            .query_row(
                "SELECT action, description FROM actionlogs \
                 WHERE project_id = ?1 AND action = '删除' AND budget_id IS NULL",
                [pid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        assert_eq!(act, "删除");
        assert_eq!(desc, "删除了项目总预算");

        // 共 5 条日志
        let cnt: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM actionlogs WHERE project_id = ?1",
                [pid],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(cnt, 5);
    }

    /// 验证 begin_tx 自愈：连接残留未提交事务时不再报
    /// “cannot start a transaction within a transaction”
    #[test]
    fn begin_tx_recovers_from_leftover_transaction() {
        let mut conn = test_conn();
        schema::create_all(&mut conn).unwrap();

        // 模拟先前命令异常中断：BEGIN 后写未提交
        conn.execute_batch("BEGIN").unwrap();
        conn.execute_batch("INSERT INTO projects (name) VALUES ('幽灵')").unwrap();

        // 残留事务下直接 BEGIN 确实会失败（对齐用户报告的报错）
        let err = conn.execute_batch("BEGIN").unwrap_err();
        assert!(
            err.to_string().contains("cannot start a transaction within a transaction"),
            "预期 BEGIN 失败，实际: {err}"
        );

        // begin_tx 自愈：自动回滚残留事务并重新开启
        crate::db::begin_tx(&conn).unwrap();
        conn.execute_batch("ROLLBACK").unwrap();

        // 自愈后正常写事务可用
        crate::db::begin_tx(&conn).unwrap();
        conn.execute_batch("INSERT INTO projects (name) VALUES ('正常')")
            .unwrap();
        conn.execute_batch("COMMIT").unwrap();
        let cnt: i64 = conn
            .query_row("SELECT COUNT(*) FROM projects", [], |r| r.get(0))
            .unwrap();
        assert_eq!(cnt, 1);
    }
}
