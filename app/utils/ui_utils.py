from PySide6.QtWidgets import (QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QHeaderView, 
                             QHBoxLayout)
from PySide6.QtGui import QFont # Import QFont
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon, InfoBar, TableWidget, ComboBox
from ..models.database import Project, sessionmaker # Import Project model and sessionmaker
from sqlalchemy import Engine # Import Engine type hint
import os

class UIUtils:
    DEFAULT_INFOBAR_DURATION = 10000
  
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
                background-color: rgba(238,238,238, 1);  
                color: #555555;
                font-weight: 500;
                padding: 8px;
                border: none;
                border-right: 1px solid rgba(0, 0, 0, 0.1);
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
        header.setStretchLastSection(True)  # 最后一列自动填充剩余空间        
        header.setSectionsMovable(True)  # 允许用户调整列宽
        
        # 设置选择模式
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)

        table.itemChanged.connect(UIUtils.set_item_tooltip)

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
                background-color: rgba(238,238,238, 1);  
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
        
        # 设置选择模式
        tree.setSelectionBehavior(QTreeWidget.SelectRows)
        tree.setSelectionMode(QTreeWidget.ExtendedSelection)

        tree.itemChanged.connect(UIUtils.set_tree_item_tooltip)

    @staticmethod
    def set_tree_item_tooltip(item: QTreeWidgetItem, column: int):
        """Sets the tooltip for a QTreeWidgetItem in a specific column."""
        if item:
            item.setToolTip(column, item.text(column))

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
    def set_item_tooltip(item: QTableWidgetItem):
        """Sets the tooltip for a QTableWidgetItem to its full text content."""
        if item:
            item.setToolTip(item.text())

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

    @staticmethod
    def create_project_selector(engine: Engine, parent=None) -> ComboBox:
        """
        创建并填充一个包含所有项目的 ComboBox。

        Args:
            engine: SQLAlchemy 数据库引擎实例。
            parent: 父控件。

        Returns:
            填充了项目列表的 ComboBox 实例。
        """
        combo_box = ComboBox(parent)
        combo_box.setPlaceholderText("请选择项目...")
        combo_box.setMinimumWidth(200) # 设置最小宽度

        # 设置字体
        font = QFont()
        font.setPointSize(16) # 设置字体大小
        font.setBold(True)    # 设置字体加粗
        combo_box.setFont(font)

        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            projects = session.query(Project).order_by(Project.financial_code).all()
            if not projects:
                combo_box.addItem("没有找到项目", userData=None)
                combo_box.setEnabled(False)
            else:
                combo_box.addItem("请选择项目...", userData=None) # 添加默认提示项
                for project in projects:
                    combo_box.addItem(f"{project.financial_code} ", userData=project)
        except Exception as e:
            print(f"Error loading projects for ComboBox: {e}")
            combo_box.addItem("加载项目出错", userData=None)
            combo_box.setEnabled(False)
        finally:
            session.close()

        return combo_box
