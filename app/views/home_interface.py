from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qfluentwidgets import (TitleLabel, SubtitleLabel, ScrollArea, CardWidget, PrimaryPushButton,
                          FluentIcon, InfoBadge, BodyLabel)
from sqlalchemy import func
from ..models.database import sessionmaker, Project, Budget, BudgetCategory, get_budget_usage, Activity, GanttTask
from datetime import datetime
from ..utils.ui_utils import UIUtils
import os

class HomeInterface(QWidget):
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self._signals_connected = False # Add flag to track signal connection
        self.setup_ui()
        self.setup_background()

    def showEvent(self, event):
        super().showEvent(event)
        # 获取主窗口实例并连接信号 (只连接一次)
        if not self._signals_connected:
            main_window = self.window()
            if main_window:
                # 连接项目列表更新信号
                if hasattr(main_window, 'project_updated'):
                    main_window.project_updated.connect(self.refresh_data)
                # 连接预算或支出更新信号
                if hasattr(main_window, 'budget_or_expense_updated'):
                    main_window.budget_or_expense_updated.connect(self.refresh_data)

                self._signals_connected = True # Mark signals as connected

    # Removed redundant post_init method which duplicated signal connections from showEvent

    def refresh_data(self):
        # 清空现有项目经费布局
        for i in reversed(range(self.project_layout.count())):
            self.project_layout.itemAt(i).widget().setParent(None)
        
        # 清空现有项目进度布局
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 重新加载数据
        self.load_projects()
        self.load_tasks() # 添加这行来刷新任务概览
    
    def setup_background(self):
        # 创建背景标签
        self.background_label = QLabel(self)
        self.background_label.setObjectName("backgroundLabel")
        
        # 加载背景图片
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(current_dir)
        bg_path = os.path.join(app_dir, 'assets', 'header1.png')
        bg_path = os.path.normpath(bg_path)
        
        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            self.background_label.setPixmap(pixmap)
            self.background_label.setScaledContents(True)
        else:
            print(f"背景图片不存在: {bg_path}")
        
        # 设置背景标签的大小和位置
        self.background_label.setGeometry(0, 0, self.width(), 340)
        self.background_label.lower()
        
        # 添加样式
        self.setStyleSheet("""
            QLabel#backgroundLabel {
                background-repeat: no-repeat;
                background-position: top;
                border-radius: 8px;
            }
        """)
    
    def setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 350, 20, 20)
        
        # 标题
        title_label = TitleLabel("科研工具集", self)
        title_label.setGeometry(20, 20, self.width() - 36, 40)
        title_label.setStyleSheet("font-size: 28px;")



        # 左右布局
        hbox = QHBoxLayout()
        hbox.setSpacing(20)
        
        # 左侧项目经费概览
        self.project_overview = ScrollArea()
        self.project_overview.setWidgetResizable(True)
        self.project_overview.setFixedWidth(530)
        self.project_overview.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }
            QWidget#qt_scrollarea_viewport {
                background-color: transparent;
            }
        """)
        
        project_container = QWidget()
        project_container.setObjectName("qt_scrollarea_viewport")
        self.project_layout = QVBoxLayout(project_container)
        self.project_layout.setSpacing(10)
        self.project_layout.setAlignment(Qt.AlignTop)
        
        # 左侧项目经费概览标题
        project_title = TitleLabel("项目经费概览", self)
        project_title.setStyleSheet("font-size: 20px; margin-bottom: 10px;")
        project_title.setGeometry(20, 320, self.width() - 36, 40)
        
        self.project_overview.setWidget(project_container)
        hbox.addWidget(self.project_overview)
        
        
        
        # 右侧项目进度概览
        self.task_overview = ScrollArea()
        self.task_overview.setWidgetResizable(True)
        self.task_overview.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }
            QWidget#qt_scrollarea_viewport {
                background-color: transparent;
            }
        """)
        
        task_container = QWidget()
        task_container.setObjectName("qt_scrollarea_viewport")
        self.task_layout = QVBoxLayout(task_container)
        self.task_layout.setSpacing(10)
        self.task_layout.setAlignment(Qt.AlignTop)
        
        # 右侧项目进度概览标题
        task_title = TitleLabel("项目进度概览", self)
        task_title.setStyleSheet("font-size: 20px; margin-bottom: 10px;")
        task_title.setGeometry(570, 320, 530, 40) # Adjust position as needed
        
        self.task_overview.setWidget(task_container)
        hbox.addWidget(self.task_overview)
        
        main_layout.addLayout(hbox)
        
        # 加载数据
        self.load_projects()
        self.load_tasks() # Call the new method
    
    def load_projects(self):
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            projects = session.query(Project).all()
            for project in projects:
                card = CardWidget()
                card.setFixedHeight(80)  # 设置卡片高度
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(15, 15, 15, 15)
                
                # 创建网格布局用于显示项目信息
                grid_layout = QGridLayout()
                grid_layout.setSpacing(10)
                
                # 获取预算使用情况
                budget_usage = get_budget_usage(session, project.id)
                total_budget = project.total_budget   
                total_spent = budget_usage['total_spent'] / 10000  # 转换为万元
                execution_rate = (budget_usage['total_spent'] / (project.total_budget * 10000)) * 100 if project.total_budget > 0 else 0
                
                # 添加项目标题
                financial_code_title = QLabel("项目")
                financial_code_title.setAlignment(Qt.AlignCenter)
                financial_code_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(financial_code_title, 0, 0)
                
                # 添加总经费标题
                total_budget_title = QLabel("总预算")
                total_budget_title.setAlignment(Qt.AlignCenter)
                total_budget_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(total_budget_title, 0, 1)
                
                # 添加总支出标题
                total_spent_title = QLabel("总支出")
                total_spent_title.setAlignment(Qt.AlignCenter)
                total_spent_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(total_spent_title, 0, 2)
                
                # 添加执行率标题
                execution_rate_title = QLabel("执行率")
                execution_rate_title.setAlignment(Qt.AlignCenter)
                execution_rate_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(execution_rate_title, 0, 3)
                
                # 添加财务编号值
                financial_code_value = QLabel(project.financial_code if project.financial_code else "--")
                financial_code_value.setAlignment(Qt.AlignCenter)
                financial_code_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(financial_code_value, 1, 0)
                
                # 添加总经费值
                total_budget_value = QLabel(f"{total_budget:.2f}<span style='font-size: 14px; font-weight: normal;'> 万元</span>")
                total_budget_value.setAlignment(Qt.AlignCenter)
                total_budget_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(total_budget_value, 1, 1)
                
                # 添加总支出值
                total_spent_value = QLabel(f"{total_spent:.2f}<span style='font-size: 14px; font-weight: normal;'> 万元</span>")
                total_spent_value.setAlignment(Qt.AlignCenter)
                total_spent_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(total_spent_value, 1, 2)
                
                # 添加执行率值
                execution_rate_value = QLabel(f"{execution_rate:.2f}<span style='font-size: 14px; font-weight: normal;'> %</span>")
                execution_rate_value.setAlignment(Qt.AlignCenter)
                execution_rate_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(execution_rate_value, 1, 3)
                execution_rate_value.setAlignment(Qt.AlignCenter)
                execution_rate_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(execution_rate_value, 1, 3)
                
                # 添加网格布局到卡片布局
                card_layout.addLayout(grid_layout)
                
                # 点击事件
                card.mousePressEvent = lambda event, p=project: self.open_project_budget(p)
                
                self.project_layout.addWidget(card)
        finally:
            session.close()
    
    
    def load_tasks(self):
        """加载并显示项目进度概览"""
        if not self.engine:
            print("数据库引擎未初始化，无法加载项目任务。")
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            # 查询所有一级甘特图任务 (level == 0)
            print("正在查询一级项目任务...")
            tasks = session.query(GanttTask).filter(GanttTask.level == 0).all()
            print(f"查询到 {len(tasks)} 个一级项目任务。")

            # 清空现有布局中的所有小部件
            while self.task_layout.count():
                item = self.task_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not tasks:
                print("没有找到一级项目任务，显示提示信息。")
                no_task_label = BodyLabel("没有找到一级项目任务。")
                no_task_label.setAlignment(Qt.AlignCenter)
                self.task_layout.addWidget(no_task_label)
                return

            print("正在创建任务卡片...")
            for task in tasks:
                print(f"处理任务: {task.name}, 项目: {task.project.financial_code if task.project else 'N/A'}, 进度: {task.progress}")
                card = CardWidget()
                card.setFixedHeight(80)  # 设置卡片高度
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(15, 15, 15, 15)

                # 创建网格布局用于显示任务信息
                grid_layout = QGridLayout()
                grid_layout.setSpacing(10)

                # 添加项目简称标题
                project_code_title = QLabel("项目")
                project_code_title.setAlignment(Qt.AlignCenter)
                project_code_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(project_code_title, 0, 0)

                # 添加任务名称标题
                task_name_title = QLabel("任务名称")
                task_name_title.setAlignment(Qt.AlignCenter)
                task_name_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(task_name_title, 0, 1)

                # 添加任务进度标题
                task_progress_title = QLabel("任务进度")
                task_progress_title.setAlignment(Qt.AlignCenter)
                task_progress_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(task_progress_title, 0, 2)

                # 添加项目简称值
                project_code_value = QLabel(task.project.financial_code if task.project else "--")
                project_code_value.setAlignment(Qt.AlignCenter)
                project_code_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(project_code_value, 1, 0)

                # 添加任务名称值
                task_name_value = QLabel(task.name)
                task_name_value.setAlignment(Qt.AlignCenter)
                task_name_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(task_name_value, 1, 1)

                # 添加任务进度值
                task_progress_value = QLabel(f"{task.progress:.0f}<span style='font-size: 14px; font-weight: normal;'> %</span>")
                task_progress_value.setAlignment(Qt.AlignCenter)
                task_progress_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(task_progress_value, 1, 2)

                # 添加网格布局到卡片布局
                card_layout.addLayout(grid_layout)

                # TODO: Add click event for task card if needed

                self.task_layout.addWidget(card)
            print("任务卡片创建完成。")

        except Exception as e:
            print(f"加载项目任务失败: {e}")
            import traceback
            traceback.print_exc() # 打印详细的异常信息
        finally:
            session.close()
            print("数据库会话已关闭。")
    
    def open_project_budget(self, project):
        # 获取主窗口实例
        main_window = self.window()
        if main_window and hasattr(main_window, 'project_budget_interface'):
            budget_interface = main_window.project_budget_interface
            
            # 确保只触发一次界面切换
            if main_window.stackedWidget.currentWidget() != budget_interface:
                main_window.navigationInterface.setCurrentItem("项目经费")
                
                if main_window.stackedWidget.indexOf(budget_interface) == -1:
                    main_window.stackedWidget.addWidget(budget_interface)
                main_window.stackedWidget.setCurrentWidget(budget_interface)
                
                # 加载项目数据
                budget_interface.load_project_data(project) # Pass the project object
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'background_label'):
            self.background_label.setGeometry(0, 0, self.width(), 300)
