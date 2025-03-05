from PySide6.QtWidgets import QWidget, QDialog, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView, QPushButton
from PySide6.QtCore import Qt, QTimer
from qfluentwidgets import FluentIcon, PushButton, InfoBar
from app.utils.ui_utils import UIUtils
from enum import Enum
from ..models.budgeting_db import BudgetEditProject, BudgetEditItem, BudgetEditCategory, BudgetEditSubCategory
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

# 使用正确的枚举类
BudgetCategory = BudgetEditCategory
BudgetSubCategory = BudgetEditSubCategory

class BudgetingInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
        # 初始化数据库连接
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'database', 'database.db')
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.Session = sessionmaker(bind=self.engine)
        
        # 确保数据库表存在
        from ..models.budgeting_db import Base as BudgetingBase
        from ..models.funding_db import Base as FundingBase
        BudgetingBase.metadata.create_all(self.engine)
        FundingBase.metadata.create_all(self.engine)
        
        # 加载已保存的项目数据
        self.load_saved_projects()
        
    def load_saved_projects(self):
        """加载已保存的项目数据"""
        session = self.Session()
        try:
            # 查询所有已保存的项目
            projects = session.query(BudgetEditProject).all()
            if projects:
                # 清空现有树形结构
                self.tree.clear()
                # 加载第一个项目（后续可以添加项目切换功能）
                project = projects[0]
                self.init_tree(project.name)
                
                # 递归加载预算项
                def load_items(parent_item, items):
                    for item in items:
                        if not item.parent_id:  # 顶级预算项
                            # 在对应的类别下查找或创建预算项
                            category_item = None
                            for i in range(parent_item.childCount()):
                                if parent_item.child(i).text(0) == (item.category.value if item.category else ""):
                                    category_item = parent_item.child(i)
                                    break
                            
                            if category_item:
                                # 在类别下查找或创建子类别
                                subcategory_item = None
                                for i in range(category_item.childCount()):
                                    if category_item.child(i).text(0) == (item.subcategory.value if item.subcategory else ""):
                                        subcategory_item = category_item.child(i)
                                        break
                                
                                if subcategory_item:
                                    # 创建预算项
                                    budget_item = QTreeWidgetItem(subcategory_item)
                                    budget_item.setText(0, item.name or "")
                                    budget_item.setText(1, item.specification or "")
                                    budget_item.setText(2, str(item.unit_price) if item.unit_price else "")
                                    budget_item.setText(3, str(item.quantity) if item.quantity else "")
                                    budget_item.setText(4, str(item.amount) if item.amount else "")
                                    budget_item.setText(5, item.remarks or "")
                                    budget_item.setFlags(budget_item.flags() | Qt.ItemIsEditable)
                                    
                                    # 递归加载子项
                                    load_items(budget_item, [i for i in items if i.parent_id == item.id])
                                    
                                    # 初始化计算父项金额
                                    self.update_parent_amount(budget_item)
                
                # 获取项目的所有预算项
                items = session.query(BudgetEditItem).filter_by(project_id=project.id).all()
                root = self.tree.topLevelItem(0)
                load_items(root, items)
                
                # 展开所有节点
                self.tree.expandAll()
                
        except Exception as e:
            UIUtils.show_error(
                title="错误",
                content=f"加载预算数据失败：{str(e)}",
                parent=self
            )
        finally:
            session.close()
    
    def setup_ui(self):
        """设置UI界面"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(26, 26, 26, 26)
        main_layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素
        # 添加标题
        title_layout = UIUtils.create_title_layout("预算编制")
        main_layout.addLayout(title_layout)
        
        # 添加按钮栏
        add_btn = UIUtils.create_action_button("添加课题", FluentIcon.LIBRARY)
        add_same_level_btn = UIUtils.create_action_button("增加同级", FluentIcon.ALIGNMENT)
        add_sub_level_btn = UIUtils.create_action_button("增加子级", FluentIcon.DOWN)
        delete_level_btn = UIUtils.create_action_button("删除该级", FluentIcon.DELETE)
        
        add_btn.clicked.connect(self.add_budget_item)
        add_same_level_btn.clicked.connect(self.add_same_level_item)
        add_sub_level_btn.clicked.connect(self.add_sub_level_item)
        delete_level_btn.clicked.connect(self.delete_level_item)
        
        button_layout = UIUtils.create_button_layout(add_btn, add_same_level_btn, add_sub_level_btn, delete_level_btn)
        main_layout.addLayout(button_layout)
        
        # 创建树形表格
        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["课题名称/预算内容", "型号规格/简要内容", "单价（元）", "数量", "经费数额", "备注"])
        
        # 设置表格样式
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
        
        # 设置列宽
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setDefaultAlignment(Qt.AlignCenter)
        
        # 允许编辑单元格
        self.tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        
        self.tree.setColumnWidth(1, 120)
        self.tree.setColumnWidth(3, 120)
        
        # 连接单元格编辑完成信号
        self.tree.itemChanged.connect(self.on_item_changed)
        
        main_layout.addWidget(self.tree)
        
    def on_item_changed(self, item, column):
        """处理单元格编辑完成事件"""
        try:
            # 添加防抖定时器
            if not hasattr(self, '_save_timer'):
                self._save_timer = QTimer()
                self._save_timer.setSingleShot(True)
                self._save_timer.timeout.connect(self.delayed_save)
            
            # 停止之前的定时器并重新启动
            self._save_timer.stop()
            self._save_timer.start(500)  # 500毫秒防抖时间
            # 获取单价和数量
            unit_price = float(item.text(2)) if item.text(2) else 0.0
            quantity = int(item.text(3)) if item.text(3) else 0
            
            # 计算经费数额
            amount = unit_price * quantity
            item.setText(4, f"{amount:.2f}")
            
            # 更新父项的经费数额
            self.update_parent_amount(item)
        except ValueError:
            # 如果输入的不是有效的数字，恢复原值
            if column == 2:
                item.setText(2, "0.00")
            elif column == 3:
                item.setText(3, "0")
            
    def delayed_save(self):
        '''防抖后的保存方法'''
        root = self.tree.topLevelItem(0)
        if root:
            session = self.Session()
            try:
                project = session.query(BudgetEditProject).filter_by(name=root.text(0)).first()
                if project:
                    self.save_tree_structure(root, project.id)
                    session.commit()
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title="错误",
                    content=f"自动保存失败：{str(e)}",
                    parent=self
                )
            finally:
                session.close()
            
    def update_parent_amount(self, item):
        """更新父项的经费数额"""
        parent = item.parent()
        if parent:
            # 计算所有子项的经费数额之和
            total_amount = 0.0
            total_quantity = 0
            for i in range(parent.childCount()):
                child = parent.child(i)
                try:
                    amount = float(child.text(4)) if child.text(4) else 0.0
                    quantity = int(child.text(3)) if child.text(3) else 0
                    total_amount += amount
                    total_quantity += quantity
                except ValueError:
                    # 如果子项金额格式错误，跳过该子项
                    continue
            
            # 更新父项的经费数额，确保显示两位小数
            parent.setText(4, f"{round(total_amount, 2):.2f}")
            
            # 更新父项的数量
            parent.setText(3, str(total_quantity))
            
            # 如果总数量大于0，计算平均单价
            if total_quantity > 0:
                avg_unit_price = total_amount / total_quantity
                parent.setText(2, f"{round(avg_unit_price, 2):.2f}")
            else:
                parent.setText(2, "0.00")
            
            # 递归更新上级父项
            self.update_parent_amount(parent)
        
    def save_tree_structure(self, item, project_id, parent_id=None, session=None):
        """递归保存树形结构到数据库"""
        try:
            # 创建新的会话
            if session is None:
                session = self.Session()
                own_session = True
            else:
                own_session = False
            
            # 如果是根节点，先删除项目的所有预算项
            if not item.parent():
                session.query(BudgetEditItem).filter_by(project_id=project_id).delete()
                session.flush()
                item_id = None
            else:
                budget_item = BudgetEditItem(
                    project_id=project_id,
                    parent_id=parent_id,
                    name=item.text(0),
                    specification=item.text(1) if item.text(1) else None,
                    unit_price=float(item.text(2)) if item.text(2) else 0.0,
                    quantity=int(item.text(3)) if item.text(3) else 0,
                    amount=float(item.text(4)) if item.text(4) else 0.0,
                    remarks=item.text(5) if item.text(5) else None
                )
                
                # 设置类别和子类别
                parent_text = item.parent().text(0) if item.parent() else None
                if parent_text and parent_text in [cat.value for cat in BudgetEditCategory]:
                    budget_item.category = BudgetEditCategory(parent_text) if parent_text in [cat.value for cat in BudgetEditCategory] else None
                    item_text = item.text(0) if item.text(0) else None
                    budget_item.subcategory = BudgetEditSubCategory(item_text) if item_text and item_text in [subcat.value for subcat in BudgetEditSubCategory] else None
                    
                session.add(budget_item)
                session.flush()
                item_id = budget_item.id
            
            # 递归处理子节点
            for i in range(item.childCount()):
                self.save_tree_structure(item.child(i), project_id, item_id, session)
                
            if own_session:
                session.commit()
                
        except Exception as e:
            if own_session:
                session.rollback()
            raise e
        finally:
            if own_session:
                session.close()
            
    def init_tree(self, project_name):
        """初始化树形结构"""
        # 添加项目根节点
        root = QTreeWidgetItem(self.tree)
        root.setText(0, project_name)
        root.setExpanded(True)
        
        # 添加直接费和间接费
        for category in BudgetEditCategory:
            category_item = QTreeWidgetItem(root)
            category_item.setText(0, category.value)
            category_item.setExpanded(True)
            
            # 添加费用子类别
            for subcategory in BudgetEditSubCategory:
                # 根据父类别添加对应的子类别
                if category == BudgetEditCategory.DIRECT and subcategory in [
                    BudgetEditSubCategory.MATERIAL,
                    BudgetEditSubCategory.OUTSOURCING,
                    BudgetEditSubCategory.FUEL,
                    BudgetEditSubCategory.CONFERENCE,
                    BudgetEditSubCategory.PUBLICATION,
                    BudgetEditSubCategory.LABOR,
                    BudgetEditSubCategory.CONSULTING,
                    BudgetEditSubCategory.MISCELLANEOUS
                ]:
                    subcategory_item = QTreeWidgetItem(category_item)
                    subcategory_item.setText(0, subcategory.value)
                elif category == BudgetEditCategory.INDIRECT and subcategory in [
                    BudgetEditSubCategory.MANAGEMENT,
                    BudgetEditSubCategory.PERFORMANCE
                ]:
                    subcategory_item = QTreeWidgetItem(category_item)
                    subcategory_item.setText(0, subcategory.value)
    
    def add_budget_item(self):
        """添加预算条目"""
        from qfluentwidgets import LineEdit, Dialog
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("添加项目")
        dialog.setFixedSize(400, 150)
        dialog.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 8px;
            }
        """)
        
        # 创建垂直布局
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 创建输入框
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("项目名称:"))
        project_name = QLineEdit()
        project_name.setPlaceholderText("请输入项目名称")
        project_name.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #0078D4;
            }
        """)
        input_layout.addWidget(project_name)
        layout.addLayout(input_layout)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        
        # 设置按钮样式
        button_style = """
            QPushButton {
                padding: 8px 16px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 4px;
                background-color: #0078D4;
                color: white;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """
        ok_btn.setStyleSheet(button_style)
        cancel_btn.setStyleSheet(button_style.replace("#0078D4", "#FFFFFF").replace("color: white", "color: black"))
        
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        # 连接信号
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        # 显示对话框
        if dialog.exec() == QDialog.Accepted:
            name = project_name.text().strip()
            if name:
                # 保存项目到数据库
                session = self.Session()
                try:
                    project = BudgetEditProject(name=name)
                    session.add(project)
                    session.commit()
                    
                    # 清空现有树形结构
                    self.tree.clear()
                    # 初始化新的树形结构
                    self.init_tree(name)
                    
                    # 保存初始结构到数据库
                    root = self.tree.topLevelItem(0)
                    self.save_tree_structure(root, project.id)
                    session.commit()
                    
                except Exception as e:
                    session.rollback()
                    UIUtils.show_error(
                        title="错误",
                        content=f"保存项目失败：{str(e)}",
                        parent=self
                    )
                finally:
                    session.close()
            else:
                UIUtils.show_warning(
                    title="警告",
                    content="项目名称不能为空！",
                    parent=self
                )
    
    def add_same_level_item(self):
        """增加同级预算项"""
        selected_item = self.tree.currentItem()
        if not selected_item:
            UIUtils.show_warning(
                title="警告",
                content="请先选择一个预算项！",
                parent=self
            )
            return
            
        parent = selected_item.parent()
        if not parent:
            UIUtils.show_warning(
                title="警告",
                content="根节点不能添加同级项！",
                parent=self
            )
            return
            
        new_item = QTreeWidgetItem(parent)
        new_item.setText(0, "新预算项")
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
        
        # 保存到数据库
        session = self.Session()
        try:
            root = self.tree.topLevelItem(0)
            project = session.query(BudgetEditProject).filter_by(name=root.text(0)).first()
            if project:
                self.save_tree_structure(root, project.id)
                session.commit()
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title="错误",
                content=f"保存预算项失败：{str(e)}",
                parent=self
            )
        finally:
            session.close()
        
    def add_sub_level_item(self):
        """增加子级预算项"""
        selected_item = self.tree.currentItem()
        if not selected_item:
            UIUtils.show_warning(
                title="警告",
                content="请先选择一个预算项！",
                parent=self
            )
            return
            
        new_item = QTreeWidgetItem(selected_item)
        new_item.setText(0, "新子级预算项")
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
        selected_item.setExpanded(True)
        
        # 保存到数据库
        session = self.Session()
        try:
            root = self.tree.topLevelItem(0)
            project = session.query(BudgetEditProject).filter_by(name=root.text(0)).first()
            if project:
                self.save_tree_structure(root, project.id)
                session.commit()
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title="错误",
                content=f"保存预算项失败：{str(e)}",
                parent=self
            )
        finally:
            session.close()
        
    def delete_level_item(self):
        """删除当前级预算项"""
        selected_item = self.tree.currentItem()
        if not selected_item:
            UIUtils.show_warning(
                title="警告",
                content="请先选择要删除的预算项！",
                parent=self
            )
            return
            
        # 如果是根节点，显示确认对话框
        if not selected_item.parent():
            confirm_dialog = QDialog(self)
            confirm_dialog.setWindowTitle('确认删除')
            confirm_dialog.setFixedSize(400, 150)
            
            layout = QVBoxLayout(confirm_dialog)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)
            
            message_label = QLabel('确定要删除整个项目吗？此操作将删除所有预算项且不可恢复！')
            message_label.setWordWrap(True)
            layout.addWidget(message_label)
            
            button_layout = QHBoxLayout()
            button_layout.setSpacing(12)
            
            ok_btn = QPushButton('确定')
            cancel_btn = QPushButton('取消')
            
            button_style = """
                QPushButton {
                    padding: 8px 16px;
                    border: 1px solid rgba(0, 0, 0, 0.1);
                    border-radius: 4px;
                    background-color: #0078D4;
                    color: white;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #106EBE;
                }
                QPushButton:pressed {
                    background-color: #005A9E;
                }
            """
            ok_btn.setStyleSheet(button_style)
            cancel_btn.setStyleSheet(button_style.replace('#0078D4', '#FFFFFF').replace('color: white', 'color: black'))
            
            button_layout.addStretch()
            button_layout.addWidget(ok_btn)
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)
            
            ok_btn.clicked.connect(confirm_dialog.accept)
            cancel_btn.clicked.connect(confirm_dialog.reject)
            
            if not confirm_dialog.exec():
                return
            
        parent = selected_item.parent()
        if parent:
            parent.removeChild(selected_item)
        else:
            # 删除根节点
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(selected_item))
        
        # 更新数据库
        session = None
        try:
            session = self.Session()
            root = self.tree.topLevelItem(0)
            if root:
                # 如果还有根节点，更新数据库
                project = session.query(BudgetEditProject).filter_by(name=root.text(0)).with_for_update().first()
                if project:
                    # 删除所有现有条目
                    session.query(BudgetEditItem).filter_by(project_id=project.id).delete()
                    session.flush()
                    # 重新保存当前树结构
                    self.save_tree_structure(root, project.id, session=session)
                    session.commit()
            else:
                # 如果没有根节点了，清空数据库
                project = session.query(BudgetEditProject).filter_by(name=selected_item.text(0)).with_for_update().first()
                if project:
                    session.query(BudgetEditItem).filter_by(project_id=project.id).delete()
                    session.query(BudgetEditProject).filter_by(id=project.id).delete()
                    session.commit()
        except Exception as e:
            if session:
                session.rollback()
            UIUtils.show_error(
                title="错误",
                content=f"删除预算项失败：{str(e)}",
                parent=self
            )
        finally:
            if session:
                session.close()
