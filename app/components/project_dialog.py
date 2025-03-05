from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                 QLineEdit, QComboBox, QDateEdit, QPushButton, 
                                 QMessageBox)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QIcon
from qfluentwidgets import (LineEdit, EditableComboBox, DateEdit, PushButton, InfoBar,
                          FluentIcon, setTheme, Theme, setThemeColor)
from app.models.funding_db import Budget, BudgetItem
from ..utils.ui_utils import UIUtils
from sqlalchemy.orm import sessionmaker

class ProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("项目信息")
        # 设置窗口大小和样式
        self.resize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 8px;
            }
        """)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 财务编号
        financial_layout = QHBoxLayout()
        financial_layout.addWidget(QLabel("财务编号:"))
        self.financial_code = LineEdit()
        self.financial_code.setPlaceholderText("请输入财务编号")
        financial_layout.addWidget(self.financial_code)
        layout.addLayout(financial_layout)
        
        # 项目名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("项目名称:"))
        self.project_name = LineEdit()
        self.project_name.setPlaceholderText("请输入项目名称")
        name_layout.addWidget(self.project_name)
        layout.addLayout(name_layout)
        
        # 项目编号
        code_layout = QHBoxLayout()
        code_layout.addWidget(QLabel("项目编号:"))
        self.project_code = LineEdit()
        self.project_code.setPlaceholderText("请输入项目编号")
        code_layout.addWidget(self.project_code)
        layout.addLayout(code_layout)
        
        # 项目类别
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("项目类别:"))
        self.project_type = EditableComboBox()
        self.project_type.setPlaceholderText("输入或选择项目类别") # 设置占位文本
        self.project_type.addItems([
            "国家自然科学基金",
            "国家重点研发计划", 
            "国家科技重大专项",
            "省部级科研项目",
            "横向科研项目",
            "校级科研项目",
            "其他科研项目"
        ])
        type_layout.addWidget(self.project_type)
        layout.addLayout(type_layout)
        
        # 开始日期
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("开始日期:"))
        self.start_date = DateEdit()
#        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        start_layout.addWidget(self.start_date)
        layout.addLayout(start_layout)
        
        # 结束日期
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("结束日期:"))
        self.end_date = DateEdit()
#        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        end_layout.addWidget(self.end_date)
        layout.addLayout(end_layout)
        
        # 总经费
        budget_layout = QHBoxLayout()
        budget_layout.addWidget(QLabel("总经费:"))
        self.total_budget = LineEdit()
        self.total_budget.setPlaceholderText("单位：万元")
        budget_layout.addWidget(self.total_budget)
        layout.addLayout(budget_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        save_btn = PushButton("保存", self, FluentIcon.SAVE)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
        
        # 设置按钮样式
        save_btn.setFixedWidth(100)
        cancel_btn.setFixedWidth(100)
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # 连接信号
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
    def accept(self):
        """保存项目信息"""
        # 数据验证
        if not self.financial_code.text().strip():
            UIUtils.show_error(
                title='错误',
                content='请输入财务编号！',
                parent=self
            )
            return
            
        if not self.project_name.text().strip():
            UIUtils.show_error(
                title='错误',
                content='请输入项目名称！',
                parent=self
            )
            return
            
        if not self.total_budget.text().strip():
            UIUtils.show_error(
                title='错误',
                content='请输入项目总经费！',
                parent=self
            )
            return
            
        try:
            float(self.total_budget.text())
        except ValueError:
            UIUtils.show_error(
                title='错误',
                content='项目总经费必须是数字！',
                parent=self
            )
            return
            
        # 保存项目信息
        super().accept()


    def add_custom_type(self):
        """添加自定义项目类别"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加自定义类别")
        dialog.setFixedSize(300, 120)
        dialog.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 8px;
            }
        """)
        
        # 创建布局
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 添加输入框
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("类别名称:"))
        type_input = LineEdit()
        type_input.setPlaceholderText("请输入项目类别名称")
        input_layout.addWidget(type_input)
        layout.addLayout(input_layout)
        
        # 添加按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        ok_btn = PushButton("确定", dialog, FluentIcon.ACCEPT)
        cancel_btn = PushButton("取消", dialog, FluentIcon.CLOSE)
        
        ok_btn.setFixedWidth(80)
        cancel_btn.setFixedWidth(80)
        
        button_layout.addStretch()   # 水平布局
        button_layout.addWidget(ok_btn)    #
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)  # 垂直布局
        
        # 连接信号
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        if dialog.exec() == QDialog.Accepted:
            new_type = type_input.text().strip()
            if new_type:
                # 检查是否已存在
                if self.project_type.findText(new_type) == -1:
                    self.project_type.addItem(new_type)
                    self.project_type.setCurrentText(new_type)
                else:
                    UIUtils.show_warning(
                        title='警告',
                        content='该项目类别已存在！',
                        parent=self
                    )
