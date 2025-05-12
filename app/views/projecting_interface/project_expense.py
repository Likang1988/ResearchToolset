import os
import shutil # Added for file operations
import sys # Needed for platform check in view_attachment (though it's in utils now)
import subprocess # Needed for platform check in view_attachment (though it's in utils now)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                 QMessageBox, QStackedWidget, QSplitter,
                                 QFileDialog, QFrame, QTableWidgetItem, # Added QFileDialog here if not present
                                 QHeaderView)
from PySide6.QtCore import Qt, Signal, QDate, QSize, QPoint # Added QPoint
from PySide6.QtGui import QIcon # Added for button icon updates
from qfluentwidgets import (FluentIcon, TableWidget, PushButton, ComboBox, CompactDateEdit,
                           LineEdit, SpinBox, TableItemDelegate, TitleLabel, InfoBar, Dialog, RoundMenu, PrimaryPushButton, ToolButton, Action) # Added Dialog, RoundMenu, Action, ToolButton
from ...models.database import sessionmaker, Budget, BudgetCategory, Expense, BudgetItem, Activity # Import Expense
from datetime import datetime
from ...components.expense_dialog import ExpenseDialog
from ...utils.ui_utils import UIUtils
from ...utils.db_utils import DBUtils
from ...utils.attachment_utils import (
    create_attachment_button, # Keep this one
    sanitize_filename, ensure_directory_exists, get_attachment_icon_path,
    view_attachment, download_attachment, ROOT_DIR # Import necessary utils
)
from ...utils.filter_utils import FilterUtils # Import FilterUtils
from collections import defaultdict
import pandas as pd # For export
import json # For storing activity data


CURRENT_OPERATOR = "系统用户"

class ProjectExpenseWidget(QWidget):
    # 添加信号，用于通知预算管理窗口更新数据
    expense_updated = Signal()

    def __init__(self, engine, project, budget):
        super().__init__()
        self.engine = engine
        self.project = project
        self.budget = budget
        self.all_expenses = [] # Store all loaded expenses
        self.current_expenses = [] # Store currently displayed/sorted/filtered expenses

        self.setup_ui()
        self.load_expenses() # This will now populate the lists and call _populate_table
        self.load_statistics()

    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("支出管理")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)  # 统一设置边距为15像素
        main_layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素

        # 标题
        title_layout = UIUtils.create_title_layout(f"支出管理-{self.project.financial_code}-{self.budget.year}")
        main_layout.addLayout(title_layout)

        # 按钮栏
        add_btn = UIUtils.create_action_button("添加支出", FluentIcon.ADD_TO)
        edit_btn = UIUtils.create_action_button("编辑支出", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除支出", FluentIcon.DELETE)

        add_btn.clicked.connect(self.add_expense)
        edit_btn.clicked.connect(self.edit_expense)
        delete_btn.clicked.connect(self.delete_expense)

        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        main_layout.addLayout(button_layout)

        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(1)  # 设置分割条宽度
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(0, 0, 0, 0.1);
                margin: 1px;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #0078D4;
                margin: 1px;
            }
            QSplitter::handle:pressed {
                background-color: #005A9E;
                margin: 1px;
            }
        """)

        # 上部 - 支出列表
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)  # 设置边距

        self.expense_table = TableWidget()
        self.expense_table.setColumnCount(9)
        self.expense_table.setHorizontalHeaderLabels([
             "支出ID", "费用类别", "开支内容", "规格型号", "供应商",
            "报账金额(元)", "报账日期", "备注", "凭证附件"
        ])
        # 禁止直接编辑表格
        self.expense_table.setEditTriggers(TableWidget.NoEditTriggers)

        # 设置表格样式
        self.expense_table.setBorderVisible(True)
        self.expense_table.setBorderRadius(8)
        self.expense_table.setWordWrap(False)
        self.expense_table.setItemDelegate(TableItemDelegate(self.expense_table))

        # 设置表格样式
        UIUtils.set_table_style(self.expense_table)

        # 设置列宽模式
        header = self.expense_table.horizontalHeader()  # 获取水平表头
        header.setSectionResizeMode(QHeaderView.Interactive)  # 可调整列宽
        header.setSortIndicatorShown(True)  # 显示排序指示器
        header.sectionClicked.connect(self.sort_table)  # 连接点击事件到排序函数

        # 隐藏行号
        self.expense_table.verticalHeader().setVisible(False)

        # 设置初始列宽
        header.resizeSection(0, 72)  # 支出ID
        header.resizeSection(1, 100)  # 费用类别
        header.resizeSection(2, 200)  # 开支内容
        header.resizeSection(3, 160)  # 规格型号
        header.resizeSection(4, 160)  # 供应商
        header.resizeSection(5, 100)  # 报账金额
        header.resizeSection(6, 100)  # 报账日期
        header.resizeSection(7, 140)  # 备注
        header.resizeSection(8, 80)  # 支出凭证


        # 允许用户调整列宽
        header.setSectionsMovable(True) # 可移动列
        header.setStretchLastSection(True) # 最后一列自动填充剩余空间

        self.expense_table.setSelectionMode(TableWidget.ExtendedSelection)
        self.expense_table.setSelectionBehavior(TableWidget.SelectRows) # 允许扩展选择整行


        top_layout.addWidget(self.expense_table) # 添加到布局中

        # 添加筛选工具栏
        filter_toolbar = QWidget()
        filter_layout = QHBoxLayout(filter_toolbar)
        filter_layout.setContentsMargins(0, 5, 0, 11)  # 设置边距，增加上下间距

        # 类别筛选
        filter_layout.addWidget(QLabel("费用类别:"))
        self.category_combo = ComboBox()
        self.category_combo.addItem("全部")
        for category in BudgetCategory:
            self.category_combo.addItem(category.value)
        self.category_combo.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.category_combo)

        filter_layout.addSpacing(10)

        # 金额范围
        filter_layout.addWidget(QLabel("金额范围:"))
        self.min_amount = LineEdit()
        self.min_amount.setPlaceholderText("最小金额")
        self.min_amount.setFixedWidth(120)
        self.min_amount.textChanged.connect(self.validate_amount_input)
        self.min_amount.textChanged.connect(self.apply_filters)

        self.max_amount = LineEdit()
        self.max_amount.setPlaceholderText("最大金额")
        self.max_amount.setFixedWidth(120)
        self.max_amount.textChanged.connect(self.validate_amount_input)
        self.max_amount.textChanged.connect(self.apply_filters)

        filter_layout.addWidget(self.min_amount)
        filter_layout.addWidget(QLabel("至"))
        filter_layout.addWidget(self.max_amount)

        filter_layout.addSpacing(10)

        # 日期范围
        filter_layout.addWidget(QLabel("日期范围:"))
        self.start_date = CompactDateEdit()
        self.end_date = CompactDateEdit()
        start_qdate = QDate(self.project.start_date.year, self.project.start_date.month, self.project.start_date.day)
        self.start_date.setDate(start_qdate)
        self.end_date.setDate(QDate.currentDate())
        # 清空金额输入框
        self.min_amount.clear()
        self.max_amount.clear()

        self.start_date.dateChanged.connect(self.apply_filters) # Connect after setting initial dates
        self.end_date.dateChanged.connect(self.apply_filters)

        filter_layout.addWidget(self.start_date)
        filter_layout.addWidget(QLabel("至"))
        filter_layout.addWidget(self.end_date)

        filter_layout.addSpacing(10)

        # 重置按钮
        reset_btn = PushButton("重置筛选")
        reset_btn.clicked.connect(self.reset_filters)
        filter_layout.addWidget(reset_btn)
        # 增加分隔线
        filter_layout.addSpacing(10)
        #filter_layout.addStretch()

        # 导出按钮
        export_excel_btn = PushButton("导出信息")
        export_excel_btn.clicked.connect(self.export_expense_excel)
        filter_layout.addWidget(export_excel_btn)

        export_voucher_btn = PushButton("导出附件")
        export_voucher_btn.clicked.connect(self.export_expense_vouchers)
        filter_layout.addWidget(export_voucher_btn)

        top_layout.addWidget(filter_toolbar)
        splitter.addWidget(top_widget)

        # 下部 - 统计表格
        bottom_widget = TableWidget()   # 创建下部widget
        bottom_layout = QVBoxLayout(bottom_widget)  # 垂直布局
        bottom_layout.setContentsMargins(0, 11, 0, 0)   #上下边距为10

        self.stats_table = TableWidget()   # 使用Fluent风格的TableWidget
        # 将合计列放在间接费右侧
        categories = list(BudgetCategory)
        indirect_index = categories.index(BudgetCategory.INDIRECT)
        self.headers = ["分类统计"] + [c.value for c in categories[:indirect_index+1]] + ["合计"] + [c.value for c in categories[indirect_index+1:]]
        self.stats_table.setColumnCount(len(self.headers))
        self.stats_table.setHorizontalHeaderLabels(self.headers)

                # 隐藏行号
        self.stats_table.verticalHeader().setVisible(False)

        # 设置表格样式
        self.stats_table.setBorderVisible(True)
        self.stats_table.setBorderRadius(8)
        self.stats_table.setWordWrap(False)
        self.stats_table.setItemDelegate(TableItemDelegate(self.stats_table))
        self.stats_table.setSelectionBehavior(TableWidget.SelectRows)
        self.stats_table.setSelectionMode(TableWidget.SingleSelection)

        # 设置表格样式
        UIUtils.set_table_style(self.stats_table)

        # 减小统计表格表头字号和行高
        stats_header = self.stats_table.horizontalHeader()
        stats_header.setStyleSheet("""
            QHeaderView::section {
                font-size: 12px; /* 减小字号 */
                padding: 2px 4px; /* 调整内边距以影响行高 */
            }
        """)


        bottom_layout.addWidget(self.stats_table)
        splitter.addWidget(bottom_widget)

        # 设置初始比例和可调整性
        splitter.setStretchFactor(0, 6)  # 上部占4/5
        splitter.setStretchFactor(1, 2)  # 下部占1/5
        splitter.setChildrenCollapsible(False)  # 防止完全折叠

        main_layout.addWidget(splitter)


    def back_to_budget(self):
        """返回到预算管理页面"""
        budget_widget = self.parent()
        if isinstance(budget_widget, QStackedWidget):
            # 切换到预算管理页面（第一个页面）
            budget_widget.setCurrentWidget(budget_widget.widget(0))
            budget_widget.removeWidget(self)

    def load_expenses(self):
        """加载所有支出数据到内存并首次填充表格"""
        try:
            Session = sessionmaker(bind=self.engine)
            with Session() as session:
                # 查询所有相关支出数据
                self.all_expenses = session.query(Expense).filter(
                    Expense.budget_id == self.budget.id
                ).order_by(Expense.date.desc()).all()
                self.current_expenses = self.all_expenses[:]
                self._populate_table(self.current_expenses)

        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'加载支出数据失败：{str(e)}',
                parent=self
            )

    def _populate_table(self, expenses_list):
        """根据给定的支出列表填充表格"""
        self.expense_table.setSortingEnabled(False) # Disable sorting during population
        self.expense_table.setRowCount(0) # Clear table first

        for row, expense in enumerate(expenses_list):
            self.expense_table.insertRow(row)

            id_item = QTableWidgetItem(str(expense.id))
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setData(Qt.UserRole, expense.id) # Store ID for potential use elsewhere
            self.expense_table.setItem(row, 0, id_item)

            cat_item = QTableWidgetItem(expense.category.value)
            cat_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 1, cat_item)

            cont_item = QTableWidgetItem(expense.content)
            cont_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.expense_table.setItem(row, 2, cont_item)

            spec_item = QTableWidgetItem(expense.specification or "")
            spec_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 3, spec_item)

            supp_item = QTableWidgetItem(expense.supplier or "")
            supp_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 4, supp_item)

            amount_item = QTableWidgetItem(f"{expense.amount:.2f}")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setData(Qt.UserRole + 1, expense.amount)
            self.expense_table.setItem(row, 5, amount_item)

            date_str = expense.date.strftime("%Y-%m-%d")
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignCenter)
            date_item.setData(Qt.UserRole + 1, expense.date)
            self.expense_table.setItem(row, 6, date_item)

            remark_item = QTableWidgetItem(expense.remarks or "")
            remark_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 7, remark_item)

            container = create_attachment_button(
                item_id=expense.id, # Pass correct ID from the expense object
                attachment_path=expense.voucher_path, # Pass correct path
                handle_attachment_func=self.handle_voucher_wrapper, # Pass the wrapper function
                parent_widget=self,
                item_type='expense'
            )
            self.expense_table.setCellWidget(row, 8, container)

        self.expense_table.setSortingEnabled(True) # Re-enable sorting after population

    def load_statistics(self):
        """加载统计数据"""
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            # 设置行数为2（预算行和分类小计行）
            self.stats_table.setRowCount(2)

            # 添加年度预算行
            budget_item = QTableWidgetItem("预算(万元)")
            budget_item.setTextAlignment(Qt.AlignCenter)
            budget_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # 不可编辑
            self.stats_table.setItem(0, 0, budget_item)

            # 获取年度预算数据
            budget_items = session.query(BudgetItem).filter_by(
                budget_id=self.budget.id
            ).all()

            # 初始化总预算金额
            total_budget = 0.0

            # 填充预算数据
            for category in BudgetCategory:
                # 查找该类别的预算金额
                budget_item = next((item for item in budget_items if item.category == category), None)
                amount = budget_item.amount if budget_item else 0.0
                total_budget += amount

                # 在对应的列显示预算金额
                col = list(BudgetCategory).index(category) + 1
                amount_item = QTableWidgetItem(f"{amount:.2f}")
                amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amount_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # 不可编辑
                self.stats_table.setItem(0, col, amount_item)

            # 在预算行的合计列显示总预算金额
            total_budget_item = QTableWidgetItem(f"{total_budget:.2f}")
            total_budget_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_budget_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # 不可编辑
            # 计算合计列的位置（间接费列索引+2）
            total_col = list(BudgetCategory).index(BudgetCategory.INDIRECT) + 2
            self.stats_table.setItem(0, total_col, total_budget_item)

            # 设置列宽
            header = self.stats_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)
            header.resizeSection(0, 98)  # 类别列
            for i in range(1, len(self.headers)):
                header.resizeSection(i, 92)  # 数据列

            header.setStretchLastSection(True)  # 最后一列自动填充剩余空间

            if not hasattr(self, 'headers'):
                categories = list(BudgetCategory)
                indirect_index = categories.index(BudgetCategory.INDIRECT)
                self.headers = ["分类统计"] + [c.value for c in categories[:indirect_index+1]] + ["合计"] + [c.value for c in categories[indirect_index+1:]]


            # 初始化合计金额
            total_amount = 0.0

            # 创建分类支出小计行
            subtotal_item = QTableWidgetItem("支出(万元)")
            subtotal_item.setTextAlignment(Qt.AlignCenter)
            subtotal_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # 不可编辑
            self.stats_table.setItem(1, 0, subtotal_item)

            # 加载各类别统计数据
            category_amounts = {}
            for category in BudgetCategory:
                # 获取该类别的所有支出记录
                expenses = session.query(Expense).filter_by(
                    budget_id=self.budget.id,
                    category=category
                ).all()

                # 计算该类别的总支出金额
                category_amount = sum(expense.amount for expense in expenses) / 10000  # 转换为万元
                category_amounts[category] = category_amount
                total_amount += category_amount

                # 在对应的列显示分类支出小计金额
                col = list(BudgetCategory).index(category) + 1
                amount_item = QTableWidgetItem(f"{category_amount:.2f}")
                amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amount_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # 不可编辑
                self.stats_table.setItem(1, col, amount_item)


            # 在分类支出小计行的合计列显示总金额
            total_amount_item = QTableWidgetItem(f"{total_amount:.2f}")
            total_amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            total_amount_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # 不可编辑
            # 计算合计列的位置（间接费列索引+2）
            total_col = list(BudgetCategory).index(BudgetCategory.INDIRECT) + 2
            self.stats_table.setItem(1, total_col, total_amount_item)

        finally:
            session.close()

    def add_expenses(self, expenses_data):
        """批量添加支出"""
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            for data in expenses_data:
                # 创建支出记录
                expense = Expense(
                    project_id=self.project.id,
                    budget_id=self.budget.id,
                    category=BudgetCategory(data['类别']),
                    content=data['开支内容'],
                    specification=data['规格型号'],
                    supplier=data['供应商'],
                    amount=float(data['报账金额']),
                    date=data['报账日期'],
                    remarks=data.get('备注', '')
                )
                session.add(expense)
                session.flush() # Flush to get expense ID if needed for activity

                # 添加活动记录
                activity = Activity(
                    project_id=self.project.id,
                    budget_id=self.budget.id,
                    expense_id=expense.id,
                    type="支出",
                    action="批量导入",
                    description=f"批量导入支出：{expense.content}，金额：{expense.amount:.2f}元",
                    operator=CURRENT_OPERATOR, # Use placeholder operator
                    category=expense.category.value,
                    amount=expense.amount,
                    related_info=f"项目: {self.project.financial_code}, 预算: {self.budget.year}"
                )
                session.add(activity)

                # 更新预算子项的已支出金额
                budget_item = session.query(BudgetItem).filter_by(
                    budget_id=self.budget.id,
                    category=BudgetCategory(data['类别'])
                ).first()

                if budget_item:
                    budget_item.spent_amount += float(data['报账金额']) / 10000

                # 更新预算总额的已支出金额
                self.budget = session.merge(self.budget)
                self.budget.spent_amount += float(data['报账金额']) / 10000

            session.commit()
            self.load_expenses() # Reload all data after batch add
            self.load_statistics()
            # 发送信号通知预算管理窗口更新数据
            self.expense_updated.emit()

        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f"批量导入支出失败：{str(e)}",
                parent=self
            )
        finally:
            session.close()

    def add_expense(self):
        """添加单个支出"""
        dialog = ExpenseDialog(engine=self.engine, budget=self.budget, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                # 创建支出记录
                expense = Expense(
                    project_id=self.project.id,
                    budget_id=self.budget.id,
                    category=data['category'],
                    content=data['content'],
                    specification=data['specification'],
                    supplier=data['supplier'],
                    amount=data['amount'],
                    date=data['date'],
                    remarks=data['remarks'],
                    voucher_path=data.get('voucher_path') # Get voucher path from dialog
                )
                session.add(expense)
                session.flush() # Flush to get expense ID

                activity = Activity(
                    project_id=self.project.id,
                    budget_id=self.budget.id,
                    expense_id=expense.id,
                    type="支出",
                    action="添加",
                    description=f"添加支出：{expense.content}，金额：{expense.amount:.2f}元",
                    operator=CURRENT_OPERATOR, # Use placeholder operator
                    category=expense.category.value,
                    amount=expense.amount,
                    related_info=f"项目: {self.project.financial_code}, 预算: {self.budget.year}"
                )
                session.add(activity)

                # 更新预算子项的已支出金额
                budget_item = session.query(BudgetItem).filter_by(
                    budget_id=self.budget.id,
                    category=data['category']
                ).first()

                if budget_item:
                    budget_item.spent_amount += data['amount'] / 10000

                # 更新预算总额的已支出金额
                self.budget = session.merge(self.budget)
                self.budget.spent_amount += data['amount'] / 10000

                session.commit()
                self.load_expenses() # Reload data after adding
                self.load_statistics()
                # 发送信号通知预算管理窗口更新数据
                self.expense_updated.emit()
                UIUtils.show_success(
                    title='成功',
                    content='支出添加成功',
                    parent=self
                )
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title='错误',
                    content=f'添加支出失败：{str(e)}',
                    parent=self
                )
            finally:
                session.close()

    def edit_expense(self):
        """编辑选中的支出"""
        selected_items = self.expense_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(
                title='警告',
                content='请先选择要编辑的支出记录',
                parent=self
            )
            return

        row = selected_items[0].row()
        expense_id_item = self.expense_table.item(row, 0)
        if not expense_id_item: return # Should not happen if row is selected

        expense_id = expense_id_item.data(Qt.UserRole)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            expense = session.query(Expense).get(expense_id)
            if not expense:
                UIUtils.show_error(
                    title='错误',
                    content='未找到选中的支出记录',
                    parent=self
                )
                return

            old_data_dict = {
                'category': expense.category.value,
                'content': expense.content,
                'specification': expense.specification,
                'supplier': expense.supplier,
                'amount': expense.amount,
                'date': str(expense.date),
                'remarks': expense.remarks,
                'voucher_path': expense.voucher_path
            }
            old_amount = expense.amount
            old_category = expense.category

            dialog = ExpenseDialog(engine=self.engine, budget=self.budget, expense=expense, parent=self)
            if dialog.exec():
                data = dialog.get_data()

                # 更新支出记录
                expense.category = data['category']
                expense.content = data['content']
                expense.specification = data['specification']
                expense.supplier = data['supplier']
                expense.amount = data['amount']
                expense.date = data['date']
                expense.remarks = data['remarks']
                expense.voucher_path = data.get('voucher_path') # Update voucher path

                new_data_dict = {
                    'category': expense.category.value,
                    'content': expense.content,
                    'specification': expense.specification,
                    'supplier': expense.supplier,
                    'amount': expense.amount,
                    'date': str(expense.date),
                    'remarks': expense.remarks,
                    'voucher_path': expense.voucher_path
                }

                activity = Activity(
                    project_id=self.project.id,
                    budget_id=self.budget.id,
                    expense_id=expense.id,
                    type="支出",
                    action="编辑",
                    description=f"编辑支出ID {expense.id}：{expense.content}，新金额：{expense.amount:.2f}元",
                    operator=CURRENT_OPERATOR, # Use placeholder operator
                    old_data=json.dumps(old_data_dict, ensure_ascii=False), # Store old data as JSON
                    new_data=json.dumps(new_data_dict, ensure_ascii=False), # Store new data as JSON
                    category=expense.category.value,
                    amount=expense.amount,
                    related_info=f"项目: {self.project.financial_code}, 预算: {self.budget.year}"
                )
                session.add(activity)

                # --- 更新预算金额 ---
                amount_diff = data['amount'] - old_amount
                category_changed = (data['category'] != old_category)

                # 如果类别改变，先从旧类别减去旧金额
                if category_changed:
                    old_budget_item = session.query(BudgetItem).filter_by(
                        budget_id=self.budget.id,
                        category=old_category
                    ).first()
                    if old_budget_item:
                        old_budget_item.spent_amount -= old_amount / 10000

                # 更新新类别（或同一类别）的金额
                new_budget_item = session.query(BudgetItem).filter_by(
                    budget_id=self.budget.id,
                    category=data['category']
                ).first()
                if new_budget_item:
                    if category_changed:
                        new_budget_item.spent_amount += data['amount'] / 10000 # Add new amount to new category
                    else:
                        new_budget_item.spent_amount += amount_diff / 10000 # Adjust amount in the same category

                # 更新预算总额的已支出金额
                self.budget = session.merge(self.budget)
                self.budget.spent_amount += amount_diff / 10000

                session.commit()
                self.load_expenses() # Reload data after editing
                self.load_statistics()
                # 发送信号通知预算管理窗口更新数据
                self.expense_updated.emit()
                UIUtils.show_success(
                    title='成功',
                    content='支出编辑成功',
                    parent=self
                )
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'编辑支出失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()

    def delete_expense(self):
        """批量删除支出"""
        selected_rows = sorted(list(set(item.row() for item in self.expense_table.selectedItems())), reverse=True)
        if not selected_rows:
            UIUtils.show_warning(
                title='警告',
                content='请先选择要删除的支出记录',
                parent=self
            )
            return

        expense_ids_to_delete = []
        for row in selected_rows:
            id_item = self.expense_table.item(row, 0)
            if id_item:
                expense_ids_to_delete.append(id_item.data(Qt.UserRole))

        if not expense_ids_to_delete:
            UIUtils.show_error(self, "错误", "无法获取选中的支出ID")
            return

        # 确认删除
        confirm_dialog = Dialog(
            title='确认删除',
            content=f'确定要删除选中的 {len(expense_ids_to_delete)} 条支出记录吗？此操作不可恢复。',
            parent=self
        )
        confirm_dialog.cancelButton.setText('取消')
        confirm_dialog.yesButton.setText('确认删除')

        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            deleted_count = 0
            total_amount_deleted = 0.0
            category_amounts_deleted = defaultdict(float)

            try:
                for expense_id in expense_ids_to_delete:
                    expense = session.query(Expense).get(expense_id)
                    if expense:
                        amount_deleted = expense.amount
                        category_deleted = expense.category
                        old_data_dict = {
                            'category': expense.category.value,
                            'content': expense.content,
                            'amount': expense.amount,
                            'date': str(expense.date)
                        }

                        # 添加活动记录 (在删除前记录)
                        activity = Activity(
                            project_id=self.project.id,
                            budget_id=self.budget.id,
                            expense_id=expense.id, # Log the ID even though it's being deleted
                            type="支出",
                            action="删除",
                            description=f"删除支出ID {expense.id}：{expense.content}，金额：{expense.amount:.2f}元",
                            operator=CURRENT_OPERATOR, # Use placeholder operator
                            old_data=json.dumps(old_data_dict, ensure_ascii=False), # Log deleted data
                            category=expense.category.value,
                            amount=expense.amount,
                            related_info=f"项目: {self.project.financial_code}, 预算: {self.budget.year}"
                        )
                        session.add(activity)

                        # 删除凭证文件（如果存在）
                        if expense.voucher_path and os.path.exists(expense.voucher_path):
                            try:
                                os.remove(expense.voucher_path)
                            except OSError as e:
                                print(f"Warning: Could not delete voucher file {expense.voucher_path}: {e}")

                        session.delete(expense)
                        deleted_count += 1
                        total_amount_deleted += amount_deleted
                        category_amounts_deleted[category_deleted] += amount_deleted

                # 更新预算金额
                for category, amount in category_amounts_deleted.items():
                    budget_item = session.query(BudgetItem).filter_by(
                        budget_id=self.budget.id,
                        category=category
                    ).first()
                    if budget_item:
                        budget_item.spent_amount -= amount / 10000

                # 更新预算总额
                self.budget = session.merge(self.budget)
                self.budget.spent_amount -= total_amount_deleted / 10000

                session.commit()
                self.load_expenses() # Reload data after deleting
                self.load_statistics()
                # 发送信号通知预算管理窗口更新数据
                self.expense_updated.emit()
                UIUtils.show_success(
                    title='成功',
                    content=f'成功删除 {deleted_count} 条支出记录',
                    parent=self
                )
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title='错误',
                    content=f'删除支出失败：{str(e)}',
                    parent=self
                )
            finally:
                session.close()

    def _generate_voucher_path(self, expense, project, original_filename):
        """Generates the specific path for an expense voucher based on business rules."""
        if not expense or not project or not original_filename:
            print("Error: Missing expense, project, or filename for path generation.")
            return None # Or raise an error

        base_folder = "vouchers"
        project_code = project.financial_code if project.financial_code else "unknown_project"
        expense_year = str(expense.date.year) if expense.date else "unknown_year"
        expense_category = expense.category.value if expense.category else "unknown_category"
        sanitized_category = sanitize_filename(expense_category)
        expense_amount = f"{expense.amount:.2f}" if expense.amount is not None else "0.00"

        original_basename = os.path.basename(original_filename)
        base_name, ext = os.path.splitext(original_basename)
        sanitized_base_name = sanitize_filename(base_name) # Sanitize only the base name

        new_filename = f"{sanitized_category}_{expense_amount}_{sanitized_base_name}{ext}"

        target_dir = os.path.join(ROOT_DIR, base_folder, project_code, expense_year)
        full_path = os.path.join(target_dir, new_filename)

        return os.path.normpath(full_path)

    def handle_voucher_wrapper(self, event, btn):
        """Handles voucher attachment actions directly within the expense widget."""
        expense_id = btn.property("item_id")
        if expense_id is None:
            UIUtils.show_error(self, "错误", "无法获取支出项ID")
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            expense_check = session.query(Expense).get(expense_id)
            if not expense_check:
                UIUtils.show_error(self, "错误", f"找不到ID为 {expense_id} 的支出项")
                return # Session closed in finally

            action_type = None
            current_path_check = expense_check.voucher_path # Get current path from DB for menu logic

            if event is None: # Left-click
                button_path = btn.property("attachment_path") # Check button's state first
                if button_path and os.path.exists(button_path):
                    menu = RoundMenu(parent=self)
                    view_action = Action(FluentIcon.VIEW, "查看", self)
                    download_action = Action(FluentIcon.DOWNLOAD, "下载", self)
                    replace_action = Action(FluentIcon.SYNC, "替换", self)
                    delete_action = Action(FluentIcon.DELETE, "删除", self)

                    view_action.triggered.connect(lambda: self._execute_voucher_action("view", expense_id, btn, session))
                    download_action.triggered.connect(lambda: self._execute_voucher_action("download", expense_id, btn, session))
                    replace_action.triggered.connect(lambda: self._execute_voucher_action("replace", expense_id, btn, session))
                    delete_action.triggered.connect(lambda: self._execute_voucher_action("delete", expense_id, btn, session))

                    menu.addAction(view_action)
                    menu.addAction(download_action)
                    menu.addAction(replace_action)
                    menu.addSeparator()
                    menu.addAction(delete_action)
                    menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
                    return # Menu handles the action, exit wrapper
                else:
                    action_type = "upload"
            elif isinstance(event, QPoint): # Right-click (Context menu request)
                menu = RoundMenu(parent=self)
                if current_path_check and os.path.exists(current_path_check):
                    view_action = Action(FluentIcon.VIEW, "查看", self)
                    download_action = Action(FluentIcon.DOWNLOAD, "下载", self)
                    replace_action = Action(FluentIcon.SYNC, "替换", self)
                    delete_action = Action(FluentIcon.DELETE, "删除", self)
                    view_action.triggered.connect(lambda: self._execute_voucher_action("view", expense_id, btn, session))
                    download_action.triggered.connect(lambda: self._execute_voucher_action("download", expense_id, btn, session))
                    replace_action.triggered.connect(lambda: self._execute_voucher_action("replace", expense_id, btn, session))
                    delete_action.triggered.connect(lambda: self._execute_voucher_action("delete", expense_id, btn, session))
                    menu.addAction(view_action)
                    menu.addAction(download_action)
                    menu.addAction(replace_action)
                    menu.addSeparator()
                    menu.addAction(delete_action)
                else:
                    upload_action = Action(FluentIcon.ADD_TO, "上传附件", self)
                    upload_action.triggered.connect(lambda: self._execute_voucher_action("upload", expense_id, btn, session))
                    menu.addAction(upload_action)
                menu.exec(btn.mapToGlobal(event))
                return # Menu handles the action, exit wrapper

            if action_type:
                 self._execute_voucher_action(action_type, expense_id, btn, session)

        except Exception as e:
            UIUtils.show_error(self, "处理附件时出错", f"发生意外错误: {e}")
            if session.is_active:
                session.rollback() # Rollback on any exception during fetch or initial logic
        finally:
            if session.is_active: # Check if session is still active before closing
                session.close()


    def _execute_voucher_action(self, action_type, expense_id, btn, session):
        """Executes the specific voucher action (called by wrapper or menu)."""
        try:
            expense = session.query(Expense).get(expense_id)
            if not expense:
                UIUtils.show_error(self, "错误", f"执行操作时找不到ID为 {expense_id} 的支出项")
                return # Session will be closed by the caller

            current_path = expense.voucher_path

            if action_type == "view":
                if current_path and os.path.exists(current_path):
                    view_attachment(current_path, self)
                else:
                    UIUtils.show_warning(self, "提示", "附件不存在")

            elif action_type == "download":
                if current_path and os.path.exists(current_path):
                    download_attachment(current_path, self)
                else:
                    UIUtils.show_warning(self, "提示", "附件不存在")

            elif action_type == "upload" or action_type == "replace":
                source_file_path, _ = QFileDialog.getOpenFileName(self, "选择凭证文件", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;PDF文件 (*.pdf);;所有文件 (*.*)") # Filter added
                if not source_file_path:
                    return # User cancelled

                old_path = current_path # Path before potential change
                new_path = self._generate_voucher_path(expense, self.project, source_file_path)

                if not new_path:
                    UIUtils.show_error(self, "错误", "无法生成附件保存路径")
                    return

                try:
                    ensure_directory_exists(os.path.dirname(new_path))
                    shutil.copy2(source_file_path, new_path)

                    expense.voucher_path = new_path
                    session.commit() # Commit this specific change

                    if action_type == "replace" and old_path and os.path.exists(old_path) and os.path.normpath(old_path) != os.path.normpath(new_path):
                        try:
                            os.remove(old_path)
                        except OSError as e:
                            print(f"警告: 无法删除旧凭证 {old_path}: {e}") # Log warning

                    btn.setIcon(QIcon(get_attachment_icon_path('attach.svg')))
                    btn.setToolTip("管理附件")
                    btn.setProperty("attachment_path", new_path)

                    UIUtils.show_success(self, "成功", "凭证已更新")
                    self.expense_updated.emit() # Notify budget window if needed
                    self.load_statistics() # Update stats immediately

                except Exception as e:
                    session.rollback() # Rollback this specific transaction
                    UIUtils.show_error(self, "错误", f"更新凭证失败: {e}")
                    if os.path.exists(new_path):
                         session.expire(expense) # Mark expense as expired to force re-fetch
                         db_path_after_rollback = getattr(session.query(Expense).get(expense_id), 'voucher_path', None)
                         if db_path_after_rollback != new_path:
                             try:
                                 print(f"Attempting to remove orphaned file: {new_path}")
                                 os.remove(new_path)
                             except Exception as remove_err:
                                 print(f"Error removing orphaned file {new_path}: {remove_err}")

            elif action_type == "delete":
                if not current_path or not os.path.exists(current_path):
                    UIUtils.show_warning(self, "提示", "没有可删除的凭证")
                    return

                confirm_dialog = Dialog('确认删除', '确定要删除此凭证吗？此操作不可恢复！', self)
                if confirm_dialog.exec():
                    try:
                        os.remove(current_path)
                        expense.voucher_path = None
                        session.commit() # Commit this specific change

                        btn.setIcon(QIcon(get_attachment_icon_path('add_outline.svg')))
                        btn.setToolTip("添加附件")
                        btn.setProperty("attachment_path", None)

                        UIUtils.show_success(self, "成功", "凭证已删除")
                        self.expense_updated.emit() # Notify budget window if needed
                        self.load_statistics() # Update stats immediately

                    except Exception as e:
                        session.rollback() # Rollback this specific transaction
                        UIUtils.show_error(self, "错误", f"删除凭证失败: {e}")

        except Exception as e:
             UIUtils.show_error(self, "处理附件操作时出错", f"发生意外错误: {e}")
             if session.is_active:
                 try:
                     session.rollback()
                 except Exception as rb_err:
                     print(f"Error during rollback in _execute_voucher_action: {rb_err}")


    def reset_filters(self):
        """重置所有筛选条件"""
        self.category_combo.setCurrentText("全部")
        start_date = QDate(self.project.start_date.year, self.project.start_date.month, self.project.start_date.day)
        self.start_date.setDate(start_date)
        self.end_date.setDate(QDate.currentDate())
        # 清空金额输入框
        self.min_amount.clear()
        self.max_amount.clear()
        self.apply_filters() # Re-apply filters which will show all items

    def apply_filters(self):
        """根据当前筛选条件使用 FilterUtils 过滤并更新表格"""
        category_filter = self.category_combo.currentText()
        min_amount_text = self.min_amount.text()
        max_amount_text = self.max_amount.text()
        start_date = self.start_date.date().toPython() # Convert QDate to datetime.date
        end_date = self.end_date.date().toPython() # Convert QDate to datetime.date

        min_amount = None
        max_amount = None
        try:
            if min_amount_text:
                min_amount = float(min_amount_text)
            if max_amount_text:
                max_amount = float(max_amount_text)
        except ValueError:
            if min_amount_text or max_amount_text:
                 UIUtils.show_warning(self, "输入错误", "金额输入无效，将忽略该金额筛选条件。")


        filter_criteria = {
            'category': category_filter,
            'start_date': start_date,
            'end_date': end_date,
            'min_amount': min_amount,
            'max_amount': max_amount,
        }

        attribute_mapping = {
            'category': 'category', # Filter key 'category' maps to Expense.category
            'date': 'date',         # Explicitly map 'date' for clarity if needed by FilterUtils internals
            'amount': 'amount'      # Explicitly map 'amount' for clarity if needed by FilterUtils internals
        }

        self.current_expenses = FilterUtils.apply_filters(
            self.all_expenses,
            filter_criteria,
            attribute_mapping
        )

        self._populate_table(self.current_expenses)

    def export_expense_excel(self):
        """导出支出信息到Excel"""
        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not export_dir:
            return

        try:
            expenses_to_export = []
            for expense in self.current_expenses: # Use the currently displayed list
                expense_data = {
                    '费用类别': expense.category.value,
                    '开支内容': expense.content,
                    '规格型号': expense.specification or "",
                    '供应商': expense.supplier or "",
                    '报账金额': expense.amount,
                    '报账日期': expense.date.strftime("%Y-%m-%d"), # Format date for Excel
                    '备注': expense.remarks or ""
                }
                expenses_to_export.append(expense_data)

            if not expenses_to_export:
                UIUtils.show_info(self, "提示", "没有可导出的支出记录。")
                return

            df = pd.DataFrame(expenses_to_export)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"支出记录_{self.project.financial_code}_{self.budget.year}_{timestamp}.xlsx"
            excel_path = os.path.join(export_dir, excel_filename)

            with pd.ExcelWriter(excel_path, engine='openpyxl', datetime_format='YYYY-MM-DD') as writer:
                df.to_excel(writer, sheet_name='支出信息', index=False)

                try:
                    from openpyxl.worksheet.datavalidation import DataValidation
                    workbook = writer.book
                    worksheet = writer.sheets['支出信息']

                    # 获取类别列表
                    category_list = [cat.value for cat in BudgetCategory]
                    category_string = '"' + ','.join(category_list) + '"' # Excel需要逗号分隔的字符串

                    # 创建数据有效性规则
                    dv = DataValidation(type="list", formula1=category_string, allow_blank=True)
                    dv.error = '您的输入不在允许的列表中'
                    dv.errorTitle = '无效输入'
                    dv.prompt = '请从下拉列表中选择一个类别'
                    dv.promptTitle = '选择类别'

                    # 应用到“费用类别”列的所有数据行（从第二行开始）
                    dv.add(f'A2:A{len(df) + 1}') # Assuming '费用类别' is the first column (A)
                    worksheet.add_data_validation(dv)

                    # 添加说明信息
                    instructions = [
                        "说明:",
                        "1. 请在“费用类别”列使用下拉列表选择。",
                        "2. “开支内容”、“报账金额”、“报账日期”为必填项。",
                        "3. “报账金额”请填写数字。",
                        "4. “报账日期”请使用 YYYY-MM-DD 格式。"
                    ]
                    start_row = len(df) + 3 # 在数据下方空一行开始写说明
                    for i, instruction in enumerate(instructions):
                        worksheet.cell(row=start_row + i, column=1, value=instruction)
                except ImportError:
                    print("Warning: openpyxl not installed. Skipping Excel data validation and instructions.")
                except Exception as val_err:
                    print(f"Warning: Error adding Excel data validation/instructions: {val_err}")


            UIUtils.show_success(self, "成功", f"支出信息已成功导出到：\n{excel_path}")

        except Exception as e:
            UIUtils.show_error(self, "导出错误", f"导出Excel文件失败：{e}")
            print(f"Error exporting expense Excel: {e}") # Log for debugging

    def export_expense_vouchers(self):
        """导出支出凭证"""
        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择凭证导出目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not export_dir:
            return

        # 获取当前显示的支出记录的凭证路径
        vouchers_to_export = []
        for expense in self.current_expenses:
            if expense.voucher_path and os.path.exists(expense.voucher_path):
                vouchers_to_export.append(expense.voucher_path)

        if not vouchers_to_export:
            UIUtils.show_info(self, "提示", "当前筛选结果中没有找到有效的支出凭证文件。")
            return

        copied_count = 0
        errors = []
        try:
            # 创建目标子目录（可选，但推荐）
            target_subdir = os.path.join(export_dir, f"凭证_{self.project.financial_code}_{self.budget.year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(target_subdir, exist_ok=True)

            for voucher_path in vouchers_to_export:
                try:
                    # 构建目标文件路径，保留原始文件名
                    dest_path = os.path.join(target_subdir, os.path.basename(voucher_path))
                    # 复制文件
                    shutil.copy2(voucher_path, dest_path)
                    copied_count += 1
                except Exception as copy_e:
                    errors.append(f"无法复制文件 {os.path.basename(voucher_path)}: {copy_e}")

            if errors:
                error_message = "\n".join(errors)
                UIUtils.show_warning(self, "导出警告", f"成功导出 {copied_count} 个凭证文件，但遇到以下错误：\n{error_message}\n\n文件已导出到：\n{target_subdir}")
            else:
                UIUtils.show_success(self, "成功", f"成功导出 {copied_count} 个凭证文件到：\n{target_subdir}")

        except Exception as e:
            UIUtils.show_error(self, "导出错误", f"导出凭证文件时发生意外错误：{e}")
            print(f"Error exporting expense vouchers: {e}") # Log for debugging

    def validate_amount_input(self):
        """验证金额输入框的内容，确保是有效的数字"""
        sender = self.sender() # Get the LineEdit that triggered the signal
        if not sender: return # Should not happen
        text = sender.text()
        sender.setStyleSheet("")
        if not text: # Allow empty input
            return

        try:
            float(text)
        except ValueError:
            sender.setStyleSheet("border: 1px solid red;") # Example: red border

    def sort_table(self, column):
        """根据点击的列对 self.current_expenses 列表进行排序并更新表格"""
        if not self.current_expenses: return # Nothing to sort

        column_map = {
            0: ('id', 'int'),
            1: ('category', 'enum'), # Sort by enum value
            2: ('content', 'str'),
            3: ('specification', 'str_none'), # Handle None values
            4: ('supplier', 'str_none'),      # Handle None values
            5: ('amount', 'float'),
            6: ('date', 'date'),
            7: ('remarks', 'str_none')       # Handle None values
        }

        if column not in column_map: return # Clicked on non-sortable column

        attr_name, sort_type = column_map[column]
        current_order = self.expense_table.horizontalHeader().sortIndicatorOrder()

        reverse = (current_order == Qt.DescendingOrder)

        def sort_key(expense):
            value = getattr(expense, attr_name, None)
            if sort_type == 'enum':
                return value.value if value else "" # Sort by enum value string
            elif sort_type == 'str_none':
                return value.lower() if value else "" # Lowercase string or empty for None
            elif sort_type == 'str':
                return value.lower() # Assume non-None string
            elif sort_type == 'date':
                 if isinstance(value, datetime): return value.date()
                 return value if value else datetime.min.date()
            return value if value is not None else (0 if sort_type in ['int', 'float'] else "")


        try:
            self.current_expenses.sort(key=sort_key, reverse=reverse)
        except Exception as e:
            print(f"Error during sorting: {e}") # Catch potential comparison errors
            return

        self._populate_table(self.current_expenses)

        self.expense_table.horizontalHeader().setSortIndicator(column, current_order)
