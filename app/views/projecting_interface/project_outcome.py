from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QDialog,  QLabel # Added QLabel
from PySide6.QtCore import Qt
from qfluentwidgets import TitleLabel, PrimaryPushButton, FluentIcon, LineEdit, ComboBox, DateEdit, InfoBar
from ...utils.ui_utils import UIUtils
from ...models.database import Project, Base, get_engine, sessionmaker # Added sessionmaker import
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, Engine # Added Engine type hint
from enum import Enum
from datetime import datetime

class AchievementType(Enum):
    PAPER = "论文"
    PATENT = "专利"
    SOFTWARE = "软件著作权"
    STANDARD = "标准"
    AWARD = "获奖"
    OTHER = "其他"

class AchievementStatus(Enum):
    DRAFT = "草稿"
    SUBMITTED = "已提交"
    ACCEPTED = "已接收"
    PUBLISHED = "已发表/授权"
    REJECTED = "已拒绝"

class ProjectOutcome(Base): # 重命名模型类
    __tablename__ = 'project_outcomes' # 重命名表名
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(200), nullable=False)  # 成果名称
    type = Column(SQLEnum(AchievementType), nullable=False)  # 成果类型
    status = Column(SQLEnum(AchievementStatus), default=AchievementStatus.DRAFT)  # 成果状态
    authors = Column(String(200))  # 作者/完成人
    submit_date = Column(Date)  # 投稿/申请日期
    publish_date = Column(Date)  # 发表/授权日期
    journal = Column(String(200))  # 期刊/授权单位
    description = Column(String(500))  # 成果描述
    remarks = Column(String(200))  # 备注

class AchievementDialog(QDialog):
    def __init__(self, parent=None, achievement=None, project=None):
        super().__init__(parent)
        self.achievement = achievement
        self.project = project
        self.setup_ui()
        if achievement:
            self.load_achievement_data()
    
    def setup_ui(self):
        self.setWindowTitle("成果信息")
        layout = QVBoxLayout(self)
        
        # 成果表单
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("成果名称")
        layout.addWidget(self.name_edit)
        
        self.type_combo = ComboBox()
        for type in AchievementType:
            self.type_combo.addItem(type.value)
        layout.addWidget(self.type_combo)
        
        self.status_combo = ComboBox()
        for status in AchievementStatus:
            self.status_combo.addItem(status.value)
        layout.addWidget(self.status_combo)
        
        self.authors_edit = LineEdit()
        self.authors_edit.setPlaceholderText("作者/完成人")
        layout.addWidget(self.authors_edit)
        
        self.submit_date = DateEdit()
        #self.submit_date.setCalendarPopup(True)
        self.submit_date.setDate(datetime.now())
        self.submit_date.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.submit_date)
        
        self.publish_date = DateEdit()
        #self.publish_date.setCalendarPopup(True)
        self.publish_date.setDate(datetime.now())
        self.publish_date.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.publish_date)
        
        self.journal_edit = LineEdit()
        self.journal_edit.setPlaceholderText("期刊/授权单位")
        layout.addWidget(self.journal_edit)
        
        self.description_edit = LineEdit()
        self.description_edit.setPlaceholderText("成果描述")
        layout.addWidget(self.description_edit)
        
        self.remarks_edit = LineEdit()
        self.remarks_edit.setPlaceholderText("备注")
        layout.addWidget(self.remarks_edit)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_btn = PrimaryPushButton("保存")
        cancel_btn = PrimaryPushButton("取消")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
    
    def load_achievement_data(self):
        self.name_edit.setText(self.achievement.name)
        self.type_combo.setCurrentText(self.achievement.type.value)
        self.status_combo.setCurrentText(self.achievement.status.value)
        self.authors_edit.setText(self.achievement.authors)
        if self.achievement.submit_date:
            self.submit_date.setDate(self.achievement.submit_date)
        if self.achievement.publish_date:
            self.publish_date.setDate(self.achievement.publish_date)
        self.journal_edit.setText(self.achievement.journal)
        self.description_edit.setText(self.achievement.description)
        self.remarks_edit.setText(self.achievement.remarks)

class ProjectOutcomeWidget(QWidget): # 重命名 Widget 类
    # Modify __init__ to accept engine and remove project
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent=parent)
        # self.project = project # Removed
        self.engine = engine # Store engine
        self.current_project = None # Track selected project
        self.setup_ui()
        # self.load_achievements() # Don't load initially, wait for selection
    
    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18) # Add some margins
        # --- Add Project Selector ---
        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目成果-", self)        
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.main_layout.addLayout(selector_layout)
        # Connect signal after UI setup
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)
        # --- Project Selector End ---

        # 按钮栏
        add_btn = UIUtils.create_action_button("新增成果", FluentIcon.ADD)
        edit_btn = UIUtils.create_action_button("编辑成果", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除成果", FluentIcon.DELETE)
        
        add_btn.clicked.connect(self.add_achievement)
        edit_btn.clicked.connect(self.edit_achievement)
        delete_btn.clicked.connect(self.delete_achievement)
        
        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        self.main_layout.addLayout(button_layout)
        
        # 成果列表
        self.achievement_table = QTableWidget()
        self.achievement_table.setColumnCount(9)
        self.achievement_table.setHorizontalHeaderLabels(["成果名称", "类型", "状态", "作者/完成人", "投稿/申请日期", "发表/授权日期", "期刊/授权单位", "描述", "备注"])
        UIUtils.set_table_style(self.achievement_table)
        
        self.main_layout.addWidget(self.achievement_table)
        
        # 搜索栏（移动到列表下方）
        search_layout = QHBoxLayout()
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索成果")
        self.search_edit.textChanged.connect(self.search_achievements)
        search_layout.addWidget(self.search_edit)
        
        self.type_filter = ComboBox()
        self.type_filter.addItem("全部类型")
        for type in AchievementType:
            self.type_filter.addItem(type.value)
        self.type_filter.currentTextChanged.connect(self.search_achievements)
        search_layout.addWidget(self.type_filter)
        
        self.status_filter = ComboBox()
        self.status_filter.addItem("全部状态")
        for status in AchievementStatus:
            self.status_filter.addItem(status.value)
        self.status_filter.currentTextChanged.connect(self.search_achievements)
        search_layout.addWidget(self.status_filter)
        
        self.main_layout.addLayout(search_layout)
    
    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_project = self.project_selector.itemData(index)
        if selected_project and isinstance(selected_project, Project):
            self.current_project = selected_project
            print(f"AchievementWidget: Project selected - {self.current_project.name}")
            self.load_achievements() # Load achievements for the selected project
        else:
            self.current_project = None
            self.achievement_table.setRowCount(0) # Clear table if no project selected
            print("AchievementWidget: No valid project selected.")

    def load_achievements(self):
        """Loads achievements for the currently selected project."""
        self.achievement_table.setRowCount(0) # Clear table first
        if not self.current_project:
            print("AchievementWidget: No project selected, cannot load achievements.")
            return

        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            print(f"OutcomeWidget: Loading outcomes for project ID: {self.current_project.id}") # 更新日志信息
            achievements = session.query(ProjectOutcome).filter( # 使用新的模型类名
                ProjectOutcome.project_id == self.current_project.id
            ).order_by(ProjectOutcome.publish_date.desc()).all() # Order by publish date

            self.achievement_table.setRowCount(len(achievements))
            for row, achievement in enumerate(achievements):
                self.achievement_table.setItem(row, 0, QTableWidgetItem(achievement.name))
                self.achievement_table.setItem(row, 1, QTableWidgetItem(achievement.type.value))
                self.achievement_table.setItem(row, 2, QTableWidgetItem(achievement.status.value))
                self.achievement_table.setItem(row, 3, QTableWidgetItem(achievement.authors))
                self.achievement_table.setItem(row, 4, QTableWidgetItem(str(achievement.submit_date) if achievement.submit_date else ""))
                self.achievement_table.setItem(row, 5, QTableWidgetItem(str(achievement.publish_date) if achievement.publish_date else ""))
                self.achievement_table.setItem(row, 6, QTableWidgetItem(achievement.journal))
                self.achievement_table.setItem(row, 7, QTableWidgetItem(achievement.description))
                self.achievement_table.setItem(row, 8, QTableWidgetItem(achievement.remarks))
        finally:
            session.close()
    
    def search_achievements(self):
        keyword = self.search_edit.text().lower()
        achievement_type = self.type_filter.currentText()
        achievement_status = self.status_filter.currentText()
        
        for row in range(self.achievement_table.rowCount()):
            show_row = True
            
            # 关键词匹配
            if keyword:
                match_found = False
                for col in [0, 3, 6, 7]:  # 搜索成果名称、作者、期刊和描述列
                    cell_text = self.achievement_table.item(row, col).text().lower()
                    if keyword in cell_text:
                        match_found = True
                        break
                show_row = match_found
            
            # 类型过滤
            if show_row and achievement_type != "全部类型":
                cell_type = self.achievement_table.item(row, 1).text()
                show_row = (cell_type == achievement_type)
            
            # 状态过滤
            if show_row and achievement_status != "全部状态":
                cell_status = self.achievement_table.item(row, 2).text()
                show_row = (cell_status == achievement_status)
            
            self.achievement_table.setRowHidden(row, not show_row)
    
    def add_achievement(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return

        dialog = AchievementDialog(self, project=self.current_project) # Pass current project if needed by dialog
        if dialog.exec():
            # Use the stored engine
            Session = sessionmaker(bind=self.engine)
            session = Session()

            try:
                achievement = ProjectOutcome( # 使用新的模型类名
                    project_id=self.current_project.id, # Use current_project.id
                    name=dialog.name_edit.text(),
                    type=AchievementType(dialog.type_combo.currentText()),
                    status=AchievementStatus(dialog.status_combo.currentText()),
                    authors=dialog.authors_edit.text(),
                    submit_date=dialog.submit_date.date().toPython(),
                    publish_date=dialog.publish_date.date().toPython(),
                    journal=dialog.journal_edit.text(),
                    description=dialog.description_edit.text(),
                    remarks=dialog.remarks_edit.text()
                )
                session.add(achievement)
                session.commit()
                self.load_achievements()
                UIUtils.show_success(self, "成功", "成果添加成功")
            finally:
                session.close()
    
    def edit_achievement(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_items = self.achievement_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要编辑的成果")
            return
        
        row = selected_items[0].row()
        achievement_name = self.achievement_table.item(row, 0).text()
        
        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            achievement = session.query(ProjectOutcome).filter( # 使用新的模型类名
                ProjectOutcome.project_id == self.current_project.id, # Use current_project.id
                ProjectOutcome.name == achievement_name
            ).first()

            if achievement:
                dialog = AchievementDialog(self, achievement, project=self.current_project) # Pass current project if needed
                if dialog.exec():
                    achievement.name = dialog.name_edit.text()
                    achievement.type = AchievementType(dialog.type_combo.currentText())
                    achievement.status = AchievementStatus(dialog.status_combo.currentText())
                    achievement.authors = dialog.authors_edit.text()
                    achievement.submit_date = dialog.submit_date.date().toPython()
                    achievement.publish_date = dialog.publish_date.date().toPython()
                    achievement.journal = dialog.journal_edit.text()
                    achievement.description = dialog.description_edit.text()
                    achievement.remarks = dialog.remarks_edit.text()
                    
                    session.commit()
                    self.load_achievements()
                    UIUtils.show_success(self, "成功", "成果更新成功")
        finally:
            session.close()
    
    def delete_achievement(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return
        selected_items = self.achievement_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请先选择要删除的成果")
            return
        
        row = selected_items[0].row()
        achievement_name = self.achievement_table.item(row, 0).text()
        
        # Use the stored engine
        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            achievement = session.query(ProjectOutcome).filter( # 使用新的模型类名
                ProjectOutcome.project_id == self.current_project.id, # Use current_project.id
                ProjectOutcome.name == achievement_name
            ).first()

            if achievement:
                session.delete(achievement)
                session.commit()
                self.load_achievements()
                UIUtils.show_success(self, "成功", "成果删除成功")
        finally:
            session.close()