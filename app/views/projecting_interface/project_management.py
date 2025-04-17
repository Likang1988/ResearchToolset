from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtGui import QIcon
from qfluentwidgets import SegmentedWidget
from ...utils.ui_utils import UIUtils
from .project_progress import ProjectProgressWidget
from .project_document import ProjectDocumentWidget
from .project_achievement import ProjectAchievementWidget

class ProjectManagementWidget(QWidget):
    # Modify __init__ to accept engine
    def __init__(self, project, engine=None, parent=None):
        super().__init__(parent=parent)
        self.project = project
        self.engine = engine # Store the passed engine
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
            icon=QIcon(UIUtils.get_svg_icon_path('progress')),
            text='项目进度',
            onClick=lambda: self.stack_widget.setCurrentIndex(0)
        )
        self.nav_widget.addItem(
            routeKey='document',
            icon=QIcon(UIUtils.get_svg_icon_path('document')),
            text='项目文档',
            onClick=lambda: self.stack_widget.setCurrentIndex(1)
        )
        self.nav_widget.addItem(
            routeKey='achievement',
            icon=QIcon(UIUtils.get_svg_icon_path('achievement')),
            text='项目成果',
            onClick=lambda: self.stack_widget.setCurrentIndex(2)
        )
        self.main_layout.addWidget(self.nav_widget)
        
        # 创建堆叠窗口
        self.stack_widget = QStackedWidget(self)
        
        # 添加各个管理页面
        # 确保 ProjectProgressWidget 接收 engine
        self.progress_widget = ProjectProgressWidget(self.project, engine=self.engine)

        # 移除传递 engine 给其他 widget，除非它们确实需要
        self.document_widget = ProjectDocumentWidget(self.project)
        # 如果 ProjectDocumentWidget 之后需要 engine，则应修改其 __init__ 并在此处传递
        # self.document_widget.engine = self.engine # 或者在这里单独设置（如果它需要）

        self.achievement_widget = ProjectAchievementWidget(self.project)
        # 如果 ProjectAchievementWidget 之后需要 engine，则应修改其 __init__ 并在此处传递
        # self.achievement_widget.engine = self.engine # 或者在这里单独设置（如果它需要）
        
        self.stack_widget.addWidget(self.progress_widget)
        self.stack_widget.addWidget(self.document_widget)
        self.stack_widget.addWidget(self.achievement_widget)
        
        self.main_layout.addWidget(self.stack_widget)
