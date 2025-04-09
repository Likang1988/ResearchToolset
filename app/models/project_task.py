from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum
from enum import Enum, unique
import json

from .database import Base

@unique
class TaskStatus(Enum):
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完成"
    DELAYED = "已延期"

class ProjectTask(Base):
    __tablename__ = 'project_tasks'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('project_tasks.id'), nullable=True)  # 父任务ID
    level = Column(Integer, default=0)  # 任务层级
    name = Column(String(100), nullable=False)  # 任务名称
    description = Column(String(500), default="")  # 任务描述
    start_date = Column(Date)  # 开始日期
    end_date = Column(Date)  # 结束日期
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.NOT_STARTED)  # 任务状态
    progress = Column(Integer, default=0)  # 进度百分比
    dependencies = Column(Text, default=json.dumps([]))  # 依赖任务ID列表(JSON格式)
    assignee = Column(String(50), default="")  # 负责人
    phase = Column(String(20), default="")  # 研究阶段
    
    # 关系定义
    parent = relationship("ProjectTask", remote_side=[id], backref="children")  # 父子任务关系
    
    project = relationship("Project", back_populates="tasks")

def migrate_project_tasks(engine):
    """迁移项目任务表"""
    from sqlalchemy import text
    
    connection = engine.connect()
    transaction = connection.begin()
    
    try:
        # 检查project_tasks表是否存在
        result = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='project_tasks'")
        )
        
        if not result.fetchone():
            # 创建新表
            connection.execute(text("""
                CREATE TABLE project_tasks (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER NOT NULL,
                    parent_id INTEGER,
                    level INTEGER DEFAULT 0,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_date DATE,
                    end_date DATE,
                    status TEXT,
                    progress INTEGER,
                    dependencies TEXT,
                    assignee TEXT,
                    phase TEXT,
                    FOREIGN KEY(project_id) REFERENCES projects(id),
                    FOREIGN KEY(parent_id) REFERENCES project_tasks(id)
                )
            """))
            
            # 提交事务
            transaction.commit()
            print("成功创建project_tasks表")
        else:
            # 检查表结构是否完整
            result = connection.execute(text("PRAGMA table_info(project_tasks)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            # 添加缺失的列
            if 'parent_id' not in columns:
                connection.execute(text("ALTER TABLE project_tasks ADD COLUMN parent_id INTEGER REFERENCES project_tasks(id)"))
            if 'level' not in columns:
                connection.execute(text("ALTER TABLE project_tasks ADD COLUMN level INTEGER DEFAULT 0"))
            if 'dependencies' not in columns:
                connection.execute(text("ALTER TABLE project_tasks ADD COLUMN dependencies TEXT DEFAULT '[]'"))
            if 'assignee' not in columns:
                connection.execute(text("ALTER TABLE project_tasks ADD COLUMN assignee TEXT DEFAULT ''"))
            if 'phase' not in columns:
                connection.execute(text("ALTER TABLE project_tasks ADD COLUMN phase TEXT DEFAULT ''"))
            
            transaction.commit()
            print("成功更新project_tasks表结构")
    
    except Exception as e:
        print(f"迁移project_tasks表失败: {str(e)}")
        transaction.rollback()
        raise e
    finally:
        connection.close()