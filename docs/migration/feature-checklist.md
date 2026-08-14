# ResearchToolset 功能对照清单（迁移验收依据）

> 版本：v1.5.0（git ad1ee6b）｜ 本清单是 Rust 迁移的唯一验收基准。
> 阶段标注：**P2~P4** = 首版（核心模块），**P5** = 第二迭代。
> 每项验收时在状态列标记 ✅ 一致 / ⚠️ 有差异（附说明） / ❌ 缺失。

## 0. 数据层与业务函数（P1，先于所有 UI）

### 0.1 数据库初始化与迁移
- [ ] `init_db` 语义：每次启动无条件执行 `create_all` 等价操作（**补建缺失表**，不重建已有表）
- [ ] `migrate_db` 语义复刻（含既有缺陷，见 §9），迁移后 schema 与 golden 一致：
  - [ ] gantt_tasks：缺 `responsible` 补列 VARCHAR(50)；缺 `"order"` 补列 INTEGER DEFAULT 0
  - [ ] project_outcomes（复数，Python 缺陷：实际表为单数，永不命中）——保持不执行
  - [ ] projects：缺 `director` 补列 VARCHAR(50)
  - [ ] expenses：缺 `voucher_path` → 建临时表→复制→DROP→RENAME（临时表**无外键**，复刻此缺陷）
  - [ ] actionlogs：`timestamp` 类型非 DATETIME 或缺 old_data/new_data/category/amount/related_info/gantt_task_id/project_document_id/project_outcome_id → 全表重建（复刻：临时表外键指向 `project_outcomes` 复数表名；timestamp 用 `datetime()` 函数规范化）
  - [ ] budget_plan_items：按 expected_columns 逐列补缺（plan_id/parent_id/category/name/specification/unit_price/quantity/amount/remarks）
- [ ] 空库（不存在 database.db）→ 建全 12 表；旧库（legacy_data.db / golden_data.db 样本）→ 迁移后与当前 schema 完全一致
- [ ] 数据库路径：源码模式取可执行文件/项目根目录下 `database/database.db`；打包模式取可执行文件旁

### 0.2 数据模型（12 表 + 枚举，字段与 golden schema.sql 逐字一致）
- [ ] projects / budgets（uix_project_year 唯一约束 ON CONFLICT FAIL）/ budget_items
- [ ] budget_plans / budget_plan_items（parent_id 自引用）
- [ ] expenses（含 voucher_path）
- [ ] gantt_tasks（uix_project_gantt_id + ix_gantt_tasks_gantt_id 索引）/ gantt_dependencies（uix_project_dependency）
- [ ] actionlogs（6 个外键）/ project_documents / project_outcome / academic_activities
- [ ] 枚举取值（与库中存储字符串一致）：
  - [ ] BudgetCategory（10 类）：设备费/材料费/外协费/燃动费/会议差旅费/出版文献费/劳务费/专家咨询费/其他支出/间接费用
  - [ ] DocumentType（10 类）：申请材料/开题材料/合同、任务书/研究数据/进展报告/外协材料/质量管理/结题材料/会议纪要/其他
  - [ ] OutcomeType（6 类）：论文/专利/软著/标准/获奖/其他
  - [ ] OutcomeStatus（5 类）：草稿/已提交/已接收/已发表、授权/已拒绝
  - [ ] ActivityType（7 类）：学术会议/学术讲座/培训活动/研讨会/工作坊/学术交流/其他
  - [ ] ActivityStatus（4 类）：未开始/进行中/已结束/已取消

### 0.3 核心业务函数
- [ ] `get_budget_usage(project_id, budget_id=None)`：total_budget（year IS NULL）/ total_spent（SUM expenses.amount）/ remaining / category_spent（按 10 类分别 SUM）；无总预算时返回全 0 结构
- [ ] `add_project_to_db`：建项目 → 自动创建总预算（year=NULL，amount 0）→ 自动创建 10 个 BudgetItem（amount=0，spent=0）→ 返回项目 id
- [ ] 间接经费二分法计算器（费率阶梯：500 万以内 20% / 1000 万以内 15% / 以上 13%，二分求最大间接经费）

## 1. 主页（P2）

- [ ] 顶部 header.png 背景图，左右两栏 ScrollArea
- [ ] 左栏：项目经费概览卡片（财务编号/总预算/总支出/执行率），每项目一张卡片
- [ ] 右栏：任务进度概览卡片（甘特任务进度）
- [ ] 点击卡片跳转到对应项目经费/进度页并加载该项目数据（main_window.stackedWidget 切换）
- [ ] 项目/预算/支出/进度变更后刷新（project_updated / budget_or_expense_updated / progress_updated 事件）
- [ ] 无项目时显示空态

## 2. 项目清单（P2）

- [ ] 8 列表格：名称/财务编号/项目编号/类别/负责人/开始日期/结束日期/总经费
- [ ] 新增项目对话框（ProjectDialog）：名称/财务编号/项目编号/类别（下拉）/负责人/起止日期/总经费；类别下拉记忆历史输入；保存校验
- [ ] 编辑项目对话框（同表单回填）
- [ ] 删除项目：确认提示；**级联删除**预算/支出/甘特/文档/成果等关联记录 + 清理 documents/、vouchers/ 附件目录；写 Actionlog
- [ ] 右键菜单：复制行数据（复制到剪贴板）
- [ ] 项目数据 JSON 导出（含全部关联数据）
- [ ] 项目数据 JSON 导入（重建项目及关联）
- [ ] 变更后发 project_list_updated → 全局 project_updated 事件（联动其他页刷新项目下拉框）
- [ ] 每次增删改写 Actionlog（type=项目, old_data/new_data JSON）

## 3. 项目经费（P3）

- [ ] 项目下拉框切换项目
- [ ] 左侧预算树形表（QSplitter 分栏）：总预算（year=NULL）/年度预算（各年份）/费用类别三级结构
- [ ] 列：类别/预算额/支出额/结余额/执行率（进度条 delegate：0→100% 浅绿→浅红线性插值，超 100% 红色）
- [ ] 新增/编辑/删除年度预算（BudgetDialog/TotalBudgetDialog）：10 类别 DoubleSpinBox 录入、结余校验
- [ ] 从"预算编制"导入预算计划（budget_plan_imported 信号）
- [ ] 执行率/结余计算（get_budget_usage 语义）
- [ ] 右侧饼图（QtCharts → ECharts）：类别分布/时间分布（年度/月度）两种视图切换；标签"金额万元+百分比"；空数据显示"暂无数据"
- [ ] 预算/支出变动发 budget_or_expense_updated 事件
- [ ] 写 Actionlog（预算类型）

## 4. 支出（P3）

- [ ] 9 列表格：类别/内容/规格/供应商/金额/日期/备注/凭证/操作
- [ ] 筛选栏：关键词/类别/金额区间/日期区间（FilterUtils 内存筛选）
- [ ] 新增/编辑对话框（ExpenseDialog）：类别下拉（10 类）、金额校验、凭证文件选择（*.pdf *.doc *.docx *.xls *.xlsx）
- [ ] 批量导入对话框（BatchImportDialog）：
  - [ ] 模板下载（xlsx，含 DataValidation 下拉校验）
  - [ ] 导入 xlsx/csv，校验必填列/空值/类别合法性，逐行报错提示
- [ ] 删除：确认；级联删凭证文件；写 Actionlog
- [ ] 凭证：上传（按 财务编号/年份/类别 目录结构拷贝）、查看（系统打开）、下载、替换、删除
- [ ] 分类统计表（下方，按类别汇总）
- [ ] 导出 Excel（含 DataValidation 下拉校验列）
- [ ] 凭证打包导出
- [ ] 排序（点击表头）
- [ ] 变更发 expense_updated / budget_or_expense_updated 事件；写 Actionlog（type=支出, old/new JSON, category, amount, related_info）

## 5. 预算编制（P4）

- [ ] 6 列可编辑三级 TreeWidget：类别/名称/型号规格/单价/数量/金额/备注
- [ ] 单价×数量自动算金额，父项金额递归汇总
- [ ] 新增同级/新增子级/删除（含子项级联）
- [ ] 保存到 DB（budget_plans + budget_plan_items）
- [ ] 导出：明细 / 汇总 / 分年度比例配置（BudgetExportDialog）
- [ ] 提供数据给经费页"从预算编制导入"（预算计划列表 + 明细导入）
- [ ] 写 Actionlog

## 6. 项目进度（甘特图）（P4）

- [ ] QWebEngineView → Tauri WebView + 复用 jQueryGantt 静态资源（app/integration/jQueryGantt/）
- [ ] 桥接层：QWebChannel → Tauri IPC（load_gantt_data / save_gantt_data / export_gantt_data）
- [ ] 任务：增删改、拖拽调整、里程碑、依赖连线（FS 等）、折叠
- [ ] 父任务进度按工期加权自动重算（Python 侧 project_progress.py:757-814 逻辑）
- [ ] 数据持久化：gantt_tasks + gantt_dependencies（gantt_id 字符串 ID）
- [ ] 导出：XLSX / JSON / CSV / TXT
- [ ] 变更发 progress_updated 事件；写 Actionlog

## 7. 项目文档 / 项目成果 / 学术活动（P5）

- [ ] 项目文档：7 列表格 + 关键词/类型筛选 + 附件（上传/查看/下载/删除）+ Excel 导出 + CRUD 对话框（DocumentDialog）+ Actionlog
- [ ] 项目成果：9 列表格（名称/类型/状态/作者/提交日期/发表日期/期刊/备注/附件）+ 筛选 + 附件 + Excel 导出 + CRUD + Actionlog
- [ ] 学术活动：9 列表格 + 关键词/类型/状态/日期筛选 + 附件 + Excel 导出 + ActivityDialog + Actionlog
- [ ] 附件统一走 attachment_utils 语义（目录结构 财务编号/年份/类别、拷贝/删除/下载/系统打开、Windows os.startfile / macOS open / Linux xdg-open）

## 8. 帮助页（P5）

- [ ] 三个展开卡片：软件简介 / 使用帮助 / 操作日志
- [ ] 操作日志表（100 条上限）：类型/动作/描述/操作人/时间/金额/相关信息
- [ ] 日志详情：old_data/new_data JSON 解析 + 字段级 diff 展示

## 9. 小工具（P5）

- [ ] 间接经费计算器（独立窗口，与 §0.3 算法一致）
- [ ] 树形列表工具（TreeList：增删同级/子级、批量添加、Excel/CSV/JSON 导入导出、层级合并单元格导出）

## 10. 全局行为

- [ ] 主窗口：Fluent 风格左侧导航栏 9 项（主页/项目清单/项目经费/项目进度/项目文档/项目成果/学术活动/预算编制/小工具/帮助[底部]），1200×800，微软雅黑 12px
- [ ] 统一样式源：ui_utils.py QSS（透明背景/圆角/hover/selected）移植为前端 CSS 组件
- [ ] 事件总线（替代 Qt 信号）：project_updated / activity_updated / budget_or_expense_updated / expense_updated / progress_updated / budget_plan_imported
- [ ] 日期处理：DATE 存 'YYYY-MM-DD'、DATETIME 存 ISO 格式，与 Python dateutil 输出一致
- [ ] 金额：FLOAT 双精度，显示保留 2 位，万元换算（饼图标签）
- [ ] 平台分支：Windows（os.startfile）/ macOS（open）文件打开
- [ ] 错误处理：数据库错误弹窗（db_utils.handle_db_error 语义），事务回滚

## 11. 已知缺陷（Python 现状，迁移先复刻，修复另行决策）

| # | 缺陷 | 位置 | 处理策略 |
|---|---|---|---|
| B1 | Project.director 列重复定义 | database.py L36/L38 | 库中仅一列，Rust 模型按实际库建模 |
| B2 | project_outcomes 复数表名迁移永不命中 | database.py L294/L445 | 复刻（不执行） |
| B3 | expenses 迁移重建丢外键/索引 | database.py L322-359 | 复刻 |
| B4 | actionlogs 临时表外键指向 project_outcomes（不存在的表） | database.py L408 | 复刻（SQLite 默认不强制外键，无实际影响） |
| B5 | generate_expense_template 重复 elif 分支 | L107-108 | 复刻时取前者 |
| B6 | 甘特图无条件开 8081 调试端口 | project_progress.py L101 | Rust 版直接不开调试端口（改进项，偏离需记录） |
| B7 | 无多线程，UI 同步阻塞 | 全局 | Rust 版用异步 command 但保持语义一致（改进项） |
| B8 | 当前 database.db 为空、数据在备份库 | 环境 | 迁移测试用 fixtures（不提交真实数据） |
| B9 | actionlogs 重建后二次 `transaction.commit()` 抛 InvalidRequestError，两表同时需重建时启动崩溃 | database.py L435 | **Rust 偏离**：后续 commit 降级 no-op，迁移可完成 |
| B10 | 无 commit 命中点时（仅 gantt_tasks/projects 补列）finally 回滚全部 ALTER，迁移实际无效 | database.py L504-507 | **Rust 偏离**：结束时提交未提交变更，迁移真正生效 |

## 12. 验收方式

1. 每模块：功能对照清单逐项走查（Python 版 vs Rust 版操作同一数据副本）
2. 数据层：golden 测试（§0.1），legacy_data.db / golden_data.db 迁移结果与 Python 版逐一 diff
3. 导出文件：openpyxl 旧导出 vs rust_xlsxwriter 新导出（内容、下拉校验、合并单元格）
4. 打包：Windows（NSIS/MSI）+ macOS（dmg）安装后可运行、可打开现有 database.db
