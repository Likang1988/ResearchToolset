"""
预算对话框模块

该模块定义了BudgetDialog和TotalBudgetDialog类，用于创建和编辑年度预算和总预算信息。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QScrollArea, QWidget, QGridLayout, QMessageBox,
    QGroupBox
)
from PySide6.QtCore import Qt, QDate, Signal
from qfluentwidgets import (
    SpinBox, DoubleSpinBox, PushButton, BodyLabel, FluentIcon, 
    setTheme, Theme, setThemeColor, InfoBar
)
from ..models.database import BudgetCategory, Budget, BudgetItem, sessionmaker
from sqlalchemy.orm import sessionmaker
from ..utils.ui_utils import UIUtils
from sqlalchemy import func

class TotalBudgetDialog(QDialog):
    """
    总预算对话框类，用于编辑项目总预算信息
    
    主要功能：
    - 编辑项目总预算
    - 预算数据验证
    - 预算子项管理
    """
    
    def __init__(self, parent=None, budget=None):
        super().__init__(parent)
        self.project = parent.project
        self.engine = parent.engine
        self.budget = budget
        self.setup_ui()
        self.load_budget_data()
        
    def setup_ui(self):
        """初始化并设置对话框的UI界面"""
        self.setWindowTitle("编辑总预算")
        layout = QVBoxLayout()
        
        # 总金额显示
        total_layout = QHBoxLayout()
        total_label = BodyLabel("总预算:")
        self.total_label = BodyLabel("0.00 万元")
        self.total_label.setAlignment(Qt.AlignRight)
        total_layout.addWidget(total_label)
        total_layout.addWidget(self.total_label)
        total_layout.addStretch()  #
        
        # 预算子项输入
        amount_group = QGroupBox("")
        amount_layout = QGridLayout()
        
        self.amount_inputs = {}
        for i, category in enumerate(BudgetCategory):
            label = BodyLabel(f"{category.value}:")
            spinbox = DoubleSpinBox()
            spinbox.setRange(0, 999999999)
            spinbox.setDecimals(2)
            spinbox.setSuffix(" 万元")
            spinbox.setValue(0.00)
            spinbox.valueChanged.connect(self.update_total)
            self.amount_inputs[category] = spinbox
            amount_layout.addWidget(label, i // 2, (i % 2) * 2)
            amount_layout.addWidget(spinbox, i // 2, (i % 2) * 2 + 1)
            
        amount_group.setLayout(amount_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.setContentsMargins(0, 10, 0, 0)
        save_btn = PushButton("保存", self, FluentIcon.SAVE)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
        
        # 设置按钮样式
        save_btn.setFixedWidth(100)
        cancel_btn.setFixedWidth(100)
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)

        # 添加到主布局
        layout.addLayout(total_layout)
        layout.addWidget(amount_group)
        layout.addStretch()  # 添加弹性空间
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 信号连接
        save_btn.clicked.connect(self.validate_and_accept)
        cancel_btn.clicked.connect(self.reject)
        
    def load_budget_data(self):
        """加载已有的总预算数据"""
        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            # 查询总预算
            total_budget = session.query(Budget).filter(
                Budget.project_id == self.project.id,
                Budget.year.is_(None)
            ).first()
            
            if total_budget:
                # 加载预算子项数据
                budget_items = session.query(BudgetItem).filter_by(
                    budget_id=total_budget.id
                ).all()
                
                for item in budget_items:
                    if item.category in self.amount_inputs:
                        self.amount_inputs[item.category].setValue(item.amount)
                
                self.update_total()
                
        except Exception as e:
            UIUtils.show_warning(
                title='警告',
                content=f'加载总预算数据失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
        
    def update_total(self):
        """根据子项金额更新总金额"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        self.total_label.setText(f"{total:.2f}万元")
                
    def update_balance_amounts(self):
        """更新各费用类别的结余金额显示"""
        Session = sessionmaker(bind=self.parent().engine)
        session = Session()
        
        try:
            # 获取总预算
            total_budget = session.query(Budget).filter(
                Budget.project_id == self.parent().project.id,
                Budget.year.is_(None)
            ).first()
            
            if total_budget:
                # 获取总预算子项
                total_budget_items = session.query(BudgetItem).filter_by(
                    budget_id=total_budget.id
                ).all()
                
                # 获取所有年度预算的支出总和（按类别）
                category_totals = {}
                total_balance = 0.0  # 初始化总结余
                for category in BudgetCategory:
                    category_spent = session.query(func.sum(BudgetItem.spent_amount)).filter(
                        BudgetItem.budget_id.in_(
                            session.query(Budget.id).filter(
                                Budget.project_id == self.parent().project.id,
                                Budget.year.isnot(None)  # 只计算年度预算
                            )
                        ),
                        BudgetItem.category == category
                    ).scalar() or 0.0
                    category_totals[category] = category_spent
                
                # 更新结余金额显示
                for category in BudgetCategory:
                    budget_item = next((item for item in total_budget_items if item.category == category), None)
                    if budget_item:
                        category_spent = category_totals[category]
                        balance = budget_item.amount - category_spent
                        total_balance += balance  # 累加到总结余
                        self.balance_labels[category].setText(f"{balance:.2f} 万元")
                    else:
                        self.balance_labels[category].setText("0.00 万元")
                
                # 更新总计结余显示
                self.total_balance_label.setText(f"{total_balance:.2f} 万元")
            
        finally:
            session.close()
            
    def validate_and_accept(self):
        """验证并保存总预算数据"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        if total <= 0:
            UIUtils.show_warning(
                title='警告',
                content='总预算金额必须大于0！',
                parent=self
            )
            return
            
        self.accept()
        
    def get_data(self):
        """获取对话框中的总预算数据"""
        return {
            'total_amount': sum(spinbox.value() for spinbox in self.amount_inputs.values()),
            'items': {
                category: spinbox.value()
                for category, spinbox in self.amount_inputs.items()
            }
        }

class BudgetDialog(QDialog):
    """
    年度预算对话框类，用于创建和编辑年度预算信息
    
    主要功能：
    - 支持年度预算的创建和编辑
    - 自动计算预算总额
    - 预算数据验证
    - 预算子项管理
    
    属性：
    - budget_updated: 信号，当预算更新时触发
    - budget: 当前编辑的预算对象
    - amount_inputs: 预算子项输入控件字典
    """
    
    # 定义信号
    budget_updated = Signal()
    
    def __init__(self, parent=None, budget=None):
        super().__init__(parent)
        self.budget = budget
        self.setup_ui()
        
        if budget:
            self.setWindowTitle("编辑预算")
            self.year_spin.setEnabled(False)  # 编辑时禁用年份选择
            self.load_budget_data()
        else:
            self.setWindowTitle("添加年度预算")
            self.year_spin.setEnabled(True)  # 添加时启用年份选择
            self.update_balance_amounts()  # 添加时更新结余金额
            
    def setup_ui(self):
        """
        初始化并设置对话框的UI界面
        """
        layout = QVBoxLayout()
        
        # 预算年度选择
        year_layout = QHBoxLayout()
        year_label = BodyLabel("预算年度:")
        self.year_spin = SpinBox()
        current_year = QDate.currentDate().year()
        self.year_spin.setRange(current_year - 10, current_year + 10)
        self.year_spin.setValue(current_year)
        self.year_spin.setAlignment(Qt.AlignRight)
        year_layout.addWidget(year_label)
        year_layout.addWidget(self.year_spin)
        year_layout.addStretch()
        
        # 预算金额输入
        amount_group = QGroupBox("")
        amount_layout = QGridLayout()
        amount_layout.setSpacing(10)
        
        # 添加表头
        header_category = BodyLabel("费用类别")
        header_budget = BodyLabel("预算金额")
        header_balance = BodyLabel("结余金额")
        amount_layout.addWidget(header_category, 0, 0) 
        amount_layout.addWidget(header_budget, 0, 1)
        amount_layout.addWidget(header_balance, 0, 2)
        # 表头居中对齐
        header_budget.setAlignment(Qt.AlignCenter)


        self.amount_inputs = {}
        self.balance_labels = {}
        for i, category in enumerate(BudgetCategory):
            # 费用类别标签
            label = BodyLabel(f"{category.value}:")
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            # 预算金额输入框
            spinbox = DoubleSpinBox()
            spinbox.setRange(0, 999999999)
            spinbox.setDecimals(2)
            spinbox.setSuffix(" 万元")
            spinbox.setValue(0.00)
            spinbox.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.amount_inputs[category] = spinbox
            
            # 结余金额标签
            balance_label = BodyLabel("0.00 万元")
            balance_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.balance_labels[category] = balance_label
            
            # 添加到布局
            amount_layout.addWidget(label, i + 1, 0)
            amount_layout.addWidget(spinbox, i + 1, 1)
            amount_layout.addWidget(balance_label, i + 1, 2)
            
        amount_group.setLayout(amount_layout)
        
        # 总计
        total_layout = QHBoxLayout()
        total_layout.setSpacing(10)
        
        # 总计标签（对应费用类别列）
        total_label = BodyLabel("总计:")
        total_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        total_layout.addWidget(total_label)
        
        # 总预算金额（对应预算金额列）
        self.total_label = BodyLabel("0.00 万元")
        self.total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_layout.addWidget(self.total_label)
        
        # 总结余金额（对应结余金额列）
        self.total_balance_label = BodyLabel("0.00 万元")
        self.total_balance_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_layout.addWidget(self.total_balance_label)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.setContentsMargins(0, 10, 0, 0)
        save_btn = PushButton("保存", self, FluentIcon.SAVE)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
        
        # 设置按钮样式
        save_btn.setFixedWidth(100)
        cancel_btn.setFixedWidth(100)
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)

        
        # 添加到主布局
        layout.addLayout(year_layout)
        layout.addWidget(amount_group)
        layout.addLayout(total_layout)
        layout.addStretch()  # 添加弹性空间
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 信号连接
        save_btn.clicked.connect(self.validate_and_accept)
        cancel_btn.clicked.connect(self.reject)
        for spinbox in self.amount_inputs.values():
            spinbox.valueChanged.connect(self.update_total)
            
    def load_budget_data(self):
        """加载并显示现有预算数据"""
        if not self.budget:
            return
            
        self.year_spin.setValue(self.budget.year)
            
        Session = sessionmaker(bind=self.parent().engine)
        session = Session()
        try:
            budget_items = session.query(BudgetItem).filter_by(
                budget_id=self.budget.id
            ).all()
            
            for item in budget_items:
                if item.category in self.amount_inputs:
                    self.amount_inputs[item.category].setValue(item.amount)
            
            # 更新结余金额显示
            self.update_balance_amounts()
        finally:
            session.close()
            
    def update_total(self):
        """更新并显示预算总额"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        self.total_label.setText(f"{total:.2f} 万元")
        
    def update_balance_amounts(self):
        """更新各费用类别的结余金额显示"""
        Session = sessionmaker(bind=self.parent().engine)
        session = Session()
        
        try:
            # 获取总预算
            total_budget = session.query(Budget).filter(
                Budget.project_id == self.parent().project.id,
                Budget.year.is_(None)
            ).first()
            
            if total_budget:
                # 获取总预算子项
                total_budget_items = session.query(BudgetItem).filter_by(
                    budget_id=total_budget.id
                ).all()
                
                # 获取所有年度预算的支出总和（按类别）
                category_totals = {}
                total_balance = 0.0  # 初始化总结余
                for category in BudgetCategory:
                    category_spent = session.query(func.sum(BudgetItem.spent_amount)).filter(
                        BudgetItem.budget_id.in_(
                            session.query(Budget.id).filter(
                                Budget.project_id == self.parent().project.id,
                                Budget.year.isnot(None)  # 只计算年度预算
                            )
                        ),
                        BudgetItem.category == category
                    ).scalar() or 0.0
                    category_totals[category] = category_spent
                
                # 更新结余金额显示
                for category in BudgetCategory:
                    budget_item = next((item for item in total_budget_items if item.category == category), None)
                    if budget_item:
                        category_spent = category_totals[category]
                        balance = budget_item.amount - category_spent
                        total_balance += balance  # 累加到总结余
                        self.balance_labels[category].setText(f"{balance:.2f} 万元")
                    else:
                        self.balance_labels[category].setText("0.00 万元")
                
                # 更新总计结余显示
                self.total_balance_label.setText(f"{total_balance:.2f} 万元")
            
        finally:
            session.close()
            
    def validate_and_accept(self):
        """验证并保存预算数据"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        if total <= 0:
            UIUtils.show_warning(
                title='警告',
                content='预算总额必须大于0！',
                parent=self
            )
            return
            
        Session = sessionmaker(bind=self.parent().engine)
        session = Session()
        
        try:
            # 开始事务
            year = self.year_spin.value()
            
            # 检查年度预算是否已存在（在同一事务中）
            existing_budget = session.query(Budget).filter_by(
                project_id=self.parent().project.id,
                year=year
            ).with_for_update().first()  # 添加行级锁
            
            if existing_budget and (not self.budget or self.budget.id != existing_budget.id):
                UIUtils.show_warning(
                    title='警告',
                    content=f'{year}年度的预算已存在！\n请选择其他年度或编辑现有预算。',
                    parent=self
                )
                return
            
            # 在这里不提交事务，只返回验证结果
            self.accept()
            
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'添加预算失败：{str(e)}',
                parent=self
            )
            
        finally:
            session.close()
            
    def get_data(self):
        """获取当前对话框中的预算数据"""
        data = {
            'year': self.year_spin.value(),
            'total_amount': sum(spinbox.value() for spinbox in self.amount_inputs.values()),
            'items': {
                category: spinbox.value()
                for category, spinbox in self.amount_inputs.items()
            }
        }
        
        return data
