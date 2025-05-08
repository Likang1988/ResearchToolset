from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from qfluentwidgets import CardWidget, TitleLabel, FluentIcon, PushButton
from ..tools.IndirectCostCalculator import IndirectCostCalculator
from ..tools.TreeList import TreeListApp
import os

class ToolsInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18) # Add some margins
        # 标题栏
        title_layout = QHBoxLayout()
        title_label = TitleLabel("小工具")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # 设置样式表
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }
            QWidget#qt_scrollarea_viewport {
                background-color: transparent;
            }
        """)
        

        # 创建工具卡片容器
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # 添加间接经费计算器卡片
        calculator_card = CardWidget()
        card_layout = QVBoxLayout(calculator_card)
        
        # 工具图标和名称
        tool_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icons', 'calculator.svg')
        icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32)) # 设置图标大小
        name_label = QLabel("间接经费计算器")
        tool_layout.addWidget(icon_label)
        tool_layout.addWidget(name_label)
        tool_layout.addStretch()
        
        # 打开按钮
        open_btn = PushButton("打开", self, FluentIcon.QUICK_NOTE)
        open_btn.clicked.connect(self.open_calculator)
        tool_layout.addWidget(open_btn)
        
        card_layout.addLayout(tool_layout)
        container_layout.addWidget(calculator_card)
        
        # 添加树形列表工具卡片
        treelist_card = CardWidget()
        treelist_layout = QVBoxLayout(treelist_card)
        
        # 工具图标和名称
        treelist_tool_layout = QHBoxLayout()
        treelist_icon_label = QLabel()
        treelist_icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icons', 'treelist.svg')
        treelist_icon_label.setPixmap(QIcon(treelist_icon_path).pixmap(32, 32)) # 设置图标大小
        treelist_name_label = QLabel("树形列表工具")
        treelist_tool_layout.addWidget(treelist_icon_label)
        treelist_tool_layout.addWidget(treelist_name_label)
        treelist_tool_layout.addStretch()
        
        # 打开按钮
        treelist_open_btn = PushButton("打开", self, FluentIcon.QUICK_NOTE)
        treelist_open_btn.clicked.connect(self.open_treelist)
        treelist_tool_layout.addWidget(treelist_open_btn)
        
        treelist_layout.addLayout(treelist_tool_layout)
        container_layout.addWidget(treelist_card)
        container_layout.addStretch()
        
        # 设置滚动区域的内容
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # 添加作者信息
        author_label = QLabel("© Likang")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(author_label)
        
    def open_calculator(self):
        """打开间接经费计算器"""
        self.calculator = IndirectCostCalculator()
        self.calculator.show()
        
    def open_treelist(self):
        """打开树形列表工具"""
        self.treelist = TreeListApp()
        self.treelist.show()