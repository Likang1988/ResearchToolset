import os
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                                QTreeWidgetItem, QApplication) # Keep QStackedWidget for now, might be used by parent, Added QApplication for clipboard
from qfluentwidgets import TreeWidget, FluentIcon, ToolButton, Dialog, TitleLabel, ToolTipFilter, ToolTipPosition # Added ComboBox
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon 
from ...components.budget_dialog import BudgetDialog, TotalBudgetDialog

# 需要在文件顶部导入
from ...models.database import Project, sessionmaker
from ...models.database import sessionmaker, Budget, BudgetCategory, BudgetItem, Expense, Actionlog, Project # Added Project
from sqlalchemy import Engine # Added Engine
from datetime import datetime
from sqlalchemy import func
from ...components.progress_bar_delegate import ProgressBarDelegate
from ...utils.ui_utils import UIUtils
from ...components.budget_chart_widget import BudgetChartWidget

class ProjectBudgetWidget(QWidget):
    # 添加信号用于通知项目清单窗口更新数据
    budget_updated = Signal()

    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.current_project = None # Track selected project
        self.budget = None # Keep this? Might relate to selected budget row
        self.setup_ui()

    def showEvent(self, event):
        """在窗口显示时连接信号"""
        super().showEvent(event)
        # 尝试连接信号
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, 'project_updated'):
                # 先断开旧连接，防止重复连接
                try:
                    main_window.project_updated.disconnect(self._refresh_project_selector)
                except RuntimeError:
                    pass # 信号未连接，忽略错误
                main_window.project_updated.connect(self._refresh_project_selector)
                # print("ProjectBudgetWidget: Connected to project_updated signal.") # Removed print
            else:
                 # print("ProjectBudgetWidget: Could not find main window or project_updated signal.") # Removed print
                 pass # Do nothing if signal not found
        except Exception as e:
            # print(f"ProjectBudgetWidget: Error connecting signal: {e}") # Removed print
            pass # Ignore connection errors silently for now

    def _refresh_project_selector(self):
        """刷新项目选择下拉框的内容"""
        # print("ProjectBudgetWidget: Refreshing project selector...") # Removed print
        if not hasattr(self, 'project_selector') or not self.engine:
            # print("ProjectBudgetWidget: Project selector or engine not initialized.") # Removed print
            return

        current_project_id = None
        if self.current_project: # 使用 self.current_project 存储的ID
            current_project_id = self.current_project.id

        self.project_selector.clear()
        self.project_selector.addItem("请选择项目...", userData=None) # 添加默认提示项

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            projects = session.query(Project).order_by(Project.financial_code).all()
            if not projects:
                self.project_selector.addItem("没有找到项目", userData=None)
                self.project_selector.setEnabled(False)
            else:
                self.project_selector.setEnabled(True)
                for project in projects:
                    self.project_selector.addItem(f"{project.financial_code} ", userData=project)

                # 尝试恢复之前的选择
                if current_project_id is not None:
                    for i in range(self.project_selector.count()):
                        data = self.project_selector.itemData(i)
                        if isinstance(data, Project) and data.id == current_project_id:
                            self.project_selector.setCurrentIndex(i)
                            break
                    else:
                        # 如果之前的项目找不到了（可能被删除），则触发一次选中事件以清空表格
                        self._on_project_selected(0) # 选中 "请选择项目..."

        except Exception as e:
            # print(f"Error refreshing project selector in BudgetWidget: {e}") # Removed print
            self.project_selector.addItem("加载项目出错", userData=None)
            self.project_selector.setEnabled(False)
        finally:
            session.close()
            # print("ProjectBudgetWidget: Project selector refreshed.") # Removed print

    def setup_ui(self):
        """设置UI界面"""        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18) # Add some margins
        main_layout.setSpacing(10)

        selector_layout = QHBoxLayout()        
        selector_label = TitleLabel("项目经费-", self)
        selector_label.setToolTip("用于创建和管理项目的经费预算信息")
        selector_label.installEventFilter(ToolTipFilter(selector_label, showDelay=300, position=ToolTipPosition.RIGHT))
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        main_layout.addLayout(selector_layout)
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)                
        

        layout = main_layout # Use main_layout directly

        # 按钮栏
        add_btn = UIUtils.create_action_button("添加预算", FluentIcon.ADD_TO)
        edit_btn = UIUtils.create_action_button("编辑预算", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除预算", FluentIcon.DELETE)

        add_btn.clicked.connect(self.add_budget)
        edit_btn.clicked.connect(self.edit_budget)
        delete_btn.clicked.connect(self.delete_budget)

        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        layout.addLayout(button_layout)
        

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
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

        # 左侧 - 预算树形表格
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)

        # 预算树形表格
        self.budget_tree = TreeWidget()
        self.budget_tree.setColumnCount(6)

        # 获取表头并设置居中对齐
        header = self.budget_tree.header()
        header.setDefaultAlignment(Qt.AlignCenter)

        # 设置列宽
        self.budget_tree.setColumnWidth(0, 136)  # 预算年度
        self.budget_tree.setColumnWidth(1, 78)  # 预算额
        self.budget_tree.setColumnWidth(2, 78)  # 支出额
        self.budget_tree.setColumnWidth(3, 78)  # 结余额
        self.budget_tree.setColumnWidth(4, 90)  # 执行率
        self.budget_tree.setColumnWidth(5, 60)  # 操作

        # 设置表头
        self.budget_tree.setHeaderLabels([
            "预算年度", "预算额\n(万元)",
            "支出额\n(万元)", "结余额\n(万元)", "执行率", "支出管理"
        ])

        self.budget_tree.setAlternatingRowColors(False)  # 启用交替行颜色

        # 为执行率列设置进度条代理
        self.progress_delegate = ProgressBarDelegate(self.budget_tree)
        self.budget_tree.setItemDelegateForColumn(4, self.progress_delegate)

        # 设置树形表格样式
        UIUtils.set_tree_style(self.budget_tree)

        # 连接选择信号
        self.budget_tree.itemSelectionChanged.connect(self.on_budget_selection_changed)

        left_layout.addWidget(self.budget_tree)
        splitter.addWidget(left_widget)

        # 右侧 - 统计图表
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)  # 右侧布局的边距

        # 创建统计图表组件
        self.chart_widget = BudgetChartWidget()
        right_layout.addWidget(self.chart_widget)
        splitter.addWidget(right_widget)

        # 设置分割器比例
        splitter.setStretchFactor(0, 12)  # 左侧占2份
        splitter.setStretchFactor(1, 5)  # 右侧占1份
        splitter.setChildrenCollapsible(False)  # 防止完全折叠

        layout.addWidget(splitter)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_project = self.project_selector.itemData(index)
        if selected_project and isinstance(selected_project, Project):
            self.current_project = selected_project
            UIUtils.show_success(self, "项目经费", f"项目已选择: {self.current_project.name}")
            #self.title_label.setText(f"预算管理 - {self.current_project.financial_code}")
            self.load_budgets() # Load budgets for the selected project
        else:
            self.current_project = None
            #self.title_label.setText("项目预算管理") # Reset title
            self.budget_tree.clear() # Clear tree if no project selected
            self.chart_widget.clear_charts() # Clear charts
            #UIUtils.show_info(self, "项目经费", "请选择一个项目以查看经费")


    def open_project_expense(self, budget):
        """打开支出管理窗口"""
        if not self.current_project:
             UIUtils.show_warning(self, "警告", "请先选择一个项目")
             return
        # 获取主窗口实例
        main_window = self.window()
        if main_window:
            # 创建项目预算界面
            from app.views.projecting_interface.project_expense import ProjectExpenseWidget
            expense_widget = ProjectExpenseWidget(self.engine, self.current_project, budget) # Added missing project argument
            expense_widget.setObjectName(f"projectExpenseInterface_{budget.id}")
            # 连接信号：当支出更新时，刷新预算数据
            expense_widget.expense_updated.connect(self.load_budgets)
            # 检查是否已存在相同预算的支出窗口
            for i in range(main_window.stackedWidget.count()):
                widget = main_window.stackedWidget.widget(i)
                if widget.objectName() == expense_widget.objectName():
                    main_window.stackedWidget.setCurrentWidget(widget)
                    return
            # 添加新窗口并切换
            main_window.stackedWidget.addWidget(expense_widget)
            main_window.stackedWidget.setCurrentWidget(expense_widget)


    def load_budgets(self):
        """加载预算数据"""
        self.budget_tree.clear()
        self.chart_widget.clear_charts() # Clear charts on load/reload

        if not self.current_project:
            # print("BudgetWidget: No project selected, cannot load budgets.") # Removed print
            return


        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            # print(f"BudgetWidget: Loading budgets for project ID: {self.current_project.id}") # Removed print
            # 加载总预算
            total_budget = session.query(Budget).filter(
                Budget.project_id == self.current_project.id, # Use current_project.id
                Budget.year.is_(None)
            ).order_by(Budget.id.asc()).first()

            if not total_budget:
                # 如果没有找到总预算，创建一个
                total_budget = Budget(
                    project_id=self.current_project.id, # Use current_project.id
                    year=None,
                    total_amount=0.0,
                    spent_amount=0.0
                )
                session.add(total_budget)
                session.flush()

                # 创建总预算子项
                for category in BudgetCategory:
                    budget_item = BudgetItem(
                        budget_id=total_budget.id,
                        category=category,
                        amount=0.0,
                        spent_amount=0.0
                    )
                    session.add(budget_item)
                session.commit()

            # 计算所有年度预算的总支出
            total_spent = session.query(func.sum(Budget.spent_amount)).filter(
                Budget.project_id == self.current_project.id, # Use current_project.id
                Budget.year.isnot(None)  # 只计算年度预算
            ).scalar() or 0.0

            # 创建总预算树项
            total_item = QTreeWidgetItem(self.budget_tree)
            total_item.setText(0, " 总预算")

            # 获取总预算子项
            budget_items = session.query(BudgetItem).filter_by(budget_id=total_budget.id).all()

            # 设置总预算行的字体为加粗和行高
            font = total_item.font(0)

            # 根据平台调整字号
            if sys.platform == 'darwin':  # macOS
                current_size = font.pointSize()
                font.setPointSize(current_size + 1 if current_size > 0 else 10) # Use a default size of 10 if item font size is invalid
            else:  # Windows/Linux
                current_size = font.pointSize()
                font.setPointSize(current_size if current_size > 0 else 10) # Use a default size of 10 if item font size is invalid

            font.setBold(True)
            for i in range(6):  # 设置所有列的字体为加粗
                total_item.setFont(i, font)

            total_item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)  # 预算额右对齐
            total_item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)  # 支出额右对齐
            total_item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)  # 结余额右对齐
            total_item.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)  # 执行率右对齐

            total_item.setText(1, f"{total_budget.total_amount:,.2f}")  # 预算额
            total_item.setText(2, f"{total_spent:,.2f}")  # 支出额
            total_item.setText(3, f"{total_budget.total_amount - total_spent:,.2f}")  # 结余额

            if total_budget.total_amount > 0:
                execution_rate = (total_spent / total_budget.total_amount) * 100
                total_item.setText(4, f"{execution_rate:.2f}%")

            # 计算各科目的总支出
            category_totals = {}
            for category in BudgetCategory:
                # 计算该科目在所有年度预算中的总支出
                category_spent = session.query(func.sum(BudgetItem.spent_amount)).filter(
                    BudgetItem.budget_id.in_(
                        session.query(Budget.id).filter(
                            Budget.project_id == self.current_project.id, # Use current_project.id
                            Budget.year.isnot(None)  # 只计算年度预算
                        )
                    ),
                    BudgetItem.category == category
                ).scalar() or 0.0
                category_totals[category] = category_spent

            # 添加总预算子项
            budget_items = session.query(BudgetItem).filter_by(budget_id=total_budget.id).all()
            first_child = None
            for i, category in enumerate(BudgetCategory):
                child = QTreeWidgetItem(total_item)
                if i == 0:
                    first_child = child
                child.setText(0, category.value)

                # 设置子项字体为加粗
                child.setFont(0, font)  # 科目名称加粗
                child.setFont(1, font)  # 预算额加粗
                child.setFont(2, font)  # 支出额加粗
                child.setFont(3, font)  # 结余额加粗
                child.setFont(4, font)  # 执行率加粗

                child.setTextAlignment(0, Qt.AlignCenter | Qt.AlignVCenter)
                child.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                child.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
                child.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
                child.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)

                # 查找该类别的预算子项
                budget_item = next((item for item in budget_items if item.category == category), None)
                if budget_item:
                    category_spent = category_totals[category]  # 使用计算的科目总支出
                    child.setText(1, f"{budget_item.amount:,.2f}")
                    child.setText(2, f"{category_spent:,.2f}")
                    child.setText(3, f"{budget_item.amount - category_spent:,.2f}")

                    if budget_item.amount > 0:
                        execution_rate = (category_spent / budget_item.amount) * 100
                        child.setText(4, f"{execution_rate:.2f}%")
                else:
                    # 如果没有找到预算子项，显示0
                    child.setText(1, "0.00")
                    child.setText(2, "0.00")
                    child.setText(3, "0.00")

            # 更新总预算图表
            total_expenses = session.query(Expense).filter(
                Expense.budget_id.in_(
                    session.query(Budget.id).filter(
                        Budget.project_id == self.current_project.id # Use current_project.id
                    )
                )
            ).all()
            self.chart_widget.update_charts(budget_items=budget_items, expenses=total_expenses)

            # 加载年度预算
            annual_budgets = session.query(Budget).filter(
                Budget.project_id == self.current_project.id, # Use current_project.id
                Budget.year.isnot(None)  # 排除总预算
            ).order_by(Budget.id.asc()).all()  # 按ID升序排序，使新添加的预算显示在最下方

            for budget in annual_budgets:
                year_item = QTreeWidgetItem(self.budget_tree)
                year_item.setText(0, f" {budget.year}年度")

                year_item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)  # 预算额右对齐
                year_item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)  # 支出额右对齐
                year_item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)  # 结余额右对齐
                year_item.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)  # 执行率右对齐

                year_item.setText(1, f"{budget.total_amount:,.2f}")  # 预算额
                year_item.setText(2, f"{budget.spent_amount:,.2f}")  # 支出额
                year_item.setText(3, f"{budget.total_amount - budget.spent_amount:,.2f}")  # 结余额

                if budget.total_amount > 0:
                    execution_rate = (budget.spent_amount / budget.total_amount) * 100
                    year_item.setText(4, f"{execution_rate:.2f}%")

                # 添加支出管理按钮
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(0, 0, 0, 0)

                expense_btn = ToolButton()
                expense_btn.setIcon(QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'icons', 'expense.svg'))))
                expense_btn.setToolTip("支出管理")
                expense_btn.clicked.connect(lambda checked=False, b=budget: self.open_project_expense(b))
                btn_layout.addWidget(expense_btn)
                # 按钮大小 - 增加尺寸以提高用户体验
                expense_btn.setFixedSize(26, 26)
                # 设置图标大小
                expense_btn.setIconSize(QSize(20, 20))

                self.budget_tree.setItemWidget(year_item, 5, btn_widget)

                # 移除统计图表相关代码

                # 加载年度预算子项
                budget_items = session.query(BudgetItem).filter_by(budget_id=budget.id).all()
                for category in BudgetCategory:
                    child = QTreeWidgetItem(year_item)
                    child.setText(0, category.value)
                    child.setTextAlignment(0, Qt.AlignCenter | Qt.AlignVCenter)  # 费用类别居中对齐
                    child.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)  # 预算额右对齐
                    child.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)  # 支出额右对齐
                    child.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)  # 结余额右对齐
                    child.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)  # 执行率右对齐

                    # 查找该类别的预算子项
                    budget_item = next((item for item in budget_items if item.category == category), None)
                    if budget_item:
                        child.setText(1, f"{budget_item.amount:,.2f}")
                        child.setText(2, f"{budget_item.spent_amount:,.2f}")
                        child.setText(3, f"{budget_item.amount - budget_item.spent_amount:,.2f}")

                        if budget_item.amount > 0:
                            execution_rate = (budget_item.spent_amount / budget_item.amount) * 100
                            child.setText(4, f"{execution_rate:.2f}%")
                    else:
                        # 如果没有找到预算子项，显示0
                        child.setText(1, "0.00")
                        child.setText(2, "0.00")
                        child.setText(3, "0.00")

                    # 如果是设备费类别，保存引用以便后续添加图表
                    if category == BudgetCategory.EQUIPMENT:
                        first_child = child

                # 移除统计图表相关代码

            # 默认折叠所有项
            self.budget_tree.collapseAll()
            # 禁用自动调整列宽，使用手动设置的列宽
            # 预算加载完成后发射信号，通知主页等更新
            self.budget_updated.emit()

        finally:
            session.close()

    def calculate_annual_budgets_total(self, session, exclude_year=None):
        """计算年度预算总和"""
        if not self.current_project: return 0.0 # Return 0 if no project selected
        query = session.query(func.sum(Budget.total_amount)).filter(
            Budget.project_id == self.current_project.id # Use current_project.id
        )
        if exclude_year:
            query = query.filter(Budget.year != exclude_year)
        return query.scalar() or 0.0

    def add_budget(self):
        """添加预算"""
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            # 检查总预算是否已设置
            total_budget = session.query(Budget).filter(
                Budget.project_id == self.current_project.id, # Use current_project.id
                Budget.year.is_(None)
            ).with_for_update().first()

            if not total_budget or total_budget.total_amount <= 0:
                UIUtils.show_warning(
                    title="警告",
                    content="请先设置总预算！",
                    parent=self
                    )
                session.close()
                return

            temp_dialog = BudgetDialog(project=self.current_project, engine=self.engine, parent=self) # Pass project and engine
            temp_dialog.update_balance_amounts() # This might need adjustment
            total_balance_text = temp_dialog.total_balance_label.text().replace(' 万元', '').replace(',', '')
            try:
                total_balance = float(total_balance_text)
            except ValueError:
                UIUtils.show_error(self, "错误", "无法获取当前总结余")
                session.close()
                return


            if total_balance <= 0:
                UIUtils.show_warning(
                    title="警告",
                    content="当前总结余为0，无法添加新的年度预算！",
                    parent=self
                    )
                session.close()
                return

            session.close()

            dialog = BudgetDialog(project=self.current_project, engine=self.engine, parent=self) # Pass project and engine
            if dialog.exec():
                # 重新打开会话进行后续操作
                session = Session()
                try:
                    data = dialog.get_data()

                    # 再次检查年度预算是否已存在（可能在对话框打开期间被其他用户添加）
                    existing_budget = session.query(Budget).filter_by(
                        project_id=self.current_project.id, # Use current_project.id
                        year=data['year']
                    ).with_for_update().first()

                    if existing_budget:
                        UIUtils.show_warning(
                            title="警告",
                            content=f"{data['year']}年度的预算已存在！\n请选择其他年度或编辑现有预算。",
                            parent=self
                        )
                        return # Keep session open for potential next action? No, close it.

                    temp_session = Session()
                    try:
                        # 获取总预算信息
                        current_total_budget = temp_session.query(Budget).filter(
                            Budget.project_id == self.current_project.id,
                            Budget.year.is_(None)
                        ).first()
                        if not current_total_budget:
                             UIUtils.show_error(self, "错误", "无法获取总预算以校验额度")
                             return # 必须有总预算才能继续

                        # 计算所有年度预算的实际已支出总额
                        total_spent_all_years = temp_session.query(func.sum(Budget.spent_amount)).filter(
                            Budget.project_id == self.current_project.id,
                            Budget.year.isnot(None)
                        ).scalar() or 0.0

                        # 计算实际剩余金额
                        actual_remaining_balance = current_total_budget.total_amount - total_spent_all_years
                    finally:
                        temp_session.close()


                    # 检查新年度预算是否超出实际剩余金额
                    if data['total_amount'] > actual_remaining_balance:
                        UIUtils.show_warning(
                            title="警告",
                            content=f"注意：新年度预算({data['total_amount']:.2f}万元)已超出项目实际剩余金额({actual_remaining_balance:.2f}万元)！允许保存，请确认。", # 更新警告信息和比较值
                            parent=self
                            )
                        # 不再阻止保存，仅弹出警告

                    # 创建年度预算
                    budget = Budget(
                        project_id=self.current_project.id, # Use current_project.id
                        year=data['year'],
                        total_amount=data['total_amount'],
                        spent_amount=0.0
                    )
                    session.add(budget)
                    session.flush()  # 获取预算ID

                    # 创建预算子项
                    for category in BudgetCategory:
                        amount = data['items'].get(category, 0.0)  # 如果没有设置金额，默认为0
                        budget_item = BudgetItem(
                            budget_id=budget.id,
                            category=category,
                            amount=amount,
                            spent_amount=0.0
                        )
                        session.add(budget_item)

                    actionlog = Actionlog(
                        project_id=self.current_project.id, # Use current_project.id
                        budget_id=budget.id,                 # 添加 budget_id 关联
                        type="预算",                         # 添加 type
                        action="新增",                       # 设置 action
                        description=f"添加了 {data['year']} 年度预算", # 使用 description
                        operator="系统用户",                 # 修正: 使用 operator
                        timestamp=datetime.now()             # 保留 timestamp
                    )
                    session.add(actionlog)

                    session.commit()
                    self.load_budgets()
                    UIUtils.show_success(self, "成功", f"{data['year']}年度预算添加成功")
                except Exception as e:
                    session.rollback()
                    UIUtils.show_error(self, "错误", f"添加预算失败: {e}")
                finally:
                    if session.is_active:
                         session.close()
        except Exception as e:
            UIUtils.show_error(self, "错误", f"添加预算时发生错误: {e}")
        finally:
            if 'session' in locals() and session.is_active:
                session.close()

    def delete_budget(self):
        """删除预算"""
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_item = self.budget_tree.currentItem()
        if not selected_item:
            UIUtils.show_warning(self, "警告", "请先选择要删除的预算")
            return

        budget_type = selected_item.text(0)

        confirm_dialog = Dialog(
            title="确认删除",
            content=f"确定要删除选中的预算 '{budget_type.strip()}' 及其所有相关数据（包括支出记录）吗？\n此操作不可恢复！",
            parent=self
        )

        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                if budget_type == " 总预算": # Note the leading space
                    # 删除总预算及其所有子项和关联支出
                    budget = session.query(Budget).filter_by(
                        project_id=self.current_project.id, year=None # Use current_project.id
                    ).with_for_update().first()
                    if budget:
                        # 删除关联支出
                        expense_ids_to_delete = session.query(Expense.id).filter(
                            Expense.budget_id.in_(
                                session.query(Budget.id).filter_by(project_id=self.current_project.id) # Use current_project.id
                            )
                        ).all()
                        if expense_ids_to_delete:
                            session.query(Expense).filter(Expense.id.in_([eid[0] for eid in expense_ids_to_delete])).delete(synchronize_session=False)

                        # 删除所有预算项（包括总预算和年度预算）
                        session.query(BudgetItem).filter(
                            BudgetItem.budget_id.in_(
                                session.query(Budget.id).filter_by(project_id=self.current_project.id) # Use current_project.id
                            )
                        ).delete(synchronize_session=False)
                        session.query(Budget).filter_by(project_id=self.current_project.id).delete(synchronize_session=False) # Use current_project.id

                        actionlog = Actionlog(
                            project_id=self.current_project.id, # Use current_project.id
                            type="预算",                             # 添加 type
                            action="删除",                           # 设置 action
                            description="删除了项目总预算",             # 使用 description
                            operator="系统用户",                     # 修正: 使用 operator
                            timestamp=datetime.now()                 # 保留 timestamp
                        )
                        session.add(actionlog)

                        session.commit()
                        self.load_budgets() # 重新加载以显示空状态或默认状态
                        UIUtils.show_success(self, "成功", "总预算已删除")
                    else:
                        UIUtils.show_error(self, "错误", "未找到总预算")
                elif budget_type.startswith(" ") and budget_type.endswith("年度"): # Check with leading space
                    # 删除年度预算及其子项和关联支出
                    try:
                        year = int(budget_type.strip()[:-2]) # 去掉"年度"后缀并去除空格
                    except ValueError:
                        UIUtils.show_error(self, "错误", "无法解析预算年度")
                        return

                    budget = session.query(Budget).filter_by(
                        project_id=self.current_project.id, year=year # Use current_project.id
                    ).with_for_update().first()
                    if budget:
                        # 删除关联支出
                        session.query(Expense).filter_by(budget_id=budget.id).delete(synchronize_session=False)
                        # 删除预算子项
                        session.query(BudgetItem).filter_by(budget_id=budget.id).delete(synchronize_session=False)
                        # 删除预算本身
                        session.delete(budget)

                        actionlog = Actionlog(
                            project_id=self.current_project.id, # Use current_project.id
                            budget_id=budget.id,                 # 添加 budget_id 关联
                            type="预算",                         # 添加 type
                            action="删除",                       # 设置 action
                            description=f"删除了 {year} 年度预算", # 使用 description
                            operator="系统用户",                 # 修正: 使用 operator
                            timestamp=datetime.now()             # 保留 timestamp
                        )
                        session.add(actionlog)

                        session.commit()
                        self.load_budgets() # 重新加载
                        UIUtils.show_success(self, "成功", f"{year}年度预算已删除")
                    else:
                        UIUtils.show_error(self, "错误", f"未找到{year}年度预算")
                else:
                    UIUtils.show_warning(self, "警告", "不能直接删除预算科目，请编辑对应的年度或总预算。")

            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "错误", f"删除预算失败: {e}")
            finally:
                if session.is_active:
                    session.close()

    def edit_budget(self):
        """编辑预算"""
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_item = self.budget_tree.currentItem()
        if not selected_item:
            UIUtils.show_warning(self, "警告", "请先选择要编辑的预算")
            return

        budget_type = selected_item.text(0)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            if budget_type == " 总预算": # Note the leading space
                # 编辑总预算
                budget = session.query(Budget).filter(
                    Budget.project_id == self.current_project.id, # Use current_project.id
                    Budget.year.is_(None)
                ).with_for_update().first()

                if not budget:
                    UIUtils.show_error(self, "错误", "未找到总预算")
                    session.close()
                    return

                # 获取总预算子项
                budget_items = session.query(BudgetItem).filter_by(budget_id=budget.id).all()

                dialog = TotalBudgetDialog(project=self.current_project, engine=self.engine, parent=self, budget=budget) # Pass project and engine
                if dialog.exec():
                    data = dialog.get_data()

                    # 检查修改后的总预算是否等于项目总经费
                    total_fund = session.query(func.sum(Project.total_budget)).filter_by(id=self.current_project.id).scalar()
                    if data['total_amount'] != total_fund:
                        UIUtils.show_error(
                            title="错误",
                            content=f"总预算({data['total_amount']}万元)不等于项目总经费({total_fund:.2f}万元)！",
                            parent=self
                        )
                        session.close()
                        return

                    # 记录旧数据
                    old_data_str = f"总预算额: {budget.total_amount}"

                    budget.total_amount = data['total_amount']

                    # 更新或创建预算子项
                    for category, amount in data['items'].items():
                        item = next((i for i in budget_items if i.category == category), None)
                        if item:
                            item.amount = amount
                        else:
                            # 如果总预算子项不存在，则创建它
                            new_item = BudgetItem(
                                budget_id=budget.id,
                                category=category,
                                amount=amount,
                                spent_amount=0.0 # 新创建的子项支出为0
                            )
                            session.add(new_item)

                    # 记录编辑总预算的活动
                    new_data_str = f"总预算额: {budget.total_amount}"
                    actionlog = Actionlog(
                        project_id=self.current_project.id, # Use current_project.id
                        budget_id=budget.id,                 # 添加 budget_id 关联
                        type="预算",                         # 添加 type
                        action="编辑",                       # 设置 action
                        description="编辑了项目总预算",         # 使用 description
                        operator="系统用户",                 # 修正: 使用 operator
                        old_data=old_data_str,
                        new_data=new_data_str
                    )
                    session.add(actionlog)

                    session.commit()
                    self.load_budgets()
                    self.budget_updated.emit() # 发射信号
                    UIUtils.show_success(self, "成功", "总预算更新成功")

            elif budget_type.startswith(" ") and budget_type.endswith("年度"): # Check with leading space
                # 编辑年度预算
                try:
                    year = int(budget_type.strip()[:-2]) # 去掉"年度"后缀并去除空格
                except ValueError:
                    UIUtils.show_error(self, "错误", "无法解析预算年度")
                    session.close()
                    return

                budget = session.query(Budget).filter(
                    Budget.project_id == self.current_project.id, # Use current_project.id
                    Budget.year == year
                ).with_for_update().first()

                if not budget:
                    UIUtils.show_error(self, "错误", f"未找到{year}年度预算")
                    session.close()
                    return

                # 获取年度预算子项
                budget_items = session.query(BudgetItem).filter_by(budget_id=budget.id).all()

                dialog = BudgetDialog(project=self.current_project, engine=self.engine, parent=self, budget=budget) # Pass project and engine
                if dialog.exec():
                    data = dialog.get_data()

                    # 检查修改后的年度预算是否超过总结余（排除当前编辑的年度）
                    total_budget = session.query(Budget).filter(
                        Budget.project_id == self.current_project.id, # Use current_project.id
                        Budget.year.is_(None)
                    ).first()

                    if not total_budget:
                        UIUtils.show_error(self, "错误", "未找到总预算，无法校验额度")
                        session.close()
                        return

                    other_annual_total = self.calculate_annual_budgets_total(session, exclude_year=year)
                    available_total = total_budget.total_amount - other_annual_total

                    # 检查年度预算是否超出可用总预算额度
                    if data['total_amount'] > available_total:
                        UIUtils.show_warning(
                            title="警告",
                            content=f"注意：年度预算({data['total_amount']:.2f}万元)已超出当前可用总预算额度({available_total:.2f}万元)！允许保存，请确认。", # 更新警告信息
                            parent=self
                        )
                        # 不再阻止保存，仅弹出警告

                    # 检查修改后的年度预算是否小于已支出金额
                    if data['total_amount'] < budget.spent_amount:
                        UIUtils.show_warning(
                            title="警告",
                            content=f"注意：年度预算({data['total_amount']:.2f}万元)小于已支出金额({budget.spent_amount:.2f}万元)！允许保存，请确认。", # 更新警告信息
                            parent=self
                        )
                        # 不再阻止保存，仅弹出警告

                    # 记录旧数据
                    old_data_str = f"年度: {year}, 预算额: {budget.total_amount}"

                    budget.total_amount = data['total_amount']

                    # 更新或创建预算子项
                    for category, amount in data['items'].items():
                        item = next((i for i in budget_items if i.category == category), None)
                        if item:
                            # 检查修改后的子项预算是否小于已支出金额
                            if amount < item.spent_amount:
                                UIUtils.show_warning(
                                    title="警告",
                                    content=f"注意：{category.value}预算({amount:.2f}万元)小于已支出金额({item.spent_amount:.2f}万元)！允许保存，请确认。", # 更新警告信息
                                    parent=self
                                )
                                # 不再阻止保存，仅弹出警告
                            item.amount = amount
                        else:
                            # 如果年度预算子项不存在，则创建它
                            new_item = BudgetItem(
                                budget_id=budget.id,
                                category=category,
                                amount=amount,
                                spent_amount=0.0 # 新创建的子项支出为0
                            )
                            session.add(new_item)

                    # 记录编辑年度预算的活动
                    new_data_str = f"年度: {year}, 预算额: {budget.total_amount}"
                    actionlog = Actionlog(
                        project_id=self.current_project.id, # Use current_project.id
                        budget_id=budget.id,                 # 添加 budget_id 关联
                        type="预算",                         # 添加 type
                        action="编辑",                       # 设置 action
                        description=f"编辑了项目 {self.current_project.financial_code} 的 {year} 年度预算", # 使用 description
                        operator="系统用户",                 # 修正: 使用 operator
                        old_data=old_data_str,
                        new_data=new_data_str
                    )
                    session.add(actionlog)

                    session.commit()
                    self.load_budgets()
                    self.budget_updated.emit() # 发射信号
                    UIUtils.show_success(self, "成功", f"{year}年度预算更新成功")
            else:
                 UIUtils.show_warning(self, "警告", "不能直接编辑预算科目，请编辑对应的年度或总预算。")

        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "错误", f"编辑预算失败: {e}")
        finally:
            if session.is_active:
                session.close()

    def on_budget_selection_changed(self):
        """当预算树选择项改变时更新图表"""
        selected_item = self.budget_tree.currentItem()
        if not selected_item or not self.current_project:
            self.chart_widget.clear_charts()
            return

        budget_type = selected_item.text(0).strip()
        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            budget_items = []
            expenses = []

            if budget_type == "总预算":
                total_budget = session.query(Budget).filter(
                    Budget.project_id == self.current_project.id,
                    Budget.year.is_(None)
                ).first()
                if total_budget:
                    budget_items = session.query(BudgetItem).filter_by(budget_id=total_budget.id).all()
                    # 获取所有年度预算的支出
                    expenses = session.query(Expense).filter(
                        Expense.budget_id.in_(
                            session.query(Budget.id).filter(
                                Budget.project_id == self.current_project.id,
                                Budget.year.isnot(None) # Only annual expenses for total view
                            )
                        )
                    ).all()
            elif budget_type.endswith("年度"):
                try:
                    year = int(budget_type.replace("年度", "").strip())
                    budget = session.query(Budget).filter(
                        Budget.project_id == self.current_project.id,
                        Budget.year == year
                    ).first()
                    if budget:
                        budget_items = session.query(BudgetItem).filter_by(budget_id=budget.id).all()
                        expenses = session.query(Expense).filter_by(budget_id=budget.id).all()
                except ValueError:
                    pass # Ignore if year parsing fails

            self.chart_widget.update_charts(budget_items=budget_items, expenses=expenses)
        except Exception as e:
            print(f"Error updating charts on selection change: {e}")
            self.chart_widget.clear_charts()
        finally:
            if session.is_active:
                session.close()

    def load_project_data(self, project: Project):
        """Loads the data for the given project."""
        if project and isinstance(project, Project):
            self.current_project = project
            self._refresh_project_selector() # Refresh selector and select the project
            self.load_budgets() # Load budgets for the selected project
        else:
            print("ProjectBudgetWidget: Invalid project object received.") # Added print for debugging
