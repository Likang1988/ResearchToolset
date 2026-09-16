//! 甘特图服务：gantt_tasks / gantt_dependencies 的加载与保存
//!
//! 对应 Python `app/views/projecting_interface/project_progress.py` 中
//! `GanttBridge.load_gantt_data` 与 `GanttBridge.save_gantt_data` 的核心逻辑：
//! - 加载：按 order 排序取任务；依赖按 successor 聚合为 "pred1,pred2" 字符串
//! - 保存：整单事务——处理删除（先删依赖再删任务）、
//!   新增（tmp_ 前缀 → 持久化 gantt_id 映射）、更新、依赖全量重建、
//!   最后从深层向浅层按 duration 加权重算父任务进度

use std::path::Path;

use chrono::TimeZone;
use rusqlite::{params, Connection, OptionalExtension, Transaction};

use crate::models::GanttTask;
use crate::DbError;

/// 甘特图任务的内存表示（对应 jQueryGantt 前端 task 对象的字段）
/// start/end 用毫秒时间戳（前端格式）；depends 为逗号分隔的前驱 id 串
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GanttTaskDto {
    pub id: String,
    pub name: String,
    pub progress: f64,
    #[serde(rename = "progressByWorklog")]
    pub progress_by_worklog: bool,
    pub relevance: i64,
    #[serde(default)]
    pub ty: String,
    #[serde(rename = "typeId", default)]
    pub type_id: String,
    pub description: Option<String>,
    pub code: Option<String>,
    pub level: i64,
    pub status: Option<String>,
    pub depends: String,
    pub can_write: bool,
    pub start: Option<i64>,
    pub duration: Option<i64>,
    pub end: Option<i64>,
    #[serde(rename = "startIsMilestone")]
    pub start_is_milestone: bool,
    #[serde(rename = "endIsMilestone")]
    pub end_is_milestone: bool,
    #[serde(default)]
    pub collapsed: bool,
    pub assigs: Vec<()>,
    #[serde(rename = "hasChild", default)]
    pub has_child: bool,
    pub responsible: Option<String>,
}

/// 甘特图项目数据（load/save 的顶层结构，与前端 saveProject 格式一致）
/// 使用 camelCase 输出，与 jQueryGantt 前端字段名（project.canWrite 等）保持一致，
/// 否则 loadProject 读到 undefined 会导致 checkButtonPermissions 隐藏全部编辑按钮。
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GanttProjectData {
    pub tasks: Vec<GanttTaskDto>,
    #[serde(default)]
    pub selected_row: i64,
    pub deleted_task_ids: Vec<String>,
    pub resources: Vec<serde_json::Value>,
    pub roles: Vec<serde_json::Value>,
    pub can_write: bool,
    pub can_delete: bool,
    pub can_write_on_parent: bool,
    pub can_add: bool,
}

/// 把 DB 时间字符串（SQLite DATETIME，如 "2026-08-21 09:00:00"）转毫秒时间戳
fn db_time_to_millis(s: &str) -> Option<i64> {
    // SQLite DATE 函数得 "YYYY-MM-DD HH:MM:SS"，转为 UTC 毫秒
    let normalized = s.trim();
    // 去掉可能存在的 'T' 分隔与毫秒尾
    let normalized = normalized.replace('T', " ");
    let dt = normalized.split('.').next().unwrap_or(&normalized);
    // 解析 "YYYY-MM-DD HH:MM:SS"（无时区则按 UTC 处理，与 Python
    // `replace(tzinfo=timezone.utc).timestamp()*1000` 一致）
    let dt = chrono::NaiveDateTime::parse_from_str(dt, "%Y-%m-%d %H:%M:%S")
        .ok()?
        .and_utc();
    Some(dt.timestamp_millis())
}

/// 毫秒时间戳转 DB 字符串（UTC，"YYYY-MM-DD HH:MM:SS"）
fn millis_to_db_time(ms: i64) -> String {
    let dt = chrono::DateTime::from_timestamp_millis(ms)
        .unwrap_or_default()
        .naive_utc();
    dt.format("%Y-%m-%d %H:%M:%S").to_string()
}

/// 任务操作日志 JSON（对齐 Python save_gantt_data 的字段集）：
/// id/name/code/level/status/start_date/duration/end_date/progress/responsible。
/// 日期取 "YYYY-MM-DD"（Python `str(date)` 语义）。
fn task_log_json(
    id: &str,
    name: &str,
    code: Option<&str>,
    level: i64,
    status: Option<&str>,
    start_date: Option<&str>,
    duration: Option<i64>,
    end_date: Option<&str>,
    progress: f64,
    responsible: Option<&str>,
) -> String {
    let date_part = |s: Option<&str>| s.map(|v| v.split(' ').next().unwrap_or(v).to_string());
    serde_json::json!({
        "id": id,
        "name": name,
        "code": code,
        "level": level,
        "status": status,
        "start_date": date_part(start_date),
        "duration": duration,
        "end_date": date_part(end_date),
        "progress": progress,
        "responsible": responsible,
    })
    .to_string()
}

/// 判定现有任务与传入任务数据是否有差异（对齐 Python `data_changed` 判定：
/// 逐字段比较 task_obj_data 与 existing_task 属性；无变化不写编辑日志）。
fn task_data_changed(
    old: &GanttTask,
    name: &str,
    code: Option<&str>,
    level: i64,
    status: Option<&str>,
    start_str: Option<&str>,
    duration: Option<i64>,
    end_str: Option<&str>,
    start_is_milestone: bool,
    end_is_milestone: bool,
    progress: f64,
    progress_by_worklog: bool,
    description: Option<&str>,
    collapsed: bool,
    has_child: bool,
    responsible: Option<&str>,
    order: i64,
) -> bool {
    old.name != name
        || old.code.as_deref() != code
        || old.level.unwrap_or(0) != level
        || old.status.as_deref() != status
        || old.start_date.as_deref() != start_str
        || old.duration != duration
        || old.end_date.as_deref() != end_str
        || old.start_is_milestone.unwrap_or(false) != start_is_milestone
        || old.end_is_milestone.unwrap_or(false) != end_is_milestone
        || old.progress.unwrap_or(0.0) != progress
        || old.progress_by_worklog.unwrap_or(false) != progress_by_worklog
        || old.description.as_deref() != description
        || old.collapsed.unwrap_or(false) != collapsed
        || old.has_child.unwrap_or(false) != has_child
        || old.responsible.as_deref() != responsible
        || old.order.unwrap_or(0) != order
}

/// 加载某项目的甘特图数据（对应 Python load_gantt_data）
pub fn load_gantt_data(
    conn: &Connection,
    project_id: i64,
) -> Result<GanttProjectData, DbError> {
    // 1. 按 order 排序取任务（order 可能为 NULL，SQLite 排序时 NULL 在最前）
    let mut stmt = conn.prepare(
        "SELECT * FROM gantt_tasks WHERE project_id = ?1 ORDER BY `order` ASC, id ASC",
    )?;
    let rows: Vec<GanttTask> = stmt
        .query_map([project_id], GanttTask::from_row)?
        .collect::<rusqlite::Result<_>>()?;

    // 2. 取全部依赖
    let mut dep_stmt = conn.prepare(
        "SELECT predecessor_gantt_id, successor_gantt_id FROM gantt_dependencies WHERE project_id = ?1",
    )?;
    let deps: Vec<(String, String)> = dep_stmt
        .query_map([project_id], |r| Ok((r.get(0)?, r.get(1)?)))?
        .collect::<rusqlite::Result<_>>()?;

    // 依赖按 successor 聚合
    let mut dep_map: std::collections::HashMap<&str, Vec<&str>> =
        std::collections::HashMap::new();
    for (pred, succ) in &deps {
        dep_map.entry(succ).or_default().push(pred);
    }

    let tasks = rows
        .iter()
        .map(|t| {
            let depends = dep_map
                .get(t.gantt_id.as_str())
                .map(|v| v.join(","))
                .unwrap_or_default();
            let progress = t.progress.unwrap_or(0.0).clamp(0.0, 100.0);
            GanttTaskDto {
                id: t.gantt_id.clone(),
                name: t.name.clone(),
                progress,
                progress_by_worklog: t.progress_by_worklog.unwrap_or(false),
                relevance: 0,
                ty: String::new(),
                type_id: String::new(),
                description: t.description.clone(),
                code: t.code.clone(),
                level: t.level.unwrap_or(0),
                status: t.status.clone(),
                depends,
                can_write: true,
                start: t.start_date.as_deref().and_then(db_time_to_millis),
                duration: t.duration,
                end: t.end_date.as_deref().and_then(db_time_to_millis),
                start_is_milestone: t.start_is_milestone.unwrap_or(false),
                end_is_milestone: t.end_is_milestone.unwrap_or(false),
                collapsed: t.collapsed.unwrap_or(false),
                assigs: vec![],
                has_child: t.has_child.unwrap_or(false),
                responsible: t.responsible.clone(),
            }
        })
        .collect();

    Ok(GanttProjectData {
        tasks,
        selected_row: if rows.is_empty() { -1 } else { 0 },
        deleted_task_ids: vec![],
        resources: vec![],
        roles: vec![],
        can_write: true,
        can_delete: true,
        can_write_on_parent: true,
        can_add: true,
    })
}

// ---- 保存（对应 Python save_gantt_data，事务内） ----

/// 保存后的任务进度重算：从最深层向浅层按 duration 加权
/// 返回 (任务 id, 名称, 更新后进度) 列表，便于前端提示/日志
fn recalc_parent_progress(
    tx: &Transaction,
    project_id: i64,
) -> Result<Vec<(i64, String, f64)>, DbError> {
    // 取全部任务按 level 倒序
    let mut stmt = tx.prepare(
        "SELECT * FROM gantt_tasks WHERE project_id = ?1 ORDER BY level DESC, id ASC",
    )?;
    let all: Vec<GanttTask> = stmt
        .query_map([project_id], GanttTask::from_row)?
        .collect::<rusqlite::Result<_>>()?;

    let mut by_level: std::collections::BTreeMap<i64, Vec<GanttTask>> =
        std::collections::BTreeMap::new();
    for t in &all {
        by_level.entry(t.level.unwrap_or(0)).or_default().push(t.clone());
    }

    let mut updated = Vec::new();
    if let Some(&max_level) = by_level.keys().max() {
        for level in (0..max_level).rev() {
            // 此层为「父层」，其直接子层 = level+1
            let Some(parents) = by_level.get(&level) else { continue };
            let Some(children) = by_level.get(&(level + 1)) else { continue };
            for parent in parents {
                if !parent.has_child.unwrap_or(false) {
                    continue;
                }
                // 直接子任务 = 层 level+1 且（本实现中按 level 分桶即满足）
                let mut total_weight = 0_i64;
                let mut weighted = 0.0_f64;
                for child in children {
                    let w = child.duration.unwrap_or(1).max(1);
                    total_weight += w;
                    let cp = child.progress.unwrap_or(0.0).clamp(0.0, 100.0);
                    weighted += cp * w as f64;
                }
                if total_weight > 0 {
                    let new_progress = (weighted / total_weight as f64 * 100.0).round() / 100.0;
                    if (parent.progress.unwrap_or(0.0) - new_progress).abs() > f64::EPSILON {
                        tx.execute(
                            "UPDATE gantt_tasks SET progress = ?1 WHERE id = ?2",
                            params![new_progress, parent.id],
                        )?;
                        updated.push((parent.id, parent.name.clone(), new_progress));
                    }
                }
            }
        }
    }
    Ok(updated)
}

/// 保存甘特图数据（整单事务）。返回新任务临时id→持久化gantt_id映射。
///
/// 对应 Python save_gantt_data：
/// 1. 删除 deletedTaskIds（先删依赖，含作为前驱的，再删任务）
/// 2. 更新/新增 tasks（tmp_ 前缀为新任务，追加映射；已有 id 更新并记变更）
/// 3. 清空该项目的旧依赖，按当前的任务 depends 全量重建（引用新映射）
/// 4. 从深层向上按 duration 加权重算父任务进度
/// 5. 提交
pub fn save_gantt_data(
    conn: &mut Connection,
    project_id: i64,
    data: &GanttProjectData,
) -> Result<std::collections::HashMap<String, String>, DbError> {
    // 连接上若残留未提交事务（先前命令异常中断，如云盘/WAL 锁导致 COMMIT 失败），
    // 直接 BEGIN 会报 "cannot start a transaction within a transaction"；
    // 先回滚自愈（与 crate::db::begin_tx 语义一致）。
    if !conn.is_autocommit() {
        conn.execute_batch("ROLLBACK")?;
    }
    let tx = conn.transaction()?;

    // 项目财务编号（任务日志 related_info="项目: {financial_code}"，对齐 Python）
    let financial_code: Option<String> = tx
        .query_row(
            "SELECT financial_code FROM projects WHERE id = ?1",
            [project_id],
            |r| r.get::<_, Option<String>>(0),
        )?;
    let related_info = |suffix: &str| {
        format!("项目: {}", financial_code.as_deref().unwrap_or(""))
            + if suffix.is_empty() { "" } else { suffix }
    };

    // ---- 1. 处理删除 ----
    {
        // 先删依赖（前驱或后继是被删 id 的都要删）
        let mut del_dep = tx.prepare(
            "DELETE FROM gantt_dependencies WHERE project_id = ?1 AND (predecessor_gantt_id = ?2 OR successor_gantt_id = ?2)",
        )?;
        for id in &data.deleted_task_ids {
            del_dep.execute(params![project_id, id])?;
        }
        // 再删任务（删除前写日志：type="任务"、action="删除"，含 old_data）
        let mut get_task = tx.prepare(
            "SELECT * FROM gantt_tasks WHERE project_id = ?1 AND gantt_id = ?2",
        )?;
        let mut del_task = tx.prepare(
            "DELETE FROM gantt_tasks WHERE project_id = ?1 AND gantt_id = ?2",
        )?;
        for id in &data.deleted_task_ids {
            let row: Option<GanttTask> = get_task
                .query_row(params![project_id, id], GanttTask::from_row)
                .optional()?;
            if let Some(t) = row {
                let old_data = task_log_json(
                    &t.gantt_id,
                    &t.name,
                    t.code.as_deref(),
                    t.level.unwrap_or(0),
                    t.status.as_deref(),
                    t.start_date.as_deref(),
                    t.duration,
                    t.end_date.as_deref(),
                    t.progress.unwrap_or(0.0),
                    t.responsible.as_deref(),
                );
                crate::logging::log_action(
                    &tx,
                    Some(project_id),
                    None,
                    None,
                    Some(t.id),
                    None,
                    None,
                    "任务",
                    "删除",
                    &format!("删除任务：{} (ID: {})", t.name, t.gantt_id),
                    "系统用户",
                    Some(&old_data),
                    None,
                    None,
                    None,
                    Some(&related_info("")),
                )?;
            }
            del_task.execute(params![project_id, id])?;
        }
    }

    // ---- 2. 更新/新增任务 ----
    // 取出该项目现有任务，建 gantt_id → 行的 map
    let existing: Vec<GanttTask> = {
        let mut stmt = tx.prepare(
            "SELECT * FROM gantt_tasks WHERE project_id = ?1",
        )?;
        let rows = stmt.query_map([project_id], GanttTask::from_row)?;
        rows.collect::<rusqlite::Result<Vec<GanttTask>>>()?
    };
    let existing_map: std::collections::HashMap<String, GanttTask> =
        existing.into_iter().map(|t| (t.gantt_id.clone(), t)).collect();

    let mut id_map: std::collections::HashMap<String, String> =
        std::collections::HashMap::new();
    let mut processed: std::collections::HashSet<String> =
        std::collections::HashSet::new();

    // 收集依赖（此时存的是临时/原始 id，第 3 步再映射）
    let mut deps_to_save: Vec<(String, String)> = Vec::new();

    for (index, task) in data.tasks.iter().enumerate() {
        let order = index as i64;
        let start_str = task.start.map(millis_to_db_time);
        let end_str = task.end.map(millis_to_db_time);
        let progress = task.progress.clamp(0.0, 100.0);

        // 解析 depends 成为后继
        let preds: Vec<String> = task
            .depends
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();

        let final_gantt_id: String;
        let is_new = task.id.starts_with("tmp_");

        if is_new {
            // 新任务：插入，持久化 gantt_id = 自增 id 的字符串
            tx.execute(
                "INSERT INTO gantt_tasks \
                 (project_id, gantt_id, name, code, level, status, start_date, duration, \
                  end_date, start_is_milestone, end_is_milestone, progress, progress_by_worklog, \
                  description, collapsed, has_child, responsible, `order`) \
                 VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18)",
                params![
                    project_id,
                    &task.id,          // 先占位
                    task.name,
                    task.code,
                    task.level,
                    task.status,
                    start_str,
                    task.duration,
                    end_str,
                    task.start_is_milestone,
                    task.end_is_milestone,
                    progress,
                    task.progress_by_worklog,
                    task.description,
                    task.collapsed,
                    task.has_child,
                    task.responsible,
                    order
                ],
            )?;
            let row_id = tx.last_insert_rowid();
            let persistent_id = row_id.to_string();
            // 回填 gantt_id 为持久化 id
            tx.execute(
                "UPDATE gantt_tasks SET gantt_id = ?1 WHERE id = ?2",
                params![persistent_id, row_id],
            )?;
            id_map.insert(task.id.clone(), persistent_id.clone());
            final_gantt_id = persistent_id.clone();
            processed.insert(final_gantt_id.clone());

            // 新增任务日志（对齐 Python：type="任务"、action="新增"、new_data、
            // gantt_task_id 关联 DB id）
            let new_data = task_log_json(
                &final_gantt_id,
                &task.name,
                task.code.as_deref(),
                task.level,
                task.status.as_deref(),
                start_str.as_deref(),
                task.duration,
                end_str.as_deref(),
                progress,
                task.responsible.as_deref(),
            );
            crate::logging::log_action(
                &tx,
                Some(project_id),
                None,
                None,
                Some(row_id),
                None,
                None,
                "任务",
                "新增",
                &format!("新增任务：{} (ID: {})", task.name, final_gantt_id),
                "系统用户",
                None,
                Some(&new_data),
                None,
                None,
                Some(&related_info("")),
            )?;
        } else if let Some(existing_task) = existing_map.get(&task.id) {
            // 现有任务：先比对旧数据判定是否有变更（对齐 Python：
            // 无变化不写编辑日志），有变更才 UPDATE + 写"编辑"日志
            let old_data = task_log_json(
                &existing_task.gantt_id,
                &existing_task.name,
                existing_task.code.as_deref(),
                existing_task.level.unwrap_or(0),
                existing_task.status.as_deref(),
                existing_task.start_date.as_deref(),
                existing_task.duration,
                existing_task.end_date.as_deref(),
                existing_task.progress.unwrap_or(0.0),
                existing_task.responsible.as_deref(),
            );
            if task_data_changed(
                existing_task,
                &task.name,
                task.code.as_deref(),
                task.level,
                task.status.as_deref(),
                start_str.as_deref(),
                task.duration,
                end_str.as_deref(),
                task.start_is_milestone,
                task.end_is_milestone,
                progress,
                task.progress_by_worklog,
                task.description.as_deref(),
                task.collapsed,
                task.has_child,
                task.responsible.as_deref(),
                order,
            ) {
                tx.execute(
                    "UPDATE gantt_tasks SET \
                     name=?1, code=?2, level=?3, status=?4, start_date=?5, duration=?6, \
                     end_date=?7, start_is_milestone=?8, end_is_milestone=?9, progress=?10, \
                     progress_by_worklog=?11, description=?12, collapsed=?13, has_child=?14, \
                     responsible=?15, `order`=?16 \
                     WHERE project_id=?17 AND gantt_id=?18",
                    params![
                        task.name,
                        task.code,
                        task.level,
                        task.status,
                        start_str,
                        task.duration,
                        end_str,
                        task.start_is_milestone,
                        task.end_is_milestone,
                        progress,
                        task.progress_by_worklog,
                        task.description,
                        task.collapsed,
                        task.has_child,
                        task.responsible,
                        order,
                        project_id,
                        task.id
                    ],
                )?;
                // 编辑任务日志（对齐 Python：old_data + new_data，gantt_task_id 关联 DB id）
                let new_data = task_log_json(
                    &task.id,
                    &task.name,
                    task.code.as_deref(),
                    task.level,
                    task.status.as_deref(),
                    start_str.as_deref(),
                    task.duration,
                    end_str.as_deref(),
                    progress,
                    task.responsible.as_deref(),
                );
                crate::logging::log_action(
                    &tx,
                    Some(project_id),
                    None,
                    None,
                    Some(existing_task.id),
                    None,
                    None,
                    "任务",
                    "编辑",
                    &format!("编辑任务：{} (ID: {})", task.name, task.id),
                    "系统用户",
                    Some(&old_data),
                    Some(&new_data),
                    None,
                    None,
                    Some(&related_info("")),
                )?;
            }
            final_gantt_id = task.id.clone();
            processed.insert(final_gantt_id.clone());
        } else {
            // 持久化 id 但 DB 中不存在（异常情况）：按新任务插入
            tx.execute(
                "INSERT INTO gantt_tasks \
                 (project_id, gantt_id, name, code, level, status, start_date, duration, \
                  end_date, start_is_milestone, end_is_milestone, progress, progress_by_worklog, \
                  description, collapsed, has_child, responsible, `order`) \
                 VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18)",
                params![
                    project_id,
                    &task.id,
                    task.name,
                    task.code,
                    task.level,
                    task.status,
                    start_str,
                    task.duration,
                    end_str,
                    task.start_is_milestone,
                    task.end_is_milestone,
                    progress,
                    task.progress_by_worklog,
                    task.description,
                    task.collapsed,
                    task.has_child,
                    task.responsible,
                    order
                ],
            )?;
            let row_id = tx.last_insert_rowid();
            final_gantt_id = task.id.clone();
            processed.insert(final_gantt_id.clone());

            // 持久化 id 但 DB 中不存在，按新任务插入并写"新增"日志（对齐 Python）
            let new_data = task_log_json(
                &final_gantt_id,
                &task.name,
                task.code.as_deref(),
                task.level,
                task.status.as_deref(),
                start_str.as_deref(),
                task.duration,
                end_str.as_deref(),
                progress,
                task.responsible.as_deref(),
            );
            crate::logging::log_action(
                &tx,
                Some(project_id),
                None,
                None,
                Some(row_id),
                None,
                None,
                "任务",
                "新增",
                &format!("新增任务：{} (ID: {})", task.name, final_gantt_id),
                "系统用户",
                None,
                Some(&new_data),
                None,
                None,
                Some(&related_info("")),
            )?;
        }

        // 记录依赖（后继是持久化 id）
        for pred in preds {
            deps_to_save.push((pred, final_gantt_id.clone()));
        }
    }

    // ---- 3. 依赖全量重建 ----
    // 先清空
    tx.execute(
        "DELETE FROM gantt_dependencies WHERE project_id = ?1",
        [project_id],
    )?;
    // 写入（前驱也做临时→持久化映射）
    {
        let mut ins_dep = tx.prepare(
            "INSERT OR IGNORE INTO gantt_dependencies \
             (project_id, predecessor_gantt_id, successor_gantt_id, type) VALUES (?1,?2,?3,?4)",
        )?;
        for (pred_raw, succ) in &deps_to_save {
            let final_pred = id_map.get(pred_raw).cloned().unwrap_or_else(|| pred_raw.clone());
            if processed.contains(&final_pred) && processed.contains(succ) {
                ins_dep.execute(params![project_id, final_pred, succ, "FS"])?;
            }
        }
    }

    // ---- 4. 重算父任务进度 ----
    recalc_parent_progress(&tx, project_id)?;

    // ---- 5. 提交 ----
    tx.commit()?;
    Ok(id_map)
}

/// 清理某项目下全部甘特数据（删除项目级联用；若无则 no-op）
/// 对应 Python 项目删除时的级联（gantt_tasks/dependencies 随外键 ON DELETE CASCADE）
/// 提供显式实现以保证确定性，且不依赖外键是否开启。
pub fn clear_project_gantt(conn: &Connection, project_id: i64) -> Result<(), DbError> {
    conn.execute(
        "DELETE FROM gantt_dependencies WHERE project_id = ?1",
        [project_id],
    )?;
    conn.execute(
        "DELETE FROM gantt_tasks WHERE project_id = ?1",
        [project_id],
    )?;
    Ok(())
}

// ---- 导出（对应 Python GanttBridge.export_gantt_data） ----

/// 毫秒时间戳 → "YYYY-MM-DD"（本地时区，与 Python `datetime.fromtimestamp` 一致）
fn ms_to_date(ms: Option<i64>) -> Option<String> {
    let ms = ms?;
    chrono::Local
        .timestamp_millis_opt(ms)
        .single()
        .map(|dt| dt.format("%Y-%m-%d").to_string())
}

/// 导出甘特数据到文件。按文件扩展名选择格式（与 Python 版一致）：
/// - .xlsx → Excel（列序同 Python XLSX 导出）
/// - .json → 原样 JSON（indent=2 便于阅读）
/// - .csv  → CSV（utf-8-sig，Excel 直接打开不乱码）
/// - .txt  → 缩进文本
/// 其余扩展名/无扩展名默认输出 Excel。
pub fn export_gantt_file(path: &Path, data: &GanttProjectData) -> Result<(), DbError> {
    let ext = path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();
    match ext.as_str() {
        "json" => export_gantt_json(path, data),
        "csv" => export_gantt_csv(path, data),
        "txt" => export_gantt_txt(path, data),
        _ => export_gantt_xlsx(path, data),
    }
}

fn export_gantt_json(path: &Path, data: &GanttProjectData) -> Result<(), DbError> {
    let json_str = serde_json::to_string_pretty(data).map_err(DbError::Json)?;
    std::fs::write(path, json_str).map_err(DbError::Io)
}

fn export_gantt_csv(path: &Path, data: &GanttProjectData) -> Result<(), DbError> {
    // 与 Python CSV 列一致；Python 用 QUOTE_ALL（每个字段都加引号）
    let header = ["ID", "名称", "层级", "开始日期", "结束日期", "工期(天)", "进度(%)", "依赖项", "状态", "描述"];
    let mut out = String::new();
    out.push_str(&header.join(","));
    out.push_str("\r\n");
    for t in &data.tasks {
        let fields = [
            t.id.clone(),
            t.name.clone(),
            t.level.to_string(),
            ms_to_date(t.start).unwrap_or_default(),
            ms_to_date(t.end).unwrap_or_default(),
            t.duration.unwrap_or(0).to_string(),
            t.progress.to_string(),
            t.depends.clone(),
            t.status.clone().unwrap_or_default(),
            t.description.clone().unwrap_or_default(),
        ];
        let quoted: Vec<String> = fields
            .iter()
            .map(|f| format!("\"{}\"", f.replace('"', "\"\"")))
            .collect();
        out.push_str(&quoted.join(","));
        out.push_str("\r\n");
    }
    // utf-8-sig（带 BOM）
    let mut bytes = vec![0xEF, 0xBB, 0xBF];
    bytes.extend_from_slice(out.as_bytes());
    std::fs::write(path, bytes).map_err(DbError::Io)
}

fn export_gantt_txt(path: &Path, data: &GanttProjectData) -> Result<(), DbError> {
    let mut out = String::from("项目甘特图数据\n");
    out.push_str(&"=".repeat(40));
    out.push_str("\n\n");
    for t in &data.tasks {
        let indent = "  ".repeat(t.level.max(0) as usize);
        let start = ms_to_date(t.start).unwrap_or_else(|| "N/A".to_string());
        let end = ms_to_date(t.end).unwrap_or_else(|| "N/A".to_string());
        let status = t.status.clone().unwrap_or_else(|| "N/A".to_string());
        out.push_str(&format!("{indent}ID: {}\n", t.id));
        out.push_str(&format!("{indent}名称: {}\n", t.name));
        out.push_str(&format!(
            "{indent}时间: {start} -> {end} (持续 {} 天)\n",
            t.duration.unwrap_or(0)
        ));
        out.push_str(&format!("{indent}进度: {}%\n", t.progress));
        if !t.depends.is_empty() {
            out.push_str(&format!("{indent}依赖: {}\n", t.depends));
        }
        if let Some(d) = &t.description {
            if !d.is_empty() {
                out.push_str(&format!("{indent}描述: {d}\n"));
            }
        }
        out.push_str(&format!("{indent}状态: {status}\n"));
        out.push_str(&"-".repeat(30));
        out.push_str("\n");
    }
    std::fs::write(path, out).map_err(DbError::Io)
}

fn export_gantt_xlsx(path: &Path, data: &GanttProjectData) -> Result<(), DbError> {
    use rust_xlsxwriter::{Format, Workbook};

    let mut wb = Workbook::new();
    let sheet = wb.add_worksheet();
    sheet
        .set_name("甘特图")
        .map_err(|e| DbError::Other(e.to_string()))?;

    // 与 Python XLSX 导出列一致：名称按层级加 2 空格缩进
    let headers: [&str; 9] = [
        "ID",
        "名称",
        "开始日期",
        "结束日期",
        "工期(天)",
        "进度(%)",
        "依赖项",
        "状态",
        "描述",
    ];
    let header_fmt = Format::new().set_bold();
    for (col, h) in headers.iter().enumerate() {
        sheet
            .write_with_format(0, col as u16, *h, &header_fmt)
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    for (idx, t) in data.tasks.iter().enumerate() {
        let row = (idx + 1) as u32;
        let indent = "  ".repeat(t.level.max(0) as usize);
        let name = format!("{indent}{}", t.name);
        sheet
            .write(row, 0, &t.id)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 1, &name)
            .map_err(|e| DbError::Other(e.to_string()))?;
        if let Some(d) = ms_to_date(t.start) {
            sheet
                .write(row, 2, d.as_str())
                .map_err(|e| DbError::Other(e.to_string()))?;
        }
        if let Some(d) = ms_to_date(t.end) {
            sheet
                .write(row, 3, d.as_str())
                .map_err(|e| DbError::Other(e.to_string()))?;
        }
        sheet
            .write(row, 4, t.duration.unwrap_or(0))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 5, t.progress)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 6, &t.depends)
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 7, t.status.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
        sheet
            .write(row, 8, t.description.as_deref().unwrap_or(""))
            .map_err(|e| DbError::Other(e.to_string()))?;
    }

    wb.save(path).map_err(|e| DbError::Other(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db;

    fn connect() -> Connection {
        let mut conn = Connection::open_in_memory().unwrap();
        // 与 db::open 一致：关闭外键强制（rusqlite 默认开启，Python/SQLAlchemy 默认关闭）
        conn.execute_batch("PRAGMA foreign_keys = OFF").unwrap();
        db::init_db(&mut conn).unwrap();
        conn
    }

    /// 建项目 + 插入一条总预算（对应 add_project_to_db 的最小集）
    fn seed_project(conn: &Connection, id: i64, name: &str) {
        conn.execute(
            "INSERT INTO projects (id, name, total_budget, start_date, end_date) \
             VALUES (?1, ?2, 100.0, '2026-01-01', '2026-12-31')",
            params![id, name],
        )
        .unwrap();
    }

    fn ms(y: i32, m: u32, d: u32) -> i64 {
        chrono::NaiveDate::from_ymd_opt(y, m, d)
            .unwrap()
            .and_hms_opt(0, 0, 0)
            .unwrap()
            .and_utc()
            .timestamp_millis()
    }

    /// 测试用最简任务（其余字段取常用默认值）
    fn dto(id: &str, name: &str, progress: f64, level: i64, depends: &str) -> GanttTaskDto {
        GanttTaskDto {
            id: id.into(), name: name.into(), progress,
            progress_by_worklog: false, relevance: 0, ty: String::new(),
            type_id: String::new(), description: None, code: None, level,
            status: Some("STATUS_ACTIVE".into()), depends: depends.into(),
            can_write: true, start: Some(ms(2026, 1, 1)), duration: Some(10),
            end: Some(ms(2026, 1, 11)), start_is_milestone: false,
            end_is_milestone: false, collapsed: false, assigs: vec![],
            has_child: false, responsible: None,
        }
    }

    fn project_data(tasks: Vec<GanttTaskDto>, deleted: Vec<String>) -> GanttProjectData {
        GanttProjectData {
            tasks, selected_row: 0, deleted_task_ids: deleted,
            resources: vec![], roles: vec![], can_write: true, can_delete: true,
            can_write_on_parent: true, can_add: true,
        }
    }

    #[test]
    fn load_empty_project_returns_empty() {
        let conn = connect();
        seed_project(&conn, 1, "空项目");
        let data = load_gantt_data(&conn, 1).unwrap();
        assert!(data.tasks.is_empty());
        assert_eq!(data.selected_row, -1);
        assert!(data.can_add);
    }

    #[test]
    fn save_then_load_round_trips() {
        let mut conn = connect();
        seed_project(&conn, 1, "项目A");

        let data = GanttProjectData {
            tasks: vec![
                GanttTaskDto {
                    id: "tmp_1".into(),
                    name: "立项准备".into(),
                    progress: 0.0,
                    progress_by_worklog: false,
                    relevance: 0,
                    ty: String::new(),
                    type_id: String::new(),
                    description: None,
                    code: None,
                    level: 0,
                    status: Some("STATUS_ACTIVE".into()),
                    depends: String::new(),
                    can_write: true,
                    start: Some(ms(2026, 1, 1)),
                    duration: Some(10),
                    end: Some(ms(2026, 1, 11)),
                    start_is_milestone: false,
                    end_is_milestone: false,
                    collapsed: false,
                    assigs: vec![],
                    has_child: true,
                    responsible: Some("张三".into()),
                },
                GanttTaskDto {
                    id: "tmp_2".into(),
                    name: "需求调研".into(),
                    progress: 50.0,
                    progress_by_worklog: false,
                    relevance: 0,
                    ty: String::new(),
                    type_id: String::new(),
                    description: None,
                    code: Some("T2".into()),
                    level: 1,
                    status: Some("STATUS_ACTIVE".into()),
                    depends: String::new(),
                    can_write: true,
                    start: Some(ms(2026, 1, 2)),
                    duration: Some(5),
                    end: Some(ms(2026, 1, 7)),
                    start_is_milestone: false,
                    end_is_milestone: false,
                    collapsed: false,
                    assigs: vec![],
                    has_child: false,
                    responsible: None,
                },
            ],
            selected_row: 0,
            deleted_task_ids: vec![],
            resources: vec![],
            roles: vec![],
            can_write: true,
            can_delete: true,
            can_write_on_parent: true,
            can_add: true,
        };

        let map = save_gantt_data(&mut conn, 1, &data).unwrap();
        assert_eq!(map.len(), 2);
        // 临时 id → 持久化 id（"1","2"）
        assert!(map.contains_key("tmp_1"));
        assert!(map.contains_key("tmp_2"));

        let loaded = load_gantt_data(&conn, 1).unwrap();
        assert_eq!(loaded.tasks.len(), 2);
        // 顺序与 order=0,1 一致
        assert_eq!(loaded.tasks[0].name, "立项准备");
        assert_eq!(loaded.tasks[1].name, "需求调研");
        assert_eq!(loaded.tasks[0].start, Some(ms(2026, 1, 1)));
        assert_eq!(loaded.tasks[1].progress, 50.0);
        // 持久化 id 已回填
        assert_eq!(loaded.tasks[0].id, "1");
        assert_eq!(loaded.tasks[1].id, "2");
    }

    #[test]
    fn save_dependencies_resolve_tmp_ids() {
        let mut conn = connect();
        seed_project(&conn, 1, "依赖项目");

        // 任务2 依赖 任务1（都先以 tmp_ 传入）
        let data = GanttProjectData {
            tasks: vec![
                GanttTaskDto {
                    id: "tmp_1".into(), name: "任务1".into(), progress: 0.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 0,
                    status: None, depends: String::new(), can_write: true,
                    start: Some(ms(2026, 2, 1)), duration: Some(3),
                    end: Some(ms(2026, 2, 4)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: false, responsible: None,
                },
                GanttTaskDto {
                    id: "tmp_2".into(), name: "任务2".into(), progress: 0.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 0,
                    status: None, depends: "tmp_1".into(), can_write: true,
                    start: Some(ms(2026, 2, 5)), duration: Some(4),
                    end: Some(ms(2026, 2, 9)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: false, responsible: None,
                },
            ],
            selected_row: 0, deleted_task_ids: vec![], resources: vec![], roles: vec![],
            can_write: true, can_delete: true, can_write_on_parent: true, can_add: true,
        };
        save_gantt_data(&mut conn, 1, &data).unwrap();

        // 检查依赖已持久化，且前驱是映射后的 "1"
        let dep: String = conn
            .query_row(
                "SELECT predecessor_gantt_id FROM gantt_dependencies WHERE project_id=1 AND successor_gantt_id='2'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(dep, "1");

        // 加载后任务2 的 depends 字符串为 "1"
        let loaded = load_gantt_data(&conn, 1).unwrap();
        assert_eq!(loaded.tasks[1].depends, "1");
    }

    #[test]
    fn save_recalculates_parent_progress() {
        let mut conn = connect();
        seed_project(&conn, 1, "父任务进度");

        // 父任务 duration=10，两个子任务 duration=6/4（总计10）
        // 子任务进度 100% + 0%，加权 = 100*6/10 = 60%
        let data = GanttProjectData {
            tasks: vec![
                GanttTaskDto {
                    id: "tmp_1".into(), name: "父任务".into(), progress: 0.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 0,
                    status: None, depends: String::new(), can_write: true,
                    start: Some(ms(2026, 3, 1)), duration: Some(10),
                    end: Some(ms(2026, 3, 11)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: true, responsible: None,
                },
                GanttTaskDto {
                    id: "tmp_2".into(), name: "子1".into(), progress: 100.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 1,
                    status: None, depends: String::new(), can_write: true,
                    start: Some(ms(2026, 3, 1)), duration: Some(6),
                    end: Some(ms(2026, 3, 7)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: false, responsible: None,
                },
                GanttTaskDto {
                    id: "tmp_3".into(), name: "子2".into(), progress: 0.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 1,
                    status: None, depends: String::new(), can_write: true,
                    start: Some(ms(2026, 3, 8)), duration: Some(4),
                    end: Some(ms(2026, 3, 12)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: false, responsible: None,
                },
            ],
            selected_row: 0, deleted_task_ids: vec![], resources: vec![], roles: vec![],
            can_write: true, can_delete: true, can_write_on_parent: true, can_add: true,
        };
        save_gantt_data(&mut conn, 1, &data).unwrap();

        // 父任务进度应为 60
        let parent_progress: f64 = conn
            .query_row("SELECT progress FROM gantt_tasks WHERE gantt_id='1'", [], |r| r.get(0))
            .unwrap();
        assert!((parent_progress - 60.0).abs() < 1e-6, "parent progress = {parent_progress}");
    }

    #[test]
    fn save_deletes_tasks_and_deps() {
        let mut conn = connect();
        seed_project(&conn, 1, "删除任务");

        // 先存两条带依赖
        let data = GanttProjectData {
            tasks: vec![
                GanttTaskDto {
                    id: "tmp_1".into(), name: "A".into(), progress: 0.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 0,
                    status: None, depends: String::new(), can_write: true,
                    start: Some(ms(2026, 4, 1)), duration: Some(2),
                    end: Some(ms(2026, 4, 3)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: false, responsible: None,
                },
                GanttTaskDto {
                    id: "tmp_2".into(), name: "B".into(), progress: 0.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 0,
                    status: None, depends: "tmp_1".into(), can_write: true,
                    start: Some(ms(2026, 4, 4)), duration: Some(2),
                    end: Some(ms(2026, 4, 6)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: false, responsible: None,
                },
            ],
            selected_row: 0, deleted_task_ids: vec![], resources: vec![], roles: vec![],
            can_write: true, can_delete: true, can_write_on_parent: true, can_add: true,
        };
        let map = save_gantt_data(&mut conn, 1, &data).unwrap();
        let id_b = map.get("tmp_2").unwrap().clone();

        // 现在删除任务 B（id_b），并保留 A
        let data2 = GanttProjectData {
            tasks: vec![
                GanttTaskDto {
                    id: "1".into(), name: "A".into(), progress: 0.0,
                    progress_by_worklog: false, relevance: 0, ty: String::new(),
                    type_id: String::new(), description: None, code: None, level: 0,
                    status: None, depends: String::new(), can_write: true,
                    start: Some(ms(2026, 4, 1)), duration: Some(2),
                    end: Some(ms(2026, 4, 3)), start_is_milestone: false,
                    end_is_milestone: false, collapsed: false, assigs: vec![],
                    has_child: false, responsible: None,
                },
            ],
            selected_row: 0,
            deleted_task_ids: vec![id_b.clone()],
            resources: vec![], roles: vec![],
            can_write: true, can_delete: true, can_write_on_parent: true, can_add: true,
        };
        save_gantt_data(&mut conn, 1, &data2).unwrap();

        // B 任务应被删，依赖也应被删
        let remain: i64 = conn
            .query_row("SELECT COUNT(*) FROM gantt_tasks WHERE project_id=1", [], |r| r.get(0))
            .unwrap();
        assert_eq!(remain, 1);
        let deps: i64 = conn
            .query_row("SELECT COUNT(*) FROM gantt_dependencies WHERE project_id=1", [], |r| r.get(0))
            .unwrap();
        assert_eq!(deps, 0);
    }

    #[test]
    fn gantt_crud_writes_actionlog() {
        let mut conn = connect();
        seed_project(&conn, 1, "甘特日志项目");
        // seed 时写入一条项目日志会与任务日志混排，这里只关心 type="任务" 的日志

        // 第一次保存：两天新任务 → 2 条"新增"
        let map = save_gantt_data(
            &mut conn,
            1,
            &project_data(
                vec![dto("tmp_1", "任务A", 0.0, 0, ""), dto("tmp_2", "任务B", 0.0, 1, "tmp_1")],
                vec![],
            ),
        )
        .unwrap();
        assert_eq!(map.get("tmp_1").unwrap(), "1");
        assert_eq!(map.get("tmp_2").unwrap(), "2");

        // 第二次保存：任务A 改名+进度（→"编辑"）、任务B 不变（无日志）、新增任务C（→"新增"）
        let mut edited_a = dto("1", "任务A", 0.0, 0, "");
        edited_a.name = "任务A改".into();
        edited_a.progress = 50.0;
        save_gantt_data(
            &mut conn,
            1,
            &project_data(
                vec![edited_a, dto("2", "任务B", 0.0, 1, "1"), dto("tmp_3", "任务C", 0.0, 0, "")],
                vec![],
            ),
        )
        .unwrap();

        // 第三次保存：任务C 位置前移（order 1→2，触发"编辑"）、删除任务B（→"删除"）
        save_gantt_data(
            &mut conn,
            1,
            &project_data(
                vec![dto("1", "任务A改", 50.0, 0, ""), dto("3", "任务C", 0.0, 0, "")],
                vec!["2".into()],
            ),
        )
        .unwrap();

        // 校验全部"任务"日志：6 条，动作序列 = 新增/新增/编辑/新增/删除/编辑
        // （第三次保存先删后改，故删除 B 排在编辑 C 之前）
        let logs: Vec<(Option<i64>, String, String, Option<String>, Option<String>)> = {
            let mut stmt = conn
                .prepare(
                    "SELECT gantt_task_id, action, description, old_data, new_data \
                     FROM actionlogs WHERE type='任务' ORDER BY id",
                )
                .unwrap();
            let rows = stmt
                .query_map([], |r| {
                    Ok((
                        r.get::<_, Option<i64>>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, String>(2)?,
                        r.get::<_, Option<String>>(3)?,
                        r.get::<_, Option<String>>(4)?,
                    ))
                })
                .unwrap();
            rows.collect::<rusqlite::Result<_>>().unwrap()
        };

        let actions: Vec<&str> = logs.iter().map(|l| l.1.as_str()).collect();
        assert_eq!(actions, ["新增", "新增", "编辑", "新增", "删除", "编辑"]);

        // 新增 A / 新增 B：关联 DB id 1、2
        assert_eq!(logs[0].0, Some(1));
        assert!(logs[0].3.is_none() && logs[0].4.is_some());
        assert_eq!(logs[1].0, Some(2));
        assert!(logs[1].4.as_deref().unwrap().contains("任务B"));

        // 编辑 A：old_data 为旧值、new_data 为新值，gantt_task_id=1
        assert_eq!(logs[2].0, Some(1));
        assert!(logs[2].3.as_deref().unwrap().contains("\"name\":\"任务A\""));
        assert!(logs[2].4.as_deref().unwrap().contains("\"name\":\"任务A改\""));
        assert!(logs[2].4.as_deref().unwrap().contains("\"progress\":50.0"));
        assert_eq!(logs[2].2, "编辑任务：任务A改 (ID: 1)");

        // 新增 C：gantt_task_id=3，new_data 含任务C
        assert_eq!(logs[3].0, Some(3));
        assert!(logs[3].4.as_deref().unwrap().contains("任务C"));

        // 删除 B：old_data 含任务B，gantt_task_id=2
        assert_eq!(logs[4].0, Some(2));
        assert!(logs[4].3.as_deref().unwrap().contains("任务B"));
        assert!(logs[4].4.is_none());

        // 编辑 C：order 前移触发的"编辑"，gantt_task_id=3
        assert_eq!(logs[5].0, Some(3));
        assert_eq!(logs[5].2, "编辑任务：任务C (ID: 3)");
    }

    #[test]
    fn clear_project_gantt_removes_all() {
        let mut conn = connect();
        seed_project(&conn, 1, "清理项目");
        let data = GanttProjectData {
            tasks: vec![GanttTaskDto {
                id: "tmp_1".into(), name: "唯一任务".into(), progress: 0.0,
                progress_by_worklog: false, relevance: 0, ty: String::new(),
                type_id: String::new(), description: None, code: None, level: 0,
                status: None, depends: String::new(), can_write: true,
                start: Some(ms(2026, 5, 1)), duration: Some(1),
                end: Some(ms(2026, 5, 2)), start_is_milestone: false,
                end_is_milestone: false, collapsed: false, assigs: vec![],
                has_child: false, responsible: None,
            }],
            selected_row: 0, deleted_task_ids: vec![], resources: vec![], roles: vec![],
            can_write: true, can_delete: true, can_write_on_parent: true, can_add: true,
        };
        save_gantt_data(&mut conn, 1, &data).unwrap();

        clear_project_gantt(&conn, 1).unwrap();
        let remain: i64 = conn
            .query_row("SELECT COUNT(*) FROM gantt_tasks WHERE project_id=1", [], |r| r.get(0))
            .unwrap();
        assert_eq!(remain, 0);
    }

    #[test]
    fn export_four_formats() {
        let conn = connect();
        seed_project(&conn, 1, "导出项目");
        let data = GanttProjectData {
            tasks: vec![GanttTaskDto {
                id: "tmp_1".into(), name: "立项准备".into(), progress: 60.0,
                progress_by_worklog: false, relevance: 0, ty: String::new(),
                type_id: String::new(), description: Some("描述,含逗号\"引号\"".into()),
                code: None, level: 0, status: Some("STATUS_ACTIVE".into()),
                depends: String::new(), can_write: true,
                start: Some(ms(2026, 1, 1)), duration: Some(10),
                end: Some(ms(2026, 1, 11)), start_is_milestone: false,
                end_is_milestone: false, collapsed: false, assigs: vec![],
                has_child: false, responsible: None,
            }],
            selected_row: 0, deleted_task_ids: vec![], resources: vec![], roles: vec![],
            can_write: true, can_delete: true, can_write_on_parent: true, can_add: true,
        };

        let dir = tempfile::tempdir().unwrap();

        // 导出日期使用本地时区，与 Python `datetime.fromtimestamp` 一致，
        // 故用同样的换算生成期望值（保证任何时区下断言都正确）
        let expect_start = ms_to_date(Some(ms(2026, 1, 1))).unwrap();

        let json_p = dir.path().join("g.json");
        export_gantt_file(&json_p, &data).unwrap();
        let json_txt = std::fs::read_to_string(&json_p).unwrap();
        assert!(json_txt.contains("立项准备"));
        assert!(json_txt.contains("STATUS_ACTIVE"));

        let csv_p = dir.path().join("g.csv");
        export_gantt_file(&csv_p, &data).unwrap();
        let csv_bytes = std::fs::read(&csv_p).unwrap();
        // utf-8-sig BOM
        assert_eq!(&csv_bytes[..3], &[0xEF, 0xBB, 0xBF]);
        let csv_txt = String::from_utf8(csv_bytes).unwrap();
        assert!(csv_txt.contains("\"立项准备\""));
        assert!(csv_txt.contains(&expect_start));
        // 引号被翻倍转义
        assert!(csv_txt.contains("\"描述,含逗号\"\"引号\"\"\""));

        let txt_p = dir.path().join("g.txt");
        export_gantt_file(&txt_p, &data).unwrap();
        let txt = std::fs::read_to_string(&txt_p).unwrap();
        assert!(txt.contains("名称: 立项准备"));
        assert!(txt.contains("进度: 60%"));

        let xlsx_p = dir.path().join("g.xlsx");
        export_gantt_file(&xlsx_p, &data).unwrap();
        // 无扩展名默认走 Excel
        let noext_p = dir.path().join("g");
        export_gantt_file(&noext_p, &data).unwrap();
        assert!(xlsx_p.exists() && noext_p.exists());
        assert!(xlsx_p.metadata().unwrap().len() > 0);
    }
}