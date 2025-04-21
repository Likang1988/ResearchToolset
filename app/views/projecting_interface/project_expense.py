import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                 QMessageBox, QStackedWidget, QSplitter,
                                 QFileDialog, QFrame, QTableWidgetItem,
                                 QHeaderView)
from PySide6.QtCore import Qt, Signal, QDate, QSize
from qfluentwidgets import (FluentIcon, TableWidget, PushButton, ComboBox, CompactDateEdit,
                           LineEdit, SpinBox, TableItemDelegate, TitleLabel, InfoBar, Dialog, RoundMenu, PrimaryPushButton, ToolButton, Action)
from ...models.database import sessionmaker, Budget, BudgetCategory, Expense, BudgetItem, Activity
from datetime import datetime
from ...components.expense_dialog import ExpenseDialog
from ...utils.ui_utils import UIUtils
from ...utils.db_utils import DBUtils
# Use attachment_utils for voucher handling
from ...utils.attachment_utils import create_attachment_button, handle_attachment, view_attachment
from collections import defaultdict
from PySide6.QtCore import QPoint # Needed for handle_attachment event check
import pandas as pd # For export

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
            "报账金额(元)", "报账日期", "备注", "支出凭证"
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
                handle_attachment_func=self.handle_voucher_wrapper,
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
        """添加单条支出"""
        dialog = ExpenseDialog(self.project, self.budget, self.engine, parent=self)
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
                    remarks=data['remarks']
                )
                session.add(expense)

                # 记录活动日志
                activity = Activity(
                    project_id=self.project.id,
                    type="支出",
                    action="添加",
                    description=f"添加支出：{expense.content} - {expense.amount}元",
                    operator="系统用户" # 假设操作员为系统用户
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
                    content='支出记录已添加！',
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
        selected_rows = self.expense_table.selectedRows()
        if not selected_rows:
            UIUtils.show_warning(
                title='警告',
                content='请先选择要编辑的支出记录！',
                parent=self
            )
            return

        if len(selected_rows) > 1:
            UIUtils.show_warning(
                title='警告',
                content='一次只能编辑一条支出记录！',
                parent=self
            )
            return

        selected_row = selected_rows[0]
        expense_id_item = self.expense_table.item(selected_row, 0) # Get item from ID column
        if not expense_id_item:
             UIUtils.show_error(self, "错误", "无法获取选中行的支出ID")
             return

        expense_id = int(expense_id_item.text())

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            expense = session.query(Expense).get(expense_id)
            if not expense:
                UIUtils.show_error(self, "错误", f"找不到 ID 为 {expense_id} 的支出记录")
                return

            # 获取旧金额用于预算调整
            old_amount = expense.amount
            old_category = expense.category

            dialog = ExpenseDialog(self.project, self.budget, self.engine, expense=expense, parent=self)
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

                # 记录活动日志
                activity = Activity(
                    project_id=self.project.id,
                    type="支出",
                    action="编辑",
                    description=f"编辑支出：{expense.content} - {expense.amount}元",
                    operator="系统用户"
                )
                session.add(activity)

                # 调整预算金额
                # 减去旧金额
                if old_category:
                    old_budget_item = session.query(BudgetItem).filter_by(
                        budget_id=self.budget.id,
                        category=old_category
                    ).first()
                    if old_budget_item:
                        old_budget_item.spent_amount -= old_amount / 10000

                # 加上新金额
                new_budget_item = session.query(BudgetItem).filter_by(
                    budget_id=self.budget.id,
                    category=data['category']
                ).first()
                if new_budget_item:
                    new_budget_item.spent_amount += data['amount'] / 10000

                # 更新预算总额
                self.budget = session.merge(self.budget)
                self.budget.spent_amount += (data['amount'] - old_amount) / 10000

                session.commit()
                self.load_expenses() # Reload data after editing
                self.load_statistics()
                # 发送信号通知预算管理窗口更新数据
                self.expense_updated.emit()

                UIUtils.show_success(
                    title='成功',
                    content='支出记录已更新！',
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
        selected_rows = self.expense_table.selectedRows()
        if not selected_rows:
            UIUtils.show_warning(
                title='警告',
                content='请先选择要删除的支出记录！',
                parent=self
            )
            return

        expense_ids = []
        for row in selected_rows:
             id_item = self.expense_table.item(row, 0)
             if id_item:
                 try:
                     expense_ids.append(int(id_item.text()))
                 except ValueError:
                     print(f"Warning: Could not parse expense ID from row {row}") # Should not happen

        if not expense_ids:
             UIUtils.show_warning(self, "警告", "未能获取选中行的支出ID")
             return


        confirm_dialog = Dialog(
            '确认删除',
            f'确定要删除选中的 {len(expense_ids)} 条支出记录吗？\n此操作不可恢复！',
            self
        )

        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                # 查询要删除的支出记录
                expenses_to_delete = session.query(Expense).filter(Expense.id.in_(expense_ids)).all()

                if expenses_to_delete:
                    total_deleted_amount = 0
                    category_deleted_amounts = defaultdict(float)

                    for expense in expenses_to_delete:
                        # 记录活动日志
                        activity = Activity(
                            project_id=self.project.id,
                            type="支出",
                            action="删除",
                            description=f"删除支出：{expense.content} - {expense.amount}元",
                            operator="系统用户"
                        )
                        session.add(activity)

                        # 累加删除金额用于预算调整
                        total_deleted_amount += expense.amount
                        category_deleted_amounts[expense.category] += expense.amount

                        # 删除凭证文件（如果存在）
                        if expense.voucher_path and os.path.exists(expense.voucher_path):
                            try:
                                os.remove(expense.voucher_path)
                                # Consider removing empty parent directories if desired
                            except OSError as e:
                                print(f"Warning: Could not delete voucher file {expense.voucher_path}: {e}")


                    # 调整预算子项金额
                    for category, deleted_amount in category_deleted_amounts.items():
                        budget_item = session.query(BudgetItem).filter_by(
                            budget_id=self.budget.id,
                            category=category
                        ).first()
                        if budget_item:
                            budget_item.spent_amount -= deleted_amount / 10000

                    # 调整预算总额
                    self.budget = session.merge(self.budget)
                    self.budget.spent_amount -= total_deleted_amount / 10000

                    # 批量删除记录
                    session.query(Expense).filter(Expense.id.in_(expense_ids)).delete(synchronize_session=False)
                    session.commit()

                    # 刷新表格
                    self.load_expenses() # Reload data after deleting
                    self.load_statistics()
                    # 发送信号通知预算管理窗口更新数据
                    self.expense_updated.emit()

                    UIUtils.show_success(
                        title='成功',
                        content='支出记录已删除！',
                        parent=self
                    )

                else:
                    UIUtils.show_warning(
                        title='警告',
                        content='未找到要删除的支出记录！',
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
        """Wraps the attachment handling logic for expense vouchers using attachment_utils."""
        expense_id = btn.property("item_id")
        if expense_id is None:
            # This error should ideally not happen with the new approach
            print(f"ERROR handle_voucher_wrapper: item_id is None for button: {btn}. This indicates an issue.")
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            # Fetch the expense item using the ID
            expense = session.query(Expense).get(expense_id)
            if not expense:
                UIUtils.show_error(self, "错误", f"找不到 ID 为 {expense_id} 的支出记录")
                return

            # Call the generic attachment handler from attachment_utils
            handle_attachment(
                event=event, # Pass the original event (QPoint or None)
                btn=btn,
                item=expense, # Pass the SQLAlchemy object
                session=session, # Pass the active session
                parent_widget=self, # Pass the current widget as parent
                project=self.project, # Pass the project object
                item_type='expense', # Specify the item type
                attachment_attr='voucher_path', # DB attribute storing the path
                base_folder='vouchers' # Base directory for storing these attachments
            )

            # Refresh the button state in the table after potential changes
            # Fetch the potentially updated expense item again
            # Use merge to ensure the object is tracked in the current session if needed, or refresh if already tracked
            expense = session.merge(expense) # Merge ensures it's in the current session
            session.refresh(expense) # Refresh its state from DB

            # Find the row and update the button widget
            # This might be inefficient for large tables, consider optimizing if needed
            # A more robust way might be to find the expense in self.current_expenses and update it, then call _populate_table
            # For now, let's try direct widget update
            for row in range(self.expense_table.rowCount()):
                # Check if the item ID in the first column matches
                id_item = self.expense_table.item(row, 0)
                if id_item and int(id_item.text()) == expense_id:
                    # Recreate the button in the correct row
                    new_container = create_attachment_button(
                        item_id=expense.id,
                        attachment_path=expense.voucher_path, # Use potentially updated path
                        handle_attachment_func=self.handle_voucher_wrapper,
                        parent_widget=self,
                        item_type='expense'
                    )
                    self.expense_table.setCellWidget(row, 8, new_container) # Column 8 for voucher/attachment
                    break # Exit loop once updated

        except Exception as e:
            session.rollback() # Rollback on any error during handling
            UIUtils.show_error(self, "错误", f"处理凭证时出错: {e}")
            print(f"Error in handle_voucher_wrapper: {e}") # Log for debugging
        finally:
            session.close() # Always close the session

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
        """应用筛选条件到内存中的支出列表并更新表格"""
        category_filter = self.category_combo.currentText()
        start_date_filter = self.start_date.date().toPython()
        end_date_filter = self.end_date.date().toPython()
        try:
            min_amount_text = self.min_amount.text().strip()
            max_amount_text = self.max_amount.text().strip()
            min_amount_filter = float(min_amount_text) if min_amount_text else None
            max_amount_filter = float(max_amount_text) if max_amount_text else None
        except ValueError:
            # Don't show warning immediately, allow user to finish typing
            # Instead, maybe highlight the field or just ignore invalid input for filtering
            min_amount_filter = None
            max_amount_filter = None
            # Or show warning only if both fields have text but are invalid?
            # For now, let's just ignore invalid input during filtering.
            pass # Ignore value error during intermediate typing

        filtered_expenses = []
        for expense in self.all_expenses: # Filter from the complete list
            # Category check
            if category_filter != "全部" and expense.category.value != category_filter:
                continue
            # Date check
            # Ensure expense.date is a date object for comparison
            expense_date = expense.date
            if isinstance(expense_date, datetime):
                expense_date = expense_date.date() # Convert datetime to date if necessary

            if expense_date < start_date_filter or expense_date > end_date_filter:
                continue
            # Amount check
            if min_amount_filter is not None and expense.amount < min_amount_filter:
                continue
            if max_amount_filter is not None and expense.amount > max_amount_filter:
                continue

            filtered_expenses.append(expense)

        self.current_expenses = filtered_expenses # Update the list used for display/sorting
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

                # 创建数据有效性验证表
                validation_data = pd.DataFrame({
                    '费用类别': [category.value for category in BudgetCategory],
                    '说明': [''] * len(BudgetCategory)
                })
                validation_data.to_excel(writer, sheet_name='费用类别', index=False)

                # 创建使用说明表
                instructions = [
                    "使用说明：",
                    "1. 费用类别、开支内容、报账金额为必填项",
                    "2. 费用类别必须是以下之一：",
                    "   " + "、".join([category.value for category in BudgetCategory]),
                    "3. 报账金额必须大于0",
                    "4. 报账日期格式为YYYY-MM-DD，可为空，默认为当前日期",
                    "5. 规格型号、供应商、备注为选填项",
                    "6. 请勿修改表头名称",
                    "7. 请勿删除或修改本说明"
                ]
                pd.DataFrame(instructions).to_excel(
                    writer,
                    sheet_name='使用说明',
                    index=False,
                    header=False
                )

            UIUtils.show_success(
                title='成功',
                content=f"支出记录已导出到：\n{excel_path}",
                parent=self
            )

            # 在文件资源管理器中打开导出目录
            import subprocess
            import platform
            if platform.system() == 'Windows':
                # Use os.startfile for better compatibility on Windows
                os.startfile(export_dir)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', export_dir])
            elif platform.system() == 'Linux':
                subprocess.run(['xdg-open', export_dir])

        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f"导出支出信息失败：{str(e)}",
                parent=self
            )

    def export_expense_vouchers(self):
        """导出支出凭证"""
        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not export_dir:
            return

        exported_count = 0
        skipped_count = 0
        error_files = []

        try:
            # 创建项目和年度子目录
            project_year_dir = os.path.join(export_dir, f"{self.project.financial_code}_{self.budget.year}_凭证")
            os.makedirs(project_year_dir, exist_ok=True)

            # 遍历当前显示的支出记录
            for expense in self.current_expenses:
                voucher_path = expense.voucher_path
                if voucher_path and os.path.exists(voucher_path):
                    try:
                        # 构建目标文件名：ID_类别_日期_内容.ext
                        base_filename = f"{expense.id}_{expense.category.value}_{expense.date.strftime('%Y%m%d')}_{expense.content}"
                        # Sanitize filename
                        safe_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in base_filename)
                        _, ext = os.path.splitext(voucher_path)
                        target_filename = f"{safe_filename}{ext}"
                        target_path = os.path.join(project_year_dir, target_filename)

                        # 复制文件
                        import shutil
                        shutil.copy2(voucher_path, target_path)
                        exported_count += 1
                    except Exception as copy_e:
                        print(f"Error copying voucher for expense {expense.id}: {copy_e}")
                        error_files.append(os.path.basename(voucher_path) if voucher_path else f"Expense ID {expense.id}")
                        skipped_count += 1
                else:
                    skipped_count += 1

            # 显示导出结果
            message = f"凭证导出完成。\n\n成功导出：{exported_count} 个\n跳过（无凭证或文件丢失）：{skipped_count} 个"
            if error_files:
                message += f"\n\n以下文件导出失败：\n" + "\n".join(error_files)

            if exported_count > 0:
                 UIUtils.show_success(self, "导出成功", message)
                 # 打开导出目录
                 import subprocess
                 import platform
                 if platform.system() == 'Windows':
                     os.startfile(project_year_dir)
                 elif platform.system() == 'Darwin':
                     subprocess.run(['open', project_year_dir])
                 else:
                     subprocess.run(['xdg-open', project_year_dir])

            elif skipped_count > 0 and not error_files:
                 UIUtils.show_info(self, "导出提示", message)
            else: # Only errors or nothing to export
                 UIUtils.show_warning(self, "导出失败", message)


        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f"导出支出凭证失败：{str(e)}",
                parent=self
            )

    def validate_amount_input(self):
        """验证金额输入框内容"""
        sender = self.sender()
        text = sender.text()
        if not text:
            return # Allow empty input

        try:
            # 尝试转换为浮点数
            amount = float(text)
            # 检查是否大于0
            if amount <= 0:
                 # 清空并提示错误
                sender.setText('')
                UIUtils.show_warning(
                    title='警告',
                    content='金额必须大于0',
                    parent=self
                )
        except ValueError:
            # 如果转换失败，清空输入框并提示错误
            sender.setText('')
            UIUtils.show_warning(
                title='警告',
                content='请输入有效的金额',
                parent=self
            )

    def sort_table(self, column):
        """对内存中的当前支出列表进行排序并更新表格"""
        if column == 8: # Don't sort by attachment button column
            return

        order = self.expense_table.horizontalHeader().sortIndicatorOrder()
        reverse_order = (order == Qt.DescendingOrder)

        try:
            # Define sort key based on column index using the Expense object attributes
            if column == 0: # 支出ID
                sort_key = lambda expense: expense.id
            elif column == 1: # 费用类别
                sort_key = lambda expense: expense.category.value
            elif column == 2: # 开支内容
                # Ensure case-insensitive sorting and handle None
                sort_key = lambda expense: (expense.content or "").lower()
            elif column == 3: # 规格型号
                sort_key = lambda expense: (expense.specification or "").lower()
            elif column == 4: # 供应商
                sort_key = lambda expense: (expense.supplier or "").lower()
            elif column == 5: # 报账金额
                sort_key = lambda expense: expense.amount
            elif column == 6: # 报账日期
                sort_key = lambda expense: expense.date
            elif column == 7: # 备注
                sort_key = lambda expense: (expense.remarks or "").lower()
            else:
                print(f"Warning: Attempted to sort by unknown column index {column}")
                return # Unknown column

            # Sort the current list (the one potentially filtered)
            self.current_expenses.sort(key=sort_key, reverse=reverse_order)

            # Repopulate the table with the sorted list
            self._populate_table(self.current_expenses)

        except Exception as e:
            UIUtils.show_error(self, "错误", f"排序失败: {e}")
