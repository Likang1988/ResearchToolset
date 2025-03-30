from PySide6.QtWidgets import QWidget, QTableWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem, QPushButton
from PySide6.QtCore import Qt
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon, InfoBar, ToolButton
from ...utils.ui_utils import UIUtils
from ...components.project_dialog import ProjectDialog
from ...models.database import Project, Activity
from sqlalchemy import desc
from .project_management import ProjectManagementWidget

class ProjectListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setup_ui()
        self.load_projects()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        # 标题栏
        title_layout = UIUtils.create_title_layout("项目管理")
        self.main_layout.addLayout(title_layout)
        
        # 按钮栏
        add_btn = UIUtils.create_action_button("新建项目", FluentIcon.ADD)
        edit_btn = UIUtils.create_action_button("编辑项目", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除项目", FluentIcon.DELETE)
        
        add_btn.clicked.connect(self.add_project)
        edit_btn.clicked.connect(self.edit_project)
        delete_btn.clicked.connect(self.delete_project)
        
        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        self.main_layout.addLayout(button_layout)
        
        # 项目列表
        self.project_table = QTableWidget()
        self.project_table.setColumnCount(9)  # 增加一列用于项目管理
        self.project_table.setHorizontalHeaderLabels(["项目名称", "项目编号", "财务编号", "项目类型", "负责人", "开始日期", "结束日期", "总预算", "项目管理"])
        UIUtils.set_table_style(self.project_table)
        
        self.main_layout.addWidget(self.project_table)
    
    def load_projects(self):
        from ...models.database import Base, get_engine
        from sqlalchemy.orm import sessionmaker
        
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            projects = session.query(Project).order_by(desc(Project.id)).all()
            self.project_table.setRowCount(len(projects))
            
            for row, project in enumerate(projects):
                self.project_table.setItem(row, 0, QTableWidgetItem(project.name))
                self.project_table.setItem(row, 1, QTableWidgetItem(project.project_code or ""))
                self.project_table.setItem(row, 2, QTableWidgetItem(project.financial_code or ""))
                self.project_table.setItem(row, 3, QTableWidgetItem(project.project_type or ""))
                self.project_table.setItem(row, 4, QTableWidgetItem(project.leader or ""))
                self.project_table.setItem(row, 5, QTableWidgetItem(str(project.start_date) if project.start_date else ""))
                self.project_table.setItem(row, 6, QTableWidgetItem(str(project.end_date) if project.end_date else ""))
                self.project_table.setItem(row, 7, QTableWidgetItem(f"{project.total_budget:.2f}" if project.total_budget else "0.00"))
                
                # 添加项目管理按钮
                manage_btn = ToolButton(FluentIcon.SETTING)
                manage_btn.setToolTip("项目管理")
                manage_btn.clicked.connect(lambda checked, p=project: self.open_project_management(p))
                self.project_table.setCellWidget(row, 8, manage_btn)
        
        finally:
            session.close()
    
    def open_project_management(self, project):
        # 获取主窗口实例
        main_window = self.window()
        if main_window:
            # 创建项目管理界面
            management_widget = ProjectManagementWidget(project)
            management_widget.setObjectName("projectManagementInterface")
            management_widget.engine = self.engine
            # 添加到主窗口的导航栏
            main_window.addSubInterface(
                management_widget,
                FluentIcon.SETTING,
                f"项目管理 - {project.name}"
            )
            # 切换到项目管理界面
            main_window.navigationInterface.setCurrentItem(f"项目管理 - {project.name}")
    
    def add_project(self):
        dialog = ProjectDialog(self)
        if dialog.exec():
            self.load_projects()
            UIUtils.show_success(self, "成功", "项目创建成功")
    
    def edit_project(self):
        selected_items = self.project_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要编辑的项目")
            return
        
        row = selected_items[0].row()
        project_name = self.project_table.item(row, 0).text()
        
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            project = session.query(Project).filter(Project.name == project_name).first()
            if project:
                dialog = ProjectDialog(self, project)
                if dialog.exec():
                    self.load_projects()
                    UIUtils.show_success(self, "成功", "项目更新成功")
        finally:
            session.close()
    
    def delete_project(self):
        selected_items = self.project_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要删除的项目")
            return
        
        row = selected_items[0].row()
        project_name = self.project_table.item(row, 0).text()
        
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            project = session.query(Project).filter(Project.name == project_name).first()
            if project:
                session.delete(project)
                session.commit()
                self.load_projects()
                UIUtils.show_success(self, "成功", "项目删除成功")
        finally:
            session.close()