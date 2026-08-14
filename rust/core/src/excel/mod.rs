//! Excel 导入导出（阶段 1 后期实现）
//!
//! 对应 Python 版 pandas + openpyxl 的全部用法：
//! - 批量导入模板生成（含 DataValidation 下拉校验）
//! - 支出批量导入解析（xlsx/csv）
//! - 支出导出（含下拉校验列）
//! - 预算编制导出（明细/汇总/分年度比例）
//! - 文档/成果/活动导出
//!
//! 读：calamine；写：rust_xlsxwriter
