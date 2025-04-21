import os
import shutil
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFileDialog, QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from qfluentwidgets import ToolButton, RoundMenu, Action, FluentIcon, Dialog
from ..utils.ui_utils import UIUtils # Assuming UIUtils is in the parent directory

# Define base directories relative to the utils directory
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(UTILS_DIR, '..', '..')) # Go up two levels to project root

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
    btn.setProperty("item_id", item_id) # Store item ID in the button property
    btn.setProperty("item_type", item_type) # Store item type
    btn.setProperty("attachment_path", attachment_path) # Store current path

    if attachment_path and os.path.exists(attachment_path):
        # Use a generic 'attached' icon if file exists
        btn.setIcon(QIcon(get_attachment_icon_path('attach.svg')))
        btn.setToolTip("管理附件")
    else:
        # Use a generic 'add attachment' icon if no file or path is invalid
        btn.setIcon(QIcon(get_attachment_icon_path('add_outline.svg'))) # Assuming an add icon exists
        btn.setToolTip("添加附件")

    btn.setFixedSize(28, 28)
    btn.setIconSize(QSize(18, 18)) # Slightly smaller icon size
    btn.clicked.connect(lambda checked=False, b=btn: handle_attachment_func(None, b)) # Pass button itself
    btn.setContextMenuPolicy(Qt.CustomContextMenu)
    btn.customContextMenuRequested.connect(lambda pos, b=btn: handle_attachment_func(pos, b)) # Pass button itself

    layout.addWidget(btn, 0, Qt.AlignCenter) # Ensure vertical centering
    container.setLayout(layout)
    return container

def create_attachment_menu(parent, attachment_path, item_id, handle_attachment_func):
    """Creates a context menu for attachment actions."""
    menu = RoundMenu(parent=parent)
    if attachment_path and os.path.exists(attachment_path):
        view_action = Action(FluentIcon.VIEW, "查看", parent)
        replace_action = Action(FluentIcon.SYNC, "替换", parent)
        delete_action = Action(FluentIcon.DELETE, "删除", parent)

        view_action.triggered.connect(lambda: handle_attachment_func("view", item_id))
        replace_action.triggered.connect(lambda: handle_attachment_func("replace", item_id))
        delete_action.triggered.connect(lambda: handle_attachment_func("delete", item_id))

        menu.addAction(view_action)
        menu.addAction(replace_action)
        menu.addSeparator()
        menu.addAction(delete_action)
    else:
        upload_action = Action(FluentIcon.UPLOAD, "上传附件", parent)
        upload_action.triggered.connect(lambda: handle_attachment_func("upload", item_id))
        menu.addAction(upload_action)

    return menu

def handle_attachment(event, btn, item, session, parent_widget, project, item_type, attachment_attr, base_folder):
    """
    Handles attachment actions (view, upload, replace, delete) via context menu or direct click.

    Args:
        event: The event triggering the handler (QPoint for context menu, None for click).
        btn: The ToolButton that was clicked or requested context menu.
        item: The database object (e.g., ProjectDocument, ProjectOutcome).
        session: The SQLAlchemy session.
        parent_widget: The parent widget for dialogs.
        project: The current project object.
        item_type: String identifier ('document', 'outcome').
        attachment_attr: The name of the attribute storing the path (e.g., 'file_path', 'attachment_path').
        base_folder: The base directory name for storing attachments (e.g., 'documents', 'outcomes').
    """
    item_id = btn.property("item_id")
    current_path = getattr(item, attachment_attr, None) # Get current path using attribute name

    if event is None: # Direct click
        if current_path and os.path.exists(current_path):
            # If attachment exists, show menu on left click
            menu = create_attachment_menu(parent_widget, current_path, item_id,
                                          lambda action_type, id: handle_attachment_action(action_type, id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn))
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        else:
            # If no attachment, trigger upload on left click
            handle_attachment_action("upload", item_id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn)
    elif isinstance(event, QPoint): # Context menu request
        menu = create_attachment_menu(parent_widget, current_path, item_id,
                                      lambda action_type, id: handle_attachment_action(action_type, id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn))
        menu.exec(btn.mapToGlobal(event))

def handle_attachment_action(action_type, item_id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn):
    """Executes the specific attachment action."""
    current_path = getattr(item, attachment_attr, None)

    if action_type == "view":
        view_attachment(current_path, parent_widget)
    elif action_type == "upload" or action_type == "replace":
        replace_attachment(item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn)
    elif action_type == "delete":
        delete_attachment(item, session, parent_widget, attachment_attr, btn)

def view_attachment(attachment_path, parent_widget):
    """Opens the attachment file using the default system application."""
    if attachment_path and os.path.exists(attachment_path):
        try:
            # Use os.startfile on Windows, open on macOS/Linux
            if os.name == 'nt':
                os.startfile(attachment_path)
            elif sys.platform == 'darwin':
                subprocess.call(['open', attachment_path])
            else:
                subprocess.call(['xdg-open', attachment_path])
        except Exception as e:
            UIUtils.show_error(parent_widget, "错误", f"无法打开附件：{e}")
    else:
        UIUtils.show_warning(parent_widget, "提示", "附件文件不存在或路径无效")

def get_new_attachment_path(item, project, item_type, base_folder, original_filename):
    """Generates a standardized path for the new attachment."""
    _, ext = os.path.splitext(original_filename)
    # Define target directory: ROOT_DIR / base_folder / project_id / item_id
    target_dir = os.path.join(ROOT_DIR, base_folder, str(project.id), str(item.id))
    os.makedirs(target_dir, exist_ok=True)
    # Define filename: item_type_item_id_original_basename_without_ext + ext
    # Sanitize original filename part if needed
    sanitized_original_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in os.path.splitext(os.path.basename(original_filename))[0])
    filename = f"{item_type}_{item.id}_{sanitized_original_name}{ext}"
    return os.path.join(target_dir, filename)


def replace_attachment(item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn):
    """Handles uploading or replacing an attachment file."""
    file_path, _ = QFileDialog.getOpenFileName(
        parent_widget,
        "选择附件文件",
        "",
        "所有文件 (*.*)" # Allow any file type, adjust if needed
    )
    if not file_path:
        return

    old_path = getattr(item, attachment_attr, None)

    try:
        # Generate new standardized path
        new_path = get_new_attachment_path(item, project, item_type, base_folder, file_path)

        # Copy the new file
        shutil.copy2(file_path, new_path)

        # Update database
        setattr(item, attachment_attr, new_path)
        session.commit()

        # Delete old file if it exists and is different from the new one
        if old_path and os.path.exists(old_path) and old_path != new_path:
            try:
                os.remove(old_path)
            except OSError as e:
                print(f"无法删除旧附件 {old_path}: {e}") # Log error but continue

        # Update button state
        btn.setIcon(QIcon(get_attachment_icon_path('attach.svg')))
        btn.setToolTip("管理附件")
        btn.setProperty("attachment_path", new_path) # Update button property

        UIUtils.show_success(parent_widget, "成功", "附件已更新")

    except Exception as e:
        session.rollback()
        UIUtils.show_error(parent_widget, "错误", f"更新附件失败：{e}")


def delete_attachment(item, session, parent_widget, attachment_attr, btn):
    """Handles deleting an attachment file and updating the database."""
    attachment_path = getattr(item, attachment_attr, None)
    if not attachment_path or not os.path.exists(attachment_path):
        UIUtils.show_warning(parent_widget, "提示", "没有可删除的附件")
        return

    confirm_dialog = Dialog(
        '确认删除',
        '确定要删除此附件吗？此操作不可恢复！',
        parent_widget
    )

    if confirm_dialog.exec():
        try:
            # Delete the file
            os.remove(attachment_path)

            # Update database
            setattr(item, attachment_attr, None)
            session.commit()

            # No need to update the button state here.
            # The table refresh in the calling widget will recreate the button
            # with the correct state based on the updated database record.
            # btn.setIcon(QIcon(get_attachment_icon_path('add_outline.svg'))) # REMOVED
            # btn.setToolTip("添加附件") # REMOVED
            # btn.setProperty("attachment_path", None) # REMOVED

            UIUtils.show_success(parent_widget, "成功", "附件已删除")

        except Exception as e:
            session.rollback()
            UIUtils.show_error(parent_widget, "错误", f"删除附件失败：{e}")