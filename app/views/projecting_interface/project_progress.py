from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QDateEdit, QTextEdit, QSpinBox, QLabel
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
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
        add_child_btn = UIUtils.create_action_button("添加子级", FluentIcon.ADD_TO)
        delete_btn = UIUtils.create_action_button("删除任务", FluentIcon.DELETE)
        
        add_btn.clicked.connect(self.add_task)
        add_child_btn.clicked.connect(self.add_child_task)
        delete_btn.clicked.connect(self.delete_task)
        
        button_layout = UIUtils.create_button_layout(add_btn, add_child_btn, delete_btn)
        self.main_layout.addLayout(button_layout)
        
        # 任务树形列表
        self.task_tree = QTreeWidget()
        self.task_tree.setColumnCount(7)
        self.task_tree.setHeaderLabels(["任务名称", "描述", "开始日期", "结束日期", "状态", "负责人", "进度"])
        UIUtils.set_tree_style(self.task_tree)
        
        self.main_layout.addWidget(self.task_tree)
    
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
            
            self.task_tree.clear()
            for task in tasks:
                item = QTreeWidgetItem()
                item.setText(0, task.name)
                item.setText(1, task.description)
                item.setText(2, str(task.start_date))
                item.setText(3, str(task.end_date))
                item.setText(4, task.status.value)
                item.setText(5, task.assignee)
                item.setText(6, f"{task.progress}%")
                self.task_tree.addTopLevelItem(item)
        finally:
            session.close()
    
    def add_task(self):
        if self.project_combo.currentData() is None:
            UIUtils.show_warning(self, "警告", "请先选择项目")
            return
            
        # 添加新行
        item = QTreeWidgetItem()
        item.setText(0, "新任务")
        item.setText(1, "")
        item.setText(2, QDate.currentDate().toString(Qt.ISODate))
        item.setText(3, QDate.currentDate().toString(Qt.ISODate))
        item.setText(4, TaskStatus.NOT_STARTED.value)
        item.setText(5, "")
        item.setText(6, "0%")
        
        # 设置可编辑
        for i in range(7):
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            
        self.task_tree.addTopLevelItem(item)
        self.task_tree.editItem(item, 0)
    
    def add_child_task(self):
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择父级任务")
            return
            
        # 添加子级任务
        parent_item = selected_items[0]
        child_item = QTreeWidgetItem(parent_item)
        child_item.setText(0, "子任务")
        child_item.setText(1, "")
        child_item.setText(2, QDate.currentDate().toString(Qt.ISODate))
        child_item.setText(3, QDate.currentDate().toString(Qt.ISODate))
        child_item.setText(4, TaskStatus.NOT_STARTED.value)
        child_item.setText(5, "")
        child_item.setText(6, "0%")
        
        # 设置可编辑
        for i in range(7):
            child_item.setFlags(child_item.flags() | Qt.ItemIsEditable)
            
        self.task_tree.expandItem(parent_item)
        self.task_tree.editItem(child_item, 0)
    
    def delete_task(self):
        selected_items = self.task_tree.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要删除的任务")
            return
        
        task_name = selected_items[0].text(0)
        
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