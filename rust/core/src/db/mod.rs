//! 数据库层：连接、建表（create_all 等价物）、迁移（migrate_db 等价物）
//!
//! 语义对齐 Python 版 `app/models/database.py`：
//! - `init_db`：连接 + 无条件补建缺失表（`Base.metadata.create_all` 等价物）
//! - `migrate_db`：列级迁移，**复刻既有行为（含缺陷）**，见 feature-checklist.md §11

pub mod migrate;
pub mod schema;

use rusqlite::Connection;
use std::path::Path;

use crate::DbError;

/// 打开数据库连接。
///
/// 与 SQLAlchemy pysqlite 行为对齐：**关闭外键强制**
/// （实测 SQLAlchemy 连接 `PRAGMA foreign_keys = 0`，Python 版依赖该默认值，
/// 如 expenses 迁移重建表时 DROP 父表不报错）。
/// 注意 rusqlite 默认开启外键，必须显式关闭。
pub fn open(db_path: &Path) -> Result<Connection, DbError> {
    let conn = Connection::open(db_path)?;
    conn.execute_batch("PRAGMA foreign_keys = OFF")?;
    Ok(conn)
}

/// init_db 等价物：打开连接并补建缺失表（已有表不动）。
pub fn init_db(conn: &mut Connection) -> Result<(), DbError> {
    schema::create_all(conn)
}
