import os # Ensure os is imported
import shutil # Ensure shutil is imported
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QFileDialog, QDialog, QLabel, QHeaderView, QApplication # Import QApplication
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QFont, QIcon
from qfluentwidgets import TitleLabel, FluentIcon, ComboBox, LineEdit, InfoBar, Dialog, BodyLabel, PushButton, TableWidget, TableItemDelegate, RoundMenu, Action, PlainTextEdit
from ...models.database import Project, sessionmaker
from ...utils.ui_utils import UIUtils
from ...models.database import Base, get_engine # Project and sessionmaker already imported
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum as SQLEnum, DateTime, Engine
from enum import Enum
from datetime import datetime
from ...utils.attachment_utils import (
    create_attachment_button, # Keep
    sanitize_filename, ensure_directory_exists, get_timestamp_str, get_attachment_icon_path,
    view_attachment, download_attachment, ROOT_DIR # Import necessary utils
)
from ...utils.filter_utils import FilterUtils # Import FilterUtils


class DocumentType(Enum):
    APPLICATION = "申请材料"
    INITIATION = "开题材料"
    CONTRACT = "合同/任务书"
    RESEARCH_DATA = "研究数据"
    PROGRESS = "进展报告"
    OUTSOURCING = "外协材料"
    QUALITY = "质量管理"
    FINALIZATION = "结题材料"
    MEETING = "会议纪要"
    OTHER = "其他"

class ProjectDocument(Base):
    __tablename__ = 'project_documents'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(100), nullable=False)  # 文档名称
    doc_type = Column(SQLEnum(DocumentType), nullable=False)  # 文档类型
    version = Column(String(20))  # 版本号
    description = Column(String(500))  # 文档描述
    file_path = Column(String(500))  # 文件路径
    upload_time = Column(DateTime, default=datetime.now)  # 上传时间
    keywords = Column(String(200))  # 关键词，用于检索

class DocumentDialog(QDialog):
    def __init__(self, parent=None, document=None):
        self.document = document
        super().__init__(parent)
        self.setWindowTitle("文档信息")
        self.setup_ui()
        if document:
            self.load_document_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10) # Adjust spacing to match ExpenseDialog

        # 文档名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel("文档名称:"))
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("请输入文档名称，必填")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # 文档类型
        type_layout = QHBoxLayout()
        type_layout.addWidget(BodyLabel("文档类型:"))
        self.type_combo = ComboBox()
        for doc_type in DocumentType:
            self.type_combo.addItem(doc_type.value)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # 版本号
        version_layout = QHBoxLayout()
        version_layout.addWidget(BodyLabel("版 本 号 :")) # Align label width
        self.version_edit = LineEdit()
        self.version_edit.setPlaceholderText("请输入版本号")
        version_layout.addWidget(self.version_edit)
        layout.addLayout(version_layout)

        # 关键词
        keywords_layout = QHBoxLayout()
        keywords_layout.addWidget(BodyLabel("关 键 词 :")) # Align label width
        self.keywords_edit = LineEdit()
        self.keywords_edit.setPlaceholderText("请输入关键词（用逗号分隔）")
        keywords_layout.addWidget(self.keywords_edit)
        layout.addLayout(keywords_layout)

        # 文档描述
        description_layout = QHBoxLayout()
        description_layout.addWidget(BodyLabel("文档描述:"))
        self.description_edit = PlainTextEdit()
        self.description_edit.setPlaceholderText("请输入文档描述")
        self.description_edit.setFixedHeight(120)
        description_layout.addWidget(self.description_edit)
        layout.addLayout(description_layout)

        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(BodyLabel("选择文件:"))
        self.file_path_edit = LineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("点击右侧按钮选择文件") # Add placeholder
        file_layout.addWidget(self.file_path_edit)
        select_file_btn = PushButton("选择文件", self, FluentIcon.FOLDER) # Use PushButton with icon
        select_file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(select_file_btn)
        layout.addLayout(file_layout)

        layout.addStretch() # Add stretch before buttons

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        save_btn = PushButton("保存", self, FluentIcon.SAVE) # Already PushButton, ensure correct icon
        cancel_btn = PushButton("取消", self, FluentIcon.CLOSE) # Already PushButton, ensure correct icon
        save_btn.clicked.connect(self.accept) # Connect accept for validation
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch() # Push buttons to the right
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            self.file_path_edit.setText(file_path)

    def accept(self):
        """Validate input before accepting the dialog."""
        if not self.name_edit.text().strip():
            UIUtils.show_warning(
                title='警告',
                content='文档名称不能为空',
                parent=self
            )
            return
        if not self.document and not self.file_path_edit.text():
             UIUtils.show_warning(
                title='警告',
                content='请选择要上传的文件',
                parent=self
            )
             return
        super().accept()

    def load_document_data(self):
        self.name_edit.setText(self.document.name)
        self.type_combo.setCurrentText(self.document.doc_type.value)
        self.version_edit.setText(self.document.version)
        self.description_edit.setPlainText(self.document.description or "") # Use setPlainText and handle None
        self.keywords_edit.setText(self.document.keywords)
        self.file_path_edit.setText(self.document.file_path)

class ProjectDocumentWidget(QWidget):
    def __init__(self, engine: Engine, parent=None):
        super().__init__(parent=parent)
        self.engine = engine
        self.current_project = None
        self.all_documents = [] # Store all loaded documents
        self.current_documents = [] # Store currently displayed documents
        self.setup_ui()

    def showEvent(self, event):
        """在窗口显示时连接信号"""
        super().showEvent(event)
        # 尝试连接信号
        try:
            main_window = self.window()
            if main_window and hasattr(main_window, 'project_updated'):
                # 先断开旧连接，防止重复连接
                try:
                    main_window.project_updated.disconnect(self._refresh_project_selector)
                except RuntimeError:
                    pass # 信号未连接，忽略错误
                main_window.project_updated.connect(self._refresh_project_selector)
                # print("ProjectDocumentWidget: Connected to project_updated signal.") # Removed print
            else:
                 # print("ProjectDocumentWidget: Could not find main window or project_updated signal.") # Removed print
                 pass # Do nothing if signal not found
        except Exception as e:
            # print(f"ProjectDocumentWidget: Error connecting signal: {e}") # Removed print
            pass # Ignore connection errors silently

    def _refresh_project_selector(self):
        """刷新项目选择下拉框的内容"""
        # print("ProjectDocumentWidget: Refreshing project selector...") # Removed print
        if not hasattr(self, 'project_selector') or not self.engine:
            # print("ProjectDocumentWidget: Project selector or engine not initialized.") # Removed print
            return

        current_project_id = None
        if self.current_project: # 使用 self.current_project 存储的ID
            current_project_id = self.current_project.id

        self.project_selector.clear()
        self.project_selector.addItem("请选择项目...", userData=None) # 添加默认提示项

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            projects = session.query(Project).order_by(Project.financial_code).all()
            if not projects:
                self.project_selector.addItem("没有找到项目", userData=None)
                self.project_selector.setEnabled(False)
            else:
                self.project_selector.setEnabled(True)
                for project in projects:
                    self.project_selector.addItem(f"{project.financial_code} ", userData=project)

                # 尝试恢复之前的选择
                if current_project_id is not None:
                    for i in range(self.project_selector.count()):
                        data = self.project_selector.itemData(i)
                        if isinstance(data, Project) and data.id == current_project_id:
                            self.project_selector.setCurrentIndex(i)
                            break
                    else:
                        # 如果之前的项目找不到了（可能被删除），则触发一次选中事件以清空表格
                        self._on_project_selected(0) # 选中 "请选择项目..."

        except Exception as e:
            # print(f"Error refreshing project selector in DocumentWidget: {e}") # Removed print
            self.project_selector.addItem("加载项目出错", userData=None)
            self.project_selector.setEnabled(False)
        finally:
            session.close()
            # print("ProjectDocumentWidget: Project selector refreshed.") # Removed print

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(18, 18, 18, 18) # Add some margins
        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目文档-", self)
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.main_layout.addLayout(selector_layout)
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)

        # 按钮栏
        add_btn = UIUtils.create_action_button("添加文档", FluentIcon.ADD)
        edit_btn = UIUtils.create_action_button("编辑文档", FluentIcon.EDIT)
        delete_btn = UIUtils.create_action_button("删除文档", FluentIcon.DELETE)


        add_btn.clicked.connect(self.add_document)
        edit_btn.clicked.connect(self.edit_document)
        delete_btn.clicked.connect(self.delete_document)


        button_layout = UIUtils.create_button_layout(add_btn, edit_btn, delete_btn)
        self.main_layout.addLayout(button_layout)

        # 文档列表
        self.document_table = TableWidget()
        self.document_table.setColumnCount(7) # 移除上传人列，总列数减1
        self.document_table.setHorizontalHeaderLabels([
            "文档名称", "类型", "版本", "关键词", # 调整顺序
            "上传时间", "描述", "文档附件" # 调整顺序，移除上传人
        ])
        # 设置表格样式
        self.document_table.setWordWrap(False)
        self.document_table.setItemDelegate(TableItemDelegate(self.document_table))
        UIUtils.set_table_style(self.document_table) # 应用通用样式

        # 设置列宽模式和排序
        header = self.document_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True) # 启用排序
        header.sectionClicked.connect(self.sort_table) # 连接排序信号

        # 隐藏行号

        # 设置初始列宽 (需要调整以适应新列)
        header.resizeSection(0, 310) # 文档名称
        header.resizeSection(1, 100) # 类型
        header.resizeSection(2, 80)  # 版本
        header.resizeSection(3, 120) # 关键词 (索引改为3)
        header.resizeSection(4, 125) # 上传时间 (索引改为4)
        header.resizeSection(5, 250) # 描述 (索引改为5)
        header.resizeSection(6, 80)  # 附件列 (索引改为6)

    # 允许用户调整列宽和移动列
        header.setSectionsMovable(True)

        self.document_table.setSelectionMode(TableWidget.ExtendedSelection)
        self.document_table.setSelectionBehavior(TableWidget.SelectRows)

        self.main_layout.addWidget(self.document_table)

        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("输入关键词搜索文档")
        self.search_edit.textChanged.connect(self.apply_filters) # Connect to new filter method
        search_layout.addWidget(self.search_edit)

        self.type_filter = ComboBox()
        self.type_filter.addItem("全部类型")
        for doc_type in DocumentType:
            self.type_filter.addItem(doc_type.value)
        self.type_filter.currentTextChanged.connect(self.apply_filters) # Connect to new filter method
        search_layout.addWidget(self.type_filter)

        reset_btn = PushButton("重置筛选")
        reset_btn.clicked.connect(self.reset_filters)
        search_layout.addWidget(reset_btn)
        self.main_layout.addLayout(search_layout)

        self.document_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.document_table.customContextMenuRequested.connect(self.show_document_context_menu)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_project = self.project_selector.itemData(index)
        if selected_project and isinstance(selected_project, Project):
            self.current_project = selected_project
            # print(f"DocumentWidget: Project selected - {self.current_project.name}") # Removed print
            self.load_documents() # Load documents for the selected project
        else:
            self.current_project = None
            self.document_table.setRowCount(0) # Clear table if no project selected
            # print("DocumentWidget: No valid project selected.") # Removed print

    def load_documents(self):
        """Loads all documents for the current project into memory and populates the table."""
        self.all_documents = []
        self.current_documents = []
        self.document_table.setRowCount(0)
        if not self.current_project:
            # print("DocumentWidget: No project selected, cannot load documents.") # Removed print
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()

        try:
            # print(f"DocumentWidget: Loading documents for project ID: {self.current_project.id}") # Removed print
            self.all_documents = session.query(ProjectDocument).filter(
                ProjectDocument.project_id == self.current_project.id
            ).order_by(ProjectDocument.upload_time.desc()).all()
            self.current_documents = self.all_documents[:] # Initial view shows all
            self._populate_table(self.current_documents)
        finally:
            session.close()

    def _populate_table(self, documents_list):
        """Populates the table based on the provided list of ProjectDocument objects."""
        self.document_table.setSortingEnabled(False)
        self.document_table.setRowCount(0)

        for row, doc in enumerate(documents_list):
            self.document_table.insertRow(row)

            name_item = QTableWidgetItem(doc.name)
            name_item.setData(Qt.UserRole, doc.id) # Store ID here
            self.document_table.setItem(row, 0, name_item)
            type_item = QTableWidgetItem(doc.doc_type.value); type_item.setTextAlignment(Qt.AlignCenter); self.document_table.setItem(row, 1, type_item)
            version_item = QTableWidgetItem(doc.version or ""); version_item.setTextAlignment(Qt.AlignCenter); self.document_table.setItem(row, 2, version_item)
            keywords_item = QTableWidgetItem(doc.keywords or ""); self.document_table.setItem(row, 3, keywords_item)
            upload_time_str = doc.upload_time.strftime("%Y-%m-%d %H:%M") if doc.upload_time else ""
            upload_time_item = QTableWidgetItem(upload_time_str); upload_time_item.setTextAlignment(Qt.AlignCenter)
            upload_time_item.setData(Qt.UserRole + 1, doc.upload_time) # Store datetime for sorting
            self.document_table.setItem(row, 4, upload_time_item)
            description_item = QTableWidgetItem(doc.description or ""); self.document_table.setItem(row, 5, description_item)

            container = create_attachment_button(
                item_id=doc.id,
                attachment_path=doc.file_path,
                handle_attachment_func=self.handle_document_attachment, # Pass the method reference directly
                parent_widget=self,
                item_type='document'
            )
            self.document_table.setCellWidget(row, 6, container) # 附件列索引从7改为6

        self.document_table.setSortingEnabled(True)

    def apply_filters(self):
        """Applies filters based on search keyword and type, updates the table."""

        keyword = self.search_edit.text() # Keep original case for potential future needs, FilterUtils handles lowercasing
        doc_type_filter = self.type_filter.currentText()

        filter_criteria = {
            'keyword': keyword,
            'keyword_attributes': ['name', 'description', 'keywords'], # Removed 'uploader'
            'doc_type': doc_type_filter
        }

        attribute_mapping = {
            'doc_type': 'doc_type' # Map filter key 'doc_type' to object attribute 'doc_type'
        }

        self.current_documents = FilterUtils.apply_filters(
            self.all_documents,
            filter_criteria,
            attribute_mapping
        )
        self._populate_table(self.current_documents)

    def reset_filters(self):
        """Resets filter inputs and reapplies filters."""
        self.search_edit.clear()
        self.type_filter.setCurrentText("全部类型")
        self.apply_filters() # Re-apply filters to show all items

    def _generate_document_path(self, project, doc_type_enum, original_filename):
        """Generates the specific path for a project document based on business rules."""
        if not project or not doc_type_enum or not original_filename:
            # print("Error: Missing project, document type, or filename for path generation.") # Removed print
            return None

        base_folder = "documents"
        project_code = project.financial_code if project.financial_code else "unknown_project"
        doc_type_str = sanitize_filename(doc_type_enum.value)
        timestamp = get_timestamp_str() # Get current timestamp string

        original_basename = os.path.basename(original_filename)
        base_name, ext = os.path.splitext(original_basename)
        sanitized_base_name = sanitize_filename(base_name)

        new_filename = f"{timestamp}_{sanitized_base_name}{ext}"

        target_dir = os.path.join(ROOT_DIR, base_folder, project_code, doc_type_str)
        full_path = os.path.join(target_dir, new_filename)

        return os.path.normpath(full_path)

    def add_document(self):
        if not self.current_project:
            UIUtils.show_warning(self, "警告", "请先选择一个项目")
            return

        dialog = DocumentDialog(self)
        if dialog.exec():
            source_file_path = dialog.file_path_edit.text() # Path selected by user
            if not source_file_path:
                UIUtils.show_warning(self, "警告", "请选择要上传的文件")
                return

            doc_type_enum = DocumentType(dialog.type_combo.currentText())

            new_file_path = self._generate_document_path(
                project=self.current_project,
                doc_type_enum=doc_type_enum,
                original_filename=source_file_path
            )
            if not new_file_path:
                 UIUtils.show_error(self, "错误", "无法生成文档保存路径")
                 return

            target_dir = os.path.dirname(new_file_path)
            ensure_directory_exists(target_dir)

            try:
                shutil.copy2(source_file_path, new_file_path) # Use copy2 to preserve metadata
            except Exception as e:
                UIUtils.show_error(self, "错误", f"复制文件失败: {e}")
                return

            Session = sessionmaker(bind=self.engine)
            session = Session()
            try:
                document = ProjectDocument(
                    project_id=self.current_project.id,
                    name=dialog.name_edit.text().strip(),
                    doc_type=doc_type_enum,
                    version=dialog.version_edit.text().strip(),
                    description=dialog.description_edit.toPlainText().strip(), # Use toPlainText()
                    keywords=dialog.keywords_edit.text().strip(),
                    file_path=new_file_path # Store the new path
                )
                session.add(document)
                session.commit()
                self.load_documents() # Reload documents to show the new one
                UIUtils.show_success(self, "成功", "文档添加成功")
            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "错误", f"添加文档到数据库失败: {e}")
                try:
                    os.remove(new_file_path)
                except OSError:
                    pass # Ignore error if file deletion fails
            finally:
                session.close()

    def edit_document(self):
        selected_items = self.document_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请选择要编辑的文档")
            return

        row = selected_items[0].row()
        doc_id = self.document_table.item(row, 0).data(Qt.UserRole)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            document = session.query(ProjectDocument).filter(
                ProjectDocument.id == doc_id
            ).first()

            if not document:
                UIUtils.show_warning(self, "警告", "未找到选中的文档")
                return

            dialog = DocumentDialog(self, document=document)
            dialog.file_path_edit.setEnabled(False)
            dialog.findChild(QPushButton, "选择文件").setEnabled(False) # Find button by name/type

            if dialog.exec():
                document.name = dialog.name_edit.text().strip()
                document.doc_type = DocumentType(dialog.type_combo.currentText())
                document.version = dialog.version_edit.text().strip()
                document.description = dialog.description_edit.toPlainText().strip() # Use toPlainText()
                document.keywords = dialog.keywords_edit.text().strip()

                session.commit()
                self.load_documents() # Reload to show changes
                UIUtils.show_success(self, "成功", "文档信息更新成功")

        except Exception as e:
            session.rollback()
            UIUtils.show_error(self, "错误", f"编辑文档失败: {e}")
        finally:
            session.close()

    def delete_document(self):
        selected_items = self.document_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请选择要删除的文档")
            return

        doc_ids_to_delete = list(set(self.document_table.item(item.row(), 0).data(Qt.UserRole) for item in selected_items))

        confirm_dialog = Dialog(
            '确认删除',
            f'确定要删除选中的 {len(doc_ids_to_delete)} 个文档吗？\n此操作将同时删除关联的文件，且不可恢复！',
            self
        )

        if confirm_dialog.exec():
            Session = sessionmaker(bind=self.engine)
            session = Session()
            deleted_count = 0
            failed_files = []
            try:
                for doc_id in doc_ids_to_delete:
                    document = session.query(ProjectDocument).filter(
                        ProjectDocument.id == doc_id
                    ).first()
                    if document:
                        file_path_to_delete = document.file_path
                        session.delete(document)
                        session.flush() # Ensure delete happens before file removal attempt

                        if file_path_to_delete and os.path.exists(file_path_to_delete):
                            try:
                                os.remove(file_path_to_delete)
                            except OSError as e:
                                print(f"Error deleting file {file_path_to_delete}: {e}")
                                failed_files.append(os.path.basename(file_path_to_delete))

                        deleted_count += 1

                session.commit()
                self.load_documents() # Refresh the table

                if failed_files:
                    UIUtils.show_warning(
                        self, "删除部分失败",
                        f"成功删除 {deleted_count} 个文档记录。\n但以下文件删除失败，请手动处理：\n{', '.join(failed_files)}"
                    )
                elif deleted_count > 0:
                    UIUtils.show_success(self, "成功", f"成功删除 {deleted_count} 个文档及其关联文件")
                else:
                     UIUtils.show_warning(self, "未删除", "没有文档被删除（可能已被其他操作移除）")


            except Exception as e:
                session.rollback()
                UIUtils.show_error(self, "错误", f"删除文档过程中发生数据库错误: {e}")
            finally:
                session.close()

    def download_document(self):
        selected_items = self.document_table.selectedItems()
        if not selected_items:
            UIUtils.show_warning(self, "警告", "请选择要下载的文档")
            return
        if len(selected_items) > 1:
             UIUtils.show_warning(self, "警告", "一次只能下载一个文档")
             return

        row = selected_items[0].row()
        doc_id = self.document_table.item(row, 0).data(Qt.UserRole)

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            document = session.query(ProjectDocument).filter(ProjectDocument.id == doc_id).first()
            if not document or not document.file_path:
                UIUtils.show_warning(self, "警告", "未找到文档文件或文件路径无效")
                return

            source_path = document.file_path
            if not os.path.exists(source_path):
                 UIUtils.show_error(self, "错误", f"文件不存在: {source_path}")
                 return

            original_filename = os.path.basename(source_path)
            _, ext = os.path.splitext(original_filename)
            suggested_filename = f"{sanitize_filename(document.name)}{ext}"

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存文档",
                suggested_filename, # Suggest filename
                f"文件 (*{ext})" # Filter by original extension
            )

            if save_path:
                try:
                    shutil.copy2(source_path, save_path)
                    UIUtils.show_success(self, "成功", f"文档已保存到: {save_path}")
                except Exception as e:
                    UIUtils.show_error(self, "错误", f"保存文件失败: {e}")

        except Exception as e:
            UIUtils.show_error(self, "错误", f"下载文档时出错: {e}")
        finally:
            session.close()

    def handle_document_attachment(self, event, btn):
        """Handles clicks on the attachment button (view/download)."""
        doc_id = btn.property("item_id")
        action_type = btn.property("action_type") # 'view' or 'download'

        if not doc_id:
            print("Error: No document ID found on button.")
            return

        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            self._execute_document_action(action_type, doc_id, btn, session)
        except Exception as e:
             UIUtils.show_error(self, "操作失败", f"处理文档附件时出错: {e}")
        finally:
            session.close()


    def _execute_document_action(self, action_type, doc_id, btn, session):
        """Executes view or download action for a document."""
        document = session.query(ProjectDocument).filter(ProjectDocument.id == doc_id).first()
        if not document or not document.file_path:
            UIUtils.show_warning(self, "警告", "未找到文档文件或文件路径无效")
            return

        file_path = document.file_path
        if not os.path.exists(file_path):
            UIUtils.show_error(self, "错误", f"文件不存在: {file_path}")
            btn.setIcon(FluentIcon.REMOVE_FROM)
            btn.setToolTip("文件丢失")
            btn.setEnabled(False)
            return

        if action_type == 'view':
            view_attachment(file_path, self)
        elif action_type == 'download':
            original_filename = os.path.basename(file_path)
            _, ext = os.path.splitext(original_filename)
            suggested_filename = f"{sanitize_filename(document.name)}{ext}"

            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "下载文档附件",
                suggested_filename,
                f"文件 (*{ext})"
            )
            if save_path:
                download_attachment(file_path, save_path, self)
        else:
            print(f"Unknown action type: {action_type}")


    def sort_table(self, column):
        """Sorts the table based on the clicked column."""
        current_order = self.document_table.horizontalHeader().sortIndicatorOrder()
        order = Qt.AscendingOrder if current_order == Qt.DescendingOrder else Qt.DescendingOrder

        column_map = {
            0: 'name',
            1: 'doc_type', # Sort by enum value
            2: 'version',
            3: 'keywords',
            4: 'upload_time', # Use the stored datetime object
            5: 'description',
        }

        sort_attribute = column_map.get(column)
        if sort_attribute:
            def sort_key(doc):
                value = getattr(doc, sort_attribute, None)
                if isinstance(value, DocumentType):
                    return value.value # Sort by enum string value
                if value is None: # Handle None values
                    return "" if isinstance(getattr(ProjectDocument, sort_attribute).type, String) else datetime.min
                if isinstance(value, str):
                    return value.lower() # Case-insensitive string sort
                return value # For dates, numbers, etc.

            reverse_sort = (order == Qt.DescendingOrder)
            self.current_documents.sort(key=sort_key, reverse=reverse_sort)
            self._populate_table(self.current_documents)
            self.document_table.horizontalHeader().setSortIndicator(column, order)

    def show_document_context_menu(self, pos):
        """显示文档表格的右键菜单"""
        menu = RoundMenu(parent=self)

        # 获取右键点击的单元格
        item = self.document_table.itemAt(pos)
        if item:
            # 添加复制操作
            copy_action = Action(FluentIcon.COPY, "复制", self)
            copy_action.triggered.connect(lambda: self.copy_cell_content(item))
            menu.addAction(copy_action)

        # 显示菜单
        menu.exec_(self.document_table.viewport().mapToGlobal(pos))

    def copy_cell_content(self, item):
        """复制单元格内容"""
        if item:
            # 获取单元格内容
            content = item.text()
            clipboard = QApplication.clipboard()
            clipboard.setText(content)