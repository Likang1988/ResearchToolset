import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidgetItem, QDialog, QHeaderView, QFileDialog, QApplication
from PySide6.QtCore import Qt, QPoint, QDate
from PySide6.QtGui import QIcon
from qfluentwidgets import TitleLabel, FluentIcon, LineEdit, ComboBox, DateEdit, CompactDateEdit, BodyLabel, PushButton, TableWidget, TableItemDelegate, Dialog, RoundMenu, Action, PlainTextEdit, ToolTipFilter, ToolTipPosition
from ..utils.ui_utils import UIUtils
from ..models.database import Base, sessionmaker, Actionlog
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, Engine
from enum import Enum
from datetime import datetime
from ..utils.attachment_utils import (
    create_attachment_button,
    sanitize_filename, ensure_directory_exists, get_timestamp_str, get_attachment_icon_path,
    view_attachment, download_attachment, ROOT_DIR,
    generate_attachment_path, handle_attachment, execute_attachment_action
)
from ..utils.filter_utils import FilterUtils
import pandas as pd
import shutil

class ActivityType(Enum):
    CONFERENCE = "学术会议"
    LECTURE = "学术讲座"
    TRAINING = "培训活动"
    SEMINAR = "研讨会"
    WORKSHOP = "工作坊"
    EXCHANGE = "学术交流"
    OTHER = "其他"

class ActivityStatus(Enum):
    PLANNED = "未开始"
    ONGOING = "进行中"
    COMPLETED = "已结束"
    CANCELLED = "已取消"

class AcademicActivity(Base):
    __tablename__ = 'academic_activities'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)  # 活动名称
    type = Column(SQLEnum(ActivityType), nullable=False)  # 活动类型
    status = Column(SQLEnum(ActivityStatus), default=ActivityStatus.PLANNED)  # 活动状态
    organizer = Column(String(200))  # 主办方
    start_date = Column(Date)  # 开始日期
    end_date = Column(Date)  # 结束日期
    location = Column(String(200))  # 活动地点
    participants = Column(String(500))  # 参与人员
    description = Column(String(500))  # 活动描述
    attachment_path = Column(String(500))  # 附件文件路径

ACTIVITY_ATTACHMENTS_DIR = os.path.join(ROOT_DIR, "activities")

class ActivityDialog(QDialog):
    def __init__(self, parent=None, activity=None):
        super().__init__(parent)
        self.activity = activity
        self.current_attachment_path = activity.attachment_path if activity and hasattr(activity, 'attachment_path') and activity.attachment_path else None
        self.new_attachment_path = None  # Path of newly selected file
        self.attachment_removed = False # Flag if existing attachment is marked for removal
        self.setup_ui()
        if activity:
            self.load_activity_data()

    def setup_ui(self):
        self.setWindowTitle("活动信息")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 活动名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel("活动名称:"))
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("请输入活动名称，必填")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 活动类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(BodyLabel("活动类型:"))
        self.type_combo = ComboBox()
        for type_enum in ActivityType:
            self.type_combo.addItem(type_enum.value)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # 活动状态
        status_layout = QHBoxLayout()
        status_layout.addWidget(BodyLabel("活动状态:"))
        self.status_combo = ComboBox()
        for status_enum in ActivityStatus:
            self.status_combo.addItem(status_enum.value)
        status_layout.addWidget(self.status_combo)
        layout.addLayout(status_layout)

        # 主办方
        organizer_layout = QHBoxLayout()
        organizer_layout.addWidget(BodyLabel("主办方:"))
        self.organizer_edit = LineEdit()
        self.organizer_edit.setPlaceholderText("请输入主办方")
        organizer_layout.addWidget(self.organizer_edit)
        layout.addLayout(organizer_layout)

        # 开始日期
        start_date_layout = QHBoxLayout()
        start_date_layout.addWidget(BodyLabel("开始日期:"))
        self.start_date = DateEdit()
        self.start_date.setDate(datetime.now().date())
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        start_date_layout.addWidget(self.start_date)
        layout.addLayout(start_date_layout)

        # 结束日期
        end_date_layout = QHBoxLayout()
        end_date_layout.addWidget(BodyLabel("结束日期:"))
        self.end_date = DateEdit()
        self.end_date.setDate(datetime.now().date())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        end_date_layout.addWidget(self.end_date)
        layout.addLayout(end_date_layout)

        # 活动地点
        location_layout = QHBoxLayout()
        location_layout.addWidget(BodyLabel("活动地点:"))
        self.location_edit = LineEdit()
        self.location_edit.setPlaceholderText("请输入活动地点")
        location_layout.addWidget(self.location_edit)
        layout.addLayout(location_layout)

        # 参与人员
        participants_layout = QHBoxLayout()
        participants_layout.addWidget(BodyLabel("参与人员:"))
        self.participants_edit = PlainTextEdit()
        self.participants_edit.setPlaceholderText("请输入参与人员")
        self.participants_edit.setFixedHeight(80)
        participants_layout.addWidget(self.participants_edit)
        layout.addLayout(participants_layout)

        # 活动描述
        description_layout = QHBoxLayout()
        description_layout.addWidget(BodyLabel("活动描述:"))
        self.description_edit = PlainTextEdit()
        self.description_edit.setPlaceholderText("请输入活动描述")
        self.description_edit.setFixedHeight(120)
        description_layout.addWidget(self.description_edit)
        layout.addLayout(description_layout)

        # 附件
        attachment_layout = QHBoxLayout()
        attachment_layout.addWidget(BodyLabel("活动附件:"))
        self.attachment_label = BodyLabel("无附件")
        self.attachment_label.setWordWrap(True)
        attachment_layout.addWidget(self.attachment_label, 1)
        self.select_attachment_btn = PushButton("选择文件", icon=FluentIcon.DOCUMENT)
        self.select_attachment_btn.clicked.connect(self._select_file)
        attachment_layout.addWidget(self.select_attachment_btn)
        self.remove_attachment_btn = PushButton("移除附件", icon=FluentIcon.DELETE)
        self.remove_attachment_btn.clicked.connect(self._remove_selected_attachment)
        self.remove_attachment_btn.setEnabled(False)
        attachment_layout.addWidget(self.remove_attachment_btn)
        layout.addLayout(attachment_layout)

        layout.addStretch()

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        save_btn = PushButton("保存", self, FluentIcon.SAVE)
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def accept(self):
        if not self.name_edit.text().strip():
            UIUtils.show_warning(
                title='警告',
                content='活动名称不能为空',
                parent=self
            )
            return
        super().accept()

    def load_activity_data(self):
        self.name_edit.setText(self.activity.name)
        self.type_combo.setCurrentText(self.activity.type.value)
        self.status_combo.setCurrentText(self.activity.status.value)
        self.organizer_edit.setText(self.activity.organizer)
        if self.activity.start_date:
            self.start_date.setDate(self.activity.start_date)
        if self.activity.end_date:
            self.end_date.setDate(self.activity.end_date)
        self.location_edit.setText(self.activity.location)
        self.participants_edit.setPlainText(self.activity.participants)
        self.description_edit.setPlainText(self.activity.description)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择附件文件", "", "所有文件 (*.*)")
        if file_path:
            self.new_attachment_path = file_path
            self.attachment_label.setText(os.path.basename(file_path))
            self.remove_attachment_btn.setEnabled(True)
            self.attachment_removed = False # If a new file is selected, it's not 'removed'

    def _remove_selected_attachment(self):
        if self.new_attachment_path: # Removing a newly selected, unsaved attachment
            self.new_attachment_path = None
            if self.current_attachment_path and os.path.exists(self.current_attachment_path):
                 self.attachment_label.setText(os.path.basename(self.current_attachment_path))
                 self.attachment_removed = False # Still has original attachment
                 self.remove_attachment_btn.setEnabled(True) # Can still remove the original one
            else:
                self.attachment_label.setText("无附件")
                self.remove_attachment_btn.setEnabled(False)
                self.attachment_removed = True # Mark for removal if no current_attachment_path
        elif self.current_attachment_path: # Removing an existing, saved attachment
            self.attachment_label.setText("无附件 (待移除)")
            self.attachment_removed = True
            self.new_attachment_path = None # Ensure new_attachment_path is None
            self.remove_attachment_btn.setEnabled(False)

    def get_attachment_state(self):
        """Determines the action to take for the attachment."""
        if self.attachment_removed:
            if self.current_attachment_path:
                return ('delete', self.current_attachment_path, None)
            else:
                return ('none', None, None)
        elif self.new_attachment_path:
            if self.current_attachment_path and os.path.normpath(self.current_attachment_path) != os.path.normpath(self.new_attachment_path):
                return ('replace', self.current_attachment_path, self.new_attachment_path)
            elif not self.current_attachment_path:
                return ('add', None, self.new_attachment_path)
        return ('none', None, None) # No change or new is same as old
        if self.activity and hasattr(self.activity, 'attachment_path') and self.activity.attachment_path and os.path.exists(self.activity.attachment_path):
            self.attachment_label.setText(os.path.basename(self.activity.attachment_path))
            self.remove_attachment_btn.setEnabled(True)
            self.current_attachment_path = self.activity.attachment_path
        else:
            self.attachment_label.setText("无附件")
            self.remove_attachment_btn.setEnabled(False)
            self.current_attachment_path = None

class ActivityInterface(QWidget):
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent=parent)
        self.engine = engine
        self.all_activities = []
        self.current_activities = []
        self.setup_ui()
        self.load_activities()

    def _get_activity(self, session, activity_id):
        """获取活动对象的辅助函数，供attachment_utils使用"""
        return session.query(AcademicActivity).get(activity_id)

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18)
        self.main_layout.setSpacing(10)

        # 标题
        title_layout = QHBoxLayout()
        title_label = TitleLabel("学术活动", self)
        title_label.setToolTip("用于创建和管理学术活动信息")
        title_label.installEventFilter(ToolTipFilter(title_label, showDelay=300, position=ToolTipPosition.RIGHT))
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        self.main_layout.addLayout(title_layout)

        # 按钮栏
        add_btn = UIUtils.create_action_button("添加活动", FluentIcon.ADD)
        edit_btn = UIUtils.create_action_button("编辑活动", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除活动", FluentIcon.DELETE)

        add_btn.clicked.connect(self.add_activity)
        edit_btn.clicked.connect(self.edit_activity)
        delete_btn.clicked.connect(self.delete_activity)

        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        self.main_layout.addLayout(button_layout)

        # 活动列表
        self.activity_table = TableWidget()
        self.activity_table.setColumnCount(9)
        self.activity_table.setHorizontalHeaderLabels([
            "活动名称", "类型", "状态", "主办方", "开始日期",
            "结束日期", "活动地点", "参与人员", "活动附件"
        ])

        self.activity_table.setWordWrap(False)
        self.activity_table.setItemDelegate(TableItemDelegate(self.activity_table))
        UIUtils.set_table_style(self.activity_table)

        header = self.activity_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True)

        header.resizeSection(0, 200)  # 活动名称
        header.resizeSection(1, 80)   # 类型
        header.resizeSection(2, 80)   # 状态
        header.resizeSection(3, 150)  # 主办方
        header.resizeSection(4, 92)   # 开始日期
        header.resizeSection(5, 92)   # 结束日期
        header.resizeSection(6, 110)  # 活动地点
        header.resizeSection(7, 200)  # 参与人员
        header.resizeSection(8, 80)   # 活动附件

        header.setSectionsMovable(True)
        self.activity_table.setSelectionMode(TableWidget.ExtendedSelection)
        self.activity_table.setSelectionBehavior(TableWidget.SelectRows)

        self.main_layout.addWidget(self.activity_table)

        vheader = self.activity_table.verticalHeader()        
        vheader.setDefaultAlignment(Qt.AlignCenter)

        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索活动")
        self.search_edit.textChanged.connect(self.apply_filters)
        search_layout.addWidget(self.search_edit)

        self.type_filter = ComboBox()
        self.type_filter.addItem("全部类型")
        for type_enum in ActivityType:
            self.type_filter.addItem(type_enum.value)
        self.type_filter.currentTextChanged.connect(self.apply_filters)
        search_layout.addWidget(self.type_filter)

        self.status_filter = ComboBox()
        self.status_filter.addItem("全部状态")
        for status_enum in ActivityStatus:
            self.status_filter.addItem(status_enum.value)
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        search_layout.addWidget(self.status_filter)

        search_layout.addWidget(QLabel("活动日期:"))
        self.start_date = CompactDateEdit()
        self.end_date = CompactDateEdit()
        self.start_date.setDate(QDate(QDate.currentDate().year(), 1, 1))
        self.end_date.setDate(QDate.currentDate())
        self.start_date.dateChanged.connect(self.apply_filters)
        self.end_date.dateChanged.connect(self.apply_filters)

        search_layout.addWidget(self.start_date)
        search_layout.addWidget(QLabel("至"))
        search_layout.addWidget(self.end_date)

        reset_btn = PushButton("重置筛选")
        reset_btn.clicked.connect(self.reset_filters)
        search_layout.addWidget(reset_btn)

        search_layout.addSpacing(10)

        export_excel_btn = PushButton("导出信息")
        export_excel_btn.clicked.connect(self.export_activity_excel)
        search_layout.addWidget(export_excel_btn)

        export_attachment_btn = PushButton("导出材料")
        export_attachment_btn.clicked.connect(self.export_activity_attachments)
        search_layout.addWidget(export_attachment_btn)

        self.main_layout.addLayout(search_layout)

        # 添加右键菜单
        self.activity_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.activity_table.customContextMenuRequested.connect(self.show_activity_context_menu)

    def load_activities(self):
        self.all_activities = []
        self.current_activities = []
        self.activity_table.setRowCount(0)

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            self.all_activities = session.query(AcademicActivity).order_by(
                AcademicActivity.start_date.desc()
            ).all()
            self.current_activities = self.all_activities[:]
            self._populate_table(self.current_activities)
        except Exception as e:
            UIUtils.show_error(self, "错误", f"加载活动数据失败: {e}")
            print(f"Error loading activities: {e}")
        finally:
            session.close()

    def _populate_table(self, activities_list):
        self.activity_table.setSortingEnabled(False)
        self.activity_table.setRowCount(len(activities_list))

        for row, activity in enumerate(activities_list):
            # 活动名称
            name_item = QTableWidgetItem(activity.name)
            name_item.setData(Qt.UserRole, activity.id)
            self.activity_table.setItem(row, 0, name_item)

            # 类型
            type_item = QTableWidgetItem(activity.type.value)
            self.activity_table.setItem(row, 1, type_item)

            # 状态
            status_item = QTableWidgetItem(activity.status.value)
            self.activity_table.setItem(row, 2, status_item)

            # 主办方
            organizer_item = QTableWidgetItem(activity.organizer or "")
            self.activity_table.setItem(row, 3, organizer_item)

            # 开始日期
            start_date = activity.start_date.strftime("%Y-%m-%d") if activity.start_date else ""
            start_date_item = QTableWidgetItem(start_date)
            self.activity_table.setItem(row, 4, start_date_item)

            # 结束日期
            end_date = activity.end_date.strftime("%Y-%m-%d") if activity.end_date else ""
            end_date_item = QTableWidgetItem(end_date)
            self.activity_table.setItem(row, 5, end_date_item)

            # 活动地点
            location_item = QTableWidgetItem(activity.location or "")
            self.activity_table.setItem(row, 6, location_item)

            # 参与人员
            participants_item = QTableWidgetItem(activity.participants or "")
            self.activity_table.setItem(row, 7, participants_item)

            # 活动附件
            attachment_widget_container = create_attachment_button(
                item_id=activity.id,
                attachment_path=activity.attachment_path,
                handle_attachment_func=lambda event, btn: handle_attachment(
                    event, btn, btn.property("item_id"), "activity", 
                    sessionmaker(bind=self.engine), self, self._get_activity, 
                    "attachment_path", None, "activities"
                ),
                parent_widget=self,
                item_type='activity' # Clarify item type
            )
            self.activity_table.setCellWidget(row, 8, attachment_widget_container)

        self.activity_table.setSortingEnabled(True)

    def add_activity(self):
        dialog = ActivityDialog(self)
        if dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                new_activity = AcademicActivity(
                    name=dialog.name_edit.text(),
                    type=ActivityType(dialog.type_combo.currentText()),
                    status=ActivityStatus(dialog.status_combo.currentText()),
                    organizer=dialog.organizer_edit.text(),
                    start_date=dialog.start_date.date().toPython(),
                    end_date=dialog.end_date.date().toPython(),
                    location=dialog.location_edit.text(),
                    participants=dialog.participants_edit.toPlainText(),
                    description=dialog.description_edit.toPlainText(),
                    attachment_path=None # Placeholder, will be updated below
                )

                attachment_action, _, new_selected_path = dialog.get_attachment_state()
                if attachment_action == 'add':
                    generated_path = self._generate_activity_path(new_activity.type, new_selected_path)
                    if generated_path:
                        try:
                            shutil.copy2(new_selected_path, generated_path)
                            new_activity.attachment_path = generated_path
                        except Exception as e:
                            UIUtils.show_error(self, "附件错误", f"保存附件失败: {e}")
                    else:
                        UIUtils.show_error(self, "附件错误", "无法生成附件路径")
                
                session.add(new_activity)
                session.commit()
                UIUtils.show_success(self, "成功", "活动添加成功")
                self.load_activities()
            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "错误", f"添加活动失败: {e}")
            finally:
                session.close()

    def edit_activity(self):
        selected_items = self.activity_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请选择要编辑的活动")
            return

        row = selected_items[0].row()
        activity_id = self.activity_table.item(row, 0).data(Qt.UserRole)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            activity = session.query(AcademicActivity).get(activity_id)
            if activity:
                dialog = ActivityDialog(self, activity)
                if dialog.exec():
                    activity.name = dialog.name_edit.text()
                    activity.type = ActivityType(dialog.type_combo.currentText())
                    activity.status = ActivityStatus(dialog.status_combo.currentText())
                    activity.organizer = dialog.organizer_edit.text()
                    activity.start_date = dialog.start_date.date().toPython()
                    activity.end_date = dialog.end_date.date().toPython()
                    activity.location = dialog.location_edit.text()
                    activity.participants = dialog.participants_edit.toPlainText()
                    activity.description = dialog.description_edit.toPlainText()

                    attachment_action, old_path_db, new_selected_path_dialog = dialog.get_attachment_state()
                    
                    if attachment_action == 'add': 
                        generated_path = self._generate_activity_path(activity.type, new_selected_path_dialog)
                        if generated_path:
                            try:
                                shutil.copy2(new_selected_path_dialog, generated_path)
                                activity.attachment_path = generated_path
                            except Exception as e:
                                UIUtils.show_error(self, "附件错误", f"保存新附件失败: {e}")
                        else:
                            UIUtils.show_error(self, "附件错误", "无法生成新附件路径")
                    elif attachment_action == 'replace': 
                        generated_path = self._generate_activity_path(activity.type, new_selected_path_dialog)
                        if generated_path:
                            try:
                                shutil.copy2(new_selected_path_dialog, generated_path)
                                if old_path_db and os.path.exists(old_path_db) and os.path.normpath(old_path_db) != os.path.normpath(generated_path):
                                    try:
                                        os.remove(old_path_db)
                                    except OSError as e_remove:
                                        print(f"Error removing old attachment {old_path_db}: {e_remove}")
                                activity.attachment_path = generated_path
                            except Exception as e:
                                UIUtils.show_error(self, "附件错误", f"替换附件失败: {e}")
                        else:
                            UIUtils.show_error(self, "附件错误", "无法生成替换附件路径")
                    elif attachment_action == 'delete': 
                        if old_path_db and os.path.exists(old_path_db):
                            try:
                                os.remove(old_path_db)
                                activity.attachment_path = None
                            except Exception as e:
                                UIUtils.show_error(self, "附件错误", f"删除旧附件失败: {e}")
                        else:
                             activity.attachment_path = None

                    session.commit()
                    UIUtils.show_success(self, "成功", "活动更新成功")
                    self.load_activities()
        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "错误", f"更新活动失败: {e}")
        finally:
            session.close()

    def delete_activity(self):
        selected_items = self.activity_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请选择要删除的活动")
            return

        if not UIUtils.show_confirm(self, "确认", "确定要删除选中的活动吗？"):
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            rows = set(item.row() for item in selected_items)
            for row in rows:
                activity_id = self.activity_table.item(row, 0).data(Qt.UserRole)
                activity = session.query(AcademicActivity).get(activity_id)
                if activity:
                    if activity.attachment_path and os.path.exists(activity.attachment_path):
                        try:
                            os.remove(activity.attachment_path)
                            print(f"Successfully removed attachment file: {activity.attachment_path}")
                        except Exception as e:
                            print(f"Error removing attachment file {activity.attachment_path}: {e}")
                            UIUtils.show_warning(self, "附件删除警告", f"无法删除附件文件: {os.path.basename(activity.attachment_path)}. 活动记录仍将删除。")
                    session.delete(activity)
            session.commit()
            UIUtils.show_success(self, "成功", "活动删除成功")
            self.load_activities()
        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "错误", f"删除活动失败: {e}")
        finally:
            session.close()

    def apply_filters(self):
        filtered_activities = self.all_activities[:]

        # 关键词搜索
        search_text = self.search_edit.text().lower()
        if search_text:
            filtered_activities = [
                activity for activity in filtered_activities
                if search_text in activity.name.lower() or
                   search_text in (activity.description or "").lower() or
                   search_text in (activity.participants or "").lower() or
                   search_text in (activity.location or "").lower()
            ]

        # 类型筛选
        selected_type = self.type_filter.currentText()
        if selected_type != "全部类型":
            filtered_activities = [
                activity for activity in filtered_activities
                if activity.type.value == selected_type
            ]

        # 状态筛选
        selected_status = self.status_filter.currentText()
        if selected_status != "全部状态":
            filtered_activities = [
                activity for activity in filtered_activities
                if activity.status.value == selected_status
            ]

        # 日期范围筛选
        start_date = self.start_date.date().toPython()
        end_date = self.end_date.date().toPython()
        filtered_activities = [
            activity for activity in filtered_activities
            if activity.start_date and start_date <= activity.start_date <= end_date
        ]

        self.current_activities = filtered_activities
        self._populate_table(self.current_activities)

    def reset_filters(self):
        self.search_edit.clear()
        self.type_filter.setCurrentText("全部类型")
        self.status_filter.setCurrentText("全部状态")
        self.start_date.setDate(QDate(QDate.currentDate().year(), 1, 1))
        self.end_date.setDate(QDate.currentDate())
        self.current_activities = self.all_activities[:]
        self._populate_table(self.current_activities)

    def show_activity_context_menu(self, pos):
        selected_items = self.activity_table.selectedItems()
        if not selected_items:
            return

        menu = RoundMenu(parent=self)

        # 获取选中的行
        row = selected_items[0].row()
        activity_id = self.activity_table.item(row, 0).data(Qt.UserRole)

        # 添加菜单项
        edit_action = Action(FluentIcon.EDIT, "编辑活动")
        edit_action.triggered.connect(self.edit_activity)
        menu.addAction(edit_action)

        delete_action = Action(FluentIcon.DELETE, "删除活动")
        delete_action.triggered.connect(self.delete_activity)
        menu.addAction(delete_action)

        menu.addSeparator()

        # 附件操作 - 使用通用的attachment_utils函数
        menu.addSeparator()
        
        Session_ctx = sessionmaker(bind=self.engine)
        session_ctx = Session_ctx()
        activity_for_menu = session_ctx.query(AcademicActivity).get(activity_id)
        has_attachment = activity_for_menu and activity_for_menu.attachment_path and os.path.exists(activity_for_menu.attachment_path)
        session_ctx.close() # 关闭用于检查附件状态的会话
        
        if has_attachment:
            view_attach_action = Action(FluentIcon.VIEW, "查看附件", self)
            view_attach_action.triggered.connect(lambda checked, aid=activity_id: 
                execute_attachment_action("view", aid, None, None, None, 
                                         self._get_activity, "attachment_path", 
                                         None, "activities", self))
            menu.addAction(view_attach_action)

            download_attach_action = Action(FluentIcon.DOWNLOAD, "下载附件", self)
            download_attach_action.triggered.connect(lambda checked, aid=activity_id: 
                execute_attachment_action("download", aid, None, None, None, 
                                         self._get_activity, "attachment_path", 
                                         None, "activities", self))
            menu.addAction(download_attach_action)

            replace_attach_action = Action(FluentIcon.SYNC, "替换附件", self)
            replace_attach_action.triggered.connect(lambda checked, aid=activity_id: 
                execute_attachment_action("replace", aid, None, None, None, 
                                         self._get_activity, "attachment_path", 
                                         None, "activities", self))
            menu.addAction(replace_attach_action)

            delete_attach_action = Action(FluentIcon.DELETE, "删除附件", self)
            delete_attach_action.triggered.connect(lambda checked, aid=activity_id: 
                execute_attachment_action("delete", aid, None, None, None, 
                                         self._get_activity, "attachment_path", 
                                         None, "activities", self))
            menu.addAction(delete_attach_action)
        else:
            upload_attach_action = Action(FluentIcon.UPLOAD, "上传附件", self)
            upload_attach_action.triggered.connect(lambda checked, aid=activity_id: 
                execute_attachment_action("replace", aid, None, None, None, 
                                         self._get_activity, "attachment_path", 
                                         None, "activities", self))
            menu.addAction(upload_attach_action)
        
        # session_ctx will be closed by _execute_activity_attachment_action if it creates its own session
        # or used and closed if passed and close_session_locally is true there.
        # However, to be safe, if _execute_activity_attachment_action doesn't run (e.g. menu closed before action), close here.
        # This is tricky. Let's make _execute_activity_attachment_action always manage its session or take one it doesn't close.
        # For now, the lambda will pass the session, and _execute will use it.
        # The session should be closed after the menu action is done.
        # A better way: connect to a slot that then calls _execute_activity_attachment_action, ensuring session is managed per call.

        # Simplified: _execute_activity_attachment_action will manage its own session if one isn't passed or is inactive.
        # The lambdas pass the session_ctx. If the action is triggered, it's used. If not, it should be closed.
        # To ensure closure, we can connect a cleanup to the menu's aboutToHide signal or similar.
        # For now, relying on _execute_activity_attachment_action to handle the passed session correctly.
        # If an action is triggered, the session is passed. If the menu is dismissed, the session might linger.
        # Let's ensure _execute_activity_attachment_action closes the session if it's passed and it's the one responsible.
        # The current logic in _execute_activity_attachment_action: if session_param is passed and active, it uses it but doesn't close it.
        # This is problematic for context menu. So, for context menu, we should NOT pass the session.
        # Let _execute_activity_attachment_action create and close its own session for context menu calls.

        # 显示菜单

        # 显示菜单
        menu.exec(self.activity_table.viewport().mapToGlobal(pos))

    # 已移除_handle_activity_attachment_action函数
    # 该函数已被attachment_utils.py中的handle_attachment函数替代

    # 已移除_execute_activity_attachment_action函数
    # 该函数已被attachment_utils.py中的execute_attachment_action函数替代

    def view_activity_attachment(self, file_path):
        # This method might become obsolete or call _execute_activity_attachment_action
        self._execute_activity_attachment_action("view", self.activity_table.item(self.activity_table.currentRow(),0).data(Qt.UserRole) if self.activity_table.currentRow() != -1 else None, None)

    def download_activity_attachment(self, file_path):
        # This method might become obsolete or call _execute_activity_attachment_action
        self._execute_activity_attachment_action("download", self.activity_table.item(self.activity_table.currentRow(),0).data(Qt.UserRole) if self.activity_table.currentRow() != -1 else None, None)

    def export_activity_excel(self):
        if not self.current_activities:
            UIUtils.show_warning(self, "警告", "没有可导出的活动数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出活动信息", "",
            "Excel Files (*.xlsx);;All Files (*)"
        )

        if not file_path:
            return

        try:
            data = []
            for activity in self.current_activities:
                data.append({
                    "活动名称": activity.name,
                    "活动类型": activity.type.value,
                    "活动状态": activity.status.value,
                    "主办方": activity.organizer,
                    "开始日期": activity.start_date,
                    "结束日期": activity.end_date,
                    "活动地点": activity.location,
                    "参与人员": activity.participants,
                    "活动描述": activity.description
                })

            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False, engine='openpyxl')
            UIUtils.show_success(self, "成功", "活动信息导出成功")
        except Exception as e:
            UIUtils.show_error(self, "错误", f"导出失败: {e}")

    def export_activity_attachments(self):
        if not self.current_activities:
            UIUtils.show_warning(self, "警告", "没有可导出的活动附件")
            return

        # 选择导出目录
        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not export_dir:
            return

        try:
            exported_count = 0
            for activity in self.current_activities:
                if activity.attachment_path and os.path.exists(activity.attachment_path):
                    # 构建目标文件路径
                    file_name = os.path.basename(activity.attachment_path)
                    target_path = os.path.join(export_dir, file_name)

                    # 如果文件已存在，添加时间戳
                    if os.path.exists(target_path):
                        name, ext = os.path.splitext(file_name)
                        target_path = os.path.join(
                            export_dir,
                            f"{name}_{get_timestamp_str()}{ext}"
                        )

                    # 复制文件
                    shutil.copy2(activity.attachment_path, target_path)
                    exported_count += 1

            if exported_count > 0:
                UIUtils.show_success(
                    self, "成功",
                    f"成功导出 {exported_count} 个活动附件"
                )
            else:
                UIUtils.show_info(
                    self, "提示",
                    "当前筛选结果中没有可导出的活动附件"
                )
        except Exception as e:
            UIUtils.show_error(self, "错误", f"导出材料失败: {e}")