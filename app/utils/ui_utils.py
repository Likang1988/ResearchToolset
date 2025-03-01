from PySide6.QtWidgets import (QWidget, QTableWidget, QHeaderView, QVBoxLayout,
                             QHBoxLayout, QLabel)
from PySide6.QtCore import Qt
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon
import os

class UIUtils:
  
    @staticmethod
    def set_table_style(table: QTableWidget):
        """设置表格通用样式"""
        table.setStyleSheet("""
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
                height: 32px;
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
        
        # 设置表格基本属性
        table.setBorderVisible(True)
        table.setBorderRadius(8)
        table.setWordWrap(False)
        
        # 设置表头属性
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True)
        header.setSectionsMovable(True)
        
        # 设置选择模式
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        
    @staticmethod
    def create_title_layout(title_text: str, with_back_button: bool = False, back_button_callback = None):
        """创建标准的标题栏布局"""
        title_layout = QHBoxLayout()
        title_label = TitleLabel(title_text)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        if with_back_button:
            back_btn = PrimaryPushButton("返回")
            back_btn.setIcon(FluentIcon.RETURN)
            if back_button_callback:
                back_btn.clicked.connect(back_button_callback)
            title_layout.addWidget(back_btn)
            
        return title_layout
    
    @staticmethod
    def create_button_layout(*buttons):
        """创建标准的按钮栏布局"""
        button_layout = QHBoxLayout()
        for button in buttons:
            button_layout.addWidget(button)
        button_layout.addStretch()
        return button_layout
    
    @staticmethod
    def create_action_button(text: str, icon: FluentIcon = None):
        """创建标准的操作按钮"""
        if icon:
            button = PrimaryPushButton(icon, text)
        else:
            button = PrimaryPushButton(text)
        return button