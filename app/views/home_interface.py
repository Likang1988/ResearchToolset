from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qfluentwidgets import (TitleLabel, ScrollArea, ElevatedCardWidget,
                          BodyLabel)
from ..models.database import sessionmaker, Project, get_budget_usage, GanttTask
import os
from collections import defaultdict # 导入 defaultdict

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
        for i in reversed(range(self.fund_layout.count())):
            self.fund_layout.itemAt(i).widget().setParent(None)

        # 清空现有项目进度布局
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 重新加载数据
        self.load_funds()
        self.load_tasks() # 添加这行来刷新任务概览

    def setup_background(self):
        # 创建背景标签
        self.background_label = QLabel(self)
        self.background_label.setObjectName("backgroundLabel")

        # 加载背景图片
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_dir = os.path.dirname(current_dir)
        bg_path = os.path.join(app_dir, 'assets', 'header.png')
        bg_path = os.path.normpath(bg_path)

        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            self.background_label.setPixmap(pixmap)
            self.background_label.setScaledContents(True)
        else:
            pass # 背景图片不存在，不打印信息

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
        main_layout.setContentsMargins(20, 280, 20, 20)

        # 标题
        title_label = TitleLabel("科研工具集", self)
        title_label.setGeometry(20, 20, self.width() - 36, 40)
        title_label.setStyleSheet("font-size: 28px;")



        # 左右布局
        hbox = QHBoxLayout()
        hbox.setSpacing(20)

        # 左侧项目经费概览部分
        fund_section_layout = QVBoxLayout()
        fund_section_layout.setContentsMargins(0, 0, 0, 0) # 移除边距
        fund_section_layout.setSpacing(6) # 设置标题和ScrollArea之间的间距

        # 左侧项目经费概览标题
        fund_title = TitleLabel("项目经费概览", self)
        fund_title.setStyleSheet("font-size: 20px;") # 移除 margin-bottom
        fund_section_layout.addWidget(fund_title, alignment=Qt.AlignLeft | Qt.AlignTop) # 左上对齐

        self.fund_overview = ScrollArea()
        self.fund_overview.setWidgetResizable(True)
        self.fund_overview.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }
            QWidget#qt_scrollarea_viewport {
                background-color: transparent;
            }
        """)

        fund_container = QWidget()
        fund_container.setObjectName("qt_scrollarea_viewport")
        self.fund_layout = QVBoxLayout(fund_container)
        self.fund_layout.setSpacing(10)
        self.fund_layout.setAlignment(Qt.AlignTop)

        self.fund_overview.setWidget(fund_container)
        fund_section_layout.addWidget(self.fund_overview)
        hbox.addLayout(fund_section_layout)


        # 右侧项目进度概览部分
        task_section_layout = QVBoxLayout()
        task_section_layout.setContentsMargins(0, 0, 0, 0) # 移除边距
        task_section_layout.setSpacing(6) # 设置标题和ScrollArea之间的间距

        # 右侧项目进度概览标题
        task_title = TitleLabel("项目进度概览", self)
        task_title.setStyleSheet("font-size: 20px;") # 移除 margin-bottom
        task_section_layout.addWidget(task_title, alignment=Qt.AlignLeft | Qt.AlignTop) # 左上对齐

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

        self.task_overview.setWidget(task_container)
        task_section_layout.addWidget(self.task_overview)
        hbox.addLayout(task_section_layout)

        main_layout.addLayout(hbox)

        # 加载数据
        self.load_funds()
        self.load_tasks() # Call the new method

    def load_funds(self):
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            funds = session.query(Project).all()

            # 如果没有项目，显示提示信息
            if not funds:
                no_fund_label = BodyLabel("暂无项目经费信息")
                no_fund_label.setAlignment(Qt.AlignCenter)
                self.fund_layout.addWidget(no_fund_label)
                return # 退出方法，不再处理项目卡片

            # 如果有项目，继续现有逻辑
            for project in funds:
                card = ElevatedCardWidget()
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

                # Removed Project title

                
                # 添加财务编号值
                project_code_label = QLabel(project.financial_code if project.financial_code else "--")
                project_code_label.setAlignment(Qt.AlignCenter) # Align center
                project_code_label.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(project_code_label, 0, 0, 2, 1, alignment=Qt.AlignCenter) # Add to grid column 0, span 2 rows, center align

                # 添加分隔线
                line = QLabel()
                line.setStyleSheet("background-color: #ccc;")
                line.setFixedWidth(1)
                grid_layout.addWidget(line, 0, 1, 2, 1) # Add to grid column 1, span 2 rows, remove alignment

                # Add Total Budget title
                total_budget_title = QLabel("总预算")
                total_budget_title.setAlignment(Qt.AlignCenter)
                total_budget_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(total_budget_title, 0, 2, alignment=Qt.AlignCenter) # Add to grid column 2, row 0

                # Add Total Spent title
                total_spent_title = QLabel("总支出")
                total_spent_title.setAlignment(Qt.AlignCenter)
                total_spent_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(total_spent_title, 0, 3, alignment=Qt.AlignCenter) # Add to grid column 3, row 0

                # Add Execution Rate title
                execution_rate_title = QLabel("执行率")
                execution_rate_title.setAlignment(Qt.AlignCenter)
                execution_rate_title.setStyleSheet("font-size: 14px; color: #666;")
                grid_layout.addWidget(execution_rate_title, 0, 4, alignment=Qt.AlignCenter) # Add to grid column 4, row 0

                # Add Total Budget value
                total_budget_value = QLabel(f"{total_budget:.2f}<span style='font-size: 14px; font-weight: normal;'> 万元</span>")
                total_budget_value.setAlignment(Qt.AlignCenter)
                total_budget_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(total_budget_value, 1, 2, alignment=Qt.AlignCenter) # Add to grid column 2, row 1

                # Add Total Spent value
                total_spent_value = QLabel(f"{total_spent:.2f}<span style='font-size: 14px; font-weight: normal;'> 万元</span>")
                total_spent_value.setAlignment(Qt.AlignCenter)
                total_spent_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(total_spent_value, 1, 3, alignment=Qt.AlignCenter) # Add to grid column 3, row 1

                # Add Execution Rate value
                execution_rate_value = QLabel(f"{execution_rate:.2f}<span style='font-size: 14px; font-weight: normal;'> %</span>")
                execution_rate_value.setAlignment(Qt.AlignCenter)
                execution_rate_value.setStyleSheet("font-size: 18px; font-weight: bold;")
                grid_layout.addWidget(execution_rate_value, 1, 4, alignment=Qt.AlignCenter) # Add to grid column 4, row 1

                # Set column stretch factors for layout
                grid_layout.setColumnStretch(0, 1) # Project code column
                grid_layout.setColumnStretch(1, 0) # Separator column (fixed width)
                grid_layout.setColumnStretch(2, 1) # Total Budget column
                grid_layout.setColumnStretch(3, 1) # Total Spent column
                grid_layout.setColumnStretch(4, 1) # Execution Rate column

                # Set row stretch to ensure vertical centering
                grid_layout.setRowStretch(0, 1)
                grid_layout.setRowStretch(1, 1)

                # 添加网格布局到卡片布局
                card_layout.addLayout(grid_layout)

                # 点击事件
                card.mousePressEvent = lambda event, p=project: self.open_project_fund(p)

                self.fund_layout.addWidget(card)
        finally:
            session.close()


    def load_tasks(self):
        """加载并显示项目进度概览"""
        if not self.engine:
            # 数据库引擎未初始化，不打印信息
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            # 查询所有一级甘特图任务 (level == 0)，并按项目分组
            # 使用 group_by 和 order_by 来按项目分组并保持一致的顺序
            tasks_by_project = session.query(GanttTask).filter(GanttTask.level == 0).order_by(GanttTask.project_id).all()

            # 清空现有布局中的所有小部件
            while self.task_layout.count():
                item = self.task_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not tasks_by_project:
                no_task_label = BodyLabel("暂无项目任务信息")
                no_task_label.setAlignment(Qt.AlignCenter)
                self.task_layout.addWidget(no_task_label)
                return

            # 正在创建项目进度卡片...

            # 按项目ID分组任务
            grouped_tasks = defaultdict(list)
            for task in tasks_by_project:
                grouped_tasks[task.project_id].append(task)

            for project_id, tasks in grouped_tasks.items():
                if not tasks:
                    continue # Skip if no tasks for this project

                card = ElevatedCardWidget()
                card_content_layout = QGridLayout(card) # Use QGridLayout for the card content
                card_content_layout.setContentsMargins(15, 15, 15, 15)
                card_content_layout.setSpacing(10) # Adjust spacing

                # 左侧：项目简称
                project_code_label = QLabel(tasks[0].project.financial_code if tasks[0].project else "--")
                project_code_label.setStyleSheet("font-size: 18px; font-weight: bold;")
                project_code_label.setAlignment(Qt.AlignCenter) # 垂直和水平居中对齐
                project_code_label.setFixedWidth(100) # 设置固定宽度
                card_content_layout.addWidget(project_code_label, 0, 0, -1, 1, alignment=Qt.AlignCenter) # Add to grid column 0, span rows

                # 添加分隔线
                line = QLabel()
                line.setStyleSheet("background-color: #ccc;")
                line.setFixedWidth(1)
                card_content_layout.addWidget(line, 0, 1, -1, 1) # Add to grid column 1, span rows, remove alignment


                # Task information directly in grid columns 2, 3, 4
                # Header row (Row 0)
                task_code_title = QLabel("任务编码")
                task_code_title.setStyleSheet("font-size: 14px; color: #666;")
                card_content_layout.addWidget(task_code_title, 0, 2, alignment=Qt.AlignCenter)

                task_name_title = QLabel("任务名称")
                task_name_title.setStyleSheet("font-size: 14px; color: #666;")
                card_content_layout.addWidget(task_name_title, 0, 3, alignment=Qt.AlignCenter)

                task_progress_title = QLabel("任务进度")
                task_progress_title.setStyleSheet("font-size: 14px; color: #666;")
                card_content_layout.addWidget(task_progress_title, 0, 4, alignment=Qt.AlignCenter)

                # Task rows (Starting from Row 1)
                for i, task in enumerate(tasks):
                    row = i + 1 # Start from row 1
                    task_code_value = QLabel(task.code if task.code else str(i + 1))
                    task_code_value.setStyleSheet("font-size: 16px; font-weight: bold;")
                    card_content_layout.addWidget(task_code_value, row, 2, alignment=Qt.AlignCenter)

                    task_name_value = QLabel(task.name)
                    task_name_value.setStyleSheet("font-size: 16px; font-weight: bold;")
                    card_content_layout.addWidget(task_name_value, row, 3, alignment=Qt.AlignCenter)

                    task_progress_value = QLabel(f"{task.progress:.2f}<span style='font-size: 14px; font-weight: normal;'> %</span>")
                    task_progress_value.setStyleSheet("font-size: 16px; font-weight: bold;")
                    card_content_layout.addWidget(task_progress_value, row, 4, alignment=Qt.AlignCenter)

                # Set column stretch factors for centering and layout
                card_content_layout.setColumnStretch(0, 1) # Project code column
                card_content_layout.setColumnStretch(1, 0) # Separator column (fixed width)
                card_content_layout.setColumnStretch(2, 1) # "编码" column
                card_content_layout.setColumnStretch(3, 2) # "名称" column (wider)
                card_content_layout.setColumnStretch(4, 1) # "进度" column

                # 添加点击事件
                card.mousePressEvent = lambda event, p=tasks[0].project: self.open_project_progress(p) # Pass the project object

                self.task_layout.addWidget(card)

            # 项目进度卡片创建完成。

        except Exception as e:
            # 加载项目任务失败，不打印详细异常信息
            pass
        finally:
            session.close()
            # 数据库会话已关闭。

    def open_project_progress(self, project):
        """打开项目进度界面并加载项目数据"""
        # 获取主窗口实例
        main_window = self.window()
        if main_window and hasattr(main_window, 'progress_interface'): # Check for progress_interface
            progress_interface = main_window.progress_interface

            # 确保只触发一次界面切换
            if main_window.stackedWidget.currentWidget() != progress_interface:
                main_window.navigationInterface.setCurrentItem("项目进度") # Use the correct item name

                if main_window.stackedWidget.indexOf(progress_interface) == -1:
                    main_window.stackedWidget.addWidget(progress_interface)
                main_window.stackedWidget.setCurrentWidget(progress_interface)

                # 加载项目数据
                # Load project data using the new method
                if hasattr(progress_interface, 'load_project_by_object'):
                    progress_interface.load_project_by_object(project) # Pass the project object
                else:
                    pass # Warning if method not found, do not print

    def open_project_fund(self, project):
        # 获取主窗口实例
        main_window = self.window()
        if main_window and hasattr(main_window, 'project_fund_interface'):
            budget_interface = main_window.project_fund_interface

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
