import os
import sys # Needed for platform check in view_attachment (though it's in utils now)
import subprocess # Needed for platform check in view_attachment (though it's in utils now)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                 QMessageBox, QStackedWidget, QSplitter,
                                 QFileDialog, QFrame, QTableWidgetItem,
                                 QHeaderView)
from PySide6.QtCore import Qt, Signal, QDate, QSize, QPoint # Added QPoint
from qfluentwidgets import (FluentIcon, TableWidget, PushButton, ComboBox, CompactDateEdit,
                           LineEdit, SpinBox, TableItemDelegate, TitleLabel, InfoBar, Dialog, RoundMenu, PrimaryPushButton, ToolButton, Action)
from ...models.database import sessionmaker, Budget, BudgetCategory, Expense, BudgetItem, Activity
from datetime import datetime
from ...components.expense_dialog import ExpenseDialog
from ...utils.ui_utils import UIUtils
from ...utils.db_utils import DBUtils
# Use attachment_utils for voucher handling
# Import the specific functions needed from attachment_utils
from ...utils.attachment_utils import create_attachment_button, handle_attachment, view_attachment
from ...utils.filter_utils import FilterUtils # Import FilterUtils
from collections import defaultdict
import pandas as pd # For export
import json # For storing activity data

# Placeholder for current user - replace with actual user management later
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
        # 将datetime.date对象转换为QDate对象
        start_qdate = QDate(self.project.start_date.year, self.project.start_date.month, self.project.start_date.day)
        self.start_date.setDate(start_qdate)
        self.end_date.setDate(QDate.currentDate())
        # 清空金额输入框
        self.min_amount.clear()
        self.max_amount.clear()
        # self.apply_filters() # Don't apply filters initially, load_expenses does the first population

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

        filter_layout.addStretch()

        # 导出按钮
        export_excel_btn = PushButton("导出信息")
        export_excel_btn.clicked.connect(self.export_expense_excel)
        filter_layout.addWidget(export_excel_btn)

        export_voucher_btn = PushButton("导出凭证")
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

        bottom_layout.addWidget(self.stats_table)
        splitter.addWidget(bottom_widget)

        # 设置初始比例和可调整性
        splitter.setStretchFactor(0, 6)  # 上部占4/5
        splitter.setStretchFactor(1, 2)  # 下部占1/5
        splitter.setChildrenCollapsible(False)  # 防止完全折叠

        main_layout.addWidget(splitter)


    def back_to_budget(self):
        """返回到预算管理页面"""
        # 获取父窗口（预算管理窗口）的QStackedWidget
        budget_widget = self.parent()
        if isinstance(budget_widget, QStackedWidget):
            # 切换到预算管理页面（第一个页面）
            budget_widget.setCurrentWidget(budget_widget.widget(0))
            # 从QStackedWidget中移除当前支出管理页面
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
                # Make a shallow copy for the initial display/filtering/sorting
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

            # --- Populate Cells ---
            # 支出ID (Col 0)
            id_item = QTableWidgetItem(str(expense.id))
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setData(Qt.UserRole, expense.id) # Store ID for potential use elsewhere
            self.expense_table.setItem(row, 0, id_item)

            # 费用类别 (Col 1)
            cat_item = QTableWidgetItem(expense.category.value)
            cat_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 1, cat_item)

            # 开支内容 (Col 2)
            cont_item = QTableWidgetItem(expense.content)
            cont_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.expense_table.setItem(row, 2, cont_item)

            # 规格型号 (Col 3)
            spec_item = QTableWidgetItem(expense.specification or "")
            spec_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 3, spec_item)

            # 供应商 (Col 4)
            supp_item = QTableWidgetItem(expense.supplier or "")
            supp_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 4, supp_item)

            # 报账金额 (Col 5)
            amount_item = QTableWidgetItem(f"{expense.amount:.2f}")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Store numeric amount for sorting if needed later, though direct object sort is preferred
            amount_item.setData(Qt.UserRole + 1, expense.amount)
            self.expense_table.setItem(row, 5, amount_item)

            # 报账日期 (Col 6)
            date_str = expense.date.strftime("%Y-%m-%d")
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignCenter)
            # Store date object for sorting
            date_item.setData(Qt.UserRole + 1, expense.date)
            self.expense_table.setItem(row, 6, date_item)

            # 备注 (Col 7)
            remark_item = QTableWidgetItem(expense.remarks or "")
            remark_item.setTextAlignment(Qt.AlignCenter)
            self.expense_table.setItem(row, 7, remark_item)

            # --- Add Attachment Button (Col 8) ---
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
            #budget_item.setBackground(Qt.lightGray)
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
            #total_budget_item.setBackground(Qt.lightGray)   # 设置背景颜色
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

            # 确保headers在load_statistics方法中可用
            if not hasattr(self, 'headers'):
                categories = list(BudgetCategory)
                indirect_index = categories.index(BudgetCategory.INDIRECT)
                self.headers = ["分类统计"] + [c.value for c in categories[:indirect_index+1]] + ["合计"] + [c.value for c in categories[indirect_index+1:]]


            # 初始化合计金额
            total_amount = 0.0

            # 创建分类支出小计行
            subtotal_item = QTableWidgetItem("支出(万元)")
            subtotal_item.setTextAlignment(Qt.AlignCenter)
            #subtotal_item.setBackground(Qt.lightGray)
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
            #total_amount_item.setBackground(Qt.lightGray)   # 设置背景颜色
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
        # Corrected call to ExpenseDialog
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

                # 添加活动记录 - Corrected arguments
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
                    # old_data and new_data can be added if needed
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

        # 获取选中行的支出ID (假设ID存储在第0列的UserRole中)
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

            # 记录旧数据用于 Activity log
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

            # Corrected call to ExpenseDialog
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

                # 记录新数据用于 Activity log
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

                # 添加活动记录 - Corrected arguments
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

        # 获取选中行的支出ID列表
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
                        # Store data before deletion for activity log
                        old_data_dict = {
                            'category': expense.category.value,
                            'content': expense.content,
                            'amount': expense.amount,
                            'date': str(expense.date)
                        }

                        # 添加活动记录 - Corrected arguments
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
                                # Optionally inform the user, but proceed with DB deletion

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

    def handle_voucher_wrapper(self, event, btn):
        """Wraps the handle_attachment call specifically for vouchers."""
        # Find the row this button belongs to
        button_pos = btn.mapToGlobal(QPoint(0, 0))
        row_index = self.expense_table.indexAt(self.expense_table.viewport().mapFromGlobal(button_pos)).row()
        if row_index < 0: return # Button not found in table?

        # Get the expense ID from the first column of that row
        id_item = self.expense_table.item(row_index, 0)
        if not id_item: return
        expense_id = id_item.data(Qt.UserRole)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            # Fetch the actual Expense object
            expense = session.query(Expense).get(expense_id)
            if not expense:
                UIUtils.show_error(self, "错误", "找不到对应的支出记录")
                return

            # Define the target directory for vouchers relative to project root
            # Assuming ROOT_DIR is defined in attachment_utils or globally accessible
            # If not, define it here or pass it down. For now, assume relative path:
            base_folder = "vouchers" # Base folder name

            # Call the generic handler with the correct arguments
            # Note: handle_attachment now expects the item object itself
            handle_attachment(
                event=event,
                btn=btn,
                item=expense, # Pass the Expense object
                session=session, # Pass the session
                parent_widget=self,
                project=self.project, # Pass the project object
                item_type='expense', # Pass item type string
                attachment_attr='voucher_path', # Attribute name on Expense model
                base_folder=base_folder # Base folder for storage
            )

            # If handle_attachment modified the path, the session within it should commit.
            # We might need to refresh the button state if handle_attachment doesn't do it.
            # Check if the button's property was updated by handle_attachment
            updated_path = btn.property("attachment_path")
            if updated_path != expense.voucher_path: # Check if path actually changed
                 # Recreate button to reflect new state (if handle_attachment didn't)
                 # This might be redundant if handle_attachment already updates the button
                 print(f"Refreshing button for expense {expense_id} after attachment change.")
                 new_container = create_attachment_button(
                     item_id=expense.id,
                     attachment_path=updated_path, # Use the path from button property
                     handle_attachment_func=self.handle_voucher_wrapper,
                     parent_widget=self,
                     item_type='expense'
                 )
                 self.expense_table.setCellWidget(row_index, 8, new_container) # Column 8 for voucher

        except Exception as e:
            # session.rollback() # Rollback might happen inside handle_attachment
            UIUtils.show_error(self, "错误", f"处理凭证时出错: {e}")
            print(f"Error in handle_voucher_wrapper: {e}") # Log for debugging
        finally:
            # Ensure session is closed, even if handled within handle_attachment
            if session.is_active:
                session.close()

    def view_voucher(self, voucher_path):
        """Opens the voucher file using the default system application via attachment_utils."""
        # Directly use the view_attachment function from the utility module
        view_attachment(voucher_path, self)

    def reset_filters(self):
        """重置所有筛选条件"""
        self.category_combo.setCurrentText("全部")
        # 将datetime.date对象转换为QDate对象
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

        # Validate and convert amount inputs
        min_amount = None
        max_amount = None
        try:
            if min_amount_text:
                min_amount = float(min_amount_text)
            if max_amount_text:
                max_amount = float(max_amount_text)
        except ValueError:
            # Show warning but allow filtering to proceed with None for invalid amount
            # Only show warning if text was actually entered
            if min_amount_text or max_amount_text:
                 UIUtils.show_warning(self, "输入错误", "金额输入无效，将忽略该金额筛选条件。")


        filter_criteria = {
            'category': category_filter,
            'start_date': start_date,
            'end_date': end_date,
            'min_amount': min_amount,
            'max_amount': max_amount,
            # 'keyword': None, # No keyword search in this widget
            # 'keyword_attributes': [],
        }

        # Define how filter keys map to Expense object attributes
        # Note: 'date' and 'amount' keys are implicitly used by FilterUtils
        # for date/amount range checks based on 'start_date'/'end_date' and 'min_amount'/'max_amount'
        attribute_mapping = {
            'category': 'category', # Filter key 'category' maps to Expense.category
            'date': 'date',         # Explicitly map 'date' for clarity if needed by FilterUtils internals
            'amount': 'amount'      # Explicitly map 'amount' for clarity if needed by FilterUtils internals
        }

        # Apply filters using FilterUtils
        self.current_expenses = FilterUtils.apply_filters(
            self.all_expenses,
            filter_criteria,
            attribute_mapping
        )

        # Update the table with filtered data
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
            # 获取当前显示的支出记录（基于 self.current_expenses）
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

            # 创建DataFrame
            df = pd.DataFrame(expenses_to_export)

            # 生成Excel文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"支出记录_{self.project.financial_code}_{self.budget.year}_{timestamp}.xlsx"
            excel_path = os.path.join(export_dir, excel_filename)

            # 保存Excel文件，设置工作表名称为'支出信息'，并设置日期格式
            with pd.ExcelWriter(excel_path, engine='openpyxl', datetime_format='YYYY-MM-DD') as writer:
                df.to_excel(writer, sheet_name='支出信息', index=False)

                # 添加数据有效性（下拉列表） - Requires openpyxl
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
                    # Adjust range based on actual data size + header
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
        # Reset style first
        sender.setStyleSheet("")
        if not text: # Allow empty input
            return

        try:
            float(text)
            # Valid number
        except ValueError:
            # Invalid number, provide visual feedback
            sender.setStyleSheet("border: 1px solid red;") # Example: red border

    def sort_table(self, column):
        """根据点击的列对 self.current_expenses 列表进行排序并更新表格"""
        if not self.current_expenses: return # Nothing to sort

        # Map column index to attribute name and type
        column_map = {
            0: ('id', 'int'),
            1: ('category', 'enum'), # Sort by enum value
            2: ('content', 'str'),
            3: ('specification', 'str_none'), # Handle None values
            4: ('supplier', 'str_none'),      # Handle None values
            5: ('amount', 'float'),
            6: ('date', 'date'),
            7: ('remarks', 'str_none')       # Handle None values
            # Column 8 (voucher) is not sortable
        }

        if column not in column_map: return # Clicked on non-sortable column

        attr_name, sort_type = column_map[column]
        current_order = self.expense_table.horizontalHeader().sortIndicatorOrder()

        # Determine reverse flag
        reverse = (current_order == Qt.DescendingOrder)

        # Define sort key function
        def sort_key(expense):
            value = getattr(expense, attr_name, None)
            if sort_type == 'enum':
                return value.value if value else "" # Sort by enum value string
            elif sort_type == 'str_none':
                return value.lower() if value else "" # Lowercase string or empty for None
            elif sort_type == 'str':
                return value.lower() # Assume non-None string
            elif sort_type == 'date':
                 # Ensure comparison between date objects
                 if isinstance(value, datetime): return value.date()
                 # Use a very early date for None to sort them first/last depending on order
                 return value if value else datetime.min.date()
            # For 'int' and 'float', None might need specific handling if possible
            # For now, assume they are present or handle potential errors if None occurs
            return value if value is not None else (0 if sort_type in ['int', 'float'] else "")


        # Sort the current_expenses list
        try:
            self.current_expenses.sort(key=sort_key, reverse=reverse)
        except Exception as e:
            print(f"Error during sorting: {e}") # Catch potential comparison errors
            # Optionally show an error to the user
            return

        # Repopulate the table with the sorted list
        self._populate_table(self.current_expenses)

        # Update sort indicator
        self.expense_table.horizontalHeader().setSortIndicator(column, current_order)
