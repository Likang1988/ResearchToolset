import os
import shutil
import sys # Added for platform check
import subprocess # Added for opening files on Linux/macOS
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFileDialog
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon
from qfluentwidgets import ToolButton, RoundMenu, Action, FluentIcon, Dialog
import re # Import regex for sanitization
import datetime # Import datetime for timestamp
from enum import Enum # 导入Enum用于类型检查
from ..utils.ui_utils import UIUtils # Assuming UIUtils is in the parent directory

# 全局缓存，用于存储 item_id 到其最新 attachment_path 的映射
# 键为 (item_type, item_id)，值为附件路径 (str) 或 None
_attachment_path_cache = {}

UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(UTILS_DIR, '..', '..')) # Go up two levels to project root


def sanitize_filename(filename):
    """Removes or replaces characters that are invalid in file paths."""
    filename = filename.strip()
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    return filename

def ensure_directory_exists(dir_path):
    """Ensures that the specified directory exists, creating it if necessary."""
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError as e:
            print(f"Error creating directory {dir_path}: {e}")
            raise

def get_timestamp_str():
    """Returns the current timestamp as a string in YYYYMMDDHHMMSS format."""
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')


def get_attachment_icon_path(icon_name):
    """Helper function to get the absolute path for an icon."""
    return os.path.abspath(os.path.join(UTILS_DIR, '..', 'assets', 'icons', icon_name))

def create_attachment_button(item_id, attachment_path, handle_attachment_func, parent_widget, item_type):
    """
    Creates a container widget with a ToolButton for attachment management.

    Args:
        item_id: The ID of the item (document, outcome, etc.).
        attachment_path: The current path to the attachment file, if any.
        handle_attachment_func: The function to call when the button is clicked or menu action triggered.
        parent_widget: The parent widget for the button.
        item_type: A string identifying the type of item ('document', 'outcome', etc.).
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignCenter)

    btn = ToolButton()
    btn.setProperty("item_id", item_id)
    btn.setProperty("item_type", item_type) # Store item type

    cache_key = (item_type, item_id)
    
    # 确定要用于显示的附件路径
    path_to_use_for_display = attachment_path # 默认使用参数传入的路径

    if cache_key in _attachment_path_cache:
        # 如果缓存中存在此项的记录，优先使用缓存的路径
        path_to_use_for_display = _attachment_path_cache[cache_key]
    else:
        # 如果缓存中不存在，说明是首次加载或缓存被清除
        # 使用参数传入的路径，并用它初始化缓存
        _attachment_path_cache[cache_key] = attachment_path
    
    # 确保按钮的 'attachment_path' 属性与我们决定用于显示的路径一致
    btn.setProperty("attachment_path", path_to_use_for_display)

    # 检查附件路径是否有效
    has_attachment = path_to_use_for_display and os.path.exists(path_to_use_for_display)
    
    if has_attachment:
        btn.setIcon(QIcon(get_attachment_icon_path('attach.svg')))
        btn.setToolTip("管理附件")
    else:
        btn.setIcon(QIcon(get_attachment_icon_path('add_outline.svg'))) # Assuming an add icon exists
        btn.setToolTip("添加附件")

    btn.setFixedSize(28, 28)
    btn.setIconSize(QSize(18, 18)) # Slightly smaller icon size
    btn.clicked.connect(lambda checked=False, b=btn: handle_attachment_func(None, b)) # Pass button itself

    layout.addWidget(btn, 0, Qt.AlignCenter) # Ensure vertical centering
    container.setLayout(layout)
    return container

def create_attachment_menu(parent, attachment_path, item_id, handle_attachment_func):
    """Creates a context menu for attachment actions."""
    menu = RoundMenu(parent=parent)
    if attachment_path and os.path.exists(attachment_path):
        view_action = Action(FluentIcon.VIEW, "查看", parent)
        download_action = Action(FluentIcon.DOWNLOAD, "下载", parent) # Added Download Action
        replace_action = Action(FluentIcon.SYNC, "替换", parent)
        open_path_action = Action(FluentIcon.FOLDER, "路径", parent) # Added Open Path Action
        delete_action = Action(FluentIcon.DELETE, "删除", parent)

        view_action.triggered.connect(lambda: handle_attachment_func("view", item_id))
        download_action.triggered.connect(lambda: handle_attachment_func("download", item_id)) # Connect Download Action
        replace_action.triggered.connect(lambda: handle_attachment_func("replace", item_id))
        open_path_action.triggered.connect(lambda: handle_attachment_func("open_path", item_id)) # Connect Open Path Action
        delete_action.triggered.connect(lambda: handle_attachment_func("delete", item_id))

        menu.addAction(view_action)
        menu.addAction(download_action) # Add Download Action to menu
        menu.addAction(replace_action)
        menu.addAction(open_path_action) # Add Open Path Action to menu
        menu.addSeparator()
        menu.addAction(delete_action)
    else:
        upload_action = Action(FluentIcon.ADD_TO, "上传附件", parent)
        upload_action.triggered.connect(lambda: handle_attachment_func("upload", item_id))
        menu.addAction(upload_action)

    return menu


def view_attachment(attachment_path, parent_widget):
    """Opens the attachment file using the default system application."""
    if attachment_path and os.path.exists(attachment_path):
        try:
            if os.name == 'nt':
                os.startfile(attachment_path)
            elif sys.platform == 'darwin': # Use sys.platform for macOS check
                subprocess.call(['open', attachment_path])
            else: # Assume Linux/other Unix-like
                subprocess.call(['xdg-open', attachment_path])
        except Exception as e:
            UIUtils.show_error(parent_widget, "错误", f"无法打开附件：{e}")
    else:
        UIUtils.show_warning(parent_widget, "提示", "附件文件不存在或路径无效")


def open_attachment_path(attachment_path, parent_widget):
    """Opens the directory containing the attachment file."""
    if attachment_path and os.path.exists(attachment_path):
        attachment_dir = os.path.dirname(attachment_path)
        try:
            if os.name == 'nt':
                os.startfile(attachment_dir)
            elif sys.platform == 'darwin': # Use sys.platform for macOS check
                subprocess.call(['open', attachment_dir])
            else: # Assume Linux/other Unix-like
                subprocess.call(['xdg-open', attachment_dir])
        except Exception as e:
            UIUtils.show_error(parent_widget, "错误", f"无法打开附件路径：{e}")
    elif attachment_path:
        UIUtils.show_warning(parent_widget, "提示", f"附件路径不存在：{os.path.dirname(attachment_path)}")
    else:
        UIUtils.show_warning(parent_widget, "提示", "附件文件不存在或路径无效")

def download_attachment(attachment_path, parent_widget):
    """Handles downloading (saving a copy) of the attachment file."""
    if not attachment_path or not os.path.exists(attachment_path):
        UIUtils.show_warning(parent_widget, "提示", "附件文件不存在或路径无效")
        return

    suggested_filename = os.path.basename(attachment_path)

    save_path, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "保存附件",
        suggested_filename, # Suggest the original filename
        "所有文件 (*.*)" # Allow saving as any type, or specify based on original?
    )

    if not save_path:
        return

    try:
        shutil.copy2(attachment_path, save_path)
        UIUtils.show_success(parent_widget, "成功", f"附件已保存到：\n{save_path}")
    except Exception as e:
        UIUtils.show_error(parent_widget, "错误", f"保存附件失败：{e}")


def generate_attachment_path(project, item_type_enum, original_filename, base_folder="attachments", item_type=None, expense=None, activity_type_enum=None):
    """通用的附件路径生成函数
    
    Args:
        project: 项目对象，必须有financial_code属性
        item_type_enum: 枚举类型对象，如DocumentType或OutcomeType
        original_filename: 原始文件名
        base_folder: 基础文件夹名称，默认为'attachments'
        item_type: 项目类型，如'expense'或'activity'
        expense: 支出对象，用于生成支出凭证路径
        activity_type_enum: 活动类型枚举，用于生成活动附件路径
        
    Returns:
        生成的附件完整路径
    """
    if not original_filename:
        print(f"Error: Missing filename for path generation.")
        return None
        
    # 处理支出凭证的特殊路径生成逻辑
    if item_type == 'expense' and expense and project:
        base_folder = "vouchers"
        project_code = project.financial_code if project.financial_code else "unknown_project"
        expense_year = str(expense.date.year) if expense.date else "unknown_year"
        expense_category = expense.category.value if expense.category else "unknown_category"
        sanitized_category = sanitize_filename(expense_category)
        expense_amount = f"{expense.amount:.2f}" if expense.amount is not None else "0.00"
        
        original_basename = os.path.basename(original_filename)
        base_name, ext = os.path.splitext(original_basename)
        sanitized_base_name = sanitize_filename(base_name) # 仅对基本名称进行清理
        
        new_filename = f"{sanitized_category}_{expense_amount}_{sanitized_base_name}{ext}"
        
        target_dir = os.path.join(ROOT_DIR, base_folder, project_code, expense_year)
        full_path = os.path.join(target_dir, new_filename)
        
        ensure_directory_exists(target_dir)
        return os.path.normpath(full_path)
    
    # 处理活动附件的特殊路径生成逻辑
    elif item_type == 'activity' and activity_type_enum:
        base_folder = "activities"
        activity_type_str = sanitize_filename(activity_type_enum.value)
        timestamp = get_timestamp_str()
        
        original_basename = os.path.basename(original_filename)
        base_name, ext = os.path.splitext(original_basename)
        sanitized_base_name = sanitize_filename(base_name)
        
        new_filename = f"{timestamp}_{sanitized_base_name}{ext}"
        
        target_dir = os.path.join(ROOT_DIR, base_folder, activity_type_str)
        full_path = os.path.join(target_dir, new_filename)
        
        ensure_directory_exists(target_dir)
        return os.path.normpath(full_path)
    
    # 默认的附件路径生成逻辑
    elif project and item_type_enum:
        project_code = project.financial_code if project.financial_code else "unknown_project"
        # 使用枚举值，并确保路径安全
        item_type_str = sanitize_filename(item_type_enum.value if isinstance(item_type_enum, Enum) else str(item_type_enum))
        timestamp = get_timestamp_str()

        # 处理原始文件名
        original_basename = os.path.basename(original_filename)
        base_name, ext = os.path.splitext(original_basename)
        sanitized_base_name = sanitize_filename(base_name)

        # 构造文件名: <timestamp>_<sanitized_original_name>.ext
        new_filename = f"{timestamp}_{sanitized_base_name}{ext}"

        # 构造完整路径
        target_dir = os.path.join(ROOT_DIR, base_folder, project_code, item_type_str)
        full_path = os.path.join(target_dir, new_filename)
        
        ensure_directory_exists(target_dir)
        return os.path.normpath(full_path)
    
    else:
        print(f"Error: Missing required parameters for path generation.")
        return None


def handle_attachment(event, btn, item_id, item_type, session_maker, parent_widget, get_item_func, attachment_attr, project_attr=None, base_folder=None):
    """通用的附件处理函数，处理附件的点击事件和菜单操作
    
    Args:
        event: 事件对象，None表示左键点击，QPoint表示右键点击位置
        btn: 附件按钮对象
        item_id: 项目ID
        item_type: 项目类型（如'document'、'outcome'等）
        session_maker: 数据库会话创建函数
        parent_widget: 父窗口对象
        get_item_func: 获取项目对象的函数，接收session和item_id参数
        attachment_attr: 附件路径属性名称
        project_attr: 项目属性名称，默认为'project_id'
        base_folder: 基础文件夹名称，如'documents'、'outcomes'等
    """
    if item_id is None:
        UIUtils.show_error(parent_widget, "错误", f"无法获取{item_type}项ID")
        return

    session = session_maker()
    try:
        # 获取项目对象
        item = get_item_func(session, item_id)
        if not item:
            UIUtils.show_error(parent_widget, "错误", f"找不到ID为 {item_id} 的{item_type}项")
            return

        action_type = None
        current_path = getattr(item, attachment_attr, None)

        if event is None:  # 左键点击
            button_path = btn.property("attachment_path")
            if button_path and os.path.exists(button_path):
                # 显示菜单
                menu = create_attachment_menu(parent_widget, button_path, item_id, 
                                             lambda action, id: execute_attachment_action(
                                                 action, id, btn, session, item, 
                                                 get_item_func, attachment_attr, 
                                                 project_attr, base_folder, parent_widget))
                menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
                return
            else:
                action_type = "replace"  # 左键点击空按钮视为'替换'（上传）
        elif isinstance(event, QPoint):  # 右键点击
            menu = RoundMenu(parent=parent_widget)
            if current_path and os.path.exists(current_path):
                view_action = Action(FluentIcon.VIEW, "查看", parent_widget)
                download_action = Action(FluentIcon.DOWNLOAD, "下载", parent_widget)
                replace_action = Action(FluentIcon.SYNC, "替换", parent_widget)
                delete_action = Action(FluentIcon.DELETE, "删除", parent_widget)
                
                view_action.triggered.connect(lambda: execute_attachment_action("view", item_id, btn, session, item, 
                                                                            get_item_func, attachment_attr, 
                                                                            project_attr, base_folder, parent_widget))
                download_action.triggered.connect(lambda: execute_attachment_action("download", item_id, btn, session, item, 
                                                                                get_item_func, attachment_attr, 
                                                                                project_attr, base_folder, parent_widget))
                replace_action.triggered.connect(lambda: execute_attachment_action("replace", item_id, btn, session, item, 
                                                                                get_item_func, attachment_attr, 
                                                                                project_attr, base_folder, parent_widget))
                delete_action.triggered.connect(lambda: execute_attachment_action("delete", item_id, btn, session, item, 
                                                                              get_item_func, attachment_attr, 
                                                                              project_attr, base_folder, parent_widget))
                
                menu.addAction(view_action)
                menu.addAction(download_action)
                menu.addAction(replace_action)
                menu.addSeparator()
                menu.addAction(delete_action)
            else:
                # 如果数据库中没有路径，只允许'替换'（上传）
                replace_action = Action(FluentIcon.SYNC, "上传/替换", parent_widget)
                replace_action.triggered.connect(lambda: execute_attachment_action("replace", item_id, btn, session, item, 
                                                                                get_item_func, attachment_attr, 
                                                                                project_attr, base_folder, parent_widget))
                menu.addAction(replace_action)
            menu.exec(btn.mapToGlobal(event))
            return

        # 如果确定了操作类型（例如，左键点击空按钮）
        if action_type:
            execute_attachment_action(action_type, item_id, btn, session, item, 
                                     get_item_func, attachment_attr, 
                                     project_attr, base_folder, parent_widget)

    except Exception as e:
        UIUtils.show_error(parent_widget, "处理附件时出错", f"发生意外错误: {e}")
        if session.is_active:
            session.rollback()
    finally:
        if session.is_active:
            session.close()


def execute_attachment_action(action_type, item_id, btn, session, item, get_item_func, 
                             attachment_attr, project_attr, base_folder, parent_widget):
    """执行特定的附件操作
    
    Args:
        action_type: 操作类型，如'view'、'download'、'replace'、'delete'
        item_id: 项目ID
        btn: 附件按钮对象
        session: 数据库会话
        item: 项目对象
        get_item_func: 获取项目对象的函数
        attachment_attr: 附件路径属性名称
        project_attr: 项目属性名称
        base_folder: 基础文件夹名称
        parent_widget: 父窗口对象
    """
    try:
        if not item:
            item = get_item_func(session, item_id)
            if not item:
                UIUtils.show_error(parent_widget, "错误", f"执行操作时找不到ID为 {item_id} 的项")
                return

        # 获取项目对象，用于路径生成
        project = None
        if project_attr:
            from ..models.database import Project
            # 修复：如果project_attr是字符串"project_attr"，则使用默认的'project_id'
            actual_attr = 'project_id' if project_attr == "project_attr" else project_attr
            project_id = getattr(item, actual_attr, None)
            if project_id:
                project = session.query(Project).get(project_id)
                if not project:
                    UIUtils.show_error(parent_widget, "错误", f"找不到关联的项目 (ID: {project_id})")
                    return

        current_path = getattr(item, attachment_attr, None)

        if action_type == "view":
            if current_path and os.path.exists(current_path):
                view_attachment(current_path, parent_widget)
            else:
                UIUtils.show_warning(parent_widget, "提示", "附件不存在")

        elif action_type == "download":
            if current_path and os.path.exists(current_path):
                download_attachment(current_path, parent_widget)
            else:
                UIUtils.show_warning(parent_widget, "提示", "附件不存在")

        elif action_type == "open_path":
            if current_path and os.path.exists(current_path):
                open_attachment_path(current_path, parent_widget)
            else:
                UIUtils.show_warning(parent_widget, "提示", "附件不存在或路径无效")

        elif action_type == "replace":  # 处理上传和替换
            source_file_path, _ = QFileDialog.getOpenFileName(parent_widget, "选择附件", "", "所有文件 (*.*)") 
            if not source_file_path:
                return  # 用户取消

            old_path = current_path
            new_path = None
            
            # 根据项目类型生成不同的路径
            item_type_str = btn.property("item_type")
            if item_type_str == 'activity' and hasattr(item, 'type'):
                new_path = generate_attachment_path(None, None, source_file_path, base_folder, 
                                                  item_type='activity', activity_type_enum=item.type)
            elif item_type_str == 'expense' and project:
                new_path = generate_attachment_path(project, None, source_file_path, base_folder, 
                                                  item_type='expense', expense=item)
            elif project and hasattr(item, 'doc_type'):
                new_path = generate_attachment_path(project, item.doc_type, source_file_path, base_folder)
            elif project and hasattr(item, 'type'):
                new_path = generate_attachment_path(project, item.type, source_file_path, base_folder)
            else:
                UIUtils.show_error(parent_widget, "错误", "无法确定项目类型，无法生成附件保存路径")
                return

            if not new_path:
                UIUtils.show_error(parent_widget, "错误", "无法生成附件保存路径")
                return

            # --- 事务开始 ---
            try:
                ensure_directory_exists(os.path.dirname(new_path))
                shutil.copy2(source_file_path, new_path)

                setattr(item, attachment_attr, new_path)
                # 如果有上传时间字段，可以更新
                if hasattr(item, 'upload_time'):
                    from datetime import datetime
                    item.upload_time = datetime.now()
                session.commit()

                # 更新缓存
                item_type_for_cache = btn.property("item_type")
                if item_type_for_cache is not None: # 确保 item_type 可获取
                    _attachment_path_cache[(item_type_for_cache, item_id)] = new_path
                else:
                    print(f"Warning: Could not update cache for item_id {item_id} due to missing item_type on button.")


                # 如果是替换且路径变化，删除旧文件
                if old_path and os.path.exists(old_path) and os.path.normpath(old_path) != os.path.normpath(new_path):
                    try:
                        os.remove(old_path)
                    except OSError as e:
                        print(f"警告: 无法删除旧附件 {old_path}: {e}")

                # 更新按钮
                btn.setIcon(QIcon(get_attachment_icon_path('attach.svg')))
                btn.setToolTip("管理附件")
                btn.setProperty("attachment_path", new_path)

                UIUtils.show_success(parent_widget, "成功", "附件已更新")

            except Exception as e:
                session.rollback()
                UIUtils.show_error(parent_widget, "错误", f"更新附件失败: {e}")
                # 清理可能已复制的文件
                if os.path.exists(new_path):
                    session.expire(item)
                    db_path_after_rollback = getattr(get_item_func(session, item_id), attachment_attr, None)
                    if db_path_after_rollback != new_path:
                        try:
                            print(f"尝试删除孤立文件: {new_path}")
                            os.remove(new_path)
                        except Exception as remove_err:
                            print(f"删除孤立文件时出错 {new_path}: {remove_err}")
            # --- 事务结束 ---

        elif action_type == "delete":
            if not current_path or not os.path.exists(current_path):
                UIUtils.show_warning(parent_widget, "提示", "没有可删除的附件")
                return

            confirm_dialog = Dialog('确认删除', '确定要删除此附件吗？此操作不可恢复！', parent_widget)
            if confirm_dialog.exec():
                # --- 事务开始 ---
                try:
                    os.remove(current_path)
                    setattr(item, attachment_attr, None)  # 在数据库中将路径设为None
                    session.commit()

                    # 更新缓存
                    item_type_for_cache = btn.property("item_type")
                    if item_type_for_cache is not None: # 确保 item_type 可获取
                        _attachment_path_cache[(item_type_for_cache, item_id)] = None
                    else:
                        print(f"Warning: Could not update cache for item_id {item_id} due to missing item_type on button during delete.")

                    # 更新按钮
                    btn.setIcon(QIcon(get_attachment_icon_path('add_outline.svg')))
                    btn.setToolTip("添加附件")
                    btn.setProperty("attachment_path", None)

                    UIUtils.show_success(parent_widget, "成功", "附件已删除")

                except Exception as e:
                    session.rollback()
                    UIUtils.show_error(parent_widget, "错误", f"删除附件失败: {e}")
                # --- 事务结束 ---

    except Exception as e:
        UIUtils.show_error(parent_widget, "处理附件操作时出错", f"发生意外错误: {e}")
        if session.is_active:
            try: session.rollback()
            except: pass