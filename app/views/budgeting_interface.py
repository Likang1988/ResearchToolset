from PySide6.QtWidgets import QWidget, QDialog, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QPushButton
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import FluentIcon, PushButton, InfoBar
from app.utils.ui_utils import UIUtils
from enum import Enum
from ..models.budgeting_db import BudgetEditProject, BudgetEditItem, BudgetEditCategory, BudgetEditSubCategory
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

# 使用正确的枚举类
BudgetCategory = BudgetEditCategory
BudgetSubCategory = BudgetEditSubCategory

class BudgetingInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 添加功能开发中的提示信息
        info_label = QLabel("预算编制功能开发中...")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("font-size: 16px; color: #666;")
        main_layout.addWidget(info_label)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)