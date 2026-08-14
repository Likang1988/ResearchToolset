//! 科研工具集核心库（Rust 迁移）
//!
//! 与 UI 完全解耦的数据层与业务逻辑，对应 Python 版：
//! - `app/models/database.py`（schema / 迁移 / 模型）
//! - `app/utils/`（附件、筛选等工具）
//! - `app/tools/IndirectCostCalculator.py`（业务算法）
//!
//! 验收依据见 `docs/migration/feature-checklist.md`。

pub mod attachments;
pub mod db;
pub mod excel;
pub mod logging;
pub mod models;
pub mod services;

pub use db::init_db;

/// 核心库统一错误类型
#[derive(Debug, thiserror::Error)]
pub enum DbError {
    #[error("数据库错误: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON 错误: {0}")]
    Json(#[from] serde_json::Error),
}
