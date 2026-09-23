//! 临时验证脚本：在真实 database/database.db 上跑 list_project_budgets(2)
//!
//! 用法：cargo run --example dump_project2_budget [数据库路径]
//! 不带参数时使用仓库根 database/database.db。
use research_toolset_core::db;
use research_toolset_core::services::budget::list_project_budgets;

fn main() {
    let db_path = std::env::args()
        .nth(1)
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| {
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .expect("仓库根应存在")
                .join("database")
                .join("database.db")
        });
    let mut conn = db::open(&db_path).expect("open db");
    db::init_db(&mut conn).expect("init_db");
    db::migrate::migrate_db(&mut conn).expect("migrate");

    let tree = list_project_budgets(&conn, 2).expect("list_project_budgets");
    match tree.total_budget {
        Some(ref t) => {
            println!(
                "[总预算] id={} total={} spent={}",
                t.id, t.total_amount, t.spent_amount
            );
            for it in &t.items {
                if it.amount.abs() > 1e-9 {
                    println!("  {}: amount={} (spent={})", it.category, it.amount, it.spent_amount);
                }
            }
        }
        None => println!("无总预算"),
    }
    println!("年度预算数: {}", tree.annual_budgets.len());
    for a in &tree.annual_budgets {
        println!(
            "[{}] id={} total={} spent={}",
            a.year.map(|y| y.to_string()).unwrap_or_else(|| "?".into()),
            a.id,
            a.total_amount,
            a.spent_amount
        );
        for it in &a.items {
            if it.amount.abs() > 1e-9 || it.spent_amount.abs() > 1e-9 {
                println!(
                    "    {}: amount={:.3} spent={:.3}",
                    it.category, it.amount, it.spent_amount
                );
            }
        }
    }
}
