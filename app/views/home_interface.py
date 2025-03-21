from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qfluentwidgets import (TitleLabel, SubtitleLabel, ScrollArea, CardWidget, PrimaryPushButton,
                          FluentIcon, InfoBadge, BodyLabel)
from sqlalchemy import func
from ..models.database import sessionmaker, Project, Budget, BudgetCategory, get_budget_usage, Activity
from datetime import datetime
from ..utils.ui_utils import UIUtils
import os

class HomeInterface(QWidget):
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self.setup_ui()
        self.setup_background()
    
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
        
        # 左侧项目概览
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
        
        # 左侧项目概览标题
        project_title = TitleLabel("项目概览", self)
        project_title.setStyleSheet("font-size: 20px; margin-bottom: 10px;")
        project_title.setGeometry(20, 320, self.width() - 36, 40)
        
        self.project_overview.setWidget(project_container)
        hbox.addWidget(self.project_overview)
        
        # 右侧最近活动
        activity_container = QWidget()
        self.activity_layout = QVBoxLayout(activity_container)
        self.activity_layout.setSpacing(10)
        self.activity_layout.setAlignment(Qt.AlignTop)
        
        # 右侧最近活动标题
        activity_title = TitleLabel("最近活动", self)
        activity_title.setStyleSheet("font-size: 20px; margin-bottom: 10px;")
        activity_title.setGeometry(570, 320, 530, 40)
        
        # 右侧最近活动
        self.recent_activity = ScrollArea()
        self.recent_activity.setWidgetResizable(True)
        self.recent_activity.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }
            QWidget#qt_scrollarea_viewport {
                background-color: transparent;
            }
        """)
        
        activity_container = QWidget()
        activity_container.setObjectName("qt_scrollarea_viewport")
        self.activity_layout = QVBoxLayout(activity_container)
        self.activity_layout.setSpacing(5)
        self.activity_layout.setAlignment(Qt.AlignTop)
        
        self.recent_activity.setWidget(activity_container)
        hbox.addWidget(self.recent_activity)
        
        main_layout.addLayout(hbox)
        
        # 加载数据
        self.load_projects()
        self.load_activities()
    
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
                
                # 添加财务编号标题
                financial_code_title = QLabel("财务编号")
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
    
    def load_activities(self):
        Session = sessionmaker(bind=self.engine)
        session = Session()
        
        try:
            activities = session.query(Activity).order_by(Activity.timestamp.desc()).limit(50).all()
            activities = [{
                "type": activity.type,
                "action": activity.action,
                "name": activity.project.name if activity.project else activity.budget.project.name if activity.budget else activity.expense.budget.project.name,
                "time": activity.timestamp.strftime("%Y-%m-%d %H:%M")
            } for activity in activities]
            
            for activity in activities:
                label = BodyLabel(f"{activity['time']} {activity['type']} {activity['action']}: {activity['name']}")
                self.activity_layout.addWidget(label)
        finally:
            session.close()
    
    def open_project_budget(self, project):
        from ..views.funding_interface.budget_management import BudgetManagementWindow
        self.budget_interface = BudgetManagementWindow(self.engine, project)
        self.budget_interface.show()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'background_label'):
            self.background_label.setGeometry(0, 0, self.width(), 300)
