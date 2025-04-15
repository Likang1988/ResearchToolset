from PySide6.QtWidgets import (QWidget, QTableWidget, QTreeWidget, QHeaderView, QVBoxLayout,
                             QHBoxLayout, QLabel)
from PySide6.QtCore import Qt
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon, InfoBar, TableWidget
import os

class UIUtils:
    # 统一设置InfoBar的显示时间为15秒
    DEFAULT_INFOBAR_DURATION = 5000
  
    @staticmethod
    def set_table_style(table: TableWidget):
        """设置表格通用样式"""
        table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                selection-background-color: rgba(0, 0, 0, 0.05);
                selection-color: black;
            }
            QTableWidget::item {
                padding: 4px 8px;
                border: none;
                height: 32px;
            }
            QTableWidget::item:hover {
                background-color: rgba(0, 0, 0, 0.03);
            }
            QHeaderView::section {
                background-color: transparent;  
                color: #555555;
                font-weight: 500;
                padding: 8px;
                border: none;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            }
            QHeaderView::section:hover {
                background-color: #f5f5f5;
            }
        """)
        
        # 设置表格基本属性
        table.setWordWrap(False)
        
        # 设置表头属性
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
    #    header.setSortIndicatorShown(True)
    #    header.setSectionsMovable(True)
        
        # 设置选择模式
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        
    @staticmethod
    def set_tree_style(tree):
        """设置树形控件通用样式"""
        tree.setStyleSheet("""
            QTreeWidget {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                selection-background-color: rgba(0, 0, 0, 0.05);
                selection-color: black;
            }
            QTreeWidget::item {
                padding: 4px 8px;
                border: none;
                height: 32px;
            }
            QTreeWidget::item:hover {
                background-color: rgba(0, 0, 0, 0.001);
            }
            QHeaderView::section {
                background-color: rgba(0, 0, 0, 0.01);  
                color: #333333;
                font-weight: 500;
                padding: 8px;
                height: 28px;
                border: none;
                border-right: 1px solid rgba(0, 0, 0, 0.1);
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            }
            QHeaderView::section:hover {
                background-color: rgba(0, 0, 0, 0.001);
            }
        """)
        
        # 设置表头属性
        header = tree.header()
        header.setSectionResizeMode(QHeaderView.Interactive)
    #    header.setSortIndicatorShown(True)
    #    header.setSectionsMovable(True)
        
        # 设置选择模式
        tree.setSelectionBehavior(QTreeWidget.SelectRows)
        tree.setSelectionMode(QTreeWidget.ExtendedSelection)

    @staticmethod
    def create_title_layout(title_text: str):
        """创建标准的标题栏布局"""
        title_layout = QHBoxLayout()
        title_label = TitleLabel(title_text)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
      
            
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

    @staticmethod
    def show_info(parent, title, content):
        """显示信息提示"""
        InfoBar.info(title=title, content=content, parent=parent, duration=UIUtils.DEFAULT_INFOBAR_DURATION)
    
    @staticmethod
    def show_success(parent, title, content):
        """显示成功提示"""
        InfoBar.success(title=title, content=content, parent=parent, duration=UIUtils.DEFAULT_INFOBAR_DURATION)
    
    @staticmethod
    def show_warning(parent, title, content):
        """显示警告提示"""
        InfoBar.warning(title=title, content=content, parent=parent, duration=UIUtils.DEFAULT_INFOBAR_DURATION)
    
    @staticmethod
    def show_error(parent, title, content):
        """显示错误提示"""
        InfoBar.error(title=title, content=content, parent=parent, duration=UIUtils.DEFAULT_INFOBAR_DURATION)

    @staticmethod
    def get_svg_icon_path(icon_name: str) -> str:
        """获取SVG图标文件的完整路径
        
        Args:
            icon_name: 图标文件名(不带扩展名)
            
        Returns:
            SVG图标的完整路径
            
        Raises:
            FileNotFoundError: 如果图标文件不存在
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, 'assets', 'icons', f'{icon_name}.svg')
        
        if not os.path.exists(icon_path):
            raise FileNotFoundError(f"SVG图标文件不存在: {icon_path}")
            
        return icon_path
