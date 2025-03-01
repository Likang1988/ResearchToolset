from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from qfluentwidgets import TitleLabel, SubtitleLabel, CardWidget

class HomeInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        # 创建欢迎卡片
        welcome_card = CardWidget(self)
        card_layout = QVBoxLayout(welcome_card)
        
        # 添加标题
        title = TitleLabel("欢迎使用科研工具集", self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)
        
        # 添加副标题
        subtitle = SubtitleLabel("本系统帮助您高效管理科研项目经费", self)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle)
        
        # 设置卡片大小
        welcome_card.setFixedSize(600, 200)
        
        # 将卡片添加到主布局
        layout.addWidget(welcome_card)