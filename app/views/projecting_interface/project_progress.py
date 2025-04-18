import json
from datetime import datetime, timezone
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel # Added QHBoxLayout, QLabel
# from PySide6.QtWebEngineWidgets import QWebEngineView # Already commented out/replaced
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl, Signal, QObject, Slot, QCoreApplication, Qt # Ensure Qt is imported
from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationInterface, TitleLabel, InfoBar, InfoBarPosition, ComboBox # Added ComboBox
from qframelesswindow.webengine import FramelessWindow, FramelessWebEngineView
from app.utils.ui_utils import UIUtils
from app.models.database import sessionmaker, GanttTask, GanttDependency, Project
import os

# --- GanttBridge Class for Python-JS Communication ---
class GanttBridge(QObject):
    """用于在Python和JavaScript之间通过QWebChannel通信的桥梁类"""
    data_saved = Signal(bool, str) # 信号：保存是否成功，消息

    # Modify __init__ to remove project argument
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.project = None # Project will be set later
        self.Session = sessionmaker(bind=self.engine)

    def set_project(self, project):
        """Sets the current project for the bridge."""
        self.project = project
        print(f"GanttBridge project set to: {project.name if project else 'None'}")

    @Slot(result=str) # 返回JSON字符串
    def load_gantt_data(self):
        """从数据库加载指定项目的甘特图数据"""
        if not self.project:
            print("GanttBridge: No project selected, returning empty data.")
            # Return empty structure if no project is selected
            return json.dumps({
                "tasks": [], "selectedRow": -1, "deletedTaskIds": [],
                "resources": [], "roles": [], "canWrite": False, "canDelete": False,
                "canWriteOnParent": False, "canAdd": False
            })

        session = self.Session()
        try:
            print(f"GanttBridge: Loading data for project ID: {self.project.id}")
            tasks_db = session.query(GanttTask).filter(GanttTask.project_id == self.project.id).order_by(GanttTask.id).all()
            dependencies_db = session.query(GanttDependency).filter(GanttDependency.project_id == self.project.id).all()

            tasks_json = []
            for task in tasks_db:
                # 将数据库时间转换为毫秒时间戳 (jQueryGantt需要)
                # 确保时间是aware的，假设数据库存储的是UTC
                start_ms = int(task.start_date.replace(tzinfo=timezone.utc).timestamp() * 1000) if task.start_date else None
                end_ms = int(task.end_date.replace(tzinfo=timezone.utc).timestamp() * 1000) if task.end_date else None

                tasks_json.append({
                    "id": task.gantt_id, # 使用存储的gantt_id
                    "name": task.name,
                    "progress": task.progress,
                    "progressByWorklog": task.progress_by_worklog,
                    "relevance": 0, # 示例值，根据需要调整
                    "type": "", # 示例值
                    "typeId": "", # 示例值
                    "description": task.description,
                    "code": task.code,
                    "level": task.level,
                    "status": task.status,
                    "depends": self._get_task_dependencies(task.gantt_id, dependencies_db),
                    "canWrite": True, # 假设可写
                    "start": start_ms,
                    "duration": task.duration,
                    "end": end_ms,
                    "startIsMilestone": task.start_is_milestone,
                    "endIsMilestone": task.end_is_milestone,
                    "collapsed": task.collapsed,
                    "assigs": [], # 假设没有分配资源
                    "hasChild": task.has_child
                })

            # 构建jQueryGantt期望的完整项目结构
            project_data = {
                "tasks": tasks_json,
                "selectedRow": 0 if tasks_json else -1, # 选中第一行或不选
                "deletedTaskIds": [], # 初始为空
                "resources": [], # 暂不处理资源
                "roles": [], # 暂不处理角色
                "canWrite": True,
                "canDelete": True,
                "canWriteOnParent": True,
                "canAdd": True
            }
            print(f"Loaded {len(tasks_json)} tasks for project {self.project.id}")
            return json.dumps(project_data, default=str) # 使用default=str处理日期等

        except Exception as e:
            print(f"Error loading Gantt data: {e}")
            session.rollback()
            # 返回一个空的或默认的项目结构，防止JS出错
            return json.dumps({
                "tasks": [], "selectedRow": -1, "deletedTaskIds": [],
                "resources": [], "roles": [], "canWrite": True, "canDelete": True,
                "canWriteOnParent": True, "canAdd": True
            })
        finally:
            session.close()

    def _get_task_dependencies(self, task_gantt_id, all_dependencies):
        """获取指定任务的依赖字符串"""
        deps = []
        for dep in all_dependencies:
            if dep.successor_gantt_id == task_gantt_id:
                # jQueryGantt 依赖格式通常是 "前置任务ID[:类型]"，这里简化为仅ID
                deps.append(str(dep.predecessor_gantt_id))
        return ",".join(deps)

    # 修改 Slot 返回类型为 str，以包含 ID 映射
    @Slot(str, result=str) # 接收JSON字符串，返回包含ID映射的JSON字符串或错误信息
    def save_gantt_data(self, project_json_str):
        """
        将甘特图数据保存到数据库。
        成功时返回包含临时ID到持久化ID映射的JSON字符串。
        失败时返回包含错误信息的JSON字符串。
        """
        if not self.project:
            print("GanttBridge: No project selected, cannot save data.")
            error_message = "未选择项目，无法保存数据。"
            self.data_saved.emit(False, error_message)
            return json.dumps({"success": False, "error": error_message})

        session = self.Session()
        new_task_id_map = {} # 存储临时ID到新数据库ID的映射
        try:
            print(f"GanttBridge: Saving data for project ID: {self.project.id}")
            project_data = json.loads(project_json_str)
            tasks_data = project_data.get("tasks", [])
            deleted_task_ids = project_data.get("deletedTaskIds", [])

            # 1. 处理删除的任务
            if deleted_task_ids:
                # 先删除依赖这些任务的记录
                session.query(GanttDependency).filter(
                    GanttDependency.project_id == self.project.id,
                    (GanttDependency.predecessor_gantt_id.in_(deleted_task_ids)) |
                    (GanttDependency.successor_gantt_id.in_(deleted_task_ids))
                ).delete(synchronize_session=False)
                # 再删除任务本身
                session.query(GanttTask).filter(
                    GanttTask.project_id == self.project.id,
                    GanttTask.gantt_id.in_(deleted_task_ids)
                ).delete(synchronize_session=False)
                print(f"Deleted tasks: {deleted_task_ids}")

            # 2. 处理现有任务和新任务
            # --- 事务开始 ---
            # 1. 处理删除的任务 (保持不变)
            if deleted_task_ids:
                session.query(GanttDependency).filter(
                    GanttDependency.project_id == self.project.id,
                    (GanttDependency.predecessor_gantt_id.in_(deleted_task_ids)) |
                    (GanttDependency.successor_gantt_id.in_(deleted_task_ids))
                ).delete(synchronize_session=False)
                session.query(GanttTask).filter(
                    GanttTask.project_id == self.project.id,
                    GanttTask.gantt_id.in_(deleted_task_ids)
                ).delete(synchronize_session=False)
                print(f"Deleted tasks: {deleted_task_ids}")

            # 2. 处理更新和新增的任务
            existing_tasks_db = session.query(GanttTask).filter(GanttTask.project_id == self.project.id).all()
            existing_task_map = {task.gantt_id: task for task in existing_tasks_db}
            processed_gantt_ids = set() # 存储处理过的持久化ID
            all_dependencies_to_save = []

            for task_data in tasks_data:
                gantt_id = str(task_data["id"]) # 确保是字符串
                depends_str = task_data.get("depends", "")

                # 转换时间戳回datetime (确保是UTC)
                start_dt = datetime.fromtimestamp(task_data["start"] / 1000, tz=timezone.utc) if task_data.get("start") is not None else None
                end_dt = datetime.fromtimestamp(task_data["end"] / 1000, tz=timezone.utc) if task_data.get("end") is not None else None

                task_obj_data = {
                    "project_id": self.project.id,
                    "name": task_data["name"],
                    "code": task_data.get("code"),
                    "level": task_data.get("level", 0),
                    "status": task_data.get("status"),
                    "start_date": start_dt,
                    "duration": task_data.get("duration"),
                    "end_date": end_dt,
                    "start_is_milestone": task_data.get("startIsMilestone", False),
                    "end_is_milestone": task_data.get("endIsMilestone", False),
                    "progress": task_data.get("progress", 0),
                    "progress_by_worklog": task_data.get("progressByWorklog", False),
                    "description": task_data.get("description"),
                    "collapsed": task_data.get("collapsed", False),
                    "has_child": task_data.get("hasChild", False)
                }

                current_gantt_id = None # 用于依赖关系处理
                is_new_task = gantt_id.startswith("tmp_")

                if is_new_task:
                    # 新任务：插入数据库
                    # 1. 创建对象时，先使用临时ID填充gantt_id，避免NOT NULL错误
                    new_task = GanttTask(gantt_id=gantt_id, **task_obj_data)
                    # 2. 添加到 session
                    session.add(new_task)
                    # 3. Flush 获取数据库生成的真实 ID
                    session.flush()
                    # 4. 生成持久化 ID (使用数据库ID)
                    persistent_gantt_id = str(new_task.id)
                    # 5. 更新任务对象的 gantt_id 为持久化 ID
                    new_task.gantt_id = persistent_gantt_id
                    # 6. 记录临时ID到持久化ID的映射
                    new_task_id_map[gantt_id] = persistent_gantt_id
                    print(f"Added new task: {gantt_id} -> {persistent_gantt_id}")
                    current_gantt_id = persistent_gantt_id
                    processed_gantt_ids.add(current_gantt_id)
                    # 注意：新任务的依赖关系需要在所有任务处理完、ID映射确定后再处理
                elif gantt_id in existing_task_map:
                    # 现有任务：更新数据库
                    existing_task = existing_task_map.pop(gantt_id) # 从map中取出并移除，表示已处理
                    for key, value in task_obj_data.items():
                        setattr(existing_task, key, value)
                    # existing_task 对象已在 session 中，修改后会自动更新，无需 merge
                    print(f"Updated task: {gantt_id}")
                    current_gantt_id = gantt_id
                    processed_gantt_ids.add(current_gantt_id)
                else:
                    # 可能是从其他地方导入的持久化ID，但不在当前数据库中
                    # 尝试作为新任务插入，但使用提供的ID
                    print(f"Task with persistent id {gantt_id} not found in DB, attempting to insert.")
                    new_task = GanttTask(gantt_id=gantt_id, **task_obj_data)
                    try:
                        session.add(new_task)
                        session.flush()
                        print(f"Inserted task with provided persistent id: {gantt_id}")
                        current_gantt_id = gantt_id
                        processed_gantt_ids.add(current_gantt_id)
                    except Exception as insert_err:
                        print(f"Failed to insert task with id {gantt_id}: {insert_err}")
                        session.rollback() # 回滚单条插入错误，继续处理其他任务
                        continue # 跳过此任务的依赖处理

                # 处理依赖关系 (需要在此任务处理完后进行，以确保ID已更新)
                if current_gantt_id and depends_str:
                    predecessor_ids = depends_str.split(',')
                    for pred_id_raw in predecessor_ids:
                        pred_id = pred_id_raw.strip()
                        if pred_id: # 确保ID不为空
                            all_dependencies_to_save.append({
                                "predecessor": pred_id,
                                "successor": current_gantt_id # 使用当前任务的持久化ID
                            })

            # 3. 处理依赖关系 (在所有任务处理完之后)
            # 先删除该项目的所有旧依赖
            session.query(GanttDependency).filter(GanttDependency.project_id == self.project.id).delete(synchronize_session=False)
            print("Cleared old dependencies.")

            # 添加新的依赖关系
            added_deps_count = 0
            for dep_data in all_dependencies_to_save:
                pred_id = dep_data["predecessor"]
                succ_id = dep_data["successor"] # 这个ID应该是持久化的

                # 如果前置任务是新创建的，使用映射后的新ID
                final_pred_id = new_task_id_map.get(pred_id, pred_id)

                # 检查ID是否存在于已处理的任务集合中，防止无效依赖
                if final_pred_id in processed_gantt_ids and succ_id in processed_gantt_ids:
                    # 检查是否已存在相同的依赖（理论上不会，因为先清空了）
                    existing_dep = session.query(GanttDependency).filter_by(
                        project_id=self.project.id,
                        predecessor_gantt_id=final_pred_id,
                        successor_gantt_id=succ_id
                    ).first()
                    if not existing_dep:
                        new_dependency = GanttDependency(
                            project_id=self.project.id,
                            predecessor_gantt_id=final_pred_id,
                            successor_gantt_id=succ_id,
                            type="FS" # 假设默认为 FS 类型
                        )
                        session.add(new_dependency)
                        added_deps_count += 1
                else:
                     print(f"Skipping dependency: Pred '{final_pred_id}' or Succ '{succ_id}' not found in processed tasks.")


            # --- 依赖关系处理 ---
            # 先删除该项目的所有旧依赖
            session.query(GanttDependency).filter(GanttDependency.project_id == self.project.id).delete(synchronize_session=False)
            print("Cleared old dependencies.")

            # 添加新的依赖关系 (使用最终的ID)
            added_deps_count = 0
            for dep_data in all_dependencies_to_save:
                pred_id_orig = dep_data["predecessor"]
                succ_id_orig = dep_data["successor"] # 这个ID应该是持久化的

                # 使用映射转换ID
                final_pred_id = new_task_id_map.get(pred_id_orig, pred_id_orig)
                final_succ_id = new_task_id_map.get(succ_id_orig, succ_id_orig) # 后继ID也可能来自新任务

                # 检查ID是否存在于已处理的任务集合中
                if final_pred_id in processed_gantt_ids and final_succ_id in processed_gantt_ids:
                    new_dependency = GanttDependency(
                        project_id=self.project.id,
                        predecessor_gantt_id=final_pred_id,
                        successor_gantt_id=final_succ_id,
                        type="FS" # 假设默认为 FS 类型
                    )
                    session.add(new_dependency)
                    added_deps_count += 1
                else:
                     print(f"Skipping dependency: Pred '{final_pred_id}' (orig: {pred_id_orig}) or Succ '{final_succ_id}' (orig: {succ_id_orig}) not found in processed tasks.")

            # --- 事务提交 ---
            session.commit()
            print(f"Saved/Updated {len(processed_gantt_ids)} tasks and added {added_deps_count} dependencies.")
            self.data_saved.emit(True, "甘特图数据保存成功！")
            # 返回包含ID映射的JSON
            return json.dumps({"success": True, "id_map": new_task_id_map})

        except Exception as e:
            session.rollback()
            print(f"Error saving Gantt data: {e}")
            error_message = f"保存失败: {e}"
            self.data_saved.emit(False, error_message)
            # 返回包含错误的JSON
            return json.dumps({"success": False, "error": error_message})
        finally:
            session.close()


class ProjectProgressWidget(QWidget):
    """项目进度管理组件，集成jQueryGantt甘特图"""

    # 定义信号
    progress_updated = Signal()

    # Modify __init__ to remove project argument
    def __init__(self, engine=None, parent=None):
        super().__init__(parent)
        # self.project = project # No longer needed here
        self.engine = engine
        self.setObjectName("projectProgressWidget")
        self.current_project = None # Track the currently selected project in the widget
        self.setup_ui()

    def setup_ui(self):
        """初始化界面"""
        self.setStyleSheet("background: transparent;")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 18, 18, 18) # Add some margins

        # --- Add Project Selector ---
        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目进度:", self)
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.layout.addLayout(selector_layout)
        # --- Project Selector End ---

        # 创建WebEngineView并设置样式
        # Use FramelessWebEngineView
        self.web_view = FramelessWebEngineView(self)
        # Ensure background is transparent (might be redundant but safe)
        self.web_view.setAttribute(Qt.WA_TranslucentBackground)
        self.web_view.setStyleSheet("background: transparent;")
        self.layout.addWidget(self.web_view) # Add web_view *after* selector

        # --- 设置 QWebChannel ---
        self.channel = QWebChannel(self.web_view.page())
        # Initialize GanttBridge without a project initially
        self.gantt_bridge = GanttBridge(self.engine, parent=self)
        self.channel.registerObject("ganttBridge", self.gantt_bridge) # 注册对象，JS端将通过 'ganttBridge' 访问
        self.web_view.page().setWebChannel(self.channel)
        # 连接保存信号到信息提示
        self.gantt_bridge.data_saved.connect(self.show_save_status)
        # -----------------------

        # 加载本地甘特图资源
        self.load_gantt()

        # Connect project selector signal
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_project = self.project_selector.itemData(index)
        if selected_project and isinstance(selected_project, Project):
            self.current_project = selected_project
            print(f"Project selected in widget: {self.current_project.name}")
            self.gantt_bridge.set_project(self.current_project)
            # Trigger data loading in JavaScript
            self.web_view.page().runJavaScript("loadInitialData();")
        else:
            # Handle "请选择项目..." or error case
            self.current_project = None
            self.gantt_bridge.set_project(None)
            # Optionally clear the Gantt chart in JS
            self.web_view.page().runJavaScript("clearGantt();")
            print("No valid project selected.")


    def load_gantt(self):
        """加载本地jQueryGantt资源"""
        try:
            # 获取绝对路径并确保路径存在
            gantt_dir = os.path.dirname(os.path.abspath(__file__))
            gantt_path = os.path.join(gantt_dir, "jQueryGantt", "gantt.html")
            libs_dir = os.path.join(gantt_dir, "jQueryGantt", "libs") # 获取libs目录
            self.qwebchannel_js_path = os.path.join(libs_dir, "qwebchannel.js") # qwebchannel.js 的路径

            if not os.path.exists(gantt_path):
                raise FileNotFoundError(f"Gantt file not found at {gantt_path}")
            if not os.path.exists(self.qwebchannel_js_path):
                 # 尝试从标准位置复制（如果需要）
                 # 或者提示用户手动放置
                 print(f"Warning: qwebchannel.js not found at {self.qwebchannel_js_path}. QWebChannel might not work.")
                 # raise FileNotFoundError(f"qwebchannel.js not found at {self.qwebchannel_js_path}")


            # 转换为file:// URL格式并设置基础URL
            gantt_url = QUrl.fromLocalFile(gantt_path)
            self.web_view.setUrl(gantt_url)

            # 设置页面加载完成后的回调
            self.web_view.loadFinished.connect(self.on_gantt_loaded)
        except Exception as e:
            print(f"Error loading Gantt: {str(e)}")

    def on_gantt_loaded(self, success):
        """甘特图加载完成回调"""
        if success:
            print("jQueryGantt HTML loaded successfully. Initializing QWebChannel...")
            # 注入 qwebchannel.js 并初始化连接
            try:
                with open(self.qwebchannel_js_path, 'r', encoding='utf-8') as f:
                    qwebchannel_js = f.read()

                # Use triple quotes and escape JS braces for f-string compatibility
                init_script = f"""
                {qwebchannel_js}

                var ganttBridge;
                new QWebChannel(qt.webChannelTransport, function (channel) {{
                    window.ganttBridge = channel.objects.ganttBridge;
                    console.log("QWebChannel connected, ganttBridge object available.");

                    // Define functions to load/clear data, called by Python later
                    window.loadInitialData = function() {{ // Escape braces
                        console.log("loadInitialData called by Python.");
                        if (window.ganttBridge && window.ganttBridge.load_gantt_data) {{ // Escape braces
                            window.ganttBridge.load_gantt_data(function(jsonData) {{ // Escape braces
                                if (jsonData) {{ // Escape braces
                                    try {{ // Escape braces
                                        var projectData = JSON.parse(jsonData);
                                        if (typeof ge !== 'undefined' && ge.loadProject) {{ // Escape braces
                                            console.log("Loading project data into Gantt:", projectData);
                                            ge.loadProject(projectData);
                                            ge.redraw();
                                            console.log("Gantt data loaded/reloaded from Python.");
                                        }} else {{ // Escape braces
                                            console.error("Gantt object 'ge' not found or loadProject method missing.");
                                        }} // Escape braces
                                    }} catch (e) {{ // Escape braces
                                        console.error("Error parsing or loading Gantt data:", e, jsonData);
                                    }} // Escape braces
                                }} else {{ // Escape braces
                                    console.warn("Received empty data from load_gantt_data.");
                                }} // Escape braces
                            }}); // Escape braces
                        }} else {{ // Escape braces
                             console.error("ganttBridge or load_gantt_data function not available.");
                        }} // Escape braces
                    }}; // Escape braces

                    window.clearGantt = function() {{ // Escape braces
                        console.log("clearGantt called by Python.");
                         if (typeof ge !== 'undefined' && ge.reset) {{ // Escape braces
                             ge.reset(); // Clear the gantt chart
                             console.log("Gantt chart cleared.");
                         }} else {{ // Escape braces
                             console.error("Gantt object 'ge' not found or reset method missing.");
                         }} // Escape braces
                    }}; // Escape braces

                    // Don't load data immediately on channel connection anymore
                    // loadInitialData(); // Remove this initial call
                }});
                console.log("QWebChannel setup initiated.");
                """
                self.web_view.page().runJavaScript(init_script)
            except Exception as e:
                 print(f"Error injecting qwebchannel.js or initializing: {e}")

        else:
            print("Failed to load jQueryGantt HTML")

    # 移除旧的 init_gantt_data 和 update_progress_data 方法
    # def init_gantt_data(self): ...
    # def update_progress_data(self, data): ...

    @Slot(bool, str)
    def show_save_status(self, success, message):
        """显示保存状态的信息提示"""
        if success:
            InfoBar.success(
                title='成功',
                content=message,
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self
            )
        else:
            InfoBar.error(
                title='错误',
                content=message,
                duration=5000, # 错误信息显示时间长一点
                position=InfoBarPosition.TOP,
                parent=self
            )