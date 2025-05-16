import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidgetItem, QDialog, QHeaderView, QFileDialog, QApplication
from PySide6.QtCore import Qt, QPoint, QDate
from PySide6.QtGui import QIcon
from qfluentwidgets import TitleLabel, FluentIcon, LineEdit, ComboBox, DateEdit, CompactDateEdit, BodyLabel, PushButton, TableWidget, TableItemDelegate, Dialog, RoundMenu, Action, PlainTextEdit
from ..utils.ui_utils import UIUtils
from ..models.database import Base, sessionmaker, Actionlog
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, Engine
from enum import Enum
from datetime import datetime
from ..utils.attachment_utils import (
    create_attachment_button,
    sanitize_filename, ensure_directory_exists, get_timestamp_str, get_attachment_icon_path,
    view_attachment, download_attachment, ROOT_DIR
)
from ..utils.filter_utils import FilterUtils
import pandas as pd

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

class ActivityDialog(QDialog):
    def __init__(self, parent=None, activity=None):
        super().__init__(parent)
        self.activity = activity
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

class ActivityInterface(QWidget):
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent=parent)
        self.engine = engine
        self.all_activities = []
        self.current_activities = []
        self.setup_ui()
        self.load_activities()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18)
        self.main_layout.setSpacing(10)

        # 标题
        title_layout = QHBoxLayout()
        title_label = TitleLabel("学术活动", self)
        title_label.setToolTip("用于创建和管理学术活动信息")
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
            "结束日期", "活动地点", "参与人员", "活动材料"
        ])

        self.activity_table.setWordWrap(False)
        self.activity_table.setItemDelegate(TableItemDelegate(self.activity_table))
        UIUtils.set_table_style(self.activity_table)

        header = self.activity_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self.sort_table)

        header.resizeSection(0, 200)  # 活动名称
        header.resizeSection(1, 80)   # 类型
        header.resizeSection(2, 80)   # 状态
        header.resizeSection(3, 150)  # 主办方
        header.resizeSection(4, 92)   # 开始日期
        header.resizeSection(5, 92)   # 结束日期
        header.resizeSection(6, 120)  # 活动地点
        header.resizeSection(7, 200)  # 参与人员
        header.resizeSection(8, 80)   # 活动材料

        header.setSectionsMovable(True)
        self.activity_table.setSelectionMode(TableWidget.ExtendedSelection)
        self.activity_table.setSelectionBehavior(TableWidget.SelectRows)

        self.main_layout.addWidget(self.activity_table)

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

            # 活动材料
            if activity.attachment_path:
                attachment_btn = create_attachment_button(
                    self, activity.attachment_path,
                    lambda p=activity.attachment_path: self.view_activity_attachment(p)
                )
                self.activity_table.setCellWidget(row, 8, attachment_btn)

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
                    description=dialog.description_edit.toPlainText()
                )
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
                        except Exception as e:
                            print(f"Error removing attachment: {e}")
                    session.delete(activity)
            session.commit()
            UIUtils.show_success(self, "成功", "活动删除成功")
            self.load_activities()
        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "错误", f"删除活动失败: {e}")
        finally:
            session.close()

    def sort_table(self, column):
        self.activity_table.sortItems(column)

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

        # 如果有附件，添加附件相关操作
        attachment_path = None
        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            activity = session.query(AcademicActivity).get(activity_id)
            if activity:
                attachment_path = activity.attachment_path
        finally:
            session.close()

        if attachment_path:
            menu.addSeparator()
            view_action = Action(FluentIcon.DOCUMENT, "查看材料")
            view_action.triggered.connect(
                lambda: self.view_activity_attachment(attachment_path)
            )
            menu.addAction(view_action)

            download_action = Action(FluentIcon.DOWNLOAD, "下载材料")
            download_action.triggered.connect(
                lambda: self.download_activity_attachment(attachment_path)
            )
            menu.addAction(download_action)

        # 显示菜单
        menu.exec(self.activity_table.viewport().mapToGlobal(pos))

    def view_activity_attachment(self, file_path):
        view_attachment(file_path)

    def download_activity_attachment(self, file_path):
        download_attachment(file_path)

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
            UIUtils.show_warning(self, "警告", "没有可导出的活动材料")
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
                    f"成功导出 {exported_count} 个活动材料"
                )
            else:
                UIUtils.show_info(
                    self, "提示",
                    "当前筛选结果中没有可导出的活动材料"
                )
        except Exception as e:
            UIUtils.show_error(self, "错误", f"导出材料失败: {e}")