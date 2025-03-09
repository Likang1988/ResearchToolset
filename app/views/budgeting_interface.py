from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QLabel, QPushButton, QMessageBox, QSpinBox, QLineEdit, QHeaderView)
from qfluentwidgets import PrimaryPushButton, TitleLabel, FluentIcon, ToolButton, InfoBar, TableItemDelegate, Dialog
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
        self.load_budget_plans()  # 添加加载预算数据的调用
        # 连接单元格编辑完成信号
        self.budget_tree.itemChanged.connect(self.on_item_changed)

    def load_budget_plans(self):
        """加载已保存的预算计划数据"""
        try:
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            # 查询所有预算计划
            budget_plans = session.query(BudgetPlan).all()
            
            for plan in budget_plans:
                # 创建顶级项目
                project_item = QTreeWidgetItem(self.budget_tree)
                project_item.setText(0, plan.name)
                project_item.setText(4, f"{plan.total_amount:.2f}")
                project_item.setText(5, plan.remarks or "")
                project_item.setFlags(project_item.flags() | Qt.ItemIsEditable)
                
                # 设置第一级项目的经费数额字体加粗
                font = project_item.font(4)
                font.setBold(True)
                project_item.setFont(4, font)
                
                
                # 添加预算类别
                for category in BudgetCategory:
                    category_item = QTreeWidgetItem(project_item)
                    category_item.setText(0, category.value)
                    category_item.setFlags(category_item.flags() & ~Qt.ItemIsEditable)  # 禁止编辑

                    
                    # 查询该类别的预算项
                    budget_items = session.query(BudgetPlanItem).filter(
                        BudgetPlanItem.plan_id == plan.id,
                        BudgetPlanItem.category == category,
                        BudgetPlanItem.parent_id.is_(None)
                    ).all()
                    
                    # 设置类别总金额
                    if budget_items:
                        category_item.setText(4, f"{budget_items[0].amount:.2f}")
                        category_item.setText(5, budget_items[0].remarks or "")
                    
                    # 查询并添加子项（包括第二级和第三级）
                    def add_sub_items(parent_item, parent_id):
                        sub_items = session.query(BudgetPlanItem).filter(
                            BudgetPlanItem.plan_id == plan.id,
                            BudgetPlanItem.category == category,
                            BudgetPlanItem.parent_id == parent_id
                        ).all()
                        
                        for sub_item in sub_items:
                            item = QTreeWidgetItem(parent_item)
                            item.setText(0, sub_item.name)
                            item.setText(1, sub_item.specification or "")
                            item.setText(2, f"{sub_item.unit_price:.2f}" if sub_item.unit_price else "")
                            item.setText(3, f"{sub_item.quantity:.0f}" if sub_item.quantity else "")
                            item.setText(4, f"{sub_item.amount:.2f}" if sub_item.amount else "")
                            item.setText(5, sub_item.remarks or "")
                            item.setFlags(item.flags() | Qt.ItemIsEditable)
                            
                            # 递归加载子项的子项
                            add_sub_items(item, sub_item.id)
                    
                    # 从第二级开始加载
                    if budget_items:
                        add_sub_items(category_item, budget_items[0].id)
            
            session.close()
            
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'加载预算数据失败：{str(e)}',
                parent=self
            )
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
            "课题名称/预算名称", "型号规格/简要内容",
            "单价（元）", "数量", "经费数额（元）", "备注"
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
        header.resizeSection(0, 400)  # 课题名称/预算内容
        header.resizeSection(1, 250)  # 型号规格/简要内容
        header.resizeSection(2, 100)  # 单价
        header.resizeSection(3, 80)  # 数量
        header.resizeSection(4, 110)  # 经费数额
        header.resizeSection(5, 120)  # 备注
        
        # 设置单元格对齐方式
        def set_item_alignment(item):
            # 型号规格列居中对齐
            item.setTextAlignment(1, Qt.AlignCenter)
            # 单价列右对齐
            item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            # 数量列居中对齐
            item.setTextAlignment(3, Qt.AlignCenter)
            
            # 根据层级设置经费数额列的对齐方式
            level = 1
            parent = item.parent()
            while parent:
                level += 1
                parent = parent.parent()
            
            # 第一、二级经费数额居中对齐，第三级右对齐
            if level <= 2:
                item.setTextAlignment(4, Qt.AlignCenter)
            else:
                item.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)
            
            # 递归设置子项的对齐方式
            for i in range(item.childCount()):
                set_item_alignment(item.child(i))
        
        # 连接信号以在添加新项时设置对齐方式
        self.budget_tree.itemChanged.connect(lambda item, column: set_item_alignment(item))
        
        
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
        project_item.setText(0, "请输入课题名称")
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
            UIUtils.show_warning(
                title='警告',
                content='请选择要删除的预算项！',
                parent=self
            )
            return
            
        # 使用Dialog显示确认对话框
        confirm_dialog = Dialog(
            '确认删除',
            '确定要删除该预算项吗？此操作不可恢复！',
            self
        )
        
        if not confirm_dialog.exec():  # 如果用户取消删除，直接返回
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
            
        try:
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            # 如果是顶级项目，删除整个预算计划及其所有子项
            if not parent:
                budget_plan = session.query(BudgetPlan).filter_by(
                    name=current_item.text(0)
                ).first()
                if budget_plan:
                    session.delete(budget_plan)
            else:
                # 获取预算计划
                top_item = current_item
                while top_item.parent():
                    top_item = top_item.parent()
                budget_plan = session.query(BudgetPlan).filter_by(
                    name=top_item.text(0)
                ).first()
                
                if budget_plan:
                    # 获取当前项目的类别
                    category_item = current_item
                    while category_item.parent() and category_item.parent().parent():
                        category_item = category_item.parent()
                    category = next((c for c in BudgetCategory if c.value == category_item.text(0)), None)
                    
                    if category:
                        # 删除当前项及其子项
                        budget_item = session.query(BudgetPlanItem).filter_by(
                            plan_id=budget_plan.id,
                            category=category,
                            name=current_item.text(0)
                        ).first()
                        if budget_item:
                            session.delete(budget_item)
            
            session.commit()
            
            # 删除界面项目
            if parent:
                parent.removeChild(current_item)
            else:
                self.budget_tree.takeTopLevelItem(
                    self.budget_tree.indexOfTopLevelItem(current_item)
                )
                
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'删除预算项失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
            
    def save_data(self):
        """保存预算数据到数据库"""
        try:
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            # 遍历所有顶级项目
            for i in range(self.budget_tree.topLevelItemCount()):
                project_item = self.budget_tree.topLevelItem(i)
                
                # 查找或创建预算计划
                budget_plan = session.query(BudgetPlan).filter_by(
                    name=project_item.text(0)
                ).first()
                
                if budget_plan:
                    # 更新现有预算计划
                    budget_plan.total_amount = float(project_item.text(4)) if project_item.text(4) else 0.0
                    budget_plan.remarks = project_item.text(5) or None
                else:
                    # 创建新的预算计划
                    budget_plan = BudgetPlan(
                        name=project_item.text(0),
                        total_amount=float(project_item.text(4)) if project_item.text(4) else 0.0,
                        remarks=project_item.text(5) or None
                    )
                    session.add(budget_plan)
                    session.flush()  # 获取预算计划ID
                
                # 保存预算类别项
                for j in range(project_item.childCount()):
                    category_item = project_item.child(j)
                    category_name = category_item.text(0)
                    category = next((c for c in BudgetCategory if c.value == category_name), None)
                    
                    if category:
                        # 查找或创建预算类别项
                        budget_item = session.query(BudgetPlanItem).filter_by(
                            plan_id=budget_plan.id,
                            category=category,
                            parent_id=None
                        ).first()
                        
                        if budget_item:
                            # 更新现有预算类别项
                            budget_item.amount = float(category_item.text(4)) if category_item.text(4) else 0.0
                            budget_item.remarks = category_item.text(5) or None
                        else:
                            # 创建新的预算类别项
                            budget_item = BudgetPlanItem(
                                plan_id=budget_plan.id,
                                category=category,
                                amount=float(category_item.text(4)) if category_item.text(4) else 0.0,
                                remarks=category_item.text(5) or None
                            )
                            session.add(budget_item)
                            session.flush()
                        
                        # 删除旧的子项
                        session.query(BudgetPlanItem).filter_by(
                            plan_id=budget_plan.id,
                            category=category,
                            parent_id=budget_item.id
                        ).delete()
                        
                        # 保存新的子项
                        for k in range(category_item.childCount()):
                            sub_item = category_item.child(k)
                            budget_sub_item = BudgetPlanItem(
                                plan_id=budget_plan.id,
                                parent_id=budget_item.id,
                                category=category,
                                name=sub_item.text(0),
                                specification=sub_item.text(1),
                                unit_price=float(sub_item.text(2)) if sub_item.text(2) else 0.0,
                                quantity=float(sub_item.text(3)) if sub_item.text(3) else 0.0,
                                amount=float(sub_item.text(4)) if sub_item.text(4) else 0.0,
                                remarks=sub_item.text(5) or None
                            )
                            session.add(budget_sub_item)
                
            # 提交事务
            session.commit()
            
            # 显示成功消息
            UIUtils.show_success(
                title='成功',
                content='预算数据保存成功！',
                parent=self
            )
            
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'保存预算数据失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
        
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