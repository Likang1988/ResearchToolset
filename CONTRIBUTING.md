# 项目学习指南

欢迎来到 ResearchToolset 项目！本指南旨在帮助新开发者快速了解和上手本项目。

## 1. 项目概述

ResearchToolset 是一个使用 Python、PySide6 和 QFluentWidgets 构建的跨平台桌面应用程序。它旨在为科研人员提供一个方便的工具集，目前的核心功能是科研经费管理，并逐步扩展到项目进度、文档、成果管理等。

**主要功能:**

*   **经费追踪**: 详细的项目、预算和支出管理。
*   **项目管理**: 项目信息的添加、编辑和维护。
*   **预算编制**: 预算计划的创建和管理。
*   **项目进度**: 甘特图任务管理。
*   **项目文档**: 附件管理。
*   **项目成果**: 成果管理。
*   **学术活动**: 活动记录和附件管理。
*   **小工具**: 例如，间接经费计算器。

**技术栈:**

*   **GUI 框架:** PySide6
*   **UI 组件库:** PySide6-Fluent-Widgets
*   **数据处理:** pandas
*   **数据库:** SQLAlchemy (SQLite)
*   **打包:** PyInstaller

## 2. 项目结构

```
ResearchToolset/
├── .git/               # Git 仓库
├── app/                # 应用程序核心代码
│   ├── assets/         # 应用程序资源 (图标、截图等)
│   ├── components/     # 可重用的 UI 组件和对话框
│   ├── integration/    # 第三方库集成 (如 jQueryGantt)
│   ├── models/         # 数据库模型 (SQLAlchemy)
│   ├── tools/          # 独立的小工具模块
│   ├── utils/          # 辅助函数和工具类
│   └── views/          # UI 视图和界面逻辑
├── database/           # 存储 SQLite 数据库文件
├── activities/         # 学术活动相关文件
├── documents/          # 项目文档存储
├── outcomes/           # 项目成果存储
├── vouchers/           # 支出凭证存储
├── .gitignore          # Git 忽略文件
├── build.py            # PyInstaller 打包脚本
├── README.md           # 项目介绍 (可能不是最新)
├── requirements.txt    # Python 依赖项
└── run.py              # 应用程序入口点
```

*   **`app/`**: 包含应用程序的所有核心代码。
    *   `assets/`: 存放应用程序的图标、图片等资源。
    *   `components/`: 包含可重用的 UI 组件和对话框，如 `batch_import_dialog.py`, `budget_chart_widget.py` 等。
    *   `integration/`: 用于集成第三方库，例如 `jQueryGantt`。
    *   `models/`: 定义了应用程序的数据模型，使用 SQLAlchemy 与数据库进行交互。核心文件是 `database.py`。
    *   `tools/`: 包含一些独立的小工具模块，如 `IndirectCostCalculator.py`。
    *   `utils/`: 存放辅助函数和工具类，如 `attachment_utils.py`, `db_utils.py`, `filter_utils.py`, `ui_utils.py`。
    *   `views/`: 包含了所有的用户界面组件和界面逻辑，使用 PySide6 和 QFluentWidgets 构建。`main_window.py` 是主窗口的定义。
*   **`database/`**: 存储 SQLite 数据库文件 `database.db`。
*   **`activities/`, `documents/`, `outcomes/`, `vouchers/`**: 这些目录用于存储不同类型的数据文件，如学术活动附件、项目文档、项目成果和支出凭证。
*   **`run.py`**: 应用程序的主入口点。它负责初始化应用程序、设置数据库和显示主窗口。
*   **`build.py`**: 用于使用 PyInstaller 将应用程序打包为可执行文件的脚本。
*   **`requirements.txt`**: 列出了项目所需的所有 Python 依赖项。

## 3. 环境设置

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/Likang1988/ResearchToolset.git
    cd ResearchToolset
    ```

2.  **安装依赖项:**
    强烈建议使用虚拟环境：
    ```bash
    python -m venv venv
    source venv/bin/activate  # 在 Windows 上使用 `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **初始化数据库:**
    第一次运行应用程序时，`run.py` 会自动检查并初始化数据库 (`database/database.db`)。如果数据库已存在，它会尝试执行迁移 (`migrate_db` 函数在 `app/models/database.py` 中定义)，以确保数据库结构是最新的。

## 4. 运行应用程序

要运行应用程序，只需在激活虚拟环境后执行 `run.py` 脚本：

```bash
python run.py
```

## 5. 核心组件

### 5.1 数据模型 (`app/models/database.py`)

应用程序使用 SQLAlchemy 作为 ORM (Object-Relational Mapping) 来管理数据库。`app/models/database.py` 定义了所有核心数据模型：

*   **`Project`**: 代表一个科研项目，包含项目名称、财务编号、类型、负责人、起止日期和总预算等信息。
*   **`Budget`**: 代表项目的预算，可以是总预算 (year=None) 或年度预算。与 `Project` 是一对多关系。
*   **`BudgetItem`**: 预算的子项，按类别（如设备费、材料费）划分。与 `Budget` 是一对多关系。
*   **`Expense`**: 支出记录，包含费用类别、内容、金额、日期和凭证路径等。与 `Project` 和 `Budget` 关联。
*   **`BudgetPlan`**: 预算编制的主表，用于管理预算计划。
*   **`BudgetPlanItem`**: 预算编制的明细项，支持树形结构。
*   **`Actionlog`**: 操作日志，记录用户对项目、预算、支出、任务、文档和成果的各项操作。
*   **`GanttTask`**: 甘特图任务，用于项目进度管理，包含任务名称、开始/结束日期、进度等。与 `Project` 关联。
*   **`GanttDependency`**: 甘特图任务之间的依赖关系。

`database.py` 还包含了 `init_db` (初始化数据库) 和 `migrate_db` (数据库迁移) 函数，用于处理数据库的创建和结构更新。

### 5.2 UI 视图 (`app/views`)

用户界面是使用 PySide6 和 QFluentWidgets 构建的。`app/views` 目录包含了应用程序的各个界面模块：

*   **`main_window.py`**: 定义了应用程序的主窗口 (`MainWindow`)，负责设置整体布局、导航栏和各个功能界面的集成。
*   **`home_interface.py`**: 主页界面。
*   **`projecting_interface/`**: 包含项目相关的界面，如 `project_list.py` (项目列表), `project_fund.py` (项目经费), `project_progress.py` (项目进度), `project_document.py` (项目文档), `project_outcome.py` (项目成果)。
*   **`budgeting_interface.py`**: 预算编制界面。
*   **`tools_interface.py`**: 小工具界面。
*   **`activity_interface.py`**: 学术活动界面。
*   **`help_interface.py`**: 帮助界面。

### 5.3 工具类 (`app/utils`)

`app/utils` 目录包含了一系列辅助函数和工具类，用于简化开发和提高代码复用性：

*   **`attachment_utils.py`**: 提供附件管理相关的函数，包括文件路径生成、文件操作（复制、删除）、附件按钮的创建和附件菜单的处理（查看、下载、替换、删除）。
*   **`db_utils.py`**: 包含 `DBUtils` 类，提供了 `with_session` 装饰器用于统一管理 SQLAlchemy 数据库会话，以及 `handle_db_error` 装饰器用于统一处理数据库操作异常并显示错误信息。
*   **`filter_utils.py`**: 包含 `FilterUtils` 类，提供了 `apply_filters` 方法，用于根据关键词、枚举值、日期范围和金额范围对数据列表进行过滤。
*   **`ui_utils.py`**: 包含 `UIUtils` 类，提供了许多 UI 相关的辅助函数，如设置表格/树形控件样式、创建标准布局和按钮、显示各种信息提示 (InfoBar)、加载 SVG 图标以及创建项目选择器 (ComboBox)。

## 6. 如何贡献

我们欢迎对 ResearchToolset 项目的任何贡献！以下是您可以如何提供帮助：

1.  **报告错误:** 如果您发现错误，请在 GitHub Issues 上提交一个详细的 issue，包含重现步骤、预期行为和实际行为。
2.  **提出功能建议:** 如果您有新功能的想法，请在 GitHub Issues 上提交一个 issue，详细描述您的需求和用例。
3.  **编写代码:** 如果您想为项目贡献代码，请遵循以下步骤：
    *   **Fork 仓库:** 在 GitHub 上 fork `Likang1988/ResearchToolset` 仓库到您自己的账户。
    *   **克隆到本地:** 将您 fork 的仓库克隆到本地开发环境。
    *   **创建分支:** 为您的新功能或 bug 修复创建一个新的分支 (例如 `feature/new-feature` 或 `bugfix/fix-bug-name`)。
    *   **编写代码:** 编写您的代码，确保遵循项目现有的编码风格和约定。
    *   **编写测试 (如果适用):** 为您的更改编写单元测试或集成测试，以确保其正确性。
    *   **运行测试和 Lint:** 在提交之前，请确保所有现有测试通过，并运行代码 Lint 工具 (例如 `flake8` 或 `pylint`) 检查代码风格。
    *   **提交更改:** 提交您的更改，并编写清晰、简洁的提交信息。
    *   **推送分支:** 将您的分支推送到您 fork 的仓库。
    *   **创建 Pull Request:** 在 GitHub 上创建一个 Pull Request，请求将您的更改合并到主仓库。请详细描述您的更改内容和目的。

在提交 Pull Request 之前，请确保您的代码符合项目的编码风格，并且您已经为您的更改添加了测试。

感谢您对 ResearchToolset 项目的关注和贡献！