from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from ..models.database import BudgetCategory
from datetime import datetime
import matplotlib as mpl
from qfluentwidgets import ToolButton, FluentIcon

class BudgetChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置中文字体
        mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
        mpl.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
        self.current_view = 'category'  # 默认显示类别分布
        self.budget_items = None
        self.expenses = None
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)
        
        # 创建切换按钮
        self.category_btn = ToolButton()
        self.category_btn.setIcon(FluentIcon.TAG)
        self.category_btn.setToolTip("类别分布")
        self.category_btn.clicked.connect(lambda: self.switch_view('category'))
        
        self.time_btn = ToolButton()
        self.time_btn.setIcon(FluentIcon.CALENDAR)
        self.time_btn.setToolTip("时间分布")
        self.time_btn.clicked.connect(lambda: self.switch_view('time'))
        
        # 设置按钮大小
        self.category_btn.setFixedSize(24, 24)
        self.time_btn.setFixedSize(24, 24)
        
        # 添加按钮到布局
        button_layout.addWidget(self.category_btn)
        button_layout.addWidget(self.time_btn)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        # 创建饼图画布
        self.figure = Figure(figsize=(4, 4))
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)
        
        # 设置背景透明
        self.figure.patch.set_alpha(0.0)
        self.canvas.setStyleSheet("background-color: transparent;")
        
    def switch_view(self, view_type):
        """切换显示的饼图类型"""
        self.current_view = view_type
        if view_type == 'category':
            self.plot_category_distribution(self.budget_items)
        elif view_type == 'time':
            # 根据预算类型选择显示年度或月度分布
            if self.budget_items and any(item.budget_id == 1 for item in self.budget_items):
                # 总预算显示年度分布
                self.plot_yearly_expenses(self.expenses)
            else:
                # 年度预算显示月度分布
                self.plot_monthly_expenses(self.expenses)
        elif view_type == 'year':
            self.plot_yearly_expenses(self.expenses)
        
    def plot_category_distribution(self, budget_items):
        """绘制费用类别分布饼图"""
        self.budget_items = budget_items
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 准备数据
        labels = []
        sizes = []
        for category in BudgetCategory:
            budget_item = next((item for item in budget_items if item.category == category), None)
            if budget_item and budget_item.amount > 0:
                labels.append(category.value)
                sizes.append(budget_item.amount)
        
        if not sizes:  # 如果没有数据，显示提示信息
            ax.text(0.5, 0.5, '暂无数据', ha='center', va='center')
            ax.axis('off')
        else:
            # 绘制饼图
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                             textprops={'fontsize': 8})
            ax.set_title('费用类别分布', pad=10, fontsize=10)
        
        self.canvas.draw()
        
    def plot_monthly_expenses(self, expenses):
        """绘制月度支出分布饼图"""
        self.expenses = expenses
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 按月份统计支出
        monthly_expenses = {}
        for expense in expenses:
            month = expense.date.strftime('%Y-%m')
            monthly_expenses[month] = monthly_expenses.get(month, 0) + expense.amount
        
        # 准备数据
        labels = list(monthly_expenses.keys())
        sizes = list(monthly_expenses.values())
        
        if not sizes:  # 如果没有数据，显示提示信息
            ax.text(0.5, 0.5, '暂无支出数据', ha='center', va='center')
            ax.axis('off')
        else:
            # 绘制饼图
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                             textprops={'fontsize': 8})
            ax.set_title('月度支出分布', pad=10, fontsize=10)
        
        self.canvas.draw()
        
    def plot_yearly_expenses(self, expenses):
        """绘制年度支出分布饼图"""
        self.expenses = expenses
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        # 按年度统计支出
        yearly_expenses = {}
        for expense in expenses:
            year = expense.date.strftime('%Y')
            yearly_expenses[year] = yearly_expenses.get(year, 0) + expense.amount
        
        # 准备数据
        labels = list(yearly_expenses.keys())
        sizes = list(yearly_expenses.values())
        
        if not sizes:  # 如果没有数据，显示提示信息
            ax.text(0.5, 0.5, '暂无支出数据', ha='center', va='center')
            ax.axis('off')
        else:
            # 绘制饼图
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                             textprops={'fontsize': 8})
            ax.set_title('年度支出分布', pad=10, fontsize=10)
        
        self.canvas.draw()
        
    def update_charts(self, budget_items=None, expenses=None):
        """更新图表数据并显示当前选中的视图"""
        self.budget_items = budget_items
        self.expenses = expenses
        
        if self.current_view == 'category':
            self.plot_category_distribution(budget_items)
        elif self.current_view == 'time':
            # 根据预算类型选择显示年度或月度分布
            if budget_items and any(item.budget_id == 1 for item in budget_items):
                # 总预算显示年度分布
                self.plot_yearly_expenses(expenses)
            else:
                # 年度预算显示月度分布
                self.plot_monthly_expenses(expenses)
        else:
            self.plot_yearly_expenses(expenses)