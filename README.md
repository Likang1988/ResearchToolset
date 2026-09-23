# 科研工具集 ResearchToolset

科研项目全生命周期管理桌面应用，基于 **Rust / Tauri 2 + React** 构建。覆盖课题申报、预算编制、进度管控、成果归档等核心场景。

## 功能特性

| 模块 | 核心能力 |
|------|---------|
| **主页** | 项目经费概览卡片 + 任务进度面板，一键跳转各模块 |
| **项目清单** | 8 列表格 CRUD、右键复制行、JSON 导入导出、级联删除（预算/支出/甘特/文档/成果）+ 附件清理 |
| **项目经费** | 三级预算树、执行率进度条、ECharts 饼图（类别/时间分布）、预算编制数据导入、总预算科目点击查看跨年度支出明细 |
| **项目进度** | jQueryGantt 甘特图：任务增删改、拖拽排期、里程碑、依赖关系、XLSX/JSON/CSV 导出 |
| **项目文档** | 7 列表格、关键词/类型筛选、附件上传/查看/下载/删除、Excel 导出 |
| **项目成果** | 9 列表格（名称/类型/状态/作者/提交/发表/期刊/备注/附件）、筛选、Excel 导出 |
| **学术活动** | 9 列表格、关键词/类型/状态/日期筛选、附件管理、Excel 导出 |
| **预算编制** | 三级可编辑预算树、单价×数量联动、父项递归汇总、明细/汇总/分年度比例导出 |
| **小工具** | 间接经费二分法计算器（费率阶梯 20%/15%/13%）+ 树形列表工具（增删/批量/导入导出） |
| **设置** | 外观主题（浅色/深色/跟随系统）、数据库查看与切换、系统维护（一键重建支出统计）、软件简介、使用帮助、操作日志（100 条上限，JSON 字段级 diff） |

## 技术栈

### 前端

- **React 19** + **TypeScript 5.8** - 组件化 UI 开发
- **Vite 7** - 构建工具
- **Tauri 2 API** - 与 Rust 后端 IPC 通信
- Tauri 官方插件：`opener` / `dialog` / `fs` / `shell`

### 后端（Rust）

- **Tauri 2** - 桌面应用框架
- **rusqlite 0.37** - SQLite 数据库（bundled 编译，无需系统依赖）
- **serde / serde_json** - 数据序列化
- **chrono** - 日期时间处理
- **calamine 0.36** - Excel 读取
- **rust_xlsxwriter 0.97** - Excel 写入
- **thiserror 2** - 错误处理

### 核心库架构

数据层与业务逻辑完全解耦，封装在独立 crate `research-toolset-core` 中（UI 无关），可被 Tauri 壳与独立测试复用。

## 项目结构

```
ResearchToolset/
├── core/                          # 核心库（UI 无关）
│   ├── src/
│   │   ├── db/                    # 数据库：schema / migration / 初始化
│   │   ├── excel/                 # Excel 导入导出
│   │   ├── services/              # 业务服务层（12 个子模块）
│   │   │   ├── activity.rs        # 学术活动
│   │   │   ├── budget.rs          # 项目预算
│   │   │   ├── budget_plan.rs     # 预算编制
│   │   │   ├── document.rs        # 项目文档
│   │   │   ├── expense.rs         # 支出管理
│   │   │   ├── gantt.rs           # 甘特图/进度
│   │   │   ├── home.rs            # 主页聚合
│   │   │   ├── indirect_cost.rs   # 间接经费计算
│   │   │   ├── outcome.rs         # 项目成果
│   │   │   ├── project.rs         # 项目清单
│   │   │   └── tree_list.rs       # 树形列表
│   │   ├── attachments.rs         # 附件管理
│   │   ├── logging.rs             # 操作日志
│   │   ├── models.rs              # 数据模型
│   │   └── lib.rs
│   ├── examples/                  # 独立示例（迁移校验、数据导出）
│   └── Cargo.toml
├── src/                           # 前端 React 代码
│   ├── components/                # 可复用组件（对话框/图表等）
│   ├── pages/                     # 10 个页面组件
│   ├── data/                      # 导航/分类/事件配置
│   ├── styles/
│   ├── App.tsx
│   └── main.tsx
├── src-tauri/                     # Tauri 应用壳
│   ├── src/                       # lib.rs / main.rs
│   ├── icons/                     # 应用图标（全尺寸）
│   ├── capabilities/
│   ├── build.rs
│   ├── tauri.conf.json
│   └── Cargo.toml
├── public/                        # 静态资源
│   ├── gantt/                     # jQueryGantt 库文件
│   └── icons/                     # 导航 SVG 图标
├── database/                      # 开发环境数据库
├── tests/                         # 集成测试
│   ├── fixtures/                  # 测试用数据库文件
│   └── golden/                    # 基准测试数据
├── package.json                   # 前端脚本/依赖
└── README.md
```

## 环境要求

- **Node.js** >= 18
- **Rust** >= 1.75（stable 工具链）
- **系统依赖**（Windows / macOS / Linux）参见 [Tauri 2 前置要求](https://tauri.app/v1/guides/getting-started/prerequisites)

## 快速开始

### 安装依赖

```bash
# 安装前端依赖
npm install
```

### 开发模式

```bash
# 启动前端 Vite + Tauri 开发窗口
npm run tauri dev
```

首次编译会下载并构建 Rust 依赖，耗时较长。启动后默认窗口大小 1200×800，前端运行在 `http://localhost:1420`。

### 生产构建

```bash
# 构建可分发安装包（写入 src-tauri/target/release/bundle/）
npm run tauri build
```

构建目标由 `tauri.conf.json` 中 `bundle.targets = "all"` 指定，生成对应平台的安装程序。

### 仅前端构建 / 预览

```bash
# 构建前端产物到 dist/
npm run build

# 本地预览构建结果
npm run preview
```

## 核心库独立使用

`core/` 可脱离 Tauri 独立运行，用于脚本化处理或测试：

```bash
cd core

# 运行示例：导出项目预算
cargo run --example dump_project2_budget

# 运行核心库测试
cargo test
```

## 数据库

- 引擎：**SQLite 3**（rusqlite bundled，自包含编译）
- 开发环境默认路径：`database/database.db`
- 迁移：启动时由 `core/src/db/migrate.rs` 自动执行 schema 初始化与版本升级
- 测试基准库：`tests/golden/schema.sql`、`tests/fixtures/*.db`

## 作者

- Likang1988

## 许可证

核心库 `research-toolset-core` 采用 **GPL-3.0**。
