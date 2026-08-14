//! 迁移对照验证工具（Rust 侧）：
//! `cargo run --example migrate_check -- <db_path>`
//! 对目标库执行 init_db + migrate_db 等价操作（与 Python 侧 py_migrate_check.py 对照）

use research_toolset_core::db::{migrate, schema};
use research_toolset_core::DbError;
use std::path::PathBuf;

fn main() -> Result<(), DbError> {
    let path = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .expect("用法: migrate_check <db_path>");
    let mut conn = research_toolset_core::db::open(&path)?;
    schema::create_all(&mut conn)?; // init_db 等价
    migrate::migrate_db(&mut conn)?; // migrate_db 等价
    println!("Rust migration done: {}", path.display());
    Ok(())
}
