import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice
from qfluentwidgets import ToolButton, FluentIcon
from ..models.database import BudgetCategory, Expense
from datetime import datetime
from collections import defaultdict

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
        self.category_btn = QPushButton("类别分布按钮")
        self.category_btn.setCheckable(True)
        self.category_btn.setChecked(True)
        self.category_btn.setFixedHeight(28)
        self.category_btn.setText("类别分布")
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
        self.time_btn = QPushButton("时间分布按钮")
        self.time_btn.setCheckable(True)
        self.time_btn.setFixedHeight(28)
        self.time_btn.setText("时间分布")
        self.time_btn.setStyleSheet("""
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
        
        if is_total_budget:
            # 总预算显示类别/年度分布
            self.category_btn.setVisible(True)
            self.time_btn.setVisible(True)
            self.category_btn.setText("类别分布")
            self.time_btn.setText("年度分布")
            if self.current_view == "category":
                self.show_total_category_chart()
            else:
                self.show_total_budget_chart()
        else:
            # 年度预算显示类别/月度分布
            self.category_btn.setVisible(True)
            self.time_btn.setVisible(True)
            self.category_btn.setText("类别分布")
            self.time_btn.setText("月度分布")
            if self.current_view == "category":
                self.show_category_chart()
            else:
                self.show_time_chart()
            
    def show_category_chart(self):
        """显示按费用类别支出的饼图"""
        self.current_view = "category"
        self.category_btn.setChecked(True)
        self.time_btn.setChecked(False)
        
        # 创建饼图
        chart = QChart()
        chart.setTitle("类别支出分布")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        # 创建饼图系列
        series = QPieSeries()
        
        # 按类别统计支出金额
        category_amounts = defaultdict(float)
        for expense in self.expenses:
            category_amounts[expense.category.value] += expense.amount / 10000  # 转换为万元
            
        # 添加饼图切片
        colors = [QColor("#FF9999"), QColor("#66B2FF"), QColor("#99FF99"), 
                 QColor("#FFCC99"), QColor("#CC99FF"), QColor("#FF99CC"),
                 QColor("#99CCFF"), QColor("#CCFF99"), QColor("#FFFF99")]
        
        # 确保有数据才添加切片
        if sum(category_amounts.values()) > 0:
            for i, (category, amount) in enumerate(category_amounts.items()):
                if amount > 0:  # 只添加金额大于0的类别
                    slice = QPieSlice(f"{category}: {amount:.2f}万元", amount)
                    slice.setLabelVisible(True)
                    slice.setBrush(colors[i % len(colors)])
                    series.append(slice)
        else:
            # 如果没有数据，添加一个空切片
            empty_slice = QPieSlice("暂无数据", 1)
            empty_slice.setLabelVisible(True)
            series.append(empty_slice)
            
        chart.addSeries(series)
        self.chart_view.setChart(chart)
        
    def show_total_budget_chart(self):
        """显示总预算支出的饼图"""
        self.current_view = "total"
        
        # 创建饼图
        chart = QChart()
        chart.setTitle("总预算支出分布")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        # 创建饼图系列
        series = QPieSeries()
        
        # 按年度统计支出金额
        year_amounts = defaultdict(float)
        for expense in self.expenses:
            year = expense.date.year
            year_amounts[f"{year}年"] += expense.amount / 10000  # 转换为万元
            
        # 添加饼图切片
        colors = [QColor("#FF9999"), QColor("#66B2FF"), QColor("#99FF99"), 
                 QColor("#FFCC99"), QColor("#CC99FF"), QColor("#FF99CC"),
                 QColor("#99CCFF"), QColor("#CCFF99"), QColor("#FFFF99")]
        
        # 确保有数据才添加切片
        if sum(year_amounts.values()) > 0:
            for i, (year, amount) in enumerate(sorted(year_amounts.items())):
                if amount > 0:  # 只添加金额大于0的年度
                    slice = QPieSlice(f"{year}: {amount:.2f}万元", amount)
                    slice.setLabelVisible(True)
                    slice.setBrush(colors[i % len(colors)])
                    series.append(slice)
        else:
            # 如果没有数据，添加一个空切片
            empty_slice = QPieSlice("暂无数据", 1)
            empty_slice.setLabelVisible(True)
            series.append(empty_slice)
            
        chart.addSeries(series)
        self.chart_view.setChart(chart)
        
    def show_time_chart(self):
        """显示按时间支出分布的饼图"""
        self.current_view = "time"
        self.category_btn.setChecked(False)
        self.time_btn.setChecked(True)
        
        # 创建饼图
        chart = QChart()
        
        # 判断是年度预算还是总预算
        is_annual_budget = any(expense.budget_id for expense in self.expenses)
        
        if is_annual_budget:
            chart.setTitle("月度支出分布")
            # 按月份统计
            time_amounts = defaultdict(float)
            for expense in self.expenses:
                month = expense.date.month
                month_name = f"{month}月"
                time_amounts[month_name] += expense.amount / 10000  # 转换为万元
                
            # 添加年度总预算数据
            if self.budget_items:
                total_budget = sum(item.amount for item in self.budget_items)
                chart.setTitle(f"月度支出分布 (总预算: {total_budget:.2f}万元)")
        else:
            chart.setTitle("年度支出分布")
            # 按年份统计
            time_amounts = defaultdict(float)
            for expense in self.expenses:
                year = expense.date.year
                year_name = f"{year}年"
                time_amounts[year_name] += expense.amount / 10000  # 转换为万元
                
            # 添加总预算数据
            if self.budget_items:
                total_budget = sum(item.amount for item in self.budget_items)
                chart.setTitle(f"年度支出分布 (总预算: {total_budget:.2f}万元)")
        
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        # 创建饼图系列
        series = QPieSeries()
        
        # 添加饼图切片
        colors = [QColor("#FF9999"), QColor("#66B2FF"), QColor("#99FF99"), 
                 QColor("#FFCC99"), QColor("#CC99FF"), QColor("#FF99CC"),
                 QColor("#99CCFF"), QColor("#CCFF99"), QColor("#FFFF99")]
        
        # 确保有数据才添加切片
        if sum(time_amounts.values()) > 0:
            for i, (time_period, amount) in enumerate(sorted(time_amounts.items())):
                if amount > 0:  # 只添加金额大于0的时间段
                    slice = QPieSlice(f"{time_period}: {amount:.2f}万元", amount)
                    slice.setLabelVisible(True)
                    slice.setBrush(colors[i % len(colors)])
                    series.append(slice)
        else:
            # 如果没有数据，添加一个空切片
            empty_slice = QPieSlice("暂无数据", 1)
            empty_slice.setLabelVisible(True)
            series.append(empty_slice)
            
        chart.addSeries(series)
        self.chart_view.setChart(chart)
    
    def show_total_category_chart(self):
        """显示总预算的费用类别支出分布饼图"""
        self.current_view = "category"
        self.category_btn.setChecked(True)
        self.time_btn.setChecked(False)
        
        # 创建饼图
        chart = QChart()
        chart.setTitle("总预算类别支出分布")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        # 创建饼图系列
        series = QPieSeries()
        
        # 按类别统计总预算金额
        category_amounts = defaultdict(float)
        for item in self.budget_items:
            category_amounts[item.category.value] += item.amount / 10000  # 转换为万元
            
        # 添加饼图切片
        colors = [QColor("#FF9999"), QColor("#66B2FF"), QColor("#99FF99"), 
                 QColor("#FFCC99"), QColor("#CC99FF"), QColor("#FF99CC"),
                 QColor("#99CCFF"), QColor("#CCFF99"), QColor("#FFFF99")]
        
        # 确保有数据才添加切片
        if sum(category_amounts.values()) > 0:
            for i, (category, amount) in enumerate(sorted(category_amounts.items())):
                if amount > 0:  # 只添加金额大于0的类别
                    slice = QPieSlice(f"{category}: {amount:.2f}万元", amount)
                    slice.setLabelVisible(True)
                    slice.setBrush(colors[i % len(colors)])
                    series.append(slice)
        else:
            # 如果没有数据，添加一个空切片
            empty_slice = QPieSlice("暂无数据", 1)
            empty_slice.setLabelVisible(True)
            series.append(empty_slice)
            
        chart.addSeries(series)
        self.chart_view.setChart(chart)
