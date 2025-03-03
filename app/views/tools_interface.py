from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from qfluentwidgets import CardWidget, TitleLabel, FluentIcon, PushButton
from ..tools.IndirectCostCalculator import IndirectCostCalculator
import os

class ToolsInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 标题栏
        title_layout = QHBoxLayout()
        title_label = TitleLabel("小工具")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea {border: none; background-color: transparent;}")
        
        # 创建工具卡片容器
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # 添加间接经费计算器卡片
        calculator_card = CardWidget()
        card_layout = QVBoxLayout(calculator_card)
        
        # 工具图标和名称
        tool_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'logo', 'calculator.svg')
        icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32)) # 设置图标大小
        name_label = QLabel("间接经费计算器")
        tool_layout.addWidget(icon_label)
        tool_layout.addWidget(name_label)
        tool_layout.addStretch()
        
        # 打开按钮
        open_btn = PushButton("打开", self, FluentIcon.GAME)
        open_btn.clicked.connect(self.open_calculator)
        tool_layout.addWidget(open_btn)
        
        card_layout.addLayout(tool_layout)
        container_layout.addWidget(calculator_card)
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