from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from qfluentwidgets import (TitleLabel, SubtitleLabel, CardWidget, PrimaryPushButton,
                          FluentIcon, InfoBadge, BodyLabel)
from ..models.database import sessionmaker, Project, Budget, BudgetCategory
from datetime import datetime
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
        bg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'header1.png')
        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            self.background_label.setPixmap(pixmap)
            self.background_label.setScaledContents(True)
        
        # 设置背景标签的大小和位置
        self.background_label.setGeometry(0, 0, self.width(), 300)
        self.background_label.lower()
        
        # 添加样式
        self.setStyleSheet("""
            QLabel#backgroundLabel {
                background-repeat: no-repeat;
                background-position: top;
                background-size: cover;
            }
        """)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'background_label'):
            self.background_label.setGeometry(0, 0, self.width(), 300)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(20)
        
        # 使用绝对定位设置标题
        title_label = TitleLabel("科研工具集", self)
        title_label.setGeometry(20, 20, self.width() - 36, 40)
        title_label.setStyleSheet("font-size: 28px;")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # 创建项目概览和最近活动的水平布局
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)
        cards_layout.setContentsMargins(0, 280, 0, 0)  # 设置上边距为320像素，确保在背景图片下方20像素
        
        # 创建项目概览卡片
        overview_card = CardWidget(self)
        overview_layout = QVBoxLayout(overview_card)
        overview_title = SubtitleLabel("项目概览", self)
        overview_layout.addWidget(overview_title)
        
        # 添加项目统计信息
        stats_layout = QGridLayout()
        stats_layout.setSpacing(10)
        
        # 从数据库获取统计信息
        stats = self.get_project_stats()
        
        # 显示统计信息
        stats_items = [
            ("进行中项目", stats['active_projects'], FluentIcon.PEOPLE),
            ("总经费（万元）", f"{stats['total_budget']/10000:.2f}", FluentIcon.GAME),
            ("本年支出（万元）", f"{stats['year_expense']/10000:.2f}", FluentIcon.CALENDAR),
            ("预算执行率", f"{stats['budget_usage']}%", FluentIcon.PIE_SINGLE)
        ]
        
        for i, (label_text, value, icon) in enumerate(stats_items):
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setSpacing(5)
            
            label = BodyLabel(label_text)
            value_label = TitleLabel(str(value))
            
            container_layout.addWidget(label)
            container_layout.addWidget(value_label)
            
            stats_layout.addWidget(container, i//2, i%2)
        
        overview_layout.addLayout(stats_layout)
        overview_card.setFixedSize(550, 400)
        
        # 创建最近活动卡片
        activity_card = CardWidget(self)
        activity_layout = QVBoxLayout(activity_card)
        activity_title = SubtitleLabel("最近活动", self)
        activity_layout.addWidget(activity_title)
        
        # 获取最近的经费使用记录
        recent_activities = self.get_recent_activities()
        for activity in recent_activities:
            activity_item = QLabel(activity)
            activity_layout.addWidget(activity_item)
        
        activity_card.setFixedSize(550, 400)
        
        # 将卡片添加到水平布局
        cards_layout.addWidget(overview_card)
        cards_layout.addWidget(activity_card)
        layout.addLayout(cards_layout)
        
        
        
    def get_project_stats(self):
        """获取项目统计信息"""
        if not self.engine:
            return {
                'active_projects': 0,
                'total_budget': 0,
                'year_expense': 0,
                'budget_usage': 0
            }
        
        try:
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            # 获取进行中的项目数量
            current_date = datetime.now().date()
            active_projects = session.query(Project).filter(
                Project.start_date <= current_date,
                Project.end_date >= current_date
            ).count()
            
            # 获取总经费
            total_budget = session.query(func.sum(Project.total_budget)).scalar() or 0
            
            # 获取本年支出
            current_year = datetime.now().year
            year_expense = session.query(func.sum(Budget.spent_amount))\
                .filter(Budget.year == current_year).scalar() or 0
            
            # 计算预算执行率
            budget_usage = round((year_expense / total_budget * 100) if total_budget > 0 else 0, 2)
            
            session.close()
            return {
                'active_projects': active_projects,
                'total_budget': total_budget,
                'year_expense': year_expense,
                'budget_usage': budget_usage
            }
        except Exception as e:
            print(f"获取项目统计信息失败：{str(e)}")
            return {
                'active_projects': 0,
                'total_budget': 0,
                'year_expense': 0,
                'budget_usage': 0
            }
    
    def get_recent_activities(self):
        """获取最近的经费使用记录"""
        if not self.engine:
            return ["暂无活动记录"]
        
        try:
            Session = sessionmaker(bind=self.engine)
            session = Session()
            
            # 获取最近5条支出记录
            recent_expenses = session.query(Budget)\
                .order_by(Budget.id.desc())\
                .limit(5).all()
            
            activities = []
            for expense in recent_expenses:
                project = session.query(Project).get(expense.project_id)
                if project:
                    activities.append(
                        f"{project.name} - {expense.year}年度支出：{expense.spent_amount:.2f}元"
                    )
            
            session.close()
            return activities if activities else ["暂无活动记录"]
        except Exception as e:
            print(f"获取最近活动失败：{str(e)}")
            return ["暂无活动记录"]
