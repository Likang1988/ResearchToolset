from PySide6.QtWidgets import QApplication, QStackedWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationInterface, FluentWindow, FluentIcon, NavigationItemPosition
from .funding_interface.project_list import ProjectListWindow
from .funding_interface.budget_list import BudgetListWindow
from .home_interface import HomeInterface
from .help_interface import HelpInterface
from .budgeting_interface import BudgetingInterface
from .tools_interface import ToolsInterface
from .projecting_interface.project_list import ProjectListWidget
import os

class MainWindow(FluentWindow):
    # 定义信号
    project_updated = Signal()
    activity_updated = Signal()
    
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self.budget_list_interface = None
        
        # 设置窗口标题和大小
        self.setWindowTitle("科研工具集")
        self.setMinimumSize(1200, 800)
        
        # 创建界面实例
        self.home_interface = HomeInterface(self.engine)
        self.home_interface.setObjectName("homeInterface")
        
        self.funding_interface = ProjectListWindow(self.engine)
        self.funding_interface.setObjectName("fundingInterface")
        
        # 创建预算编制界面实例
        self.budget_edit_interface = BudgetingInterface(self.engine)
        self.budget_edit_interface.setObjectName("budgetingInterface")
        
        self.help_interface = HelpInterface()
        self.help_interface.setObjectName("helpInterface")

        # 创建项目管理界面实例
        self.project_interface = ProjectListWidget()
        self.project_interface.setObjectName("projectInterface")
        self.project_interface.engine = self.engine
        
        # 添加导航项
        self.addSubInterface(
            self.home_interface,
            FluentIcon.HOME,
            "主页"
        )
        
        # 使用自定义SVG图标
        funding_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons', 'funding_tab.svg')
        self.addSubInterface(  
            self.funding_interface,
            QIcon(funding_icon_path),
            "经费追踪"
        )
        
        # 添加预算编制导航项
        budget_edit_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons', 'budgeting_tab.svg')
        self.addSubInterface(
            self.budget_edit_interface,
            QIcon(budget_edit_icon_path),
            "预算编制"
        )
        
        self.addSubInterface(
            self.help_interface,
            FluentIcon.HELP,
            "帮助",
            position=NavigationItemPosition.BOTTOM
        )

        # 添加工具界面
        self.tools_interface = ToolsInterface()
        self.tools_interface.setObjectName("toolsInterface")
        self.addSubInterface(
            self.tools_interface,
            FluentIcon.DEVELOPER_TOOLS,
            "小工具"
        )

        # 添加项目管理导航项
        project_icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons', 'project_tab.svg')
        self.addSubInterface(
            self.project_interface,
            QIcon(project_icon_path),
            "项目管理"
        )
        
        # 设置当前页面
        self.navigationInterface.setCurrentItem("主页")
