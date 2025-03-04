import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QTextEdit, QFormLayout, QGroupBox)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt

class IndirectCostCalculator(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()
        
        # 创建输入表单
        form_group = QGroupBox("输入参数")
        form_layout = QFormLayout()
        
        self.total_funds_edit = QLineEdit()
        self.equipment_cost_edit = QLineEdit()
        self.external_cooperation_cost_edit = QLineEdit()
        self.rate1_edit = QLineEdit("20")
        self.rate2_edit = QLineEdit("15")
        self.rate3_edit = QLineEdit("13")
        
        form_layout.addRow("总经费（万元）:", self.total_funds_edit)
        form_layout.addRow("设备费（万元）:", self.equipment_cost_edit)
        form_layout.addRow("外部协作费（万元）:", self.external_cooperation_cost_edit)
        form_layout.addRow("500万元以下比例（%）:", self.rate1_edit)
        form_layout.addRow("500-1000万元比例（%）:", self.rate2_edit)
        form_layout.addRow("1000万元以上比例（%）:", self.rate3_edit)
        
        form_group.setLayout(form_layout)
        main_layout.addWidget(form_group)

        # 创建计算按钮
        self.calculate_button = QPushButton("计算最大间接经费")
        self.calculate_button.clicked.connect(self.calculate_indirect_cost)
        main_layout.addWidget(self.calculate_button)

        # 创建结果显示区域
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        main_layout.addWidget(self.result_text)

        # 添加作者信息
        author_label = QLabel("© Likang")
        author_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(author_label)

        self.setLayout(main_layout)
        self.setWindowTitle('间接经费计算器')
        self.setStyleSheet("""
            QWidget {
                font-family: 'Microsoft YaHei', Arial, sans-serif;
                font-size: 14px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dcdcdc;
                border-radius: 5px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #dcdcdc;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTextEdit {
                border: 1px solid #dcdcdc;
                border-radius: 3px;
            }
            QLabel {
                color: #666;
                font-size: 12px;
            }
        """)
        self.show()

    def calculate_indirect_cost(self):
        try:
            total_funds = float(self.total_funds_edit.text())
            equipment_cost = float(self.equipment_cost_edit.text())
            external_cooperation_cost = float(self.external_cooperation_cost_edit.text())
            rate1 = float(self.rate1_edit.text()) / 100
            rate2 = float(self.rate2_edit.text()) / 100
            rate3 = float(self.rate3_edit.text()) / 100

            indirect_cost = self.calculate_max_indirect_cost(total_funds, equipment_cost, external_cooperation_cost, rate1, rate2, rate3)

            self.result_text.setHtml(f"<h3>计算结果</h3><p>最大间接经费：<b>{indirect_cost:.2f}</b> 万元</p>")
        except ValueError:
            self.result_text.setHtml("<h3>错误</h3><p style='color: red;'>请输入有效的数字</p>")

    def calculate_max_indirect_cost(self, total_funds, equipment_cost, external_cooperation_cost, rate1, rate2, rate3):
        def calc_indirect(direct):
            base = direct - equipment_cost - external_cooperation_cost
            if base <= 500:
                return base * rate1
            elif base <= 1000:
                return 500 * rate1 + (base - 500) * rate2
            else:
                return 500 * rate1 + 500 * rate2 + (base - 1000) * rate3

        left, right = 0, total_funds
        while right - left > 0.01:
            mid = (left + right) / 2
            if mid + calc_indirect(mid) > total_funds:
                right = mid
            else:
                left = mid

        return total_funds - left

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = IndirectCostCalculator()
    sys.exit(app.exec())
