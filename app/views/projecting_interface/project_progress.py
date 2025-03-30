from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QDateEdit, QTextEdit, QSpinBox, QLabel
from PySide6.QtCore import Qt, QDate
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon, InfoBar, Dialog, LineEdit
from ...utils.ui_utils import UIUtils
from ...models.database import Project, Base, get_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum
from enum import Enum

class TaskStatus(Enum):
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完成"
    DELAYED = "已延期"

class ProjectTask(Base):
    __tablename__ = 'project_tasks'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(100), nullable=False)  # 任务名称
    description = Column(String(500))  # 任务描述
    start_date = Column(Date)  # 开始日期
    end_date = Column(Date)  # 结束日期
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.NOT_STARTED)  # 任务状态
    assignee = Column(String(50))  # 负责人
    progress = Column(Integer, default=0)  # 进度百分比

class TaskDialog(Dialog):
    def __init__(self, parent=None, task=None):
        super().__init__("任务信息", "", parent)
        self.task = task
        self.setup_ui()
        if task:
            self.load_task_data()
    
    def setup_ui(self):
        self.setWindowTitle("任务信息")
        # 使用父类的布局而不是创建新的
        layout = self.layout()
        
        # 任务表单
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("任务名称")
        layout.addWidget(self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("任务描述")
        layout.addWidget(self.description_edit)
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        layout.addWidget(self.start_date)
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        layout.addWidget(self.end_date)
        
        self.status_combo = QComboBox()
        for status in TaskStatus:
            self.status_combo.addItem(status.value)
        layout.addWidget(self.status_combo)
        
        self.assignee_edit = LineEdit()
        self.assignee_edit.setPlaceholderText("负责人")
        layout.addWidget(self.assignee_edit)
        
        self.progress_spin = QSpinBox()
        self.progress_spin.setRange(0, 100)
        self.progress_spin.setSuffix("%")
        layout.addWidget(self.progress_spin)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_btn = PrimaryPushButton("保存")
        cancel_btn = PrimaryPushButton("取消")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    
    def load_task_data(self):
        self.name_edit.setText(self.task.name)
        self.description_edit.setText(self.task.description)
        self.start_date.setDate(self.task.start_date)
        self.end_date.setDate(self.task.end_date)
        self.status_combo.setCurrentText(self.task.status.value)
        self.assignee_edit.setText(self.task.assignee)
        self.progress_spin.setValue(self.task.progress)

class ProjectProgressWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent=parent)
        self.project = project
        self.setup_ui()
        self.load_tasks()
    
    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        # 标题栏
        title_layout = UIUtils.create_title_layout("项目进度管理")
        self.main_layout.addLayout(title_layout)
        
        # 项目选择
        self.project_combo = QComboBox()
        self.load_projects()
        self.main_layout.addWidget(self.project_combo)
        
        # 按钮栏
        add_btn = UIUtils.create_action_button("新建任务", FluentIcon.ADD)
        edit_btn = UIUtils.create_action_button("编辑任务", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除任务", FluentIcon.DELETE)
        
        add_btn.clicked.connect(self.add_task)
        edit_btn.clicked.connect(self.edit_task)
        delete_btn.clicked.connect(self.delete_task)
        
        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        self.main_layout.addLayout(button_layout)
        
        # 任务列表
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(7)
        self.task_table.setHorizontalHeaderLabels(["任务名称", "描述", "开始日期", "结束日期", "状态", "负责人", "进度"])
        UIUtils.set_table_style(self.task_table)
        
        self.main_layout.addWidget(self.task_table)
    
    def load_projects(self):
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            projects = session.query(Project).all()
            self.project_combo.clear()
            for project in projects:
                self.project_combo.addItem(project.name, project.id)
        finally:
            session.close()
    
    def load_tasks(self):
        if self.project_combo.currentData() is None:
            return
            
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            tasks = session.query(ProjectTask).filter(
                ProjectTask.project_id == self.project_combo.currentData()
            ).all()
            
            self.task_table.setRowCount(len(tasks))
            for row, task in enumerate(tasks):
                self.task_table.setItem(row, 0, QTableWidgetItem(task.name))
                self.task_table.setItem(row, 1, QTableWidgetItem(task.description))
                self.task_table.setItem(row, 2, QTableWidgetItem(str(task.start_date)))
                self.task_table.setItem(row, 3, QTableWidgetItem(str(task.end_date)))
                self.task_table.setItem(row, 4, QTableWidgetItem(task.status.value))
                self.task_table.setItem(row, 5, QTableWidgetItem(task.assignee))
                self.task_table.setItem(row, 6, QTableWidgetItem(f"{task.progress}%"))
        finally:
            session.close()
    
    def add_task(self):
        if self.project_combo.currentData() is None:
            UIUtils.show_warning(self, "警告", "请先选择项目")
            return
            
        dialog = TaskDialog(self)
        if dialog.exec():
            Session = sessionmaker(bind=get_engine())
            session = Session()
            
            try:
                task = ProjectTask(
                    project_id=self.project_combo.currentData(),
                    name=dialog.name_edit.text(),
                    description=dialog.description_edit.toPlainText(),
                    start_date=dialog.start_date.date().toPython(),
                    end_date=dialog.end_date.date().toPython(),
                    status=TaskStatus(dialog.status_combo.currentText()),
                    assignee=dialog.assignee_edit.text(),
                    progress=dialog.progress_spin.value()
                )
                session.add(task)
                session.commit()
                self.load_tasks()
                UIUtils.show_success(self, "成功", "任务创建成功")
            finally:
                session.close()
    
    def edit_task(self):
        selected_items = self.task_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要编辑的任务")
            return
        
        row = selected_items[0].row()
        task_name = self.task_table.item(row, 0).text()
        
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            task = session.query(ProjectTask).filter(
                ProjectTask.project_id == self.project_combo.currentData(),
                ProjectTask.name == task_name
            ).first()
            
            if task:
                dialog = TaskDialog(self, task)
                if dialog.exec():
                    task.name = dialog.name_edit.text()
                    task.description = dialog.description_edit.toPlainText()
                    task.start_date = dialog.start_date.date().toPython()
                    task.end_date = dialog.end_date.date().toPython()
                    task.status = TaskStatus(dialog.status_combo.currentText())
                    task.assignee = dialog.assignee_edit.text()
                    task.progress = dialog.progress_spin.value()
                    
                    session.commit()
                    self.load_tasks()
                    UIUtils.show_success(self, "成功", "任务更新成功")
        finally:
            session.close()
    
    def delete_task(self):
        selected_items = self.task_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要删除的任务")
            return
        
        row = selected_items[0].row()
        task_name = self.task_table.item(row, 0).text()
        
        Session = sessionmaker(bind=get_engine())
        session = Session()
        
        try:
            task = session.query(ProjectTask).filter(
                ProjectTask.project_id == self.project_combo.currentData(),
                ProjectTask.name == task_name
            ).first()
            
            if task:
                session.delete(task)
                session.commit()
                self.load_tasks()
                UIUtils.show_success(self, "成功", "任务删除成功")
        finally:
            session.close()