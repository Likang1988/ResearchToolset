import json
from datetime import datetime, timezone
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog # Added QHBoxLayout, QLabel, QFileDialog
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl, Signal, QObject, Slot
from qfluentwidgets import TitleLabel, InfoBar, InfoBarPosition, ToolTipFilter, ToolTipPosition
from qframelesswindow.webengine import FramelessWebEngineView
from app.utils.ui_utils import UIUtils
# 需要在文件顶部导入
from app.models.database import Project, sessionmaker, Actionlog # Import Actionlog
from app.models.database import sessionmaker, GanttTask, GanttDependency, Project, Actionlog # Import Actionlog
from enum import Enum # Import Enum
import os # 确保导入 os 模块
import csv
from io import StringIO # 用于 CSV 写入内存
import pandas as pd # Import pandas

class ProjectProgressWidget(QWidget):
    """项目进度管理组件，集成jQueryGantt甘特图"""

    # 定义信号
    progress_updated = Signal()

    def __init__(self, engine=None, parent=None):
        super().__init__(parent)        
        self.engine = engine
        self.setObjectName("projectProgressWidget")
        self.current_project = None # Track the currently selected project in the widget
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
                # print("ProjectProgressWidget: Connected to project_updated signal.") # Removed print
            else:
                 # print("ProjectProgressWidget: Could not find main window or project_updated signal.") # Removed print
                 pass # Do nothing if signal not found
        except Exception as e:
            # print(f"ProjectProgressWidget: Error connecting signal: {e}") # Removed print
            pass # Ignore connection errors silently


    def _refresh_project_selector(self):
        """刷新项目选择下拉框的内容"""
        # print("ProjectProgressWidget: Refreshing project selector...") # Removed print
        if not hasattr(self, 'project_selector') or not self.engine:
            # print("ProjectProgressWidget: Project selector or engine not initialized.") # Removed print
            return

        current_project_id = None
        current_data = self.project_selector.currentData()
        if isinstance(current_data, Project):
            current_project_id = current_data.id

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
                         # 如果之前的项目找不到了（可能被删除），则触发一次选中事件以清空甘特图
                         self._on_project_selected(0) # 选中 "请选择项目..."

        except Exception as e:
            # print(f"Error refreshing project selector: {e}") # Removed print
            self.project_selector.addItem("加载项目出错", userData=None)
            self.project_selector.setEnabled(False)
        finally:
            session.close()
            # print("ProjectProgressWidget: Project selector refreshed.") # Removed print

    def setup_ui(self):
        """初始化界面"""
        # 启用QtWebEngine远程调试，端口8081
        os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "8081"
        # -------------------------------
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 18, 18, 18) # Add some margins

        selector_layout = QHBoxLayout()
        selector_label = TitleLabel("项目进度-", self)
        selector_label.setToolTip("以甘特图形式管理项目任务进度")
        selector_label.installEventFilter(ToolTipFilter(selector_label, showDelay=300, position=ToolTipPosition.RIGHT))
        self.project_selector = UIUtils.create_project_selector(self.engine, self)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.project_selector)
        selector_layout.addStretch()
        self.layout.addLayout(selector_layout)

        self.web_view = FramelessWebEngineView(self)
        self.layout.addWidget(self.web_view) # Add web_view *after* selector

        self.channel = QWebChannel(self.web_view.page())
        self.gantt_bridge = GanttBridge(self.engine, self.web_view, parent=self) # Pass web_view
        self.channel.registerObject("ganttBridge", self.gantt_bridge) # 注册对象，JS端将通过 'ganttBridge' 访问
        self.web_view.page().setWebChannel(self.channel)
        # 连接保存信号到信息提示
        self.gantt_bridge.data_saved.connect(self.show_save_status)
        # -----------------------

        # 加载本地甘特图资源
        self.load_gantt()

        self.project_selector.currentIndexChanged.connect(self._on_project_selected)

    def _on_project_selected(self, index):
        """Handles project selection change."""
        selected_project = self.project_selector.itemData(index)
        if selected_project and isinstance(selected_project, Project):
            self.current_project = selected_project
            UIUtils.show_success(self, "项目进度", f"项目已选择: {self.current_project.name}")
            self.gantt_bridge.set_project(self.current_project)
            self.web_view.page().runJavaScript("loadInitialData();")
        else:
            self.current_project = None
            self.gantt_bridge.set_project(None)
            self.web_view.page().runJavaScript("clearGantt();")
            UIUtils.show_info(self, "项目进度", "请选择一个项目以查看进度")


    def load_project_by_object(self, project):
        """根据项目对象在项目选择器中选中项目并加载数据"""
        if not project or not hasattr(self, 'project_selector'):
            print("无效的项目对象或项目选择器未初始化。")
            return

        # 查找项目在 ComboBox 中的索引
        index = -1
        for i in range(self.project_selector.count()):
            data = self.project_selector.itemData(i)
            if isinstance(data, Project) and data.id == project.id:
                index = i
                break

        if index != -1:
            self.project_selector.setCurrentIndex(index) # 这将触发 _on_project_selected
        else:
            print(f"未在项目选择器中找到项目: {project.financial_code}")


    def load_gantt(self):
        """加载本地jQueryGantt资源"""
        try:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            gantt_base_dir = os.path.abspath(os.path.join(current_dir, '..', '..', 'integration', 'jQueryGantt'))
            gantt_path = os.path.join(gantt_base_dir, "gantt.html")
            libs_dir = os.path.join(gantt_base_dir, "libs") # 获取新的libs目录
            self.qwebchannel_js_path = os.path.join(libs_dir, "qwebchannel.js") # qwebchannel.js 的路径

            if not os.path.exists(gantt_path):
                raise FileNotFoundError(f"Gantt file not found at {gantt_path}")
            if not os.path.exists(self.qwebchannel_js_path):
                 # 尝试从标准位置复制（如果需要）
                 # 或者提示用户手动放置
                 # print(f"Warning: qwebchannel.js not found at {self.qwebchannel_js_path}. QWebChannel might not work.") # Removed print
                 pass # Silently ignore if not found for now


            gantt_url = QUrl.fromLocalFile(gantt_path)
            self.web_view.setUrl(gantt_url)

            # 设置页面加载完成后的回调
            self.web_view.loadFinished.connect(self.on_gantt_loaded)
        except Exception as e:
            # print(f"Error loading Gantt: {str(e)}") # Removed print
            pass # Silently ignore loading errors for now

    def on_gantt_loaded(self, success):
        """甘特图加载完成回调"""
        if success:
            # 添加增强调试信息
            self.web_view.page().runJavaScript("""
                try {
                    console.group('Gantt Debug Info');
                    console.log('Gantt chart loaded successfully');
                    console.log('Debug URL: http://127.0.0.1:8081');
                    console.log('Tasks count:', ge.tasks.length);
                    console.log('Links count:', ge.links.length);
                    
                    // 暴露Gantt对象到全局以便调试
                    window.debugGantt = {
                        getTasks: function() { return ge.tasks; },
                        getLinks: function() { return ge.links; },
                        getCurrentTask: function() { return ge.currentTask; },
                        getRecursionLimit: function() { return 10; }
                    };
                    
                    // 添加递归保护检查
                    if (typeof Task.prototype._originalMoveTo === 'undefined') {
                        Task.prototype._originalMoveTo = Task.prototype.moveTo;
                        Task.prototype.moveTo = function(start, ignoreMilestones, propagateToInferiors, depth) {
                            depth = depth || 0;
                            if (depth > debugGantt.getRecursionLimit()) {
                                console.error('Recursion limit exceeded in moveTo');
                                return false;
                            }
                            return this._originalMoveTo(start, ignoreMilestones, propagateToInferiors, depth);
                        };
                    }
                    console.groupEnd();
                } catch (e) {
                    console.error('Gantt debug initialization error:', e);
                }
            """)
            try:
                with open(self.qwebchannel_js_path, 'r', encoding='utf-8') as f:
                    qwebchannel_js = f.read()

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
                 # print(f"Error injecting qwebchannel.js or initializing: {e}") # Removed print
                 pass # Silently ignore injection errors

        else:
            # print("Failed to load jQueryGantt HTML") # Removed print
            pass # Silently ignore load failure

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

class GanttBridge(QObject):
    """用于在Python和JavaScript之间通过QWebChannel通信的桥梁类"""
    data_saved = Signal(bool, str) # 信号：保存是否成功，消息

    def __init__(self, engine, web_view, parent=None): # Added web_view parameter
        super().__init__(parent)
        self.engine = engine
        self.web_view = web_view # Store web_view instance for PNG export
        self.project = None # Project will be set later
        self.Session = sessionmaker(bind=self.engine)

    def set_project(self, project):
        """Sets the current project for the bridge."""
        self.project = project
        # print(f"GanttBridge project set to: {project.name if project else 'None'}") # Removed print

    @Slot(result=str) # 返回JSON字符串
    def load_gantt_data(self):
        """从数据库加载指定项目的甘特图数据"""
        if not self.project:
            # print("GanttBridge: No project selected, returning empty data.") # Removed print
            return json.dumps({
                "tasks": [], "selectedRow": -1, "deletedTaskIds": [],
                "resources": [], "roles": [], "canWrite": False, "canDelete": False,
                "canWriteOnParent": False, "canAdd": False
            })

        session = self.Session()
        try:
            # print(f"GanttBridge: Loading data for project ID: {self.project.id}") # Removed print
            # 按照 order 字段排序加载任务
            tasks_db = session.query(GanttTask).filter(GanttTask.project_id == self.project.id).order_by(GanttTask.order).all()
            dependencies_db = session.query(GanttDependency).filter(GanttDependency.project_id == self.project.id).all()

            tasks_json = []
            for task in tasks_db:
                # 打印任务ID和进度，用于调试
                print(f"Loading task {task.gantt_id}: progress = {task.progress}")

                start_ms = int(task.start_date.replace(tzinfo=timezone.utc).timestamp() * 1000) if task.start_date else None
                end_ms = int(task.end_date.replace(tzinfo=timezone.utc).timestamp() * 1000) if task.end_date else None

                # 确保进度值是浮点数且在0-100之间
                progress = float(task.progress) if task.progress is not None else 0.0
                progress = max(0.0, min(100.0, progress))
                
                tasks_json.append({
                    "id": task.gantt_id, # 使用存储的gantt_id
                    "name": task.name,
                    "progress": progress,  # 使用处理后的进度值
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
                    "hasChild": task.has_child,
                    "responsible": task.responsible # 添加负责人字段
                })

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
            # print(f"Loaded {len(tasks_json)} tasks for project {self.project.id}") # Removed print
            return json.dumps(project_data, default=str) # 使用default=str处理日期等

        except Exception as e:
            # print(f"Error loading Gantt data: {e}") # Removed print
            session.rollback()
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
                deps.append(str(dep.predecessor_gantt_id))
        return ",".join(deps)

    @Slot(str, result=str) # 接收JSON字符串，返回包含ID映射的JSON字符串或错误信息
    def save_gantt_data(self, project_json_str):
        """
        将甘特图数据保存到数据库。
        成功时返回包含临时ID到持久化ID映射的JSON字符串。
        失败时返回包含错误信息的JSON字符串。
        """
        if not self.project:
            # print("GanttBridge: No project selected, cannot save data.") # Removed print
            error_message = "未选择项目，无法保存数据。"
            self.data_saved.emit(False, error_message)
            return json.dumps({"success": False, "error": error_message})

        session = self.Session()
        new_task_id_map = {} # 存储临时ID到新数据库ID的映射
        try:
            # print(f"GanttBridge: Saving data for project ID: {self.project.id}") # Removed print
            project_data = json.loads(project_json_str)
            tasks_data = project_data.get("tasks", [])
            deleted_task_ids = project_data.get("deletedTaskIds", [])

            # --- 事务开始 ---
            # 1. 处理删除的任务
            if deleted_task_ids:
                # 记录删除的任务
                for deleted_gantt_id in deleted_task_ids:
                    task_to_delete = session.query(GanttTask).filter(
                        GanttTask.project_id == self.project.id,
                        GanttTask.gantt_id == deleted_gantt_id
                    ).first()
                    if task_to_delete:
                        old_data_str = json.dumps({
                            "id": task_to_delete.gantt_id,
                            "name": task_to_delete.name,
                            "code": task_to_delete.code,
                            "level": task_to_delete.level,
                            "status": task_to_delete.status,
                            "start_date": str(task_to_delete.start_date),
                            "duration": task_to_delete.duration,
                            "end_date": str(task_to_delete.end_date),
                            "progress": task_to_delete.progress,
                            "responsible": task_to_delete.responsible
                        }, default=str, ensure_ascii=False)

                        actionlog = Actionlog(
                            project_id=self.project.id,
                            gantt_task_id=task_to_delete.id, # 关联到数据库中的任务ID
                            type="任务",
                            action="删除",
                            description=f"删除任务：{task_to_delete.name} (ID: {task_to_delete.gantt_id})",
                            operator="系统用户",
                            old_data=old_data_str,
                            related_info=f"项目: {self.project.financial_code}"
                        )
                        session.add(actionlog)

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
                # print(f"Deleted tasks: {deleted_task_ids}") # Removed print

            # 2. 处理更新和新增的任务
            existing_tasks_db = session.query(GanttTask).filter(GanttTask.project_id == self.project.id).all()
            existing_task_map = {task.gantt_id: task for task in existing_tasks_db}
            processed_gantt_ids = set() # 存储处理过的持久化ID
            all_dependencies_to_save = []

            for index, task_data in enumerate(tasks_data): # 添加 enumerate 获取索引
                gantt_id = str(task_data["id"]) # 确保是字符串
                depends_str = task_data.get("depends", "")

                start_dt = datetime.fromtimestamp(task_data["start"] / 1000, tz=timezone.utc) if task_data.get("start") is not None else None
                end_dt = datetime.fromtimestamp(task_data["end"] / 1000, tz=timezone.utc) if task_data.get("end") is not None else None

                # 处理进度值，确保是浮点数且在0-100之间
                progress = task_data.get("progress", 0)
                try:
                    progress = float(progress)
                    progress = max(0.0, min(100.0, progress))
                    print(f"Processing task {task_data['name']}, progress = {progress}")
                except (TypeError, ValueError):
                    progress = 0.0
                    print(f"Invalid progress value for task {task_data['name']}, defaulting to 0")


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
                    "progress": progress,  # 使用处理后的进度值
                    "progress_by_worklog": task_data.get("progressByWorklog", False),
                    "description": task_data.get("description"),
                    "collapsed": task_data.get("collapsed", False),
                    "has_child": task_data.get("hasChild", False),
                    "responsible": task_data.get("responsible"), # 添加负责人字段
                    "order": index # 添加 order 字段
                }

                current_gantt_id = None # 用于依赖关系处理
                is_new_task = gantt_id.startswith("tmp_")

                if is_new_task:
                    # 新任务：插入数据库
                    new_task = GanttTask(gantt_id=gantt_id, **task_obj_data)
                    session.add(new_task)
                    session.flush()
                    persistent_gantt_id = str(new_task.id)
                    new_task.gantt_id = persistent_gantt_id
                    new_task_id_map[gantt_id] = persistent_gantt_id

                    # 添加操作日志 (新增任务)
                    actionlog = Actionlog(
                        project_id=self.project.id,
                        gantt_task_id=new_task.id, # 关联到新创建的任务ID
                        type="任务",
                        action="新增",
                        description=f"新增任务：{new_task.name} (ID: {new_task.gantt_id})",
                        operator="系统用户", # TODO: 获取当前登录用户
                        new_data=json.dumps({
                            "id": new_task.gantt_id,
                            "name": new_task.name,
                            "code": new_task.code,
                            "level": new_task.level,
                            "status": new_task.status,
                            "start_date": str(new_task.start_date),
                            "duration": new_task.duration,
                            "end_date": str(new_task.end_date),
                            "progress": new_task.progress,
                            "responsible": new_task.responsible
                        }, default=str, ensure_ascii=False),
                        related_info=f"项目: {self.project.financial_code}"
                    )
                    session.add(actionlog)

                    # print(f"Added new task: {gantt_id} -> {persistent_gantt_id}") # Removed print
                    current_gantt_id = persistent_gantt_id
                    processed_gantt_ids.add(current_gantt_id)
                elif gantt_id in existing_task_map:
                    # 现有任务：更新数据库
                    existing_task = existing_task_map.pop(gantt_id) # 从map中取出并移除，表示已处理

                    # 记录旧数据
                    old_data = {
                        "id": existing_task.gantt_id,
                        "name": existing_task.name,
                        "code": existing_task.code,
                        "level": existing_task.level,
                        "status": existing_task.status,
                        "start_date": str(existing_task.start_date),
                        "duration": existing_task.duration,
                        "end_date": str(existing_task.end_date),
                        "progress": existing_task.progress,
                        "responsible": existing_task.responsible
                    }
                    old_data_str = json.dumps(old_data, default=str, ensure_ascii=False)


                    # 检查数据是否有变化
                    data_changed = False
                    for key, value in task_obj_data.items():
                        # 比较新旧数据，注意处理日期和枚举类型
                        old_value = getattr(existing_task, key)
                        if isinstance(old_value, datetime) and isinstance(value, datetime):
                            if old_value.replace(tzinfo=None) != value.replace(tzinfo=None): # 忽略时区比较
                                data_changed = True
                                break
                        elif isinstance(old_value, Enum) and isinstance(value, Enum):
                             if old_value != value:
                                 data_changed = True
                                 break
                        elif old_value != value:
                            data_changed = True
                            break

                    if data_changed:
                        for key, value in task_obj_data.items():
                            setattr(existing_task, key, value)

                        # 记录新数据
                        new_data = {
                            "id": existing_task.gantt_id,
                            "name": existing_task.name,
                            "code": existing_task.code,
                            "level": existing_task.level,
                            "status": existing_task.status,
                            "start_date": str(existing_task.start_date),
                            "duration": existing_task.duration,
                            "end_date": str(existing_task.end_date),
                            "progress": existing_task.progress,
                            "responsible": existing_task.responsible
                        }
                        new_data_str = json.dumps(new_data, default=str, ensure_ascii=False)

                        # 添加操作日志 (编辑任务)
                        actionlog = Actionlog(
                            project_id=self.project.id,
                            gantt_task_id=existing_task.id, # 关联到数据库中的任务ID
                            type="任务",
                            action="编辑",
                            description=f"编辑任务：{existing_task.name} (ID: {existing_task.gantt_id})",
                            operator="系统用户", # TODO: 获取当前登录用户
                            old_data=old_data_str,
                            new_data=new_data_str,
                            related_info=f"项目: {self.project.financial_code}"
                        )
                        session.add(actionlog)
                        # print(f"Recorded edit for task: {gantt_id}") # Added print for debugging
                    # else:
                        # print(f"Task data for {gantt_id} unchanged, no edit log recorded.") # Added print for debugging


                    # print(f"Updated task: {gantt_id}") # Removed print
                    current_gantt_id = gantt_id
                    processed_gantt_ids.add(current_gantt_id)
                else:
                    # print(f"Task with persistent id {gantt_id} not found in DB, attempting to insert.") # Removed print
                    new_task = GanttTask(gantt_id=gantt_id, **task_obj_data)
                    try:
                        session.add(new_task)
                        session.flush()

                        # 添加操作日志 (新增任务 - 持久化ID)
                        actionlog = Actionlog(
                            project_id=self.project.id,
                            gantt_task_id=new_task.id, # 关联到新创建的任务ID
                            type="任务",
                            action="新增",
                            description=f"新增任务：{new_task.name} (ID: {new_task.gantt_id})",
                            operator="系统用户", # TODO: 获取当前登录用户
                            new_data=json.dumps({
                                "id": new_task.gantt_id,
                                "name": new_task.name,
                                "code": new_task.code,
                                "level": new_task.level,
                                "status": new_task.status,
                                "start_date": str(new_task.start_date),
                                "duration": new_task.duration,
                                "end_date": str(new_task.end_date),
                                "progress": new_task.progress,
                                "responsible": new_task.responsible
                            }, default=str, ensure_ascii=False),
                            related_info=f"项目: {self.project.financial_code}"
                        )
                        session.add(actionlog)

                        # print(f"Inserted task with provided persistent id: {gantt_id}") # Removed print
                        current_gantt_id = gantt_id
                        processed_gantt_ids.add(current_gantt_id)
                    except Exception as insert_err:
                        # print(f"Failed to insert task with id {gantt_id}: {insert_err}") # Removed print
                        session.rollback() # 回滚单条插入错误，继续处理其他任务
                        continue # 跳过此任务的依赖处理

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
            # print("Cleared old dependencies.") # Removed print

            # 添加新的依赖关系
            added_deps_count = 0
            for dep_data in all_dependencies_to_save:
                pred_id = dep_data["predecessor"]
                succ_id = dep_data["successor"] # 这个ID应该是持久化的

                final_pred_id = new_task_id_map.get(pred_id, pred_id)

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

            added_deps_count = 0
            for dep_data in all_dependencies_to_save:
                pred_id_orig = dep_data["predecessor"]
                succ_id_orig = dep_data["successor"] # 这个ID应该是持久化的

                final_pred_id = new_task_id_map.get(pred_id_orig, pred_id_orig)
                final_succ_id = new_task_id_map.get(succ_id_orig, succ_id_orig) # 后继ID也可能来自新任务

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

            # --- 重新计算父任务进度 ---
            def calculate_parent_task_progress(parent_task, children_tasks):
                """计算父任务的进度"""
                if not children_tasks:
                    return parent_task.progress or 0

                total_weight = 0
                weighted_progress = 0

                for child in children_tasks:
                    # 使用 duration 作为权重，如果 duration 为 None 或 0，使用默认权重 1
                    weight = max(child.duration or 1, 1)  # 确保权重至少为1
                    total_weight += weight
                    # 使用子任务的进度，如果为 None，默认为 0
                    child_progress = max(min(child.progress or 0, 100), 0)  # 确保进度在0-100之间
                    weighted_progress += child_progress * weight

                # 计算加权平均进度，保留两位小数
                if total_weight > 0:
                    return round(weighted_progress / total_weight, 2)
                return 0

            try:
                # 按层级和ID排序获取所有任务
                all_tasks_after_save = session.query(GanttTask).filter(
                    GanttTask.project_id == self.project.id
                ).order_by(GanttTask.level.desc(), GanttTask.id).all()

                # 创建任务层级映射
                tasks_by_level = {}
                for task in all_tasks_after_save:
                    if task.level not in tasks_by_level:
                        tasks_by_level[task.level] = []
                    tasks_by_level[task.level].append(task)

                # 从底层开始向上计算父任务进度
                max_level = max(tasks_by_level.keys()) if tasks_by_level else 0
                for level in range(max_level - 1, -1, -1):  # 从最深层级-1开始向上
                    if level not in tasks_by_level:
                        continue

                    for parent_task in tasks_by_level[level]:
                        if not parent_task.has_child:
                            continue

                        # 获取直接子任务
                        children_tasks = [task for task in tasks_by_level.get(level + 1, [])
                                        if task.level == parent_task.level + 1]

                        # 计算并更新父任务进度
                        new_progress = calculate_parent_task_progress(parent_task, children_tasks)
                        if parent_task.progress != new_progress:
                            parent_task.progress = new_progress
                            logging.info(f"更新父任务 '{parent_task.name}' 的进度为: {new_progress}%")

            except Exception as e:
                logging.error(f"计算父任务进度时出错: {str(e)}")
                raise


            # --- 事务提交 ---
            session.commit()
            # print(f"Saved/Updated {len(processed_gantt_ids)} tasks and added {added_deps_count} dependencies. Parent progress recalculated.") # Removed print
            self.data_saved.emit(True, "甘特图数据保存成功！")
            # 数据保存成功后，调用JS函数刷新甘特图
            self.web_view.page().runJavaScript("loadInitialData();")
            # 发出信号通知进度数据已更新
            self.parent().progress_updated.emit() # 假设父级是 ProjectProgressWidget
            return json.dumps({"success": True, "id_map": new_task_id_map})

        except Exception as e:
            session.rollback()
            # print(f"Error saving Gantt data: {e}") # Removed print
            error_message = f"保存失败: {e}"
            self.data_saved.emit(False, error_message)
            return json.dumps({"success": False, "error": error_message})
        finally:
            session.close()



    @Slot(str) # 只接收 JSON 字符串
    def export_gantt_data(self, gantt_json_str):
        """
        接收来自 JavaScript 的甘特图 JSON 数据，弹出“另存为”对话框，
        让用户选择文件类型（通过过滤器）并保存。
        """
        if not self.project:
            error_message = "未选择项目，无法导出数据。"
            print(f"GanttBridge: {error_message}")
            self.data_saved.emit(False, error_message)
            return

        print(f"GanttBridge: Received export request.")

        try:
            parent_widget = self.parent() if isinstance(self.parent(), QWidget) else None
            now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_filename = f"项目_{self.project.financial_code}_甘特图_{now_str}"
            default_dir = os.path.expanduser("~") # 用户主目录

            filters = {
                "Excel 文件 (*.xlsx)": "XLSX",
                "JSON 文件 (*.json)": "JSON",
                "CSV 文件 (*.csv)": "CSV",
                "文本文档 (*.txt)": "TXT",
                "所有文件 (*)": "ALL"
            }
            filter_string = ";;".join(filters.keys())
            default_filter = "Excel 文件 (*.xlsx)" # Default to Excel

            default_filepath = os.path.join(default_dir, f"{base_filename}.xlsx") # Default filename with Excel ext

            filePath, selectedFilter = QFileDialog.getSaveFileName(
                parent_widget,
                "导出甘特图数据",
                default_filepath,
                filter_string,
                default_filter # Set the initial filter
            )

            if not filePath:
                print("GanttBridge: Export cancelled by user.")
                self.data_saved.emit(False, "导出已取消")
                return

            export_format = filters.get(selectedFilter, "JSON") # Default to JSON if filter unknown
            if export_format == "ALL": # If user selected "All files", try to guess from extension or default
                ext = os.path.splitext(filePath)[1].lower()
                if ext == ".xlsx": export_format = "XLSX"
                elif ext == ".json": export_format = "JSON"
                elif ext == ".csv": export_format = "CSV"
                elif ext == ".txt": export_format = "TXT"
                else: export_format = "XLSX" # Default to Excel if extension is missing or unknown

            file_base, file_ext = os.path.splitext(filePath)
            required_ext = ""
            if export_format == "XLSX": required_ext = ".xlsx"
            elif export_format == "JSON": required_ext = ".json"
            elif export_format == "CSV": required_ext = ".csv"
            elif export_format == "TXT": required_ext = ".txt"

            if not file_ext and required_ext:
                filePath += required_ext
            elif file_ext.lower() != required_ext and required_ext:
                 print(f"Warning: File extension mismatch ('{file_ext}' vs '{required_ext}'). Saving as {export_format}.")
                 filePath = file_base + required_ext # Force correct extension


            print(f"GanttBridge: Exporting data to: {filePath} as {export_format}")

            try:
                gantt_data = json.loads(gantt_json_str)
                tasks = gantt_data.get("tasks", [])

                if export_format == "JSON":
                    with open(filePath, 'w', encoding='utf-8') as f:
                        json.dump(gantt_data, f, ensure_ascii=False, indent=4)

                elif export_format == "CSV":
                    output = StringIO()
                    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
                    header = ["ID", "名称", "层级", "开始日期", "结束日期", "工期(天)", "进度(%)", "依赖项", "状态", "描述"]
                    writer.writerow(header)
                    for task in tasks:
                        start_str = datetime.fromtimestamp(task["start"] / 1000).strftime('%Y-%m-%d') if task.get("start") else ""
                        end_str = datetime.fromtimestamp(task["end"] / 1000).strftime('%Y-%m-%d') if task.get("end") else ""
                        duration_days = task.get("duration", "")
                        writer.writerow([
                            task.get("id", ""), task.get("name", ""), task.get("level", ""),
                            start_str, end_str, duration_days, task.get("progress", ""),
                            task.get("depends", ""), task.get("status", ""), task.get("description", "")
                        ])
                    with open(filePath, 'w', encoding='utf-8-sig', newline='') as f:
                        f.write(output.getvalue())
                    output.close()

                elif export_format == "TXT":
                    with open(filePath, 'w', encoding='utf-8') as f:
                        f.write(f"项目: {self.project.name} ({self.project.financial_code}) - 甘特图数据\n")
                        f.write("=" * 40 + "\n\n")
                        for task in tasks:
                            indent = "  " * task.get("level", 0)
                            start_str = datetime.fromtimestamp(task["start"] / 1000).strftime('%Y-%m-%d') if task.get("start") else "N/A"
                            end_str = datetime.fromtimestamp(task["end"] / 1000).strftime('%Y-%m-%d') if task.get("end") else "N/A"
                            f.write(f"{indent}ID: {task.get('id', 'N/A')}\n")
                            f.write(f"{indent}名称: {task.get('name', 'N/A')}\n")
                            f.write(f"{indent}时间: {start_str} -> {end_str} (持续 {task.get('duration', '?')} 天)\n")
                            f.write(f"{indent}进度: {task.get('progress', 0)}%\n")
                            if task.get('depends'): f.write(f"{indent}依赖: {task.get('depends')}\n")
                            if task.get('description'): f.write(f"{indent}描述: {task.get('description')}\n")
                            f.write(f"{indent}状态: {task.get('status', 'N/A')}\n")
                            f.write("-" * 30 + "\n")

                elif export_format == "XLSX":
                    tasks_for_df = []
                    for task in tasks:
                        start_str = pd.to_datetime(task["start"] / 1000, unit='s').strftime('%Y-%m-%d') if task.get("start") else None
                        end_str = pd.to_datetime(task["end"] / 1000, unit='s').strftime('%Y-%m-%d') if task.get("end") else None
                        indent = "  " * task.get("level", 0)
                        tasks_for_df.append({
                            "ID": task.get("id", ""),
                            "名称": indent + task.get("name", ""), # Add indentation
                            "开始日期": start_str,
                            "结束日期": end_str,
                            "工期(天)": task.get("duration", ""),
                            "进度(%)": task.get("progress", ""),
                            "依赖项": task.get("depends", ""),
                            "状态": task.get("status", ""),
                            "描述": task.get("description", "")
                        })
                    df = pd.DataFrame(tasks_for_df)
                    df = df[["ID", "名称", "开始日期", "结束日期", "工期(天)", "进度(%)", "依赖项", "状态", "描述"]]
                    df.to_excel(filePath, index=False, engine='openpyxl')


                else:
                     raise ValueError(f"内部错误：未处理的导出格式 '{export_format}'")


                print(f"GanttBridge: Data exported successfully to {filePath}")
                self.data_saved.emit(True, f"数据已成功导出为 {export_format} 到 {os.path.basename(filePath)}")

            except Exception as e:
                error_message = f"导出为 {export_format} 时出错: {e}"
                print(f"GanttBridge: {error_message}")
                self.data_saved.emit(False, error_message)

        except Exception as e:
            error_message = f"准备导出时发生错误: {e}"
            print(f"GanttBridge: {error_message}")
            self.data_saved.emit(False, error_message)



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