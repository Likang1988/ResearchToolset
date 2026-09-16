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
///
/// 额外设置：
/// - `journal_mode = DELETE`：使用回滚日志模式，事务提交后 journal 文件即删除，
///   不会像 WAL 模式那样残留 `database.db-wal` / `database.db-shm`。
///   本项目为单连接 Mutex 串行访问，无需 WAL 的并发读能力。
///   （若在云同步盘上遇到 journal 占用导致的 IO 错误，可改回 WAL。）
/// - `busy_timeout`：避免并发连接撞锁时报 SQLITE_BUSY。
pub fn open(db_path: &Path) -> Result<Connection, DbError> {
    let conn = Connection::open(db_path)?;
    conn.execute_batch("PRAGMA foreign_keys = OFF")?;
    conn.execute_batch("PRAGMA journal_mode = DELETE")?;
    conn.execute_batch("PRAGMA busy_timeout = 5000")?;
    Ok(conn)
}

/// init_db 等价物：打开连接并补建缺失表（已有表不动）。
pub fn init_db(conn: &mut Connection) -> Result<(), DbError> {
    schema::create_all(conn)
}

/// 开启新事务的自愈入口。
///
/// 若连接上残留未提交事务（例如先前某个命令在事务中异常中断），
/// 直接 `execute_batch("BEGIN")` 会报
/// “cannot start a transaction within a transaction”；
/// 这里先回滚残留事务再重新 BEGIN，保证各命令相互隔离、出错自愈。
pub(crate) fn begin_tx(conn: &Connection) -> Result<(), DbError> {
    if !conn.is_autocommit() {
        // 残留事务必须成功回滚，否则连接状态未知，后续全部写/读都会异常
        conn.execute_batch("ROLLBACK")?;
    }
    conn.execute_batch("BEGIN")?;
    Ok(())
}
