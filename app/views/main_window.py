from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentWindow, FluentIcon, NavigationItemPosition
from ..utils.ui_utils import UIUtils
from .projecting_interface.project_list import ProjectListWindow
from .projecting_interface.project_fund import ProjectBudgetWidget
from .projecting_interface.project_progress import ProjectProgressWidget
from .projecting_interface.project_document import ProjectDocumentWidget # Import Document Widget
from .projecting_interface.project_outcome import ProjectOutcomeWidget # Import Outcome Widget
from .home_interface import HomeInterface
from .help_interface import HelpInterface
from .budgeting_interface import BudgetingInterface
from .tools_interface import ToolsInterface
from .activity_interface import ActivityInterface # Import Activity Interface
import os
import sys # Import sys for path joining robustness if needed, though os should suffice

class MainWindow(FluentWindow):
    # 定义信号
    project_updated = Signal()
    activity_updated = Signal()
    budget_or_expense_updated = Signal() # 新增信号，用于预算或支出更新
    
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self.project_fund_interface = None
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.abspath(os.path.join(current_dir, '..', 'assets', 'icon.ico'))

        # 设置窗口标题和大小
        self.setWindowTitle("科研工具集")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path)) # Use the absolute file path
            # print(f"Icon set from: {icon_path}") # Removed print
        else:
            print(f"警告: 图标文件未找到于 {icon_path}") # Add a warning if not found
        self.resize(1200, 800)

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
            QIcon(UIUtils.my_svgicon('projecting_tab')),
            "项目清单"
        )
        self.projecting_interface.project_list_updated.connect(self.project_updated)

        # 添加项目经费导航项
        self.project_fund_interface = ProjectBudgetWidget(self.engine) 
        self.project_fund_interface.setObjectName("projectBudgetInterface")
        self.addSubInterface(
            self.project_fund_interface,
            QIcon(UIUtils.my_svgicon('budgeting_tab')), 
            "项目经费"
        )
        self.project_fund_interface.budget_updated.connect(self.budget_or_expense_updated)
        
        # 添加项目进度导航项
        self.progress_interface = ProjectProgressWidget(self.engine) 
        self.progress_interface.setObjectName("progressInterface")
        self.addSubInterface(
            self.progress_interface,
            QIcon(UIUtils.my_svgicon('progress')), 
            "项目进度"
        )
        # 连接 progress_updated 信号到 HomeInterface 的 refresh_data 槽
        self.progress_interface.progress_updated.connect(self.home_interface.refresh_data)
        
        # 添加项目文档导航项
        self.document_interface = ProjectDocumentWidget(self.engine)
        self.document_interface.setObjectName("documentInterface")
        self.addSubInterface(
            self.document_interface,
            QIcon(UIUtils.my_svgicon('document')), 
            "项目文档"
        )

        # 添加项目成果导航项
        self.achievement_interface = ProjectOutcomeWidget(self.engine) 
        self.achievement_interface.setObjectName("outcomeInterface")
        self.addSubInterface(
            self.achievement_interface,
            QIcon(UIUtils.my_svgicon('outcome')), 
            "项目成果"
        )

        # 添加学术活动导航项
        self.activity_interface = ActivityInterface(self.engine)
        self.activity_interface.setObjectName("activityInterface")
        self.addSubInterface(
            self.activity_interface,
            QIcon(UIUtils.my_svgicon('activity')),
            "学术活动"
        )
        
        # 添加预算编制导航项
        self.budget_edit_interface = BudgetingInterface(self.engine)
        self.budget_edit_interface.setObjectName("budgetingInterface")
        self.addSubInterface(
            self.budget_edit_interface,
            QIcon(UIUtils.my_svgicon('budgeting_interface')),
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
        self.help_interface = HelpInterface(self.engine) # Pass the engine
        self.help_interface.setObjectName("helpInterface")
        self.addSubInterface(
            self.help_interface,
            FluentIcon.HELP,
            "帮助",
            position=NavigationItemPosition.BOTTOM
        )
                
        if hasattr(self.progress_interface, '_refresh_project_selector'):
            self.project_updated.connect(self.progress_interface._refresh_project_selector)
        if hasattr(self.project_fund_interface, '_refresh_project_selector'):
            self.project_updated.connect(self.project_fund_interface._refresh_project_selector)
        if hasattr(self.document_interface, '_refresh_project_selector'):
            self.project_updated.connect(self.document_interface._refresh_project_selector)
        if hasattr(self.achievement_interface, '_refresh_project_selector'):
            self.project_updated.connect(self.achievement_interface._refresh_project_selector)
        if hasattr(self.budget_edit_interface, '_refresh_project_selector'):
             self.project_updated.connect(self.budget_edit_interface._refresh_project_selector)

        # 设置当前页面
        self.navigationInterface.setCurrentItem("主页")
        self.navigationInterface.setExpandWidth(150)
        FluentWindow.updateFrameless(self)
        


