from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QLabel, QPushButton, QMessageBox, QSpinBox, QLineEdit, QHeaderView)
from qfluentwidgets import PrimaryPushButton, TitleLabel, FluentIcon, ToolButton, InfoBar, TableItemDelegate
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from ..models.database import sessionmaker, BudgetCategory, BudgetPlan, BudgetPlanItem
from ..utils.ui_utils import UIUtils

class BudgetingInterface(QWidget):
    """预算编制界面"""
    
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self.setup_ui()
        
        # 连接单元格编辑完成信号
        self.budget_tree.itemChanged.connect(self.on_item_changed)
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        
        # 标题栏
        title_label = TitleLabel("预算编制")
        layout.addWidget(title_label)
        
        # 按钮栏
        button_layout = QHBoxLayout()
        
        # 左侧按钮组
        left_buttons = QHBoxLayout()
        add_budget_btn = UIUtils.create_action_button("添加预算", FluentIcon.ADD_TO)
        add_same_level_btn = UIUtils.create_action_button("增加同级", FluentIcon.ADD)
        add_sub_level_btn = UIUtils.create_action_button("增加子级", FluentIcon.DOWN)
        delete_btn = UIUtils.create_action_button("删除该级", FluentIcon.DELETE)
        
        left_buttons.addWidget(add_budget_btn)
        left_buttons.addWidget(add_same_level_btn)
        left_buttons.addWidget(add_sub_level_btn)
        left_buttons.addWidget(delete_btn)
        left_buttons.addStretch()
        
        # 右侧按钮组
        right_buttons = QHBoxLayout()
        save_btn = UIUtils.create_action_button("保存数据", FluentIcon.SAVE)
        export_btn = UIUtils.create_action_button("导出数据", FluentIcon.DOWNLOAD)
        
        right_buttons.addStretch()
        right_buttons.addWidget(save_btn)
        right_buttons.addWidget(export_btn)
        
        # 添加按钮组到按钮栏
        button_layout.addLayout(left_buttons)
        button_layout.addLayout(right_buttons)
        layout.addLayout(button_layout)
        
        # 树形列表
        self.budget_tree = QTreeWidget()
        self.budget_tree.setColumnCount(6)
        self.budget_tree.setHeaderLabels([
            "课题名称/预算内容", "型号规格/简要内容",
            "单价（元）", "数量", "经费数额", "备注"
        ])
        
        # 设置树形列表样式
        self.budget_tree.setStyleSheet("""
            QTreeWidget {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                selection-background-color: rgba(0, 120, 212, 0.1);
                selection-color: black;
            }
            QTreeWidget::item {
                height: 36px;
                padding: 2px;
            }
            QTreeWidget::item:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QTreeWidget QHeaderView::section {
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
        
        # 设置编辑触发器为单击
        self.budget_tree.setEditTriggers(QTreeWidget.SelectedClicked | QTreeWidget.EditKeyPressed)
        
        # 设置列宽
        header = self.budget_tree.header()
        header.setDefaultAlignment(Qt.AlignCenter)  # 设置表头居中对齐
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.resizeSection(0, 200)  # 课题名称/预算内容
        header.resizeSection(1, 150)  # 型号规格/简要内容
        header.resizeSection(2, 100)  # 单价
        header.resizeSection(3, 100)  # 数量
        header.resizeSection(4, 120)  # 经费数额
        header.resizeSection(5, 120)  # 备注
        
        # 设置单元格对齐方式
        self.budget_tree.setItemDelegateForColumn(0, TableItemDelegate(self.budget_tree))  # 第0列
        self.budget_tree.setItemDelegateForColumn(1, TableItemDelegate(self.budget_tree))  # 第1列
        self.budget_tree.setItemDelegateForColumn(2, TableItemDelegate(self.budget_tree))  # 第2列
        self.budget_tree.setItemDelegateForColumn(3, TableItemDelegate(self.budget_tree))  # 第3列
        self.budget_tree.setItemDelegateForColumn(4, TableItemDelegate(self.budget_tree))  # 第4列
        self.budget_tree.setItemDelegateForColumn(5, TableItemDelegate(self.budget_tree))  # 第5列
        
        layout.addWidget(self.budget_tree)
        
        # 连接信号
        add_budget_btn.clicked.connect(self.add_budget)
        add_same_level_btn.clicked.connect(self.add_same_level)
        add_sub_level_btn.clicked.connect(self.add_sub_level)
        delete_btn.clicked.connect(self.delete_item)
        save_btn.clicked.connect(self.save_data)
        export_btn.clicked.connect(self.export_data)
        
    def add_budget(self):
        """添加新预算项目"""
        # 创建项目总行（第一级）
        project_item = QTreeWidgetItem(self.budget_tree)
        project_item.setText(0, "请输入项目名称")
        project_item.setFlags(project_item.flags() | Qt.ItemIsEditable)
        
        # 添加预算类别（第二级）
        for category in BudgetCategory:
            category_item = QTreeWidgetItem(project_item)
            category_item.setText(0, category.value)
            category_item.setFlags(category_item.flags() & ~Qt.ItemIsEditable)  # 禁止编辑
        
        self.budget_tree.expandAll()
        
    def add_same_level(self):
        """添加同级预算项"""
        current_item = self.budget_tree.currentItem()
        if not current_item:
            return
            
        parent = current_item.parent()
        new_item = QTreeWidgetItem()
        new_item.setText(0, "请输入该级预算名称")
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
        
        if parent:
            parent.insertChild(parent.indexOfChild(current_item) + 1, new_item)
        else:
            self.budget_tree.insertTopLevelItem(
                self.budget_tree.indexOfTopLevelItem(current_item) + 1, new_item
            )
            
    def add_sub_level(self):
        """添加子级预算项"""
        current_item = self.budget_tree.currentItem()
        if not current_item:
            return
            
        # 计算当前项的层级
        level = 1
        parent = current_item
        while parent.parent():
            level += 1
            parent = parent.parent()
            
        # 如果当前已经是第三级，不允许继续添加
        if level >= 3:
            UIUtils.show_warning(
                title="警告",
                content="最多只能添加三级预算项！",
                parent=self
            )
            return
            
        new_item = QTreeWidgetItem(current_item)
        new_item.setText(0, "请输入该级预算名称")
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
        current_item.setExpanded(True)
        
    def delete_item(self):
        """删除预算项"""
        current_item = self.budget_tree.currentItem()
        if not current_item:
            return
            
        # 如果是预算类别项（第二级），不允许删除
        parent = current_item.parent()
        if parent and parent.parent() is None and \
           current_item.text(0) in [category.value for category in BudgetCategory]:
            UIUtils.show_warning(
                title="警告",
                content="预算类别项不可删除！",
                parent=self
            )
            return
            
        # 删除项目
        if parent:
            parent.removeChild(current_item)
        else:
            self.budget_tree.takeTopLevelItem(
                self.budget_tree.indexOfTopLevelItem(current_item)
            )
            
    def save_data(self):
        """保存预算数据到数据库"""
        # TODO: 实现数据保存逻辑
        pass
        
    def export_data(self):
        """导出预算数据"""
        # TODO: 实现数据导出逻辑
        pass
    def on_item_changed(self, item, column):
        """处理单元格编辑完成事件"""
        if column in [2, 3]:  # 单价或数量列被修改
            try:
                # 获取单价和数量
                price = float(item.text(2)) if item.text(2) else 0
                quantity = float(item.text(3)) if item.text(3) else 0
                
                # 计算经费数额
                amount = price * quantity
                item.setText(4, f"{amount:.2f}")
                
                # 更新父项经费数额
                self.update_parent_amount(item)
            except ValueError:
                # 输入的不是有效数字，清空经费数额
                item.setText(4, "")
                
    def update_parent_amount(self, item):
        """更新父项经费数额"""
        parent = item.parent()
        if parent:
            # 计算所有子项经费数额之和
            total_amount = 0
            for i in range(parent.childCount()):
                child = parent.child(i)
                try:
                    amount = float(child.text(4)) if child.text(4) else 0
                    total_amount += amount
                except ValueError:
                    continue
            
            # 如果是项目名称行，不显示单价和数量
            if not parent.parent():  # 顶级项目
                parent.setText(2, "")  # 清空单价
                parent.setText(3, "")  # 清空数量
            
            # 更新父项经费数额
            parent.setText(4, f"{total_amount:.2f}")
            
            # 递归更新上级项目
            self.update_parent_amount(parent)