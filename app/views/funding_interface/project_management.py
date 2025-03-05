from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QLabel, QTableWidgetItem, QStackedWidget)
from qfluentwidgets import PrimaryPushButton, ToolButton, InfoBar, Dialog
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, TableWidget, TableItemDelegate, TitleLabel
from ...components.project_dialog import ProjectDialog
from .budget_management import BudgetManagementWindow
from ...models.funding_db import init_db, add_project_to_db, sessionmaker, Project, Budget
from ...utils.ui_utils import UIUtils
from ...utils.db_utils import DBUtils
from sqlalchemy import func
import os

class ProjectManagementWindow(QWidget):
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        
        
        self.project = None
        self.setWindowTitle("经费追踪")
        self.setup_ui()

    
    def setup_ui(self):
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 创建QStackedWidget
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # 创建项目管理页面
        self.project_page = QWidget()
        self.setup_project_page()
        self.stacked_widget.addWidget(self.project_page)
        
        # 初始显示项目管理页面
        self.stacked_widget.setCurrentWidget(self.project_page)

            # 添加作者信息
        author_label = QLabel("© Likang")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(author_label)

    def setup_project_page(self):
        layout = QVBoxLayout(self.project_page)
        layout.setContentsMargins(15, 15, 15, 15)  # 统一设置边距为15像素
        layout.setSpacing(10)  # 设置组件之间的垂直间距为10像素
        
        # 标题
        title_layout = UIUtils.create_title_layout("项目管理")
        layout.addLayout(title_layout)
        
        # 按钮栏
        add_btn = UIUtils.create_action_button("添加项目", FluentIcon.ADD_TO)
        edit_btn = UIUtils.create_action_button("编辑项目", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除项目", FluentIcon.DELETE)
        
        add_btn.clicked.connect(self.add_project)
        edit_btn.clicked.connect(self.edit_project)
        delete_btn.clicked.connect(self.delete_selected_project)
        
        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        layout.addLayout(button_layout)
        
        # 项目表格
        self.project_table = TableWidget()
        self.project_table.setColumnCount(9)  # 增加一列
        self.project_table.setHorizontalHeaderLabels([
            "财务编号", "项目名称", "项目编号", 
            "项目类别", "开始日期", "结束日期", "总经费\n（万元）", "执行率", "操作"
        ])
        self.project_table.setSelectionBehavior(TableWidget.SelectRows)
        self.project_table.setSelectionMode(TableWidget.SingleSelection)
        self.project_table.setBorderVisible(True)
        self.project_table.setBorderRadius(8)
        self.project_table.setWordWrap(False)
        self.project_table.setItemDelegate(TableItemDelegate(self.project_table))
        layout.addWidget(self.project_table)
        self.refresh_project_table()
    def refresh_project_table(self):
        # 清空现有表格
        self.project_table.setRowCount(0)
        
        # 从数据库获取项目数据
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            # 按ID升序排序，使新添加的项目显示在最下方
            projects = session.query(Project).order_by(Project.id.asc()).all()
            
            # 填充表格数据
            for idx, project in enumerate(projects, 1):
                row_position = self.project_table.rowCount()
                self.project_table.insertRow(row_position)
                
                # 添加项目信息
                item = QTableWidgetItem(project.financial_code)
                item.setData(Qt.UserRole, project.id)  # 存储项目ID
                self.project_table.setItem(row_position, 0, item)
                self.project_table.setItem(row_position, 1, QTableWidgetItem(project.name))            
                self.project_table.setItem(row_position, 2, QTableWidgetItem(project.project_code))
                self.project_table.setItem(row_position, 3, QTableWidgetItem(project.project_type))
                self.project_table.setItem(row_position, 4, QTableWidgetItem(str(project.start_date)))
                self.project_table.setItem(row_position, 5, QTableWidgetItem(str(project.end_date)))
                self.project_table.setItem(row_position, 6, QTableWidgetItem(str(project.total_budget)))
                
                # 获取总预算执行率
                total_budget = session.query(Budget).filter(
                    Budget.project_id == project.id,
                    Budget.year.is_(None)
                ).first()
                
                if total_budget and total_budget.total_amount > 0:
                    # 计算所有年度预算的总支出
                    total_spent = session.query(func.sum(Budget.spent_amount)).filter(
                        Budget.project_id == project.id,
                        Budget.year.isnot(None)  # 只计算年度预算
                    ).scalar() or 0.0
                    
                    execution_rate = (total_spent / total_budget.total_amount) * 100
                    self.project_table.setItem(row_position, 7, QTableWidgetItem(f"{execution_rate:.2f}%"))
                else:
                    self.project_table.setItem(row_position, 7, QTableWidgetItem("0.00%"))
                
                
                # 预算管理按钮
                btn_widget = QWidget()  # 创建一个新的QWidget
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setAlignment(Qt.AlignCenter)  # 设置按钮居中对齐
                
                budget_btn = ToolButton()
                budget_btn.setIcon(QIcon(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'logo', 'budget.svg'))))
                budget_btn.setToolTip("预算管理")
                budget_btn.clicked.connect(lambda checked=False, p=project: self.open_budget_management(p))  # 传递项目对象
                btn_layout.addWidget(budget_btn)  # 将按钮添加到布局中
                # 按钮大小
                budget_btn.setFixedSize(28, 28)
                # 图标大小
                budget_btn.setIconSize(QSize(20, 20))

                self.project_table.setCellWidget(row_position, 8, btn_widget)  # 将按钮放置在第9列（操作列）
            
            session.close()
            
            # 调整列宽
            self.project_table.resizeColumnsToContents() # 调整列宽
            self.project_table.setColumnWidth(0, 80)  # 财务编号列宽
            self.project_table.setColumnWidth(1, 330)  # 项目名称列宽
            self.project_table.setColumnWidth(2, 130)  # 项目编号列宽
            self.project_table.setColumnWidth(3, 130)  # 项目类别列宽
            self.project_table.setColumnWidth(4, 90)  # 开始日期列宽
            self.project_table.setColumnWidth(5, 90)  # 结束日期列宽
            self.project_table.setColumnWidth(6, 70)  # 总经费列宽
            self.project_table.setColumnWidth(7, 70)  # 执行率列宽
            self.project_table.setColumnWidth(8, 90)  # 操作列宽

            # 禁止直接编辑
            self.project_table.setEditTriggers(TableWidget.NoEditTriggers)

            # 设置表格对齐方式
            for row_position in range(self.project_table.rowCount()):
                for col in range(self.project_table.columnCount()):
                    item = self.project_table.item(row_position, col)
                    if item:
                        # 第0、2、3、4、5列设置为居中对齐
                        if col in [0, 2, 3, 4, 5]:
                            item.setTextAlignment(Qt.AlignCenter)
                        # 第6列(总经费)设置为右对齐
                        elif col in [6, 7]:
                            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        # 其他列保持默认左对齐
                        else:
                            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            # 设置表格样式
            UIUtils.set_table_style(self.project_table)

        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'刷新项目列表失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
    def add_project(self):
        """添加项目"""
        dialog = ProjectDialog(self)
        if dialog.exec() == ProjectDialog.Accepted:
            # 获取项目信息
            financial_code = dialog.financial_code.text().strip()
            name = dialog.project_name.text().strip()
            project_code = dialog.project_code.text().strip()
            project_type = dialog.project_type.currentText()
            start_date = dialog.start_date.date().toPython()
            end_date = dialog.end_date.date().toPython()
            total_budget = dialog.total_budget.text().strip()
            
            # 添加项目到数据库
            try:
                Session = sessionmaker(bind=self.engine)
                session = Session()
                
                # 创建新项目
                project = Project(
                    name=name,
                    financial_code=financial_code,
                    project_code=project_code,
                    project_type=project_type,
                    start_date=start_date,
                    end_date=end_date,
                    total_budget=float(total_budget) if total_budget else 0.0
                )
                session.add(project)
                session.flush()  # 获取项目ID
                
                # 保存项目ID供后续使用
                self.project_id = project.id
                
                # 提交事务
                session.commit()
                
                # 刷新项目列表
                self.refresh_project_table()
                
                # 显示成功消息
                UIUtils.show_success(self,
                    title='成功',
                    content='项目添加成功',
                    parent=self
                )
                
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title='错误',
                    content=f'添加项目失败：{str(e)}',
                    parent=self
                )
            finally:
                session.close()
    def edit_project(self):
        selected_rows = self.project_table.selectedItems()
        if not selected_rows:
            UIUtils.show_warning(
                title='警告',
                content='请选择要编辑的项目！',
                parent=self
            )
            return
            
        row = selected_rows[0].row()
        project_id = self.project_table.item(row, 0).data(Qt.UserRole)
        
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            project = session.query(Project).filter(Project.id == project_id).first()
            
            if project:
                dialog = ProjectDialog(self)
                dialog.financial_code.setText(project.financial_code)
                dialog.project_name.setText(project.name)
                dialog.project_code.setText(project.project_code)
                dialog.project_type.setCurrentText(project.project_type)
                dialog.start_date.setDate(project.start_date)
                dialog.end_date.setDate(project.end_date)
                dialog.total_budget.setText(str(project.total_budget))
                
                if dialog.exec() == ProjectDialog.Accepted:
                    project.financial_code = dialog.financial_code.text().strip()
                    project.name = dialog.project_name.text().strip()
                    project.project_code = dialog.project_code.text().strip()
                    project.project_type = dialog.project_type.currentText()
                    project.start_date = dialog.start_date.date().toPython()
                    project.end_date = dialog.end_date.date().toPython()
                    project.total_budget = float(dialog.total_budget.text()) if dialog.total_budget.text() else 0.0
                    
                    session.commit()
                    self.refresh_project_table()
            else:
                UIUtils.show_warning(
                    title='警告',
                    content='未找到选中的项目！',
                    parent=self
                )
                
        except Exception as e:
            session.rollback()
            UIUtils.show_error(
                title='错误',
                content=f'编辑项目失败：{str(e)}',
                parent=self
            )
        finally:
            session.close()
            
    def delete_selected_project(self):
        selected_rows = self.project_table.selectedItems()
        if not selected_rows:
            UIUtils.show_warning(
                title='警告',
                content='请选择要删除的项目！',
                parent=self
            )
            return
            
        row = selected_rows[0].row()
        project_id = self.project_table.item(row, 0).data(Qt.UserRole)
        
        # 使用InfoBar显示确认对话框
        confirm_dialog = Dialog(
            '确认删除',
            '确定要删除该项目吗？此操作不可恢复！',
            self
        )
        
        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            try:
                session.query(Project).filter(Project.id == project_id).delete()
                session.commit()
                self.refresh_project_table()
                UIUtils.show_success(self,
                    title='成功',
                    content='项目已成功删除',
                    parent=self
                )
            except Exception as e:
                session.rollback()
                UIUtils.show_error(
                    title='错误',
                    content=f'删除项目失败：{str(e)}',
                    parent=self
                )
            finally:
                session.close()
        
    def open_budget_management(self, project):
        """打开经费管理窗口"""
        self.project = project
        budget_window = BudgetManagementWindow(self.engine, project)
        
        # 如果已存在预算管理窗口，先移除它
        if hasattr(self, 'budget_window'):
            self.stacked_widget.removeWidget(self.budget_window)
            self.budget_window.deleteLater()
        
        # 保存新的预算管理窗口实例
        self.budget_window = budget_window
        self.stacked_widget.addWidget(budget_window)
        
        # 切换到经费管理页面
        self.stacked_widget.setCurrentWidget(self.budget_window)
    def add_budget(self, budget_data):
        """添加项目预算"""
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            # 创建新的预算记录
            budget = Budget(
                project_id=budget_data['project_id'],
                year=budget_data['year'],
                total_amount=budget_data['total_amount'],
                remark=budget_data.get('remark', '')
            )
            
            session.add(budget)
            session.commit()
            
            # 如果预算管理窗口已打开，则刷新数据
            if hasattr(self, 'budget_window'):
                self.budget_window.refresh_budget_table()
                
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.c
