from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QLabel, QPushButton, QMessageBox, QSpinBox, QDoubleSpinBox, QHeaderView)
from PySide6.QtCore import Qt, Signal
from qfluentwidgets import TitleLabel, FluentIcon, PrimaryPushButton
from ..models.database import BudgetCategory, BudgetPlan, BudgetPlanItem, sessionmaker
from ..utils.ui_utils import UIUtils
from sqlalchemy.orm import Session

class BudgetingInterface(QWidget):
    """预算编制界面"""
    
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题
        title_layout = QHBoxLayout()
        title = TitleLabel('预算编制')
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 按钮栏
        button_layout = QHBoxLayout()
        add_btn = PrimaryPushButton('添加预算', self, FluentIcon.ADD)
        add_same_level_btn = PrimaryPushButton('增加同级', self, FluentIcon.MENU)
        add_sub_level_btn = PrimaryPushButton('增加子级', self, FluentIcon.DOWN)
        delete_level_btn = PrimaryPushButton('删除该级', self, FluentIcon.DELETE)
        save_btn = PrimaryPushButton('保存数据', self, FluentIcon.SAVE)
        export_btn = PrimaryPushButton('导出数据', self, FluentIcon.DOWNLOAD)
        
        button_layout.addWidget(add_btn)
        button_layout.addWidget(add_same_level_btn)
        button_layout.addWidget(add_sub_level_btn)
        button_layout.addWidget(delete_level_btn)
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(export_btn)
        layout.addLayout(button_layout)
        
        # 设置新按钮样式
        save_btn.setStyleSheet(add_btn.styleSheet())
        export_btn.setStyleSheet(add_btn.styleSheet())
        
        # 禁用层级管理按钮，直到选中项目
        add_same_level_btn.setEnabled(False)
        add_sub_level_btn.setEnabled(False)
        delete_level_btn.setEnabled(False)
        
        # 树形列表
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels([
            '课题名称/预算内容',
            '型号规格/简要内容',
            '单价（元）',
            '数量',
            '经费数额',
            '备注'
        ])
        
        # 设置列宽
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 第一列自适应宽度
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 第二列自适应宽度
        for i in range(2, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)  # 其他列根据内容调整宽度
        
        add_same_level_btn.setStyleSheet(add_btn.styleSheet())
        add_sub_level_btn.setStyleSheet(add_btn.styleSheet())
        delete_level_btn.setStyleSheet(add_btn.styleSheet())

        # 设置树形列表样式
        self.tree.setStyleSheet("""
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
            QTreeWidget::item:selected {
                background-color: rgba(0, 120, 212, 0.1);
                color: black;
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
        self.tree.setAlternatingRowColors(True)  # 启用交替行颜色
        
        layout.addWidget(self.tree)
        
        # 信号连接
        add_btn.clicked.connect(self.add_budget_item)
        add_same_level_btn.clicked.connect(self.add_same_level_item)
        add_sub_level_btn.clicked.connect(self.add_sub_level_item)
        delete_level_btn.clicked.connect(self.delete_level_item)
        save_btn.clicked.connect(self.save_all_budget_data)
        export_btn.clicked.connect(self.export_budget_data)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        
        # 保存按钮引用
        self.add_same_level_btn = add_same_level_btn
        self.add_sub_level_btn = add_sub_level_btn
        self.delete_level_btn = delete_level_btn
        
        # 加载已有预算数据
        self.load_budget_data()
        
    def add_budget_item(self):
        """添加预算项目"""
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, "请输入项目名称")
        root_item.setFlags(root_item.flags() | Qt.ItemIsEditable)
        root_item.setData(0, Qt.UserRole + 1, "project")  # 标记为项目节点
        
        # 添加预算类别子项
        for category in BudgetCategory:
            child = QTreeWidgetItem(root_item)
            child.setText(0, category.value)
            child.setFlags(child.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
            child.setData(0, Qt.UserRole, category)
            child.setData(0, Qt.UserRole + 1, "category")  # 标记为类别节点
            
        self.tree.expandAll()
        self.save_budget_data(root_item)
        
    def add_same_level_item(self):
        """添加同级预算项"""
        current_item = self.tree.currentItem()
        if not current_item:
            return
            
        parent = current_item.parent()
        if not parent:
            # 如果是顶级项目，添加新的项目
            self.add_budget_item()
            return
            
        # 获取当前项的类型
        item_type = current_item.data(0, Qt.UserRole + 1)
        if item_type == "category":
            return  # 不允许在类别层级添加同级
            
        # 创建新的同级项
        new_item = QTreeWidgetItem(parent)
        new_item.setText(0, "请输入预算内容")
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
        new_item.setData(0, Qt.UserRole + 1, "budget_item")
        
        # 设置默认值
        new_item.setText(2, "0.00")  # 单价
        new_item.setText(3, "0")     # 数量
        new_item.setText(4, "0.00")  # 经费数额
        
        self.tree.setCurrentItem(new_item)
        self.save_budget_data(new_item)
        
    def add_sub_level_item(self):
        """添加子级预算项"""
        current_item = self.tree.currentItem()
        if not current_item:
            return
            
        # 获取当前项的类型
        item_type = current_item.data(0, Qt.UserRole + 1)
        if item_type == "category":
            # 在类别下添加预算项
            new_item = QTreeWidgetItem(current_item)
            new_item.setText(0, "请输入预算内容")
            new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
            new_item.setData(0, Qt.UserRole + 1, "budget_item")
            
            # 设置默认值
            new_item.setText(2, "0.00")  # 单价
            new_item.setText(3, "0")     # 数量
            new_item.setText(4, "0.00")  # 经费数额
            
            self.tree.setCurrentItem(new_item)
            self.save_budget_data(new_item)
            
    def delete_level_item(self):
        """删除当前级别项目"""
        current_item = self.tree.currentItem()
        if not current_item:
            return
            
        # 获取当前项的类型
        item_type = current_item.data(0, Qt.UserRole + 1)
        if item_type == "category":
            return  # 不允许删除类别节点
            
        # 确认删除
        reply = QMessageBox.question(
            self,
            '确认删除',
            '确定要删除该预算项吗？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            session = Session(self.engine)
            try:
                # 如果是项目节点，删除整个预算计划
                if item_type == "project":
                    name = current_item.text(0)
                    budget_plan = session.query(BudgetPlan).filter_by(name=name).first()
                    if budget_plan:
                        session.delete(budget_plan)
                        session.commit()
                # 如果是预算子项，删除对应的预算项
                elif item_type == "budget_item":
                    parent = current_item.parent()
                    if parent:
                        category = current_item.data(0, Qt.UserRole)
                        budget_plan = session.query(BudgetPlan).filter_by(name=parent.text(0)).first()
                        if budget_plan:
                            plan_item = session.query(BudgetPlanItem).filter_by(
                                budget_plan_id=budget_plan.id,
                                category=category
                            ).first()
                            if plan_item:
                                session.delete(plan_item)
                                session.commit()
                
                # 从树形控件中移除节点
                parent = current_item.parent()
                if parent:
                    parent.removeChild(current_item)
                    self.update_parent_amount(parent)
                else:
                    index = self.tree.indexOfTopLevelItem(current_item)
                    self.tree.takeTopLevelItem(index)
                    
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title='错误',
                    content=f'删除预算项失败：{str(e)}',
                    parent=self
                )
            finally:
                session.close()
    
    def on_selection_changed(self):
        """处理选择变化"""
        current_item = self.tree.currentItem()
        if not current_item:
            self.add_same_level_btn.setEnabled(False)
            self.add_sub_level_btn.setEnabled(False)
            self.delete_level_btn.setEnabled(False)
            return
            
        # 获取当前项的类型
        item_type = current_item.data(0, Qt.UserRole + 1)
        
        # 设置按钮状态
        self.add_same_level_btn.setEnabled(item_type != "category")
        self.add_sub_level_btn.setEnabled(item_type == "category")
        self.delete_level_btn.setEnabled(item_type != "category")
        
    def on_item_changed(self, item, column):
        """处理项目内容变化"""
        if column in [2, 3]:  # 单价或数量变化时
            try:
                price = float(item.text(2) or 0)
                quantity = int(item.text(3) or 0)
                amount = price * quantity
                item.setText(4, f"{amount:.2f}")
                
                # 更新父项的经费总额
                if item.parent():
                    self.update_parent_amount(item.parent())
                    # 如果父项是项目根节点，不需要再更新上级
                    if item.parent().parent() is None:
                        # 保存更新后的数据
                        self.save_budget_data(item)
                        # 更新总行经费数额
                        self.update_total_amount()
                    else:
                        # 如果是项目根节点，直接保存
                        self.save_budget_data(item)
            except ValueError:
                pass
                
    def update_parent_amount(self, parent_item):
        """更新父项的经费总额"""
        total = 0.0
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            try:
                amount = float(child.text(4) or 0)
                total += amount
            except ValueError:
                pass
        parent_item.setText(4, f"{total:.2f}")
        
    def load_budget_data(self):
        """从数据库加载预算数据"""
        session = Session(self.engine)
        try:
            # 获取所有预算编制项目
            budget_plans = session.query(BudgetPlan).all()
            
            for plan in budget_plans:
                # 创建项目根节点
                root_item = QTreeWidgetItem(self.tree)
                root_item.setText(0, plan.name)
                root_item.setFlags(root_item.flags() | Qt.ItemIsEditable)
                
                # 加载预算子项
                for plan_item in plan.budget_plan_items:
                    child = QTreeWidgetItem(root_item)
                    child.setText(0, plan_item.category.value)
                    child.setText(1, plan_item.specification or "")  # 型号规格
                    child.setText(2, str(plan_item.unit_price or 0.00))  # 单价
                    child.setText(3, str(plan_item.quantity or 0))      # 数量
                    child.setText(4, str(plan_item.amount))             # 经费数额
                    child.setText(5, plan_item.remarks or "")           # 备注
                    child.setFlags(child.flags() | Qt.ItemIsEditable)
                    child.setData(0, Qt.UserRole, plan_item.category)
                    
            self.tree.expandAll()
            
        finally:
            session.close()
            
    def save_budget_data(self, item):
        """保存预算数据到数据库"""
        session = Session(self.engine)
        try:
            if item.parent() is None:  # 根节点（项目）
                name = item.text(0)
                if name == "请输入项目名称":
                    return
                    
                # 创建或更新预算编制
                budget_plan = session.query(BudgetPlan).filter_by(name=name).first()
                if not budget_plan:
                    budget_plan = BudgetPlan(name=name)
                    session.add(budget_plan)
                    
                # 更新预算子项
                for i in range(item.childCount()):
                    child = item.child(i)
                    category = child.data(0, Qt.UserRole)
                    if not category:
                        continue
                        
                    plan_item = session.query(BudgetPlanItem).filter_by(
                        budget_plan_id=budget_plan.id,
                        category=category
                    ).first()
                    
                    if not plan_item:
                        plan_item = BudgetPlanItem(
                            budget_plan_id=budget_plan.id,
                            category=category
                        )
                        session.add(plan_item)
                        
                    try:
                        # 保存所有字段
                        plan_item.specification = child.text(1)
                        plan_item.unit_price = float(child.text(2) or 0)
                        plan_item.quantity = int(child.text(3) or 0)
                        plan_item.amount = float(child.text(4) or 0)
                        plan_item.remarks = child.text(5)
                    except ValueError:
                        pass
                        
                session.commit()
            
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'保存预算数据失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
    
    def update_total_amount(self):
        """更新总行经费数额"""
        total_amount = 0.0
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            project_item = root.child(i)
            # 获取每个预算类别的经费数额
            amount_str = project_item.text(4)
            try:
                amount = float(amount_str) if amount_str else 0.0
                total_amount += amount
            except ValueError:
                continue
        
        # 更新总行经费数额
        total_item = self.tree.topLevelItem(0)
        if total_item:
            total_item.setText(4, f"{total_amount:.2f}")
            
    def save_all_budget_data(self):
        """保存所有预算数据"""
        try:
            root = self.tree.invisibleRootItem()
            for i in range(root.childCount()):
                project_item = root.child(i)
                self.save_budget_data(project_item)
            UIUtils.show_success(
                title='成功',
                content='预算数据保存成功！',
                parent=self
            )
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'保存预算数据失败：{str(e)}',
                parent=self
            )
    
    def export_budget_data(self):
        """导出预算数据到Excel"""
        try:
            import pandas as pd
            from PySide6.QtWidgets import QFileDialog
            
            # 创建数据列表
            data = []
            root = self.tree.invisibleRootItem()
            
            # 遍历所有项目
            for i in range(root.childCount()):
                project_item = root.child(i)
                project_name = project_item.text(0)
                
                # 遍历项目下的预算类别
                for j in range(project_item.childCount()):
                    category_item = project_item.child(j)
                    category_name = category_item.text(0)
                    
                    # 收集预算数据
                    row = {
                        '项目名称': project_name,
                        '预算类别': category_name,
                        '型号规格': category_item.text(1),
                        '单价（元）': category_item.text(2),
                        '数量': category_item.text(3),
                        '经费数额': category_item.text(4),
                        '备注': category_item.text(5)
                    }
                    data.append(row)
            
            # 创建DataFrame
            df = pd.DataFrame(data)
            
            # 选择保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出预算数据",
                "预算编制数据.xlsx",
                "Excel文件 (*.xlsx)"
            )
            
            if file_path:
                # 保存到Excel
                df.to_excel(file_path, index=False)
                UIUtils.show_success(
                    title='成功',
                    content=f'预算数据已导出至：{file_path}',
                    parent=self
                )
        except Exception as e:
            UIUtils.show_error(
                title='错误',
                content=f'导出预算数据失败：{str(e)}',
                parent=self
            )