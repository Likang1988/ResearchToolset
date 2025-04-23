import os
import shutil
import sys # Added for platform check
import subprocess # Added for opening files on Linux/macOS
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFileDialog, QApplication
from PySide6.QtCore import Qt, QSize, QPoint
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
    # btn.setContextMenuPolicy(Qt.CustomContextMenu) # Disabled right-click menu
    # btn.customContextMenuRequested.connect(lambda pos, b=btn: handle_attachment_func(pos, b)) # Disabled right-click menu

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
        delete_action = Action(FluentIcon.DELETE, "删除", parent)

        view_action.triggered.connect(lambda: handle_attachment_func("view", item_id))
        download_action.triggered.connect(lambda: handle_attachment_func("download", item_id)) # Connect Download Action
        replace_action.triggered.connect(lambda: handle_attachment_func("replace", item_id))
        delete_action.triggered.connect(lambda: handle_attachment_func("delete", item_id))

        menu.addAction(view_action)
        menu.addAction(download_action) # Add Download Action to menu
        menu.addAction(replace_action)
        menu.addSeparator()
        menu.addAction(delete_action)
    else:
        upload_action = Action(FluentIcon.ADD_TO, "上传附件", parent)
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
    # For context menu (right-click), we still need the item's state initially to build the correct menu
    context_menu_path = getattr(item, attachment_attr, None)

    if event is None: # Direct click (left-click)
        # --- CRITICAL CHANGE for left-click behavior ---
        # Use the button's property, which is updated immediately after actions
        button_path = btn.property("attachment_path")
        if button_path and os.path.exists(button_path):
            # If button property indicates an existing attachment, show menu
            # Pass the button_path to create_attachment_menu for consistency
            # Pass button_path as path_to_use for view/download actions triggered from this menu
            menu = create_attachment_menu(parent_widget, button_path, item_id,
                                          lambda action_type, id, path=button_path: handle_attachment_action(action_type, id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn, path))
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        else:
            # If button property indicates no attachment, trigger upload. Upload doesn't need path_to_use.
            # We can pass None or an empty string, or adjust handle_attachment_action if needed, but current implementation handles it.
            handle_attachment_action("upload", item_id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn, None) # Pass None for path_to_use
    elif isinstance(event, QPoint): # Context menu request (right-click)
        # Build the context menu based on the item's state at the time of the right-click
        # Use context_menu_path here which was fetched from the item earlier
        # Pass context_menu_path as path_to_use for view/download actions triggered from this menu
        menu = create_attachment_menu(parent_widget, context_menu_path, item_id,
                                      lambda action_type, id, path=context_menu_path: handle_attachment_action(action_type, id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn, path))
        menu.exec(btn.mapToGlobal(event))

def handle_attachment_action(action_type, item_id, item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn, path_to_use):
    """Executes the specific attachment action."""
    # Note: 'item' might hold outdated path info immediately after an action via the menu.
    # 'path_to_use' holds the path that was valid when the menu was created/clicked.

    if action_type == "view":
        # Use the path that was valid when the menu action was triggered
        view_attachment(path_to_use, parent_widget)
    elif action_type == "download":
        # Use the path that was valid when the menu action was triggered
        download_attachment(path_to_use, parent_widget)
    elif action_type == "upload" or action_type == "replace":
        # Upload/Replace needs the item to update the DB and generate new path
        replace_attachment(item, session, parent_widget, project, item_type, attachment_attr, base_folder, btn)
    elif action_type == "delete":
        # Delete needs the item to update the DB
        delete_attachment(item, session, parent_widget, attachment_attr, btn)

import sys # Add sys import if not already present at the top
import subprocess # Add subprocess import if not already present at the top

# ... (ensure other necessary imports like shutil, QFileDialog are present)

def view_attachment(attachment_path, parent_widget):
    """Opens the attachment file using the default system application."""
    if attachment_path and os.path.exists(attachment_path):
        try:
            # Use os.startfile on Windows, open on macOS/Linux
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

def download_attachment(attachment_path, parent_widget):
    """Handles downloading (saving a copy) of the attachment file."""
    if not attachment_path or not os.path.exists(attachment_path):
        UIUtils.show_warning(parent_widget, "提示", "附件文件不存在或路径无效")
        return

    # Suggest a filename based on the original attachment name
    suggested_filename = os.path.basename(attachment_path)

    # Open 'Save As' dialog
    save_path, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "保存附件",
        suggested_filename, # Suggest the original filename
        "所有文件 (*.*)" # Allow saving as any type, or specify based on original?
    )

    if not save_path:
        # User cancelled the dialog
        return

    try:
        # Copy the file to the chosen location
        shutil.copy2(attachment_path, save_path)
        UIUtils.show_success(parent_widget, "成功", f"附件已保存到：\n{save_path}")
    except Exception as e:
        UIUtils.show_error(parent_widget, "错误", f"保存附件失败：{e}")


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

            # Update button state to reflect deletion
            btn.setIcon(QIcon(get_attachment_icon_path('add_outline.svg')))
            btn.setToolTip("添加附件")
            btn.setProperty("attachment_path", None) # Clear the stored path

            UIUtils.show_success(parent_widget, "成功", "附件已删除")

        except Exception as e:
            session.rollback()
            UIUtils.show_error(parent_widget, "错误", f"删除附件失败：{e}")