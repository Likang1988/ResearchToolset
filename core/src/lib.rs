//! 科研工具集核心库
//!
//! 与 UI 完全解耦的数据层与业务逻辑：
//! - `db`：连接、建表与列级迁移
//! - `models` / `services`：数据模型与业务逻辑（含间接经费算法）
//! - `attachments` / `excel` / `logging`：附件、导入导出与操作日志

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
    #[error("{0}")]
    Other(String),
}
