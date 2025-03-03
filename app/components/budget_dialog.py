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
    setTheme, Theme, setThemeColor
)
from ..models.database import BudgetCategory, Budget, BudgetItem, sessionmaker
from sqlalchemy.orm import sessionmaker
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
        amount_group = QGroupBox("预算金额")
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
            InfoBar.warning(
                title='警告',
                content=f'加载总预算数据失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
        
    def update_total(self):
        """根据子项金额更新总金额"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        self.total_label.setText(f"{total:.2f}")
                
    def validate_and_accept(self):
        """验证并保存总预算数据"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        if total <= 0:
            InfoBar.warning(
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
        amount_group = QGroupBox("预算金额")
        amount_layout = QGridLayout()
        
        self.amount_inputs = {}
        for i, category in enumerate(BudgetCategory):
            label = BodyLabel(f"{category.value}:")
            spinbox = DoubleSpinBox()
            spinbox.setRange(0, 999999999)
            spinbox.setDecimals(2)
            spinbox.setSuffix(" 万元")
            spinbox.setValue(0.00)
            self.amount_inputs[category] = spinbox
            amount_layout.addWidget(label, i // 2, (i % 2) * 2)
            amount_layout.addWidget(spinbox, i // 2, (i % 2) * 2 + 1)
            
        amount_group.setLayout(amount_layout)
        
        # 总计
        total_layout = QHBoxLayout()
        total_label = BodyLabel("总计:")
        self.total_label = BodyLabel("0.00 万元")
        total_layout.addWidget(total_label)
        total_layout.addWidget(self.total_label)
        
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
        finally:
            session.close()
            
    def update_total(self):
        """更新并显示预算总额"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        self.total_label.setText(f"{total:.2f} 万元")
        
    def validate_and_accept(self):
        """验证并保存预算数据"""
        total = sum(spinbox.value() for spinbox in self.amount_inputs.values())
        if total <= 0:
            InfoBar.warning(
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
                InfoBar.warning(
                    title='警告',
                    content=f'{year}年度的预算已存在！\n请选择其他年度或编辑现有预算。',
                    parent=self
                )
                return
            
            # 在这里不提交事务，只返回验证结果
            self.accept()
            
        except Exception as e:
            InfoBar.error(
                title='错误',
                content=f'验证预算失败：{str(e)}',
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
