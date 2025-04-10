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
from ...utils.voucher_utils import create_voucher_button, create_voucher_menu, view_voucher
from collections import defaultdict

class ProjectExpenseWindow(QWidget):
    # 添加信号，用于通知预算清单窗口更新数据
    expense_updated = Signal()
    
    def __init__(self, engine, project, budget):
        super().__init__()
        self.engine = engine
        self.project = project
        self.budget = budget
        
        
        self.setup_ui()
        self.load_expenses()
        self.load_statistics()
        
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("支出清单")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 统一设置边距为15像素
        main_layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素
        
        # 标题
        title_layout = UIUtils.create_title_layout(f"支出清单-{self.project.financial_code}-{self.budget.year}", True, self.back_to_budget)
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
    
        
        # 设置表格样式
        UIUtils.set_table_style(self.expense_table)
        
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
        start_date = QDate(self.project.start_date.year, self.project.start_date.month, self.project.start_date.day)
        self.start_date.setDate(start_date)
        self.end_date.setDate(QDate.currentDate())
        # 清空金额输入框
        self.min_amount.clear()
        self.max_amount.clear()
        self.apply_filters()
        
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
        splitter.setStretchFactor(0, 5)  # 上部占4/5
        splitter.setStretchFactor(1, 2)  # 下部占1/5
        splitter.setChildrenCollapsible(False)  # 防止完全折叠
        
        main_layout.addWidget(splitter)
        
        # 设置整体样式
        self.setStyleSheet("""     
            QSplitter::handle {   // 分割条样式
                background-color: rgba(0, 0, 0, 0.1);
                margin: 2px 0px;  // 上下边距
            }
            QLabel {
                color: #333333;   // 文本颜色
            }
        """)
        
    def back_to_budget(self):
        """返回到预算清单页面"""
        # 获取父窗口（预算清单窗口）的QStackedWidget
        budget_window = self.parent()
        if isinstance(budget_window, QStackedWidget):
            # 切换到预算清单页面（第一个页面）
            budget_window.setCurrentWidget(budget_window.widget(0))
            # 从QStackedWidget中移除当前支出清单页面
            budget_window.removeWidget(self)
            
    def load_expenses(self):
        """加载支出数据"""
        try:
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            # 清空表格
            self.expense_table.setRowCount(0)
            
            # 查询支出数据
            expenses = session.query(Expense).filter(
                Expense.budget_id == self.budget.id
            ).order_by(Expense.date.desc()).all()
            
            # 填充表格
            for expense in expenses:
                row = self.expense_table.rowCount()
                self.expense_table.insertRow(row)
                
                # 设置单元格内容和对齐方式               
                
                 # 支出ID列
                id_item = QTableWidgetItem(str(expense.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 0, id_item)
                
                # 费用类别 - 居中对齐
                item = QTableWidgetItem(expense.category.value)
                item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, expense.id)  # 存储支出ID
                self.expense_table.setItem(row, 1, item)  
               
                # 开支内容 - 左对齐
                item = QTableWidgetItem(expense.content)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.expense_table.setItem(row, 2, item)
                
                # 规格型号 - 居中对齐
                item = QTableWidgetItem(expense.specification or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 3, item)
                
                # 供应商 - 居中对齐
                item = QTableWidgetItem(expense.supplier or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 4, item)
                
                # 报账金额 - 右对齐
                item = QTableWidgetItem(f"{expense.amount:.2f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.expense_table.setItem(row, 5, item)
                
                # 报账日期 - 居中对齐
                item = QTableWidgetItem(expense.date.strftime("%Y-%m-%d"))
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 6, item)
                
                # 备注 - 居中对齐
                item = QTableWidgetItem(expense.remarks or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 7, item)
                
                # 在其他单元格也存储支出ID，确保选中任意单元格都能获取ID
                for col in range(1, self.expense_table.columnCount()):
                    cell_item = self.expense_table.item(row, col)
                    if cell_item:
                        cell_item.setData(Qt.UserRole, expense.id)
                    elif col == 8:  # 处理凭证按钮
                        btn = self.expense_table.cellWidget(row, col)
                        if btn:
                            btn.setProperty("expense_id", expense.id)
                

                # 添加上传凭证按钮
                container = create_voucher_button(expense.id, expense.voucher_path, self.handle_voucher)
                self.expense_table.setCellWidget(row, 8, container)
                
               
                
            session.close()
            
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'加载支出数据失败：{str(e)}',
                parent=self
            )
            
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
            self.load_expenses()
            self.load_statistics()
            # 发送信号通知预算清单窗口更新数据
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
        """添加支出"""
        dialog = ExpenseDialog(self.project.id, self)
        if dialog.exec():
            try:
                # 获取表单数据
                data = dialog.get_data()
                
                Session = sessionmaker(bind=self.engine)
                session = Session()
                
                try:
                    # 创建新的支出记录
                    expense = Expense(
                        project_id=self.project.id,  # 添加project_id字段
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
                    
                    # 记录添加支出的活动
                    activity = Activity(
                        project_id=self.project.id,
                        budget_id=self.budget.id,
                        expense_id=expense.id,
                        type="支出",
                        action="新增",
                        description=f"添加支出：{data['content']} - {data['amount']}元",
                        operator="系统用户"
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
                    self.load_expenses()
                    self.load_statistics()
                    # 发送信号通知预算清单窗口更新数据
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
                    
            except Exception as e:
                UIUtils.show_error(
                    title='错误',
                    content=f'获取表单数据失败：{str(e)}',
                    parent=self
                )
                
    def edit_expense(self):
        """编辑支出"""
        # 获取当前选中的行
        selected_items = self.expense_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(
                title='警告',
                content='请选择一条要编辑的支出记录！',
                parent=self
            )
            return
            
        # 获取选中行的支出ID（从ID列获取）
        selected_row = selected_items[0].row()
        id_item = self.expense_table.item(selected_row, 0)  # 第0列是支出ID
        if not id_item:
            UIUtils.show_warning(
                title='警告',
                content='无法获取支出记录ID！',
                parent=self
            )
            return
            
        expense_id = id_item.text()
        
        Session = sessionmaker(bind=self.engine)
        session = Session()        
        try:
            # 直接通过ID查询支出记录
            expense = session.query(Expense).filter_by(id=expense_id).first()
            
            if expense:
                # 创建编辑对话框
                dialog = ExpenseDialog(self.project.id, self)
                
                # 设置当前数据
                dialog.set_data({
                    'category': expense.category,
                    'content': expense.content,
                    'specification': expense.specification,
                    'supplier': expense.supplier,
                    'amount': expense.amount,
                    'date': expense.date,
                    'remarks': expense.remarks
                })
                
                if dialog.exec():
                    try:
                        # 获取新数据
                        data = dialog.get_data()
                        
                        # 更新支出记录
                        old_amount = expense.amount
                        expense.category = data['category']
                        expense.content = data['content']
                        expense.specification = data['specification']
                        expense.supplier = data['supplier']
                        expense.amount = data['amount']
                        expense.date = data['date']
                        expense.remarks = data['remarks']
                        
                        # 更新预算子项的已支出金额
                        budget_item = session.query(BudgetItem).filter_by(
                            budget_id=self.budget.id,
                            category=data['category']
                        ).first()
                        
                        if budget_item:
                            # 减去旧金额，加上新金额
                            budget_item.spent_amount = budget_item.spent_amount - (old_amount / 10000) + (data['amount'] / 10000)
                            
                        # 更新预算总额的已支出金额
                        self.budget = session.merge(self.budget)
                        self.budget.spent_amount = self.budget.spent_amount - (old_amount / 10000) + (data['amount'] / 10000)
                        
                        # 记录编辑支出的活动
                        activity = Activity(
                            project_id=self.project.id,
                            budget_id=self.budget.id,
                            expense_id=expense.id,
                            type="支出",
                            action="编辑",
                            description=f"编辑支出：{data['content']} - {data['amount']}元",
                            operator="系统用户"
                        )
                        session.add(activity)
                        
                        session.commit()
                        self.load_expenses()
                        self.load_statistics()
                        # 发送信号通知预算清单窗口更新数据
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
            else:
                UIUtils.show_warning(
                    title='警告',
                    content='获取支出记录失败！',
                    parent=self
                )
                        
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'获取支出记录失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
            
    def delete_expense(self):
        """批量删除支出"""
        # 获取所有选中的行
        selected_ranges = self.expense_table.selectedRanges()
        if not selected_ranges:
            UIUtils.show_warning(
                title='警告',
                content='请选择要删除的支出记录！',
                parent=self
            )
            return
            
        # 收集所有选中的唯一行号
        selected_rows = set()
        for item in self.expense_table.selectedItems():
            selected_rows.add(item.row())

        # 获取所有支出ID
        expense_ids = []
        for row in selected_rows:
            id_item = self.expense_table.item(row, 0)
            if id_item:
                expense_ids.append(id_item.text())
                
        if not expense_ids:
            UIUtils.show_warning(
                title='警告',
                content='无法获取支出记录ID！',
                parent=self
            )
            return
            
        # 使用Dialog显示确认对话框
        confirm_dialog = Dialog(
            '确认批量删除',
            f'确定要删除选中的{len(expense_ids)}条支出记录吗？此操作不可恢复！',
            self
        )
        
        if confirm_dialog.exec():
            total_amount = 0
            category_amounts = defaultdict(float)
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            try:
                # 查询支出记录
                expenses = session.query(Expense).filter(Expense.id.in_(expense_ids)).all()
                
                if expenses:
                    # 计算总金额和分类金额
                    for expense in expenses:
                        total_amount += expense.amount
                        category_amounts[expense.category] += expense.amount

                    # 更新预算子项
                    for category, amount in category_amounts.items():
                        budget_item = session.query(BudgetItem).filter_by(
                            budget_id=self.budget.id,
                            category=category
                        ).first()
                        if budget_item:
                            budget_item.spent_amount -= amount / 10000

                    # 更新总预算
                    self.budget = session.merge(self.budget)
                    self.budget.spent_amount -= total_amount / 10000

                    # 记录删除支出的活动
                    for expense in expenses:
                        activity = Activity(
                            project_id=self.project.id,
                            budget_id=self.budget.id,
                            expense_id=expense.id,
                            type="支出",
                            action="删除",
                            description=f"删除支出：{expense.content} - {expense.amount}元",
                            operator="系统用户"
                        )
                        session.add(activity)
                    
                    # 批量删除记录
                    session.query(Expense).filter(Expense.id.in_(expense_ids)).delete(synchronize_session=False)
                    session.commit()
                    
                    # 刷新表格
                    self.load_expenses()
                    self.load_statistics()
                    # 发送信号通知预算清单窗口更新数据
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

    def get_voucher_path(self, expense, file_ext=None):
        """生成凭证文件路径"""
        # 生成基础目录：vouchers/项目编号/年度
        base_dir = os.path.join("vouchers", self.project.financial_code, str(self.budget.year))
        
        # 生成文件名：类别_日期_内容
        filename_parts = [
            expense.category.value,       # 类别
            expense.date.strftime("%Y%m%d"),  # 日期
            expense.content               # 内容
        ]
        # 确保文件名合法
        filename = "_".join(filename_parts)
        filename = "".join(c for c in filename if c.isalnum() or c in ('_', '.', '-'))
        
        # 如果提供了扩展名，添加到文件名中
        if file_ext:
            filename = f"{filename}{file_ext}"
            
        return os.path.join(base_dir, filename)

    def handle_voucher(self, event, btn):
        """处理凭证上传、替换、删除或查看"""
        expense_id = btn.property("expense_id")
        current_path = btn.property("voucher_path")
        
        Session = sessionmaker(bind=self.engine)
        session = Session()
        expense = session.query(Expense).get(expense_id)
        
        if not expense:
            session.close()
            return
            
        # 检查当前凭证文件是否存在
        has_valid_voucher = current_path and os.path.exists(current_path)
        
        if has_valid_voucher:  # 已有有效凭证
            if event and event.button() == Qt.RightButton:  # 右键点击
                # 创建右键菜单
                menu = create_voucher_menu(
                    parent=self,
                    current_path=current_path,
                    view_func=lambda path: view_voucher(path, self),
                    replace_func=lambda: self.replace_voucher(expense, session, btn),
                    delete_func=lambda: self.delete_voucher(expense, session, btn, current_path)
                )
                
                # 显示菜单并获取用户选择
                menu.exec_(event.globalPos())
            else:  # 左键点击，直接查看凭证
                view_voucher(current_path, self)
        else:  # 无凭证或凭证文件不存在
            if current_path:  # 数据库中有路径但文件不存在
                # 更新数据库和按钮状态
                expense.voucher_path = None
                session.commit()
                btn.setProperty("voucher_path", None)
                btn.setIcon(FluentIcon.ADD_TO)
            
            # 上传新凭证
            self.replace_voucher(expense, session, btn)
        
        session.close()
        
    def replace_voucher(self, expense, session, sender):
        """替换或上传新凭证"""
        import os
        import shutil
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择凭证文件",
            "",
            "支持的文件 (*.pdf *.jpg *.jpeg *.png)"
        )
        
        if file_path:
            try:
                # 获取文件扩展名
                _, file_ext = os.path.splitext(file_path)
                
                # 生成目标路径
                target_path = self.get_voucher_path(expense, file_ext)
                
                # 确保目标目录存在
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                # 复制文件
                shutil.copy2(file_path, target_path)
                
                # 更新数据库
                expense.voucher_path = target_path
                session.commit()
                
                # 更新按钮状态
                sender.setIcon(FluentIcon.CERTIFICATE)
                sender.setIconSize(QSize(16, 16)) # 设置图标大小
                sender.setProperty("voucher_path", target_path)
                
            except Exception as e:
                UIUtils.show_warning(
                title='警告',
                content=f"上传凭证失败: {str(e)}",
                parent=self
            )

    def view_voucher(self, voucher_path):
        """查看凭证文件"""
        import platform
        import subprocess
        import os
        
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', voucher_path])
            elif platform.system() == 'Windows':
                os.startfile(voucher_path)
            else:  # Linux或其他系统
                subprocess.run(['xdg-open', voucher_path])
        except Exception as e:
            UIUtils.show_warning(
                title='警告',
                content=f"打开凭证文件失败: {str(e)}",
                parent=self
            )
            
    def delete_voucher(self, expense, session, btn, voucher_path):
        """删除凭证文件"""
        import os
        
        # 确认删除
        confirm_dialog = Dialog(
            '确认删除',
            '确定要删除该凭证吗？此操作不可恢复！',
            self
        )
        
        if confirm_dialog.exec():
            try:
                # 如果文件存在则删除
                if os.path.exists(voucher_path):
                    os.remove(voucher_path)
                
                # 更新数据库
                expense.voucher_path = None
                session.commit()
                
                # 更新按钮状态
                btn.setIcon(FluentIcon.ADD_TO)
                btn.setIconSize(QSize(16, 16))
                btn.setProperty("voucher_path", None)
                
                UIUtils.show_success(
                    title='成功',
                    content='凭证已成功删除',
                    parent=self
                )
                
            except Exception as e:
                UIUtils.show_error(
                    title='错误',
                    content=f"删除凭证失败: {str(e)}",
                    parent=self
                )

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
        self.apply_filters()
        
    def apply_filters(self):
        """应用筛选条件"""
        filters = {
            'category': None if self.category_combo.currentText() == "全部" else self.category_combo.currentText(),
            'start_date': self.start_date.date().toPython(),
            'end_date': self.end_date.date().toPython(),
            'min_amount': float(self.min_amount.text()) if self.min_amount.text() and float(self.min_amount.text()) > 0 else None,
            'max_amount': float(self.max_amount.text()) if self.max_amount.text() and float(self.max_amount.text()) > 0 else None,
            'supplier': None
        }
        
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            # 构建查询
            query = session.query(Expense).filter(Expense.budget_id == self.budget.id)
            
            # 应用筛选条件
            if filters['category']:
                query = query.filter(Expense.category == BudgetCategory(filters['category']))
            if filters['start_date']:
                query = query.filter(Expense.date >= filters['start_date'])
            if filters['end_date']:
                query = query.filter(Expense.date <= filters['end_date'])
            if filters['min_amount']:
                query = query.filter(Expense.amount >= filters['min_amount'])
            if filters['max_amount']:
                query = query.filter(Expense.amount <= filters['max_amount'])
            
            # 获取筛选后的支出记录
            expenses = query.order_by(Expense.date.desc()).all()
            
            # 更新表格显示
            self.expense_table.setRowCount(0)
            for expense in expenses:
                row = self.expense_table.rowCount()
                self.expense_table.insertRow(row)
                
                
                # 设置单元格内容
                id_item = QTableWidgetItem(str(expense.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 0, id_item)

                item = QTableWidgetItem(expense.category.value)
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 1, item)
                
                item = QTableWidgetItem(expense.content)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.expense_table.setItem(row, 2, item)
                
                item = QTableWidgetItem(expense.specification or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 3, item)
                
                item = QTableWidgetItem(expense.supplier or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 4, item)
                
                item = QTableWidgetItem(f"{expense.amount:.2f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.expense_table.setItem(row, 5, item)
                
                item = QTableWidgetItem(expense.date.strftime("%Y-%m-%d"))
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 6, item)
                
                item = QTableWidgetItem(expense.remarks or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 7, item)
                
                # 添加凭证按钮
                container = create_voucher_button(expense.id, expense.voucher_path, self.handle_voucher)
                self.expense_table.setCellWidget(row, 8, container)
                
                
                
            session.close()
            
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f"应用筛选条件失败：{str(e)}",
                parent=self
            )
        finally:
            session.close()
            
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
            # 获取当前显示的支出记录（考虑筛选条件）
            expenses = []
            for row in range(self.expense_table.rowCount()):
                expense_data = {
                    'category': self.expense_table.item(row, 1).text(),
                    'content': self.expense_table.item(row, 2).text(),
                    'specification': self.expense_table.item(row, 3).text(),
                    'supplier': self.expense_table.item(row, 4).text(),
                    'amount': float(self.expense_table.item(row, 5).text()),
                    'date': self.expense_table.item(row, 6).text(),
                    'remarks': self.expense_table.item(row, 7).text()
                }
                expenses.append(expense_data)
            
            # 导出Excel文件
            import pandas as pd
            from datetime import datetime
            
            # 创建DataFrame
            df = pd.DataFrame(expenses)
            
            # 重命名列
            df.columns = ['费用类别', '开支内容', '规格型号', '供应商', '报账金额', '报账日期', '备注']
            
            # 确保日期格式为YYYY-MM-DD
            df['报账日期'] = pd.to_datetime(df['报账日期'], format='%Y-%m-%d').dt.strftime('%Y-%m-%d')
            
            # 生成Excel文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"支出记录_{timestamp}.xlsx"
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

            # 在文件资源清单器中打开导出目录
            import subprocess
            import platform
            if platform.system() == 'Windows':
                subprocess.run(['explorer', export_dir])
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
            
        try:
            # 创建凭证目录结构：导出目录/支出凭证/项目编号/年度/
            vouchers_dir = os.path.join(
                export_dir, 
                "支出凭证",
                self.project.financial_code,
                str(self.budget.year)
            )
            os.makedirs(vouchers_dir, exist_ok=True)
            
            # 复制凭证文件
            import shutil
            exported_count = 0
            
            # 获取当前显示的所有支出记录
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            try:
                for row in range(self.expense_table.rowCount()):
                    voucher_btn = self.expense_table.cellWidget(row, 8)
                    voucher_path = voucher_btn.property("voucher_path")
                    expense_id = voucher_btn.property("expense_id")
                    
                    if voucher_path and os.path.exists(voucher_path):
                        # 获取支出记录
                        expense = session.query(Expense).get(expense_id)
                        if expense:
                            # 获取原始文件扩展名
                            _, ext = os.path.splitext(voucher_path)
                            
                            # 生成目标路径
                            target_path = os.path.join(
                                vouchers_dir,
                                os.path.basename(self.get_voucher_path(expense, ext))
                            )
                            
                            # 复制文件
                            shutil.copy2(voucher_path, target_path)
                            exported_count += 1
            finally:
                session.close()
            
            if exported_count > 0:
                UIUtils.show_success(
                    title='导出成功',
                    content=f"已导出 {exported_count} 个支出凭证到：\n{vouchers_dir}",
                    parent=self
                )
                # 在文件资源清单器中打开导出目录
                os.startfile(vouchers_dir)
            else:
                UIUtils.show_info(
                    title='提示',
                    content= "当前筛选结果中没有可导出的支出凭证",
                    parent=self
                )
            
        except Exception as e:
            UIUtils.show_error(
                    title='错误',
                    content= f"导出支出凭证失败：{str(e)}",
                    parent=self
                )
            
    def validate_amount_input(self):
        """验证金额输入"""
        sender = self.sender()
        text = sender.text()
        
        # 如果输入为空，允许
        if not text:
            return
            
        try:
            # 尝试转换为浮点数
            amount = float(text)
            # 确保金额不为负数
            if amount < 0:
                sender.setText('')
                UIUtils.show_warning(
                    title='警告',
                    content='金额不能为负数',
                    parent=self
                )
        except ValueError:
            # 如果转换失败，清空输入并显示警告
            sender.setText('')
            UIUtils.show_warning(
                title='警告',
                content='请输入有效的金额',
                parent=self
            )

    def sort_table(self, column):
        """排序表格"""
        # 获取当前排序顺序
        order = self.expense_table.horizontalHeader().sortIndicatorOrder()
        
        # 获取所有行的数据
        rows_data = []
        for row in range(self.expense_table.rowCount()):
            row_data = []
            for col in range(self.expense_table.columnCount()):
                if col == 8:  # 支出凭证列
                    container = self.expense_table.cellWidget(row, col)
                    if container:
                        # 从容器中获取按钮
                        btn = container.findChild(ToolButton)
                        if btn:
                            row_data.append({
                                'expense_id': btn.property("expense_id"),
                                'voucher_path': btn.property("voucher_path")
                            })
                        else:
                            row_data.append(None)
                    else:
                        row_data.append(None)
                else:
                    item = self.expense_table.item(row, col)
                    row_data.append(item.text() if item else "")
            rows_data.append(row_data)
        
        # 根据选定列排序
        if column != 8:  # 不对支出凭证列进行排序
            def sort_key(x):
                value = x[column]
                if not value:  # 处理空值
                    return float('-inf') if order == Qt.AscendingOrder else float('inf')
                # 尝试转换为数字
                try:
                    # 移除可能的货币符号和空格
                    cleaned_value = value.strip().replace('¥', '').replace(',', '')
                    if cleaned_value.replace('.', '').isdigit():
                        return float(cleaned_value)
                except (ValueError, AttributeError):
                    pass
                # 如果不是数字，返回原始值
                return value
            
            rows_data.sort(key=sort_key, reverse=(order == Qt.DescendingOrder))
        
        # 更新表格数据
        for row, row_data in enumerate(rows_data):
            for col, cell_data in enumerate(row_data):
                if col == 8:  # 支出凭证列
                    if cell_data:
                        # 创建新的按钮和容器
                        container = create_voucher_button(cell_data['expense_id'], cell_data['voucher_path'], self.handle_voucher)                        
                        self.expense_table.setCellWidget(row, col, container)
                else:
                    item = QTableWidgetItem(str(cell_data))
                    if col == 1:  # 费用类别列
                        item.setTextAlignment(Qt.AlignCenter)
                    elif col == 2:  # 开支内容列
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    elif col == 5:  # 报账金额列
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:  # 其他列
                        item.setTextAlignment(Qt.AlignCenter)
                    self.expense_table.setItem(row, col, item)