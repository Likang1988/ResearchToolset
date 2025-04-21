from PySide6.QtWidgets import QApplication, QStackedWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationInterface, FluentWindow, FluentIcon, NavigationItemPosition
from qframelesswindow import FramelessWindow, StandardTitleBar
from ..utils.ui_utils import UIUtils
from .projecting_interface.project_list import ProjectListWindow
from .projecting_interface.project_budget import ProjectBudgetWidget
from .projecting_interface.project_progress import ProjectProgressWidget
from .projecting_interface.project_document import ProjectDocumentWidget # Import Document Widget
from .projecting_interface.project_outcome import ProjectOutcomeWidget # Import Outcome Widget
from .home_interface import HomeInterface
from .help_interface import HelpInterface
from .budgeting_interface import BudgetingInterface
from .tools_interface import ToolsInterface
import os

class MainWindow(FluentWindow):
    # 定义信号
    project_updated = Signal()
    activity_updated = Signal()
    budget_or_expense_updated = Signal() # 新增信号，用于预算或支出更新
    
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self.project_budget_interface = None
        
        # 设置窗口标题和大小
        self.setWindowTitle("科研工具集")
        self.setWindowIcon(QIcon(':/assets/icon.ico'))
        self.resize(1200, 800)
        #self.setMinimumSize(1200, 800)

        # 启用 Mica 特效 (解决 WebEngineView 导致背景失效的问题)
        self.setMicaEffectEnabled(False)

        # 添加主页导航项
        self.home_interface = HomeInterface(self.engine)
        self.home_interface.setObjectName("homeInterface")        
        self.addSubInterface(
            self.home_interface,
            FluentIcon.HOME,
            "主页"
        )

        # 添加项目清单导航项
        self.projecting_interface = ProjectListWindow(self.engine)
        self.projecting_interface.setObjectName("projectingInterface")
        self.addSubInterface(  
            self.projecting_interface,
            QIcon(UIUtils.get_svg_icon_path('projecting_tab')),
            "项目清单"
        )
        # 连接 ProjectListWindow 的信号到 MainWindow 的信号
        self.projecting_interface.project_list_updated.connect(self.project_updated)

        # 添加项目进度导航项
        self.progress_interface = ProjectProgressWidget(self.engine) 
        self.progress_interface.setObjectName("progressInterface")
        self.addSubInterface(
            self.progress_interface,
            QIcon(UIUtils.get_svg_icon_path('progress')), 
            "项目进度"
        )      
                                                              
        # 添加项目经费导航项
        self.project_budget_interface = ProjectBudgetWidget(self.engine) 
        self.project_budget_interface.setObjectName("projectBudgetInterface")
        self.addSubInterface(
            self.project_budget_interface,
            QIcon(UIUtils.get_svg_icon_path('budgeting_tab')), 
            "项目经费"
        )
        # 连接 ProjectBudgetWidget 的信号到 MainWindow 的新信号
        self.project_budget_interface.budget_updated.connect(self.budget_or_expense_updated)
        
        # 添加项目文档导航项
        self.document_interface = ProjectDocumentWidget(self.engine) 
        self.document_interface.setObjectName("documentInterface")
        self.addSubInterface(
            self.document_interface,
            QIcon(UIUtils.get_svg_icon_path('document')), 
            "项目文档"
        )

        # 添加项目成果导航项
        self.achievement_interface = ProjectOutcomeWidget(self.engine) 
        self.achievement_interface.setObjectName("outcomeInterface")
        self.addSubInterface(
            self.achievement_interface,
            QIcon(UIUtils.get_svg_icon_path('outcome')), 
            "项目成果"
        )
        
        # 添加预算编制导航项
        self.budget_edit_interface = BudgetingInterface(self.engine)
        self.budget_edit_interface.setObjectName("budgetingInterface")
        self.addSubInterface(
            self.budget_edit_interface,
            QIcon(UIUtils.get_svg_icon_path('budgeting_interface')),
            "预算编制"
        )

        # 添加小工具导航项
        self.tools_interface = ToolsInterface()
        self.tools_interface.setObjectName("toolsInterface")
        self.addSubInterface(
            self.tools_interface,
            FluentIcon.DEVELOPER_TOOLS,
            "小工具"
        )

        # 添加帮助导航项
        self.help_interface = HelpInterface()
        self.help_interface.setObjectName("helpInterface")
        self.addSubInterface(
            self.help_interface,
            FluentIcon.HELP,
            "帮助",
            position=NavigationItemPosition.BOTTOM
        )
                
        # 设置当前页面
        self.navigationInterface.setCurrentItem("主页")
        self.navigationInterface.setExpandWidth(150)
        #self.setMicaEffectEnabled(True)
        FluentWindow.updateFrameless(self)
        


