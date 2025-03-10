from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QButtonGroup)
from qfluentwidgets import PushButton, FluentIcon, CompactSpinBox, CheckBox, RadioButton 
from PySide6.QtCore import Qt

class BudgetExportDialog(QDialog):
    """预算导出对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("导出预算数据")
        self.resize(400, 300)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 导出形式
        export_form_label = QLabel("导出形式：")
        export_form_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(export_form_label)
        
        # 预算明细复选框
        self.detail_checkbox = CheckBox("预算明细")
        layout.addWidget(self.detail_checkbox)
        
        # 预算汇总复选框及其子选项
        self.summary_checkbox = CheckBox("预算汇总")
        layout.addWidget(self.summary_checkbox)
        
        # 预算汇总子选项容器
        summary_options_layout = QVBoxLayout()
        summary_options_layout.setContentsMargins(20, 0, 0, 0)
        layout.addLayout(summary_options_layout)
        
        # 细分年度选项
        self.year_detail_checkbox = CheckBox("细分年度：")
        year_detail_layout = QHBoxLayout()
        year_detail_layout.addWidget(self.year_detail_checkbox)
        
        # 项目周期选择器
        self.year_spinbox = CompactSpinBox ()
        self.year_spinbox.setRange(1, 10)
        self.year_spinbox.setValue(3)
        self.year_spinbox.setEnabled(False)
        self.year_spinbox.setFixedWidth(80)
        year_detail_layout.addWidget(self.year_spinbox)
        year_detail_layout.addWidget(QLabel("年"))
        year_detail_layout.addStretch()
        summary_options_layout.addLayout(year_detail_layout)
        
        # 预算比例设置选项
        proportion_layout = QVBoxLayout()
        proportion_layout.setContentsMargins(40, 0, 0, 0)
        
        # 比例设置选项组
        self.proportion_group = QButtonGroup(self)
        self.set_proportion_radio = RadioButton("设置比例：")
        self.no_proportion_radio = RadioButton("比例留空")
        self.proportion_group.addButton(self.set_proportion_radio)
        self.proportion_group.addButton(self.no_proportion_radio)
        self.no_proportion_radio.setChecked(True)
        proportion_layout.addWidget(self.set_proportion_radio)
        proportion_layout.addWidget(self.no_proportion_radio)
        
        # 年度比例设置
        self.proportion_layout = QHBoxLayout()
        self.proportion_layout.setContentsMargins(20, 0, 0, 0)
        self.proportion_spinboxes = []
        self.proportion_labels = []
        for i in range(3):  # 默认显示3年
            spinbox = CompactSpinBox ()
            spinbox.setRange(0, 100)
            spinbox.setValue(30 if i != 1 else 40)  # 默认30-40-30
            spinbox.setSuffix("%")
            spinbox.setEnabled(False)
            spinbox.setFixedWidth(80)
            self.proportion_spinboxes.append(spinbox)
            
            label = QLabel(f"第{i+1}年")
            self.proportion_labels.append(label)
            
            self.proportion_layout.addWidget(label)
            self.proportion_layout.addWidget(spinbox)
            if i < 2:  # 不在最后一个后面添加间距
                self.proportion_layout.addSpacing(10)
        
        proportion_layout.addLayout(self.proportion_layout)
        summary_options_layout.addLayout(proportion_layout)
        
        # 单位设置
        unit_layout = QHBoxLayout()       
        unit_label = QLabel("设置单位：")
        unit_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(unit_label)
        



        self.unit_group = QButtonGroup(self)
        self.unit_yuan = RadioButton("元")
        self.unit_wan = RadioButton("万元")
        self.unit_group.addButton(self.unit_yuan)
        self.unit_group.addButton(self.unit_wan)
        self.unit_yuan.setChecked(True)
        unit_layout.addWidget(self.unit_yuan)
        unit_layout.addWidget(self.unit_wan)
        unit_layout.addStretch()
        layout.addLayout(unit_layout)
        
        # 按钮组
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = PushButton("取消")
        self.cancel_button.setIcon(FluentIcon.CANCEL)
        self.export_button = PushButton("导出")
        self.export_button.setIcon(FluentIcon.SAVE)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.export_button)
        layout.addLayout(button_layout)
        
        # 连接信号
        self.summary_checkbox.stateChanged.connect(self.on_summary_state_changed)
        self.year_detail_checkbox.stateChanged.connect(self.on_year_detail_state_changed)
        self.set_proportion_radio.toggled.connect(self.on_proportion_radio_toggled)
        self.year_spinbox.valueChanged.connect(self.on_year_count_changed)
        self.cancel_button.clicked.connect(self.reject)
        self.export_button.clicked.connect(self.accept)
        
    def on_summary_state_changed(self, state):
        """处理预算汇总复选框状态变化"""
        enabled = bool(state)
        self.year_detail_checkbox.setEnabled(enabled)
        if not enabled:
            self.year_detail_checkbox.setChecked(False)
    
    def on_year_detail_state_changed(self, state):
        """处理细分年度复选框状态变化"""
        enabled = bool(state)
        self.year_spinbox.setEnabled(enabled)
        self.set_proportion_radio.setEnabled(enabled)
        self.no_proportion_radio.setEnabled(enabled)
        if not enabled:
            self.set_proportion_radio.setChecked(False)
            self.no_proportion_radio.setChecked(True)
    
    def on_proportion_radio_toggled(self, checked):
        """处理比例设置单选框状态变化"""
        for spinbox in self.proportion_spinboxes:
            spinbox.setEnabled(checked)
    
    def on_year_count_changed(self, value):
        """处理年数变化"""
        # 更新比例设置界面
        current_count = len(self.proportion_spinboxes)
        
        if value > current_count:
            # 添加新的比例设置
            for i in range(current_count, value):
                if i > 0:
                    self.proportion_layout.addSpacing(10)
                
                label = QLabel(f"第{i+1}年")
                self.proportion_labels.append(label)
                self.proportion_layout.addWidget(label)
                
                spinbox = CompactSpinBox ()
                spinbox.setRange(0, 100)
                spinbox.setValue(30 if i != 1 else 40)  # 默认30-40-30
                spinbox.setSuffix("%")
                spinbox.setEnabled(self.set_proportion_radio.isChecked())
                spinbox.setFixedWidth(80)
                self.proportion_spinboxes.append(spinbox)
                self.proportion_layout.addWidget(spinbox)
        
        elif value < current_count:
            # 移除多余的比例设置
            for i in range(current_count - 1, value - 1, -1):
                # 移除间距（如果存在）
                if i > 0:
                    # 计算间距的索引位置
                    spacing_index = (i * 4) - 1  # 每组控件占4个位置（label, spinbox, spacing）
                    self.proportion_layout.takeAt(spacing_index)
                
                # 移除spinbox
                spinbox_index = i * 2 + 1
                spinbox = self.proportion_spinboxes[i]
                self.proportion_layout.removeWidget(spinbox)
                spinbox.deleteLater()
                self.proportion_spinboxes.pop()
                
                # 移除label
                label_index = i * 2
                label = self.proportion_labels[i]
                self.proportion_layout.removeWidget(label)
                label.deleteLater()
                self.proportion_labels.pop()
    
    def get_export_config(self):
        """获取导出配置"""
        return {
            'export_detail': self.detail_checkbox.isChecked(),
            'export_summary': self.summary_checkbox.isChecked(),
            'year_detail': self.year_detail_checkbox.isChecked(),
            'year_count': self.year_spinbox.value() if self.year_detail_checkbox.isChecked() else 1,
            'set_proportion': self.set_proportion_radio.isChecked(),
            'proportions': [spinbox.value() for spinbox in self.proportion_spinboxes] if self.set_proportion_radio.isChecked() else None,
            'unit': '万元' if self.unit_wan.isChecked() else '元',
            'format_settings': {
                'indent_levels': True,
                'column_alignments': {
                    'price': 'right',
                    'quantity': 'center',
                    'amount': 'right'
                },
                'numeric_format': True,
                'font_styles': {
                    'project': {'bold': True, 'size': 14},
                    'category': {'bold': False, 'size': 12},
                    'item': {'bold': False, 'size': 11}
                }
            }
        }