from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

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