from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from qfluentwidgets import SegmentedWidget, FluentIcon
from ...utils.ui_utils import UIUtils
from .project_progress import ProjectProgressWidget
from .project_document import ProjectDocumentWidget
from .project_achievement import ProjectAchievementWidget

class ProjectManagementWidget(QWidget):
    def __init__(self, project, parent=None):
        super().__init__(parent=parent)
        self.project = project
        self.engine = None
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        # 标题栏
        title_layout = UIUtils.create_title_layout(f"项目管理 - {self.project.name}")
        self.main_layout.addLayout(title_layout)
        
        # 创建分段导航栏
        self.nav_widget = SegmentedWidget(self)
        self.nav_widget.addItem(
            routeKey='progress',
            icon=FluentIcon.GAME,
            text='项目进度',
            onClick=lambda: self.stack_widget.setCurrentIndex(0)
        )
        self.nav_widget.addItem(
            routeKey='document',
            icon=FluentIcon.DOCUMENT,
            text='项目文档',
            onClick=lambda: self.stack_widget.setCurrentIndex(1)
        )
        self.nav_widget.addItem(
            routeKey='achievement',
            icon=FluentIcon.GAME,
            text='项目成果',
            onClick=lambda: self.stack_widget.setCurrentIndex(2)
        )
        self.main_layout.addWidget(self.nav_widget)
        
        # 创建堆叠窗口
        self.stack_widget = QStackedWidget(self)
        
        # 添加各个管理页面
        self.progress_widget = ProjectProgressWidget(self.project)
        self.progress_widget.engine = self.engine
        self.document_widget = ProjectDocumentWidget(self.project)
        self.document_widget.engine = self.engine
        self.achievement_widget = ProjectAchievementWidget(self.project)
        self.achievement_widget.engine = self.engine
        
        self.stack_widget.addWidget(self.progress_widget)
        self.stack_widget.addWidget(self.document_widget)
        self.stack_widget.addWidget(self.achievement_widget)
        
        self.main_layout.addWidget(self.stack_widget)