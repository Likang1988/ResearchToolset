# 科研工具集 - ResearchToolset

## 项目简介
这是一个专为科研人员设计的工具，目前的功能主要为科研经费管理，旨在帮助科研人员高效管理和追踪项目资金使用情况。系统提供直观的界面和完整的功能，让项目经费管理变得简单高效。

## 主要功能
- **项目管理**
  - 添加、编辑、删除项目信息
  - 支持多种项目类别（国家自然科学基金、国家重点研发计划等）
  - 项目基本信息维护（项目编号、起止时间、总经费等）

- **经费管理**
  - 项目预算管理
  - 支出记录管理
  - 支持批量导入支出记录
  - 经费使用进度追踪
  - 经费使用率统计

## 系统要求
- Python 3.6+
- Windows 操作系统

## 安装步骤
1. 克隆项目到本地：
```bash
git clone https://github.com/Likang1988/ResearchToolset.git
cd ResearchToolset
```

2. 安装依赖包：
```bash
pip install -r requirements.txt
```

## 使用说明
1. 运行程序：
```bash
python run.py
```

2. 基本操作流程：
   - 添加新项目：点击"添加项目"按钮，填写项目信息
   - 管理项目经费：在项目列表中点击"经费管理"按钮
   - 批量导入支出：在经费管理页面使用"批量导入"功能

## 依赖项
- PySide6 >= 6.5.0
- PySide6-Fluent-Widgets >= 1.7.4
- pandas >= 2.0.0
- matplotlib >= 3.7.0
- openpyxl >= 3.1.0
- python-dateutil >= 2.8.2
- SQLAlchemy >= 2.0.0

## 功能特点
- 现代化的用户界面
- 支持批量数据导入
- 直观的经费使用统计
- 完善的数据管理功能
- 灵活的项目分类管理

## 注意事项
- 首次使用时需要创建数据库
- 建议定期备份数据库文件
- 批量导入数据时请使用系统提供的模板

## 作者
© Likang