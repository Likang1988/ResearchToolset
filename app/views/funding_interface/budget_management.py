import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                                 QLabel, QPushButton, QMessageBox, QSpinBox, QTableWidget, QTableWidgetItem,
                                 QStackedWidget, QTreeWidgetItem)
from qfluentwidgets import PrimaryPushButton, TitleLabel, FluentIcon, ToolButton, InfoBar, Dialog
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from ...components.budget_dialog import BudgetDialog, TotalBudgetDialog
from .expense_management import ExpenseManagementWindow
from ...models.funding_db import sessionmaker, Budget, BudgetCategory, BudgetItem, Expense
from datetime import datetime
from sqlalchemy import func
from ...components.progress_bar_delegate import ProgressBarDelegate
from ...utils.ui_utils import UIUtils
from ...utils.db_utils import DBUtils
from ...components.budget_chart_widget import BudgetChartWidget

class BudgetManagementWindow(QWidget):
    def __init__(self, engine, project):   
        super().__init__()
        self.engine = engine
        self.project = project
        self.budget = None
        self.setup_ui()
        self.load_budgets()
        
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("预算管理")
        main_layout = QVBoxLayout(self)
        
        # 创建QStackedWidget
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # 创建预算管理页面
        self.budget_page = QWidget()
        self.setup_budget_page()
        self.stacked_widget.addWidget(self.budget_page)
        
        # 初始显示预算管理页面
        self.stacked_widget.setCurrentWidget(self.budget_page)
        
    def setup_budget_page(self):
        """设置预算管理页面"""
        layout = QVBoxLayout(self.budget_page)
        layout.setContentsMargins(6, 6, 6, 6)  # 统一设置边距为15像素
        layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素
        
        # 标题
        title_layout = UIUtils.create_title_layout(f"预算管理-{self.project.financial_code}", True, self.back_to_project)
        layout.addLayout(title_layout)
        
        # 按钮栏
        add_btn = UIUtils.create_action_button("添加预算", FluentIcon.ADD_TO)
        edit_btn = UIUtils.create_action_button("编辑预算", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除预算", FluentIcon.DELETE)
        
        add_btn.clicked.connect(self.add_budget)
        edit_btn.clicked.connect(self.edit_budget)
        delete_btn.clicked.connect(self.delete_budget)
        
        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        layout.addLayout(button_layout)
        
        # 预算树形表格
        self.budget_tree = QTreeWidget()
        self.budget_tree.setColumnCount(6)  # 减少为6列，删除统计列
        
        # 获取表头并设置居中对齐
        header = self.budget_tree.header()
        header.setDefaultAlignment(Qt.AlignCenter)  # 设置表头默认对齐方式为居中对齐
        
        # 设置列宽
        self.budget_tree.setColumnWidth(0, 140)  # 预算年度
        self.budget_tree.setColumnWidth(1, 100)  # 预算额
        self.budget_tree.setColumnWidth(2, 100)  # 支出额
        self.budget_tree.setColumnWidth(3, 100)  # 结余额
        self.budget_tree.setColumnWidth(4, 100)  # 执行率
        self.budget_tree.setColumnWidth(5, 300)  # 操作/统计图表
        
        # 设置行高
        self.budget_tree.setStyleSheet("""
            QTreeWidget::item {
                height: 36px;  /* 增加行高 */
                padding: 2px;
            }
            QTreeWidget {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                selection-background-color: rgba(0, 120, 212, 0.1);
                selection-color: black;
            }
            QTreeWidget::item:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QTreeWidget QHeaderView::section {
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
        
        # 设置表头
        self.budget_tree.setHeaderLabels([
            "预算年度", "预算额(万元)", 
            "支出额(万元)", "结余额(万元)", "执行率", "操作 / 统计"
        ])
       

        self.budget_tree.setAlternatingRowColors(True)  # 启用交替行颜色
        
        # 为执行率列设置进度条代理
        self.progress_delegate = ProgressBarDelegate(self.budget_tree)
        self.budget_tree.setItemDelegateForColumn(4, self.progress_delegate)  # 调整执行率列的索引

        layout.addWidget(self.budget_tree)
        
    def back_to_project(self):
        """返回到项目管理页面"""
        # 获取父窗口（ProjectManagementWindow）
        # 由于BudgetManagementWindow是添加到QStackedWidget中的，
        # 需要获取QStackedWidget的父窗口才是ProjectManagementWindow
        stacked_widget = self.parent()
        if isinstance(stacked_widget, QStackedWidget):
            project_window = stacked_widget.parent()
            if hasattr(project_window, 'project_page'):
                # 切换到项目管理页面
                stacked_widget.setCurrentWidget(project_window.project_page)

    def open_expense_management(self, budget):
        """打开支出管理窗口"""
        expense_window = ExpenseManagementWindow(self.engine, self.project, budget)
        # 连接支出更新信号
        expense_window.expense_updated.connect(self.load_budgets)
        # 将支出管理窗口添加到当前预算管理窗口的QStackedWidget中
        self.stacked_widget.addWidget(expense_window)
        # 切换到支出管理页面
        self.stacked_widget.setCurrentWidget(expense_window)
        

        
    def load_budgets(self):
        """加载预算数据"""
        self.budget_tree.clear()
        
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            
            # 加载总预算
            total_budget = session.query(Budget).filter(
                Budget.project_id == self.project.id,
                Budget.year.is_(None)
            ).order_by(Budget.id.asc()).first()
            
            if not total_budget:
                # 如果没有找到总预算，创建一个
                total_budget = Budget(
                    project_id=self.project.id,
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
                Budget.project_id == self.project.id,
                Budget.year.isnot(None)  # 只计算年度预算
            ).scalar() or 0.0
            
            # 创建总预算树项
            total_item = QTreeWidgetItem(self.budget_tree)
            total_item.setText(0, " 总预算")
            
            # 获取总预算子项
            budget_items = session.query(BudgetItem).filter_by(budget_id=total_budget.id).all()
            
            # 设置总预算行的字体为加粗和行高
            font = total_item.font(0)
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
                            Budget.project_id == self.project.id,
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
            
            # 创建总预算的统计图表
            chart_widget = BudgetChartWidget()
            # 获取总预算的支出记录
            expenses = session.query(Expense).filter(
                Expense.budget_id.in_(
                    session.query(Budget.id).filter(
                        Budget.project_id == self.project.id
                    )
                )
            ).all()
            # 获取总预算项
            total_budget_items = session.query(BudgetItem).filter_by(
                budget_id=total_budget.id
            ).all()
            chart_widget.update_charts(budget_items=total_budget_items, expenses=expenses)
            
            # 将图表添加到设备费类别的单元格中
            if first_child:
                self.budget_tree.setItemWidget(first_child, 5, chart_widget)
                # 连接折叠信号
                self.budget_tree.itemExpanded.connect(lambda item: chart_widget.setVisible(True) if item == total_item else None)
                self.budget_tree.itemCollapsed.connect(lambda item: chart_widget.setVisible(False) if item == total_item else None)
                # 初始状态根据父项是否展开
                chart_widget.setVisible(total_item.isExpanded())
            
            # 加载年度预算
            annual_budgets = session.query(Budget).filter(
                Budget.project_id == self.project.id,
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
                expense_btn.setIcon(QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'logo', 'expense.svg'))))
                expense_btn.setToolTip("支出管理")
                expense_btn.clicked.connect(lambda checked=False, b=budget: self.open_expense_management(b))
                btn_layout.addWidget(expense_btn)
                # 按钮大小 - 增加尺寸以提高用户体验
                expense_btn.setFixedSize(28, 28)
                # 设置图标大小
                expense_btn.setIconSize(QSize(22, 22))
                
                self.budget_tree.setItemWidget(year_item, 5, btn_widget)
                
                # 添加年度预算的统计图表
                chart_widget = BudgetChartWidget()
                # 获取该年度的支出记录
                expenses = session.query(Expense).filter(
                    Expense.budget_id == budget.id
                ).all()
                # 获取当前年度的预算项
                current_budget_items = session.query(BudgetItem).filter_by(
                    budget_id=budget.id
                ).all()
                chart_widget.update_charts(budget_items=current_budget_items, expenses=expenses)
                
                # 将图表添加到设备费类别的单元格中
                first_child = None
                for child in range(year_item.childCount()):
                    if year_item.child(child).text(0) == BudgetCategory.EQUIPMENT.value:
                        first_child = year_item.child(child)
                        break
                
                if first_child:
                    self.budget_tree.setItemWidget(first_child, 5, chart_widget)
                    # 连接折叠信号
                    self.budget_tree.itemExpanded.connect(lambda item: chart_widget.setVisible(True) if item == year_item else None)
                    self.budget_tree.itemCollapsed.connect(lambda item: chart_widget.setVisible(False) if item == year_item else None)
                    # 初始状态根据父项是否展开
                    chart_widget.setVisible(year_item.isExpanded())
                
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

                # 创建年度预算的统计图表
                chart_widget = BudgetChartWidget()
                # 获取该年度的支出记录
                expenses = session.query(Expense).filter(
                    Expense.budget_id == budget.id
                ).all()
                # 获取当前年度的预算项
                current_budget_items = session.query(BudgetItem).filter_by(
                    budget_id=budget.id
                ).all()
                chart_widget.update_charts(budget_items=current_budget_items, expenses=expenses)
                
                # 将图表添加到设备费类别的单元格中
                if first_child:
                    self.budget_tree.setItemWidget(first_child, 5, chart_widget)
                    # 连接折叠信号
                    self.budget_tree.itemExpanded.connect(lambda item: chart_widget.setVisible(True) if item == year_item else None)
                    self.budget_tree.itemCollapsed.connect(lambda item: chart_widget.setVisible(False) if item == year_item else None)
                    # 初始状态根据父项是否展开
                    chart_widget.setVisible(year_item.isExpanded())
            
            # 默认折叠所有项
            self.budget_tree.collapseAll()
            # 禁用自动调整列宽，使用手动设置的列宽
            # for i in range(self.budget_tree.columnCount()):
            #     self.budget_tree.resizeColumnToContents(i)
                
        finally:
            session.close()
            
    def calculate_annual_budgets_total(self, session, exclude_year=None):
        """计算年度预算总和"""
        query = session.query(func.sum(Budget.total_amount)).filter(
            Budget.project_id == self.project.id
        )
        if exclude_year:
            query = query.filter(Budget.year != exclude_year)
        return query.scalar() or 0.0

    def add_budget(self):
        """添加预算"""
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            # 检查总预算是否已设置
            total_budget = session.query(Budget).filter(
                Budget.project_id == self.project.id,
                Budget.year.is_(None)
            ).with_for_update().first()
            
            if not total_budget or total_budget.total_amount <= 0:
                UIUtils.show_warning(
                    title="警告", 
                    content="请先设置总预算！",
                    parent=self
                    )
                return
                
            # 计算已有年度预算总和
            annual_total = session.query(func.sum(Budget.total_amount)).filter(
                Budget.project_id == self.project.id,
                Budget.year.isnot(None)
            ).scalar() or 0.0
            
            remaining_budget = total_budget.total_amount - annual_total
            if remaining_budget <= 0:
                UIUtils.show_warning(
                    title="警告", 
                    content="已达到总预算限额，无法添加新的年度预算！",
                    parent=self
                    )
                return
            
            # 关闭当前会话，让dialog使用自己的会话进行验证
            session.close()
            
            dialog = BudgetDialog(self)
            if dialog.exec():
                # 重新打开会话进行后续操作
                session = Session()
                try:
                    data = dialog.get_data()
                    
                    # 再次检查年度预算是否已存在（可能在对话框打开期间被其他用户添加）
                    existing_budget = session.query(Budget).filter_by(
                        project_id=self.project.id,
                        year=data['year']
                    ).with_for_update().first()
                    
                    if existing_budget:
                        UIUtils.show_warning(                            
                            title="警告",
                            content=f"{data['year']}年度的预算已存在！\n请选择其他年度或编辑现有预算。",
                            parent=self
                        )
                        return
                    
                    # 重新检查预算限额（因为可能在对话框打开期间发生变化）
                    annual_total = session.query(func.sum(Budget.total_amount)).filter(
                        Budget.project_id == self.project.id,
                        Budget.year.isnot(None)
                    ).scalar() or 0.0
                    
                    remaining_budget = total_budget.total_amount - annual_total
                    if data['total_amount'] > remaining_budget:
                        UIUtils.show_warning(
                            title="警告", 
                            content=f"年度预算({data['total_amount']}万元)超出剩余总预算({remaining_budget:.2f}万元)！",
                            parent=self
                            )
                        return
                    
                    # 创建年度预算
                    budget = Budget(
                        project_id=self.project.id,
                        year=data['year'],
                        total_amount=data['total_amount'],
                        spent_amount=0.0
                    )
                    session.add(budget)
                    session.flush()  # 获取预算ID
                    
                    # 创建预算子项
                    for category in BudgetCategory:  # 遍历所有预算类别
                        amount = data['items'].get(category, 0.0)  # 如果没有设置金额，默认为0
                        budget_item = BudgetItem(
                            budget_id=budget.id,
                            category=category,
                            amount=amount,
                            spent_amount=0.0
                        )
                        session.add(budget_item)
                    
                    session.commit()
                    self.load_budgets()
                    
                except Exception as e:
                    session.rollback()
                    error_msg = f"添加预算失败：\n错误类型：{type(e).__name__}\n错误信息：{str(e)}"
                    print(error_msg)  # 打印错误信息到控制台
                    UIUtils.show_error(
                        title= "错误", 
                        content=error_msg,
                        parent=self
                        )
                finally:
                    session.close()
                    
        except Exception as e:
            session.rollback()
            error_msg = f"添加预算失败：\n错误类型：{type(e).__name__}\n错误信息：{str(e)}"
            print(error_msg)  # 打印错误信息到控制台
            UIUtils.show_error(
                title= "错误", 
                content=error_msg,
                parent=self
                )
        finally:
            if session:
                session.close()
            
    def delete_budget(self):
        """删除预算"""
        current_item = self.budget_tree.currentItem()
        if not current_item:
            UIUtils.show_warning(
                title= "警告", 
                content="请选择要删除的预算！",
                parent=self
                )
            return
            
        budget_type = current_item.text(0)
        if budget_type == " 总预算":
            UIUtils.show_warning(
                title= "警告", 
                content="不能删除总预算！",
                parent=self
                )
            return
            
        # 确认删除
        confirm_dialog = Dialog(
            '确认删除',
            f'确定要删除{budget_type}预算吗？此操作不可恢复！',
            self
        )
        
        if not confirm_dialog.exec():
            return
            
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            if budget_type.endswith("年度"):
                year = int(budget_type[:-2])  # 去掉"年度"后缀
                budget = session.query(Budget).filter_by(
                    project_id=self.project.id,
                    year=year
                ).first()
                
                if budget:
                    # 删除预算及其子项
                    session.query(BudgetItem).filter_by(budget_id=budget.id).delete()
                    session.delete(budget)
                    session.commit()
                    self.load_budgets()
                    UIUtils.show_success(
                        title= "成功", 
                        content= f"{budget_type}预算已删除",
                        parent=self
                        )
                    
                else:
                    UIUtils.show_error(
                        title= "错误", 
                        content="未找到要删除的预算！",
                        parent=self
                        )
                    
        except Exception as e:
            session.rollback()
            error_msg = f"删除预算时发生错误：\n错误类型：{type(e).__name__}\n错误信息：{str(e)}"
            print(error_msg)  # 打印错误信息到控制台
            UIUtils.show_error(
                title= "错误", 
                content=error_msg,
                parent=self
                )
        finally:
            session.close()

    def edit_budget(self):
        """编辑预算"""
        current_item = self.budget_tree.currentItem()
        if not current_item:
            UIUtils.show_warning(
                title='警告',
                content='请选择要编辑的预算！',
                parent=self
            )
            return
            
        # 验证选中项是否为有效的预算项
        budget_type = current_item.text(0)
        if not (" 总预算" in budget_type or budget_type.endswith("年度")):
            UIUtils.show_warning(
                title='警告',
                content='请选择有效的预算项进行编辑！',
                parent=self
            )
            return
            
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            budget_type = current_item.text(0)
            
            if budget_type == " 总预算":
                # 编辑总预算
                budget = session.query(Budget).filter(
                    Budget.project_id == self.project.id,
                    Budget.year.is_(None)
                ).with_for_update().first()  # 添加行级锁
                
                if budget:
                    print(f"开始编辑总预算，当前总额：{budget.total_amount}")  # 调试信息
                    try:
                        dialog = TotalBudgetDialog(self, budget)  # 传入当前预算数据
                        if dialog.exec():
                            try:
                                data = dialog.get_data()
                                print(f"获取到新的总预算数据：{data}")  # 调试信息
                                
                                # 更新总预算
                                budget.total_amount = data['total_amount']
                                # 更新子项金额
                                for item in budget.budget_items:
                                    if item.category in data['items']:
                                        item.amount = data['items'][item.category]
                                    else:
                                        item.amount = 0.0  # 处理缺失的类别
                                
                                session.commit()
                                print("总预算更新成功")  # 调试信息
                                self.load_budgets()
                            except Exception as e:
                                session.rollback()
                                print(f"更新总预算时发生错误：{str(e)}")  # 调试信息
                                UIUtils.show_error(
                            title='错误',
                            content=f'更新总预算失败：{str(e)}',
                            parent=self
                        )
                    except Exception as e:
                        print(f"打开总预算编辑对话框时发生错误：{str(e)}")
                        UIUtils.show_error(
                            title='错误',
                            content=f'无法打开总预算编辑对话框：{str(e)}',
                            parent=self
                        )
                        return
                else:
                    UIUtils.show_error(
                        title='错误',
                        content='未找到总预算数据！',
                        parent=self
                    )
                    
            elif budget_type.endswith("年度"):
                # 编辑年度预算
                try:
                    year = int(budget_type[:-2])  # 去掉"年度"后缀
                    budget = session.query(Budget).filter_by(
                        project_id=self.project.id,
                        year=year
                    ).with_for_update().first()  # 添加行级锁
                    
                    if budget:
                        dialog = BudgetDialog(self, budget)
                        dialog.budget_updated.connect(self.load_budgets)
                        if dialog.exec():
                            try:
                                data = dialog.get_data()
                                
                                # 更新年度预算
                                budget.total_amount = data['total_amount']
                                # 更新子项金额
                                # 更新子项金额，处理可能缺失的类别
                                for item in budget.budget_items:
                                    if item.category in data['items']:
                                        item.amount = data['items'][item.category]
                                    else:
                                        # 如果类别不存在于新数据中，则设置为0
                                        item.amount = 0.0
                                
                                session.commit()
                                self.load_budgets()
                            except Exception as e:
                                print(f"处理预算数据时发生错误: {str(e)}")
                                raise
                    else:
                        UIUtils.show_error(
                            title='错误',
                            content='未找到预算数据！',
                            parent=self
                        )
                        
                except ValueError:
                    UIUtils.show_error(
                        title='错误',
                        content='无效的预算年度格式',
                        parent=self
                    )
                    
            else:
                UIUtils.show_warning(
                    title='警告',
                    content='请选择总预算或年度预算进行编辑',
                    parent=self
                )
                
        except Exception as e:
            session.rollback()
            error_msg = f"编辑预算时发生错误：\n错误类型：{type(e).__name__}\n错误信息：{str(e)}"
            print(error_msg)  # 打印错误信息到控制台
            UIUtils.show_error(
                title='错误',
                content=error_msg,
                parent=self
            )
        finally:
            session.close()
