import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice
from qfluentwidgets import ToolButton, FluentIcon
from ..models.funding_db import BudgetCategory, Expense
from datetime import datetime
from collections import defaultdict
from abc import ABC, abstractmethod

class BudgetChartBase(ABC):
    """预算图表基类，定义图表的基本接口和共用方法"""
    
    def __init__(self):
        self.colors = [
            QColor("#FF9999"), QColor("#66B2FF"), QColor("#99FF99"), 
            QColor("#FFCC99"), QColor("#CC99FF"), QColor("#FF99CC"),
            QColor("#99CCFF"), QColor("#CCFF99"), QColor("#FFFF99")
        ]
    
    def create_empty_chart(self, title):
        """创建空的饼图"""
        chart = QChart()
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        series = QPieSeries()
        empty_slice = QPieSlice("暂无数据", 1)
        empty_slice.setLabelVisible(True)
        series.append(empty_slice)
        chart.addSeries(series)
        return chart
    
    def create_pie_chart(self, title, data_dict):
        """创建带数据的饼图"""
        if not data_dict or sum(data_dict.values()) <= 0:
            return self.create_empty_chart(title)
            
        chart = QChart()
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        series = QPieSeries()
        total_amount = sum(amount for amount in data_dict.values() if amount > 0)
        for i, (label, amount) in enumerate(sorted(data_dict.items())):
            if amount > 0:
                percentage = (amount / total_amount) * 100
                slice = QPieSlice(f"{label}: {amount:.2f}万元 ({percentage:.1f}%)", amount)
                slice.setLabelVisible(True)
                slice.setBrush(self.colors[i % len(self.colors)])
                series.append(slice)
                
        chart.addSeries(series)
        return chart
    
    @abstractmethod
    def show_category_distribution(self):
        """显示类别分布图表"""
        pass
    
    @abstractmethod
    def show_time_distribution(self):
        """显示时间分布图表"""
        pass

class TotalBudgetChart(BudgetChartBase):
    """总预算图表类，处理总预算的图表展示"""
    
    def __init__(self, budget_items, expenses):
        super().__init__()
        self.budget_items = budget_items
        self.expenses = expenses
    
    def show_category_distribution(self):
        """显示总预算的类别分布"""
        category_amounts = defaultdict(float)
        # 统计所有年度预算中各类费用的支出金额
        for expense in self.expenses:
            category_amounts[expense.category.value] += expense.amount / 10000
        
        return self.create_pie_chart("总预算类别分布", category_amounts)
    
    def show_time_distribution(self):
        """显示总预算的年度分布"""
        year_amounts = defaultdict(float)
        for expense in self.expenses:
            year = expense.date.year
            year_amounts[f"{year}年"] += expense.amount / 10000
        
        return self.create_pie_chart("总预算年度支出分布", year_amounts)

class AnnualBudgetChart(BudgetChartBase):
    """年度预算图表类，处理年度预算的图表展示"""
    
    def __init__(self, budget_items, expenses):
        super().__init__()
        self.budget_items = budget_items
        self.expenses = expenses
        self.total_budget = sum(item.amount for item in budget_items) if budget_items else 0
    
    def show_category_distribution(self):
        """显示年度预算的类别分布"""
        category_amounts = defaultdict(float)
        for expense in self.expenses:
            category_amounts[expense.category.value] += expense.amount / 10000
        
        return self.create_pie_chart("类别支出分布", category_amounts)
    
    def show_time_distribution(self):
        """显示年度预算的月度分布"""
        month_amounts = defaultdict(float)
        for expense in self.expenses:
            month = expense.date.month
            month_amounts[f"{month}月"] += expense.amount / 10000
        
        title = f"月度支出分布 (总预算: {self.total_budget:.2f}万元)" if self.total_budget > 0 else "月度支出分布"
        return self.create_pie_chart(title, month_amounts)

class BudgetChartWidget(QWidget):
    """预算图表组件，用于显示预算和支出的饼图统计
    
    支持按费用类别和时间维度（年度/月度）展示数据
    提供切换按钮在不同图表间切换
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.budget_items = []
        self.expenses = []
        self.current_view = "category"  # 默认按类别视图
        self.chart_handler = None
        self.setup_ui()
    
    def setup_ui(self):
        """初始化UI组件"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(5)
        
        # 按钮组布局
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)
        button_layout.setAlignment(Qt.AlignCenter)
        
        # 创建按钮组
        self.button_group = QButtonGroup(self)
        
        # 类别分布按钮
        self.category_btn = QPushButton("类别分布")
        self.category_btn.setCheckable(True)
        self.category_btn.setChecked(True)
        self.category_btn.setFixedHeight(28)
        self.category_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                padding: 4px 8px;
                color: #333333;
            }
            QPushButton:checked {
                background-color: #0078d4;
                color: white;
            }
            QPushButton:hover {
                background-color: #e5e5e5;
            }
            QPushButton:checked:hover {
                background-color: #006cc1;
            }
        """)
        
        # 时间分布按钮
        self.time_btn = QPushButton("时间分布")
        self.time_btn.setCheckable(True)
        self.time_btn.setFixedHeight(28)
        self.time_btn.setStyleSheet(self.category_btn.styleSheet())
        
        # 添加按钮到按钮组
        self.button_group.addButton(self.category_btn, 1)
        self.button_group.addButton(self.time_btn, 2)
        
        # 添加按钮到布局
        button_layout.addWidget(self.category_btn)
        button_layout.addWidget(self.time_btn)
        
        # 添加按钮布局到主布局
        self.main_layout.addLayout(button_layout)
        
        # 创建图表视图
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
        self.chart_view.setMinimumHeight(200)  # 设置最小高度
        self.chart_view.setStyleSheet("background-color: transparent;")
        
        # 添加图表视图到主布局
        self.main_layout.addWidget(self.chart_view)
        
        # 连接信号
        self.category_btn.clicked.connect(self.show_category_chart)
        self.time_btn.clicked.connect(self.show_time_chart)
    
    def update_charts(self, budget_items=None, expenses=None):
        """更新图表数据
        
        Args:
            budget_items: 预算项目列表
            expenses: 支出记录列表
        """
        if budget_items is not None:
            self.budget_items = budget_items
        if expenses is not None:
            self.expenses = expenses
        
        # 判断是总预算还是年度预算
        is_total_budget = any(item.budget.year is None for item in self.budget_items)
        
        # 创建对应的图表处理器
        if is_total_budget:
            self.chart_handler = TotalBudgetChart(self.budget_items, self.expenses)
            self.category_btn.setText("类别分布")
            self.time_btn.setText("年度分布")
        else:
            self.chart_handler = AnnualBudgetChart(self.budget_items, self.expenses)
            self.category_btn.setText("类别分布")
            self.time_btn.setText("月度分布")
        
        # 更新当前视图
        if self.current_view == "category":
            self.show_category_chart()
        else:
            self.show_time_chart()
    
    def show_category_chart(self):
        """显示类别分布图表"""
        if self.chart_handler:
            self.current_view = "category"
            self.category_btn.setChecked(True)
            self.time_btn.setChecked(False)
            chart = self.chart_handler.show_category_distribution()
            self.chart_view.setChart(chart)
    
    def show_time_chart(self):
        """显示时间分布图表"""
        if self.chart_handler:
            self.current_view = "time"
            self.category_btn.setChecked(False)
            self.time_btn.setChecked(True)
            chart = self.chart_handler.show_time_distribution()
            self.chart_view.setChart(chart)
