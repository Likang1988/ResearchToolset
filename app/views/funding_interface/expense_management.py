import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                 QMessageBox, QStackedWidget, QSplitter,
                                 QFileDialog, QFrame, QTableWidgetItem,
                                 QHeaderView)
from PySide6.QtCore import Qt, Signal, QDate, QSize
from qfluentwidgets import (FluentIcon, TableWidget, PushButton, ComboBox, CalendarPicker, 
                           LineEdit, SpinBox, TableItemDelegate, TitleLabel, InfoBar, Dialog, RoundMenu, PrimaryPushButton, ToolButton, Action)
from ...models.database import sessionmaker, Budget, BudgetCategory, Expense, BudgetItem
from datetime import datetime
from ...components.expense_dialog import ExpenseDialog
from ...utils.ui_utils import UIUtils
from ...utils.db_utils import DBUtils

class ExpenseManagementWindow(QWidget):
    # 添加信号，用于通知预算管理窗口更新数据
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
        self.setWindowTitle("支出管理")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)  # 统一设置边距为15像素
        main_layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素
        
        # 标题
        title_layout = UIUtils.create_title_layout(f"支出管理-{self.project.financial_code}-{self.budget.year}", True, self.back_to_budget)
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
        self.expense_table.setColumnCount(9)  # 增加支出ID列
        self.expense_table.setHorizontalHeaderLabels([
            "费用类别", "开支内容", "规格型号", "供应商", 
            "报账金额(元)", "报账日期", "备注", "支出凭证", "支出ID"
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
        
        # 设置初始列宽
        header.resizeSection(0, 100)  # 费用类别
        header.resizeSection(1, 220)  # 开支内容
        header.resizeSection(2, 140)  # 规格型号
        header.resizeSection(3, 140)  # 供应商
        header.resizeSection(4, 100)  # 报账金额
        header.resizeSection(5, 100)  # 报账日期
        header.resizeSection(6, 120)  # 备注
        header.resizeSection(7, 100)  # 支出凭证
        header.resizeSection(8, 80)  # 支出ID
        
        # 允许用户调整列宽
        header.setSectionsMovable(True) # 可移动列
        
        self.expense_table.setSelectionBehavior(TableWidget.SelectRows) # 选中整行
        self.expense_table.setSelectionMode(TableWidget.ExtendedSelection) # 允许多选
        
        # 设置表格样式
        UIUtils.set_table_style(self.expense_table)
        
        top_layout.addWidget(self.expense_table) # 添加到布局中
        
        # 添加筛选工具栏
        filter_toolbar = QWidget()
        filter_layout = QHBoxLayout(filter_toolbar)
        filter_layout.setContentsMargins(0, 5, 0, 15)  # 设置边距，增加上下间距
        
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
        self.start_date = CalendarPicker()
        self.end_date = CalendarPicker()
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
        bottom_layout.setContentsMargins(0, 15, 0, 0)   #上下边距为10
        
        self.stats_table = TableWidget()   # 使用Fluent风格的TableWidget
        # 将合计列放在间接费右侧
        categories = list(BudgetCategory)
        indirect_index = categories.index(BudgetCategory.INDIRECT)
        self.headers = ["分类统计"] + [c.value for c in categories[:indirect_index+1]] + ["合计"] + [c.value for c in categories[indirect_index+1:]]
        self.stats_table.setColumnCount(len(self.headers))
        self.stats_table.setHorizontalHeaderLabels(self.headers)
        
        # 设置表格样式
        self.stats_table.setBorderVisible(True)
        self.stats_table.setBorderRadius(8)
        self.stats_table.setWordWrap(False)
        self.stats_table.setItemDelegate(TableItemDelegate(self.stats_table))
        self.stats_table.setSelectionBehavior(TableWidget.SelectRows)
        self.stats_table.setSelectionMode(TableWidget.SingleSelection)
        
        # 设置表格样式
        self.stats_table.setStyleSheet("""
            TableWidget {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                selection-background-color: rgba(0, 120, 212, 0.1);
                selection-color: black;
            }
            TableWidget::item {
                padding: 4px 8px;
                border: none;
                height: 32px;
            }
            TableWidget::item:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QHeaderView::section {
                background-color: #f3f3f3;
                color: #333333;
                font-weight: 500;
                padding: 8px;
                border: none;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            }
            QHeaderView::section:hover {
                background-color: #e5e5e5;
            }
        """)
        
        bottom_layout.addWidget(self.stats_table)
        splitter.addWidget(bottom_widget)
        
        # 设置初始比例和可调整性
        splitter.setStretchFactor(0, 5)  # 上部占4/5
        splitter.setStretchFactor(1, 2)  # 下部占1/5
        splitter.setChildrenCollapsible(False)  # 防止完全折叠
        
        main_layout.addWidget(splitter)
        
        # 设置整体样式
        self.setStyleSheet("""     
            QSplitter::handle {
                background-color: rgba(0, 0, 0, 0.1);
                margin: 2px 0px;  // 上下边距
            }
            QLabel {
                color: #333333;
            }
        """)
        
    def back_to_budget(self):
        """返回到预算管理页面"""
        # 获取父窗口（预算管理窗口）的QStackedWidget
        budget_window = self.parent()
        if isinstance(budget_window, QStackedWidget):
            # 切换到预算管理页面（第一个页面）
            budget_window.setCurrentWidget(budget_window.widget(0))
            # 从QStackedWidget中移除当前支出管理页面
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
                # 费用类别 - 居中对齐
                item = QTableWidgetItem(expense.category.value)
                item.setTextAlignment(Qt.AlignCenter)
                item.setData(Qt.UserRole, expense.id)  # 存储支出ID
                self.expense_table.setItem(row, 0, item)
                
                # 在其他单元格也存储支出ID，确保选中任意单元格都能获取ID
                for col in range(1, self.expense_table.columnCount()):
                    cell_item = self.expense_table.item(row, col)
                    if cell_item:
                        cell_item.setData(Qt.UserRole, expense.id)
                    elif col == 7:  # 处理凭证按钮
                        btn = self.expense_table.cellWidget(row, col)
                        if btn:
                            btn.setProperty("expense_id", expense.id)
                
                # 开支内容 - 左对齐
                item = QTableWidgetItem(expense.content)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.expense_table.setItem(row, 1, item)
                
                # 规格型号 - 居中对齐
                item = QTableWidgetItem(expense.specification or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 2, item)
                
                # 供应商 - 居中对齐
                item = QTableWidgetItem(expense.supplier or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 3, item)
                
                # 报账金额 - 右对齐
                item = QTableWidgetItem(f"{expense.amount:.2f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.expense_table.setItem(row, 4, item)
                
                # 报账日期 - 居中对齐
                item = QTableWidgetItem(expense.date.strftime("%Y-%m-%d"))
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 5, item)
                
                # 备注 - 居中对齐
                item = QTableWidgetItem(expense.remarks or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 6, item)
                
                # 添加上传凭证按钮
                upload_btn = ToolButton()
                upload_btn.setFixedSize(30, 30)  # 设置按钮大小
                if not expense.voucher_path:
                    # 显示添加图标
                    upload_btn.setIcon(FluentIcon.ADD_TO)
                    upload_btn.setIconSize(QSize(16, 16))
                    upload_btn.setStyleSheet("""
                        QPushButton {
                            background: transparent;
                        }
                        QPushButton:hover {
                            background: rgba(24, 144, 255, 0.1);
                            border-radius: 4px;
                        }
                    """)
                else:
                    # 显示凭证图标
                    upload_btn.setIcon(FluentIcon.CERTIFICATE)
                    upload_btn.setIconSize(QSize(16, 16))
                    upload_btn.setStyleSheet("""
                        QPushButton {
                            background: transparent;
                        }
                        QPushButton:hover {
                            background: rgba(24, 144, 255, 0.1);
                            border-radius: 4px;  
                        }
                    """)
                upload_btn.setProperty("expense_id", expense.id)
                upload_btn.setProperty("voucher_path", expense.voucher_path)
                upload_btn.mousePressEvent = lambda event, btn=upload_btn: self.handle_voucher(event, btn)
                
                # 创建容器widget用于居中显示按钮
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                layout.setAlignment(Qt.AlignCenter)
                layout.addWidget(upload_btn, 0, Qt.AlignCenter)
                self.expense_table.setCellWidget(row, 7, container)
                
                # 添加支出ID列
                id_item = QTableWidgetItem(str(expense.id))
                id_item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 8, id_item)
                
            session.close()
            
        except Exception as e:
            InfoBar.error(
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
            header.resizeSection(0, 102)  # 类别列
            for i in range(1, len(self.headers)):
                header.resizeSection(i, 84)  # 数据列
                
            # 确保headers在load_statistics方法中可用
            if not hasattr(self, 'headers'):
                categories = list(BudgetCategory)
                indirect_index = categories.index(BudgetCategory.INDIRECT)
                self.headers = ["分类统计"] + [c.value for c in categories[:indirect_index+1]] + ["合计"] + [c.value for c in categories[indirect_index+1:]]
                
            # 设置表格样式
            self.stats_table.setStyleSheet("""
                QTableWidget {
                    background-color: transparent;
                    border: 1px solid rgba(0, 0, 0, 0.1);
                    border-radius: 8px;
                    selection-background-color: rgba(0, 120, 212, 0.1);
                    selection-color: black;
                }
                QTableWidget::item {
                    padding: 4px 8px;
                    border: none;
                }
                QTableWidget::item:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                }
                QHeaderView::section {
                    background-color: #f3f3f3;
                    color: #333333;
                    font-weight: 500;
                    padding: 8px;
                    border: none;
                    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
                }
                QHeaderView::section:hover {
                    background-color: #e5e5e5;
                }
            """)
            
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
            # 发送信号通知预算管理窗口更新数据
            self.expense_updated.emit()
            
        except Exception as e:
            session.rollback()
            InfoBar.error(
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
                    # 发送信号通知预算管理窗口更新数据
                    self.expense_updated.emit()
                    
                    InfoBar.success(
                        title='成功',
                        content='支出记录已添加！',
                        parent=self
                    )
                    
                except Exception as e:
                    session.rollback()
                    InfoBar.error(
                        title='错误',
                        content=f'添加支出失败：{str(e)}',
                        parent=self
                    )
                finally:
                    session.close()
                    
            except Exception as e:
                InfoBar.error(
                    title='错误',
                    content=f'获取表单数据失败：{str(e)}',
                    parent=self
                )
                
    def edit_expense(self):
        """编辑支出"""
        # 获取当前选中的行
        selected_items = self.expense_table.selectedItems()
        if not selected_items:
            InfoBar.warning(
                title='警告',
                content='请选择一条要编辑的支出记录！',
                parent=self
            )
            return
            
        # 获取选中行的支出ID（从ID列获取）
        selected_row = selected_items[0].row()
        id_item = self.expense_table.item(selected_row, 8)  # 第8列是支出ID
        if not id_item:
            InfoBar.warning(
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
                        
                        session.commit()
                        self.load_expenses()
                        self.load_statistics()
                        # 发送信号通知预算管理窗口更新数据
                        self.expense_updated.emit()
                        
                        InfoBar.success(
                            title='成功',
                            content='支出记录已更新！',
                            parent=self
                        )
                        
                    except Exception as e:
                        session.rollback()
                        InfoBar.error(
                            title='错误',
                            content=f'编辑支出失败：{str(e)}',
                            parent=self
                        )
            else:
                InfoBar.warning(
                    title='警告',
                    content='获取支出记录失败！',
                    parent=self
                )
                        
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'获取支出记录失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
            
    def delete_expense(self):
        """删除支出"""
        """删除支出"""
        # 获取当前选中的行
        selected_items = self.expense_table.selectedItems()
        if not selected_items:
            InfoBar.warning(
                title='警告',
                content='请选择要删除的支出记录！',
                parent=self
            )
            return
            
        # 获取选中行的支出ID（从ID列获取）
        selected_row = selected_items[0].row()
        id_item = self.expense_table.item(selected_row, 8)  # 第8列是支出ID
        if not id_item:
            InfoBar.warning(
                title='警告',
                content='无法获取支出记录ID！',
                parent=self
            )
            return
            
        expense_id = id_item.text()
        
        # 使用Dialog显示确认对话框
        confirm_dialog = Dialog(
            '确认删除',
            '确定要删除该支出记录吗？此操作不可恢复！',
            self
        )
        
        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            try:
                # 查询支出记录
                expense = session.query(Expense).filter_by(id=expense_id).first()
                
                if expense:
                    # 更新预算子项的已支出金额
                    budget_item = session.query(BudgetItem).filter_by(
                        budget_id=self.budget.id,
                        category=expense.category
                    ).first()
                    
                    if budget_item:
                        budget_item.spent_amount -= expense.amount / 10000
                        
                    # 更新预算总额的已支出金额
                    self.budget = session.merge(self.budget)
                    self.budget.spent_amount -= expense.amount / 10000
                    
                    # 删除支出记录
                    session.delete(expense)
                    session.commit()
                    
                    # 刷新表格
                    self.load_expenses()
                    self.load_statistics()
                    # 发送信号通知预算管理窗口更新数据
                    self.expense_updated.emit()
                    
                    InfoBar.success(
                        title='成功',
                        content='支出记录已删除！',
                        parent=self
                    )
                    
                else:
                    InfoBar.warning(
                        title='警告',
                        content='未找到要删除的支出记录！',
                        parent=self
                    )
                    
            except Exception as e:
                session.rollback()
                InfoBar.error(
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
        import os
        import shutil
        import subprocess
        import platform
        
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
                menu = RoundMenu(parent=self)
                # 添加菜单项并设置图标
                view_action = Action(FluentIcon.VIEW, "查看凭证", self)
                replace_action = Action(FluentIcon.SYNC, "替换凭证", self)
                delete_action = Action(FluentIcon.DELETE, "删除凭证", self)
                
                # 连接信号到槽函数
                view_action.triggered.connect(lambda: self.view_voucher(current_path))
                replace_action.triggered.connect(lambda: self.replace_voucher(expense, session, btn))
                delete_action.triggered.connect(lambda: self.delete_voucher(expense, session, btn, current_path))
                
                menu.addAction(view_action)
                menu.addAction(replace_action)
                menu.addAction(delete_action)
                
                # 显示菜单并获取用户选择
                menu.exec_(event.globalPos())
            else:  # 左键点击，直接查看凭证
                try:
                    if platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', current_path])
                    elif platform.system() == 'Windows':
                        os.startfile(current_path)
                    else:  # Linux或其他系统
                        subprocess.run(['xdg-open', current_path])
                except Exception as e:
                    InfoBar.warning(
                        title='警告',
                        content=f"打开凭证文件失败: {str(e)}",
                        parent=self
                    )
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
                sender.setStyleSheet("""
                    QPushButton {
                        border: none;
                        background: transparent;
                    }
                    QPushButton:hover {
                        background: rgba(24, 144, 255, 0.1);
                        border-radius: 4px;
                    }
                """)
                sender.setProperty("voucher_path", target_path)
                
            except Exception as e:
                InfoBar.warning(
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
            InfoBar.warning(
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
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                    }
                    QPushButton:hover {
                        background: rgba(24, 144, 255, 0.1);
                        border-radius: 4px;
                    }
                """)
                btn.setProperty("voucher_path", None)
                
                InfoBar.success(
                    title='成功',
                    content='凭证已成功删除',
                    parent=self
                )
                
            except Exception as e:
                InfoBar.error(
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
            'start_date': self.start_date.getDate().toPython(),
            'end_date': self.end_date.getDate().toPython(),
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
                item = QTableWidgetItem(expense.category.value)
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 0, item)
                
                item = QTableWidgetItem(expense.content)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.expense_table.setItem(row, 1, item)
                
                item = QTableWidgetItem(expense.specification or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 2, item)
                
                item = QTableWidgetItem(expense.supplier or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 3, item)
                
                item = QTableWidgetItem(f"{expense.amount:.2f}")
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.expense_table.setItem(row, 4, item)
                
                item = QTableWidgetItem(expense.date.strftime("%Y-%m-%d"))
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 5, item)
                
                item = QTableWidgetItem(expense.remarks or "")
                item.setTextAlignment(Qt.AlignCenter)
                self.expense_table.setItem(row, 6, item)
                
                # 添加凭证按钮
                upload_btn = PushButton("上传凭证" if not expense.voucher_path else "查看凭证")
                upload_btn.setProperty("expense_id", expense.id)
                upload_btn.setProperty("voucher_path", expense.voucher_path)
                upload_btn.mousePressEvent = lambda event, btn=upload_btn: self.handle_voucher(event, btn)
                self.expense_table.setCellWidget(row, 7, upload_btn)
                
        except Exception as e:
            InfoBar.error(
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
                    'category': self.expense_table.item(row, 0).text(),
                    'content': self.expense_table.item(row, 1).text(),
                    'specification': self.expense_table.item(row, 2).text(),
                    'supplier': self.expense_table.item(row, 3).text(),
                    'amount': float(self.expense_table.item(row, 4).text()),
                    'date': self.expense_table.item(row, 5).text(),
                    'remarks': self.expense_table.item(row, 6).text()
                }
                expenses.append(expense_data)
            
            # 导出Excel文件
            import pandas as pd
            from datetime import datetime
            
            # 创建DataFrame
            df = pd.DataFrame(expenses)
            
            # 重命名列
            df.columns = ['费用类别', '开支内容', '规格型号', '供应商', '报账金额(元)', '报账日期', '备注']
            
            # 生成Excel文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f"支出记录_{timestamp}.xlsx"
            excel_path = os.path.join(export_dir, excel_filename)
            
            # 保存Excel文件
            df.to_excel(excel_path, index=False, engine='openpyxl')
            
            InfoBar.success(
                title='成功',
                content=f"支出记录已导出到：\n{excel_path}",
                parent=self
            )

            # 在文件资源管理器中打开导出目录
            os.startfile(export_dir)
            
        except Exception as e:
            InfoBar.error(
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
                    voucher_btn = self.expense_table.cellWidget(row, 7)
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
                InfoBar.success(
                    title='导出成功',
                    content=f"已导出 {exported_count} 个支出凭证到：\n{vouchers_dir}",
                    parent=self
                )
                # 在文件资源管理器中打开导出目录
                os.startfile(vouchers_dir)
            else:
                InfoBar.info(
                    title='提示',
                    content= "当前筛选结果中没有可导出的支出凭证",
                    parent=self
                )
            
        except Exception as e:
            InfoBar.error(
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
                InfoBar.warning(
                    title='警告',
                    content='金额不能为负数',
                    parent=self
                )
        except ValueError:
            # 如果转换失败，清空输入并显示警告
            sender.setText('')
            InfoBar.warning(
                title='警告',
                content='请输入有效的金额',
                parent=self
            )

    def sort_table(self, column):
        """根据列排序表格"""
        # 获取当前排序顺序
        header = self.expense_table.horizontalHeader()
        order = header.sortIndicatorOrder()
        
        # 获取所有行的数据
        rows = []
        for row in range(self.expense_table.rowCount()):
            row_data = []
            for col in range(self.expense_table.columnCount()):
                if col == 7:  # 处理凭证列
                    # 获取凭证按钮的容器
                    container = self.expense_table.cellWidget(row, col)
                    if container:
                        # 从容器中获取按钮
                        btn = container.findChild(PushButton)
                        if btn:
                            row_data.append({
                                'expense_id': btn.property("expense_id"),
                                'voucher_path': btn.property("voucher_path")
                            })
                        else:
                            row_data.append(None)
                    else:
                        row_data.append(None)
                    continue
                
                item = self.expense_table.item(row, col)
                if col == 4:  # 金额列，转换为数字
                    value = float(item.text())
                elif col == 5:  # 日期列，转换为日期对象
                    value = datetime.strptime(item.text(), "%Y-%m-%d")
                else:
                    value = item.text()
                row_data.append(value)
            rows.append(row_data)
        
        # 根据选定的列进行排序
        if column != 7:  # 不对凭证列排序
            rows.sort(key=lambda x: x[column], reverse=(order == Qt.DescendingOrder))
        
        # 重新填充表格
        self.expense_table.setRowCount(0)  # 清空表格
        self.expense_table.setRowCount(len(rows))  # 重新设置行数
        
        for i, row_data in enumerate(rows):
            for col in range(self.expense_table.columnCount()):
                if col == 7:  # 处理凭证按钮
                    btn_data = row_data[col]
                    if btn_data:
                        # 创建新的按钮容器
                        container = QWidget()
                        layout = QHBoxLayout(container)
                        layout.setContentsMargins(0, 0, 0, 0)
                        layout.setSpacing(0)
                        layout.setAlignment(Qt.AlignCenter)
                        
                        # 创建新按钮
                        upload_btn = PushButton()
                        upload_btn.setFixedSize(30, 30)
                        
                        # 设置按钮属性和样式
                        if not btn_data['voucher_path']:
                            upload_btn.setIcon(FluentIcon.ADD_TO)
                        else:
                            upload_btn.setIcon(FluentIcon.CERTIFICATE)
                        upload_btn.setIconSize(QSize(16, 16))
                        upload_btn.setStyleSheet("""
                            QPushButton {
                                background: transparent;
                            }
                            QPushButton:hover {
                                background: rgba(24, 144, 255, 0.1);
                                border-radius: 4px;
                            }
                        """)
                        
                        # 设置按钮属性
                        upload_btn.setProperty("expense_id", btn_data['expense_id'])
                        upload_btn.setProperty("voucher_path", btn_data['voucher_path'])
                        upload_btn.mousePressEvent = lambda event, btn=upload_btn: self.handle_voucher(event, btn)
                        
                        # 将按钮添加到容器中
                        layout.addWidget(upload_btn, 0, Qt.AlignCenter)
                        self.expense_table.setCellWidget(i, col, container)
                else:
                    # 处理普通单元格
                    item = QTableWidgetItem()
                    value = row_data[col]
                    if isinstance(value, float):  # 金额
                        item.setText(f"{value:.2f}")
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    elif isinstance(value, datetime):  # 日期
                        item.setText(value.strftime("%Y-%m-%d"))
                        item.setTextAlignment(Qt.AlignCenter)
                    else:  # 其他文本
                        item.setText(str(value))
                        item.setTextAlignment(Qt.AlignCenter if col != 1 else Qt.AlignLeft | Qt.AlignVCenter)
                    self.expense_table.setItem(i, col, item)