//! 操作日志（对应 Python 各视图内联的 Actionlog 写入逻辑，阶段 1 后期实现）
//!
//! 计划实现：
//! - `log_action`：写入 actionlogs（type/action/description/operator/old_data/new_data/category/amount/related_info）
//! - 变更 diff 生成（JSON 字段级对比，对应 `help_interface.find_diff`）
