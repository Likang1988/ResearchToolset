//! 数据模型：12 张表的结构体与枚举
//!
//! 字段与 `tests/golden/schema.sql` 逐字一致。
//! 日期/时间列以字符串存储（SQLite 实际存储格式），金额用 Option<f64>（schema 可空）。
//! 枚举 **存储层（budget_items.category）用英文 KEY**（EQUIPMENT/MATERIAL/…），
//! 展示层用中文（设备费/材料费/…）。因此：
//! - DB 查询/写入时使用 `storage_key()`（英文 KEY）
//! - 展示/serde 输出到前端时使用 `label()`（中文）
//! 注意：写入 DB 的是枚举名（如 EQUIPMENT）而非中文 label（如 "设备费"），
//! 与既有数据库核对证实如此。

use serde::{Deserialize, Serialize};

/// 预算费用类别（10 类）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum BudgetCategory {
    #[serde(rename = "设备费")]
    Equipment,
    #[serde(rename = "材料费")]
    Material,
    #[serde(rename = "外协费")]
    Outsourcing,
    #[serde(rename = "燃动费")]
    Fuel,
    #[serde(rename = "会议差旅费")]
    Conference,
    #[serde(rename = "出版文献费")]
    Publication,
    #[serde(rename = "劳务费")]
    Labor,
    #[serde(rename = "专家咨询费")]
    Consulting,
    #[serde(rename = "其他支出")]
    Miscellaneous,
    #[serde(rename = "间接费用")]
    Indirect,
}

impl BudgetCategory {
    pub const ALL: [BudgetCategory; 10] = [
        BudgetCategory::Equipment,
        BudgetCategory::Material,
        BudgetCategory::Outsourcing,
        BudgetCategory::Fuel,
        BudgetCategory::Conference,
        BudgetCategory::Publication,
        BudgetCategory::Labor,
        BudgetCategory::Consulting,
        BudgetCategory::Miscellaneous,
        BudgetCategory::Indirect,
    ];

    /// 展示层中文名（表格列、前端图例用）
    pub fn label(self) -> &'static str {
        match self {
            BudgetCategory::Equipment => "设备费",
            BudgetCategory::Material => "材料费",
            BudgetCategory::Outsourcing => "外协费",
            BudgetCategory::Fuel => "燃动费",
            BudgetCategory::Conference => "会议差旅费",
            BudgetCategory::Publication => "出版文献费",
            BudgetCategory::Labor => "劳务费",
            BudgetCategory::Consulting => "专家咨询费",
            BudgetCategory::Miscellaneous => "其他支出",
            BudgetCategory::Indirect => "间接费用",
        }
    }

    /// 存储层英文 KEY（budget_items.category 实际写入的字符串）
    pub fn storage_key(self) -> &'static str {
        match self {
            BudgetCategory::Equipment => "EQUIPMENT",
            BudgetCategory::Material => "MATERIAL",
            BudgetCategory::Outsourcing => "OUTSOURCING",
            BudgetCategory::Fuel => "FUEL",
            BudgetCategory::Conference => "CONFERENCE",
            BudgetCategory::Publication => "PUBLICATION",
            BudgetCategory::Labor => "LABOR",
            BudgetCategory::Consulting => "CONSULTING",
            BudgetCategory::Miscellaneous => "MISCELLANEOUS",
            BudgetCategory::Indirect => "INDIRECT",
        }
    }

    /// 旧别名：兼容还没改过来的调用点。推荐直接用 `label()` 或 `storage_key()`
    pub fn as_str(self) -> &'static str {
        self.label()
    }

    /// 从中文 label（如「设备费」）反查枚举；找不到返回 None
    pub fn from_label(label: &str) -> Option<BudgetCategory> {
        Self::ALL.iter().find(|c| c.label() == label).copied()
    }

    /// 从存储英文 KEY（如「EQUIPMENT」）反查枚举；找不到返回 None
    pub fn from_storage_key(key: &str) -> Option<BudgetCategory> {
        Self::ALL
            .iter()
            .find(|c| c.storage_key() == key)
            .copied()
    }
}

/// 文档类型（DocumentType）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DocumentType {
    #[serde(rename = "申请材料")]
    Application,
    #[serde(rename = "开题材料")]
    Initiation,
    #[serde(rename = "合同/任务书")]
    Contract,
    #[serde(rename = "研究数据")]
    ResearchData,
    #[serde(rename = "进展报告")]
    Progress,
    #[serde(rename = "外协材料")]
    Outsourcing,
    #[serde(rename = "质量管理")]
    Quality,
    #[serde(rename = "结题材料")]
    Finalization,
    #[serde(rename = "会议纪要")]
    Meeting,
    #[serde(rename = "其他")]
    Other,
}

/// 成果类型（OutcomeType）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OutcomeType {
    #[serde(rename = "论文")]
    Paper,
    #[serde(rename = "专利")]
    Patent,
    #[serde(rename = "软著")]
    Software,
    #[serde(rename = "标准")]
    Standard,
    #[serde(rename = "获奖")]
    Award,
    #[serde(rename = "其他")]
    Other,
}

/// 成果状态（OutcomeStatus）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OutcomeStatus {
    #[serde(rename = "草稿")]
    Draft,
    #[serde(rename = "已提交")]
    Submitted,
    #[serde(rename = "已接收")]
    Accepted,
    #[serde(rename = "已发表/授权")]
    Published,
    #[serde(rename = "已拒绝")]
    Rejected,
}

/// 学术活动类型（ActivityType）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActivityType {
    #[serde(rename = "学术会议")]
    Conference,
    #[serde(rename = "学术讲座")]
    Lecture,
    #[serde(rename = "培训活动")]
    Training,
    #[serde(rename = "研讨会")]
    Seminar,
    #[serde(rename = "工作坊")]
    Workshop,
    #[serde(rename = "学术交流")]
    Exchange,
    #[serde(rename = "其他")]
    Other,
}

/// 学术活动状态（ActivityStatus）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActivityStatus {
    #[serde(rename = "未开始")]
    Planned,
    #[serde(rename = "进行中")]
    Ongoing,
    #[serde(rename = "已结束")]
    Completed,
    #[serde(rename = "已取消")]
    Cancelled,
}

// ─────────────────────────── 12 张表的结构体 ───────────────────────────

/// projects
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Project {
    pub id: i64,
    pub name: String,
    pub financial_code: Option<String>,
    pub project_code: Option<String>,
    pub project_type: Option<String>,
    pub leader: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub total_budget: Option<f64>,
    pub director: Option<String>,
}

impl Project {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(Project {
            id: row.get("id")?,
            name: row.get("name")?,
            financial_code: row.get("financial_code")?,
            project_code: row.get("project_code")?,
            project_type: row.get("project_type")?,
            leader: row.get("leader")?,
            start_date: row.get("start_date")?,
            end_date: row.get("end_date")?,
            total_budget: row.get("total_budget")?,
            director: row.get("director")?,
        })
    }
}

/// budgets（year=NULL 表示总预算）
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Budget {
    pub id: i64,
    pub project_id: i64,
    pub year: Option<i64>,
    pub total_amount: Option<f64>,
    pub spent_amount: Option<f64>,
}

impl Budget {
    pub fn is_total_budget(&self) -> bool {
        self.year.is_none()
    }

    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(Budget {
            id: row.get("id")?,
            project_id: row.get("project_id")?,
            year: row.get("year")?,
            total_amount: row.get("total_amount")?,
            spent_amount: row.get("spent_amount")?,
        })
    }
}

/// budget_items
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BudgetItem {
    pub id: i64,
    pub budget_id: i64,
    pub category: String,
    pub amount: Option<f64>,
    pub spent_amount: Option<f64>,
}

impl BudgetItem {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(BudgetItem {
            id: row.get("id")?,
            budget_id: row.get("budget_id")?,
            category: row.get("category")?,
            amount: row.get("amount")?,
            spent_amount: row.get("spent_amount")?,
        })
    }
}

/// budget_plans（预算编制主表，注意：无 project_id 字段）
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BudgetPlan {
    pub id: i64,
    pub name: String,
    pub create_date: Option<String>,
    pub total_amount: Option<f64>,
    pub remarks: Option<String>,
}

impl BudgetPlan {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(BudgetPlan {
            id: row.get("id")?,
            name: row.get("name")?,
            create_date: row.get("create_date")?,
            total_amount: row.get("total_amount")?,
            remarks: row.get("remarks")?,
        })
    }
}

/// budget_plan_items（parent_id 自引用构建树）
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BudgetPlanItem {
    pub id: i64,
    pub plan_id: i64,
    pub parent_id: Option<i64>,
    pub category: Option<String>,
    pub name: Option<String>,
    pub specification: Option<String>,
    pub unit_price: Option<f64>,
    pub quantity: Option<i64>,
    pub amount: Option<f64>,
    pub remarks: Option<String>,
}

impl BudgetPlanItem {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(BudgetPlanItem {
            id: row.get("id")?,
            plan_id: row.get("plan_id")?,
            parent_id: row.get("parent_id")?,
            category: row.get("category")?,
            name: row.get("name")?,
            specification: row.get("specification")?,
            unit_price: row.get("unit_price")?,
            quantity: row.get("quantity")?,
            amount: row.get("amount")?,
            remarks: row.get("remarks")?,
        })
    }
}

/// expenses
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Expense {
    pub id: i64,
    pub project_id: i64,
    pub budget_id: i64,
    pub category: String,
    pub content: String,
    pub specification: Option<String>,
    pub supplier: Option<String>,
    pub amount: Option<f64>,
    pub date: Option<String>,
    pub remarks: Option<String>,
    pub voucher_path: Option<String>,
}

impl Expense {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(Expense {
            id: row.get("id")?,
            project_id: row.get("project_id")?,
            budget_id: row.get("budget_id")?,
            category: row.get("category")?,
            content: row.get("content")?,
            specification: row.get("specification")?,
            supplier: row.get("supplier")?,
            amount: row.get("amount")?,
            date: row.get("date")?,
            remarks: row.get("remarks")?,
            voucher_path: row.get("voucher_path")?,
        })
    }
}

/// gantt_tasks
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GanttTask {
    pub id: i64,
    pub project_id: i64,
    pub gantt_id: String,
    pub name: String,
    pub code: Option<String>,
    pub level: Option<i64>,
    pub status: Option<String>,
    pub start_date: Option<String>,
    pub duration: Option<i64>,
    pub end_date: Option<String>,
    pub start_is_milestone: Option<bool>,
    pub end_is_milestone: Option<bool>,
    pub progress: Option<f64>,
    pub progress_by_worklog: Option<bool>,
    pub description: Option<String>,
    pub collapsed: Option<bool>,
    pub has_child: Option<bool>,
    pub responsible: Option<String>,
    pub order: Option<i64>,
}

impl GanttTask {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(GanttTask {
            id: row.get("id")?,
            project_id: row.get("project_id")?,
            gantt_id: row.get("gantt_id")?,
            name: row.get("name")?,
            code: row.get("code")?,
            level: row.get("level")?,
            status: row.get("status")?,
            start_date: row.get("start_date")?,
            duration: row.get("duration")?,
            end_date: row.get("end_date")?,
            start_is_milestone: row.get("start_is_milestone")?,
            end_is_milestone: row.get("end_is_milestone")?,
            progress: row.get("progress")?,
            progress_by_worklog: row.get("progress_by_worklog")?,
            description: row.get("description")?,
            collapsed: row.get("collapsed")?,
            has_child: row.get("has_child")?,
            responsible: row.get("responsible")?,
            order: row.get("order")?,
        })
    }
}

/// gantt_dependencies
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct GanttDependency {
    pub id: i64,
    pub project_id: i64,
    pub predecessor_gantt_id: String,
    pub successor_gantt_id: String,
    pub r#type: Option<String>,
}

impl GanttDependency {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(GanttDependency {
            id: row.get("id")?,
            project_id: row.get("project_id")?,
            predecessor_gantt_id: row.get("predecessor_gantt_id")?,
            successor_gantt_id: row.get("successor_gantt_id")?,
            r#type: row.get("type")?,
        })
    }
}

/// project_documents
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProjectDocument {
    pub id: i64,
    pub project_id: i64,
    pub name: String,
    pub doc_type: String,
    pub version: Option<String>,
    pub description: Option<String>,
    pub file_path: Option<String>,
    pub upload_time: Option<String>,
    pub keywords: Option<String>,
}

impl ProjectDocument {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(ProjectDocument {
            id: row.get("id")?,
            project_id: row.get("project_id")?,
            name: row.get("name")?,
            doc_type: row.get("doc_type")?,
            version: row.get("version")?,
            description: row.get("description")?,
            file_path: row.get("file_path")?,
            upload_time: row.get("upload_time")?,
            keywords: row.get("keywords")?,
        })
    }
}

/// project_outcome（单数表名）
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ProjectOutcome {
    pub id: i64,
    pub project_id: i64,
    pub name: String,
    pub r#type: String,
    pub status: Option<String>,
    pub authors: Option<String>,
    pub submit_date: Option<String>,
    pub publish_date: Option<String>,
    pub journal: Option<String>,
    pub description: Option<String>,
    pub remarks: Option<String>,
    pub attachment_path: Option<String>,
}

impl ProjectOutcome {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(ProjectOutcome {
            id: row.get("id")?,
            project_id: row.get("project_id")?,
            name: row.get("name")?,
            r#type: row.get("type")?,
            status: row.get("status")?,
            authors: row.get("authors")?,
            submit_date: row.get("submit_date")?,
            publish_date: row.get("publish_date")?,
            journal: row.get("journal")?,
            description: row.get("description")?,
            remarks: row.get("remarks")?,
            attachment_path: row.get("attachment_path")?,
        })
    }
}

/// academic_activities
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AcademicActivity {
    pub id: i64,
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

impl AcademicActivity {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(AcademicActivity {
            id: row.get("id")?,
            name: row.get("name")?,
            r#type: row.get("type")?,
            status: row.get("status")?,
            organizer: row.get("organizer")?,
            start_date: row.get("start_date")?,
            end_date: row.get("end_date")?,
            location: row.get("location")?,
            participants: row.get("participants")?,
            description: row.get("description")?,
            attachment_path: row.get("attachment_path")?,
        })
    }
}

/// actionlogs（操作日志）
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Actionlog {
    pub id: i64,
    pub project_id: Option<i64>,
    pub budget_id: Option<i64>,
    pub expense_id: Option<i64>,
    pub gantt_task_id: Option<i64>,
    pub project_document_id: Option<i64>,
    pub project_outcome_id: Option<i64>,
    pub r#type: String,
    pub action: String,
    pub description: String,
    pub operator: String,
    pub timestamp: Option<String>,
    pub old_data: Option<String>,
    pub new_data: Option<String>,
    pub category: Option<String>,
    pub amount: Option<f64>,
    pub related_info: Option<String>,
}

impl Actionlog {
    pub fn from_row(row: &rusqlite::Row) -> rusqlite::Result<Self> {
        Ok(Actionlog {
            id: row.get("id")?,
            project_id: row.get("project_id")?,
            budget_id: row.get("budget_id")?,
            expense_id: row.get("expense_id")?,
            gantt_task_id: row.get("gantt_task_id")?,
            project_document_id: row.get("project_document_id")?,
            project_outcome_id: row.get("project_outcome_id")?,
            r#type: row.get("type")?,
            action: row.get("action")?,
            description: row.get("description")?,
            operator: row.get("operator")?,
            timestamp: row.get("timestamp")?,
            old_data: row.get("old_data")?,
            new_data: row.get("new_data")?,
            category: row.get("category")?,
            amount: row.get("amount")?,
            related_info: row.get("related_info")?,
        })
    }
}
