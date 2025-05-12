from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Date, DateTime, Enum as SQLEnum, UniqueConstraint, func, text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, backref
from enum import Enum
from datetime import datetime
import os

Base = declarative_base()

class BudgetCategory(Enum):
    """预算类别"""
    EQUIPMENT = "设备费"
    MATERIAL = "材料费"
    OUTSOURCING = "外协费"
    FUEL = "燃动费"
    CONFERENCE = "会议差旅"
    PUBLICATION = "出版文献"
    LABOR = "劳务费"
    CONSULTING = "专家咨询费"
    MISCELLANEOUS = "其他支出"
    INDIRECT = "间接费"

class Project(Base):
    """项目"""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    financial_code = Column(String(50))
    project_code = Column(String(50))
    project_type = Column(String(50))
    leader = Column(String(50))
    start_date = Column(Date)
    end_date = Column(Date)
    total_budget = Column(Float, default=0.00)
    director = Column(String(50)) # 添加负责人字段
    budgets = relationship("Budget", back_populates="project", cascade="all, delete-orphan")
    director = Column(String(50))

class Budget(Base):
    """预算"""
    __tablename__ = 'budgets'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    year = Column(Integer)  # None 表示总预算，否则为年度预算
    total_amount = Column(Float, default=0.0)  # 预算总额
    spent_amount = Column(Float, default=0.0)  # 已支出金额
    
    project = relationship("Project", back_populates="budgets")
    budget_items = relationship("BudgetItem", back_populates="budget", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="budget", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('project_id', 'year', 
            name='uix_project_year',
            sqlite_on_conflict='FAIL'  # SQLite特定的冲突处理
        ),
    )

    def is_total_budget(self):
        """判断是否为总预算"""
        return self.year is None

class BudgetItem(Base):
    """预算子项"""
    __tablename__ = 'budget_items'
    
    id = Column(Integer, primary_key=True)
    budget_id = Column(Integer, ForeignKey('budgets.id'), nullable=False)
    category = Column(SQLEnum(BudgetCategory), nullable=False)  # 使用 SQLAlchemy 的 Enum
    amount = Column(Float, default=0.0)  # 预算金额
    spent_amount = Column(Float, default=0.0)  # 已支出金额
    
    budget = relationship("Budget", back_populates="budget_items")

class BudgetPlan(Base):
    """预算编制主表"""
    __tablename__ = 'budget_plans'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # 预算名称
    create_date = Column(Date, default=datetime.now)  # 创建日期
    total_amount = Column(Float, default=0.0)  # 预算总额
    remarks = Column(String(200))  # 备注
    
    # 建立与预算项目的一对多关系
    items = relationship("BudgetPlanItem", back_populates="plan", cascade="all, delete-orphan")

class BudgetPlanItem(Base):
    """预算编制明细表"""
    __tablename__ = 'budget_plan_items'
    
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey('budget_plans.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('budget_plan_items.id'))  # 父级ID，用于构建树形结构
    category = Column(SQLEnum(BudgetCategory), nullable=True)  # 预算类别，可为空
    name = Column(String(100))  # 课题名称/预算内容
    specification = Column(String(100))  # 型号规格/简要内容
    unit_price = Column(Float, default=0.0)  # 单价
    quantity = Column(Integer, default=0)  # 数量
    amount = Column(Float, default=0.0)  # 经费数额
    remarks = Column(String(200))  # 备注
    
    # 建立与预算编制主表的多对一关系
    plan = relationship("BudgetPlan", back_populates="items")
    # 建立自引用关系，用于树形结构
    children = relationship("BudgetPlanItem", backref=backref('parent', remote_side=[id]))

class Activity(Base):
    """操作记录"""
    __tablename__ = 'activities'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    budget_id = Column(Integer, ForeignKey('budgets.id'), nullable=True)
    expense_id = Column(Integer, ForeignKey('expenses.id'), nullable=True)
    gantt_task_id = Column(Integer, ForeignKey('gantt_tasks.id'), nullable=True) # 添加甘特图任务外键
    project_document_id = Column(Integer, ForeignKey('project_documents.id'), nullable=True) # 添加项目文档外键
    project_outcome_id = Column(Integer, ForeignKey('project_outcome.id'), nullable=True) # 添加项目成果外键，修正表名为 'project_outcome'

    type = Column(String(50), nullable=False)  # 操作类型：项目/预算/支出/任务/文档/成果
    action = Column(String(50), nullable=False)  # 操作：新增/编辑/删除
    description = Column(String(200), nullable=False)  # 操作描述
    operator = Column(String(50), nullable=False)  # 操作人
    timestamp = Column(DateTime, default=datetime.now)  # 操作时间
    
    # 变更前后的详细信息
    old_data = Column(String(500))  # 变更前的数据，JSON格式
    new_data = Column(String(500))  # 变更后的数据，JSON格式
    category = Column(String(50))  # 操作对象的类别（如费用类别、预算年度等）
    amount = Column(Float)  # 涉及的金额（如有）
    related_info = Column(String(200))  # 相关信息（如项目编号、财务编号等）

    project = relationship("Project", backref="activities")
    budget = relationship("Budget", backref="activities")
    expense = relationship("Expense", backref="activities")
    gantt_task = relationship("GanttTask", backref="activities") # 添加关系
    project_document = relationship("ProjectDocument", backref="activities") # 添加关系
    project_outcome = relationship("ProjectOutcome", backref="activities") # 添加关系


class Expense(Base):
    """支出"""
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    budget_id = Column(Integer, ForeignKey('budgets.id'), nullable=False)
    category = Column(SQLEnum(BudgetCategory), nullable=False)  # 费用类别
    content = Column(String(200), nullable=False)  # 开支内容
    specification = Column(String(100))  # 规格型号
    supplier = Column(String(100))  # 供应商
    amount = Column(Float, default=0.0)  # 报账金额（元）
    date = Column(Date, default=datetime.now)  # 报账日期
    remarks = Column(String(200))  # 备注
    voucher_path = Column(String(500))  # 支出凭证文件路径
    
    project = relationship("Project", backref="expenses")
    budget = relationship("Budget", back_populates="expenses")

    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    



class GanttTask(Base):
    """甘特图任务"""
    __tablename__ = 'gantt_tasks'

    id = Column(Integer, primary_key=True)  # 使用数据库自增ID作为主键
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False) # 关联到项目
    gantt_id = Column(String(50), nullable=False, index=True) # jQueryGantt中的任务ID (可能是临时ID或持久化后的ID)
    name = Column(String(255), nullable=False)
    code = Column(String(50))
    level = Column(Integer, default=0)
    status = Column(String(50)) # e.g., STATUS_ACTIVE, STATUS_SUSPENDED
    start_date = Column(DateTime) # 存储为DateTime对象
    duration = Column(Integer) # 持续时间（天）
    end_date = Column(DateTime) # 存储为DateTime对象
    start_is_milestone = Column(Boolean, default=False)
    end_is_milestone = Column(Boolean, default=False)
    progress = Column(Float, default=0.0) # 进度百分比
    progress_by_worklog = Column(Boolean, default=False)
    description = Column(String(500))
    collapsed = Column(Boolean, default=False)
    has_child = Column(Boolean, default=False) # 标记是否有子任务
    responsible = Column(String(50)) # 添加负责人字段
    order = Column(Integer, default=0) # 添加任务排序字段

    project = relationship("Project", backref="gantt_tasks")

    __table_args__ = (UniqueConstraint('project_id', 'gantt_id', name='uix_project_gantt_id'),)

class GanttDependency(Base):
    """甘特图任务依赖关系"""
    __tablename__ = 'gantt_dependencies'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False) # 关联到项目
    predecessor_gantt_id = Column(String(50), nullable=False) # 前置任务的 gantt_id
    successor_gantt_id = Column(String(50), nullable=False) # 后置任务的 gantt_id
    type = Column(String(10)) # 依赖类型，例如 'FS' (Finish-to-Start)

    project = relationship("Project", backref="gantt_dependencies")

    # 唯一约束：同一个项目下的依赖关系应该是唯一的
    __table_args__ = (UniqueConstraint('project_id', 'predecessor_gantt_id', 'successor_gantt_id', name='uix_project_dependency'),)



def get_budget_usage(session, project_id, budget_id=None):
    """获取预算使用情况
    
    Args:
        session: SQLAlchemy session
        project_id: 项目ID
        budget_id: 预算ID（可选）
    
    Returns:
        dict: 包含预算使用情况的字典
    """
    try:
        # 查询总预算
        total_budget = session.query(Budget).filter(
            Budget.project_id == project_id,
            Budget.year.is_(None)
        ).first()

        if not total_budget:
            return {
                "total_budget": 0.0,
                "total_spent": 0.0,
                "remaining": 0.0,
                "category_spent": {category: 0.0 for category in BudgetCategory}
            }

        # 查询年度预算
        annual_budgets = session.query(Budget).filter(
            Budget.project_id == project_id,
            Budget.year.isnot(None)
        ).all()

        # 计算总支出
        total_spent = session.query(func.sum(Expense.amount)).filter(
            Expense.project_id == project_id
        ).scalar() or 0.0

        # 计算各科目支出
        category_spent = {}
        for category in BudgetCategory:
            spent = session.query(func.sum(Expense.amount)).filter(
                Expense.project_id == project_id,
                Expense.category == category
            ).scalar() or 0.0
            category_spent[category] = spent

        return {
            "total_budget": total_budget.total_amount,
            "total_spent": total_spent,
            "remaining": total_budget.total_amount - total_spent,
            "category_spent": category_spent
        }

    except Exception as e:
        session.rollback()
        raise e

def migrate_db(engine):
    """迁移数据库"""
    from sqlalchemy import text
    
    connection = engine.connect()
    transaction = connection.begin()
    
    # 执行项目任务表迁移
    try:
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='gantt_tasks'"))
        if result.fetchone():
            result = connection.execute(text("PRAGMA table_info(gantt_tasks)"))
            columns = [row[1] for row in result.fetchall()]
            if 'responsible' not in columns:
                connection.execute(text("ALTER TABLE gantt_tasks ADD COLUMN responsible VARCHAR(50)"))
                print("成功添加 responsible 列到 gantt_tasks 表")
            if 'order' not in columns: # 添加对 order 列的检查
                connection.execute(text("ALTER TABLE gantt_tasks ADD COLUMN \"order\" INTEGER DEFAULT 0")) # 添加 order 列，注意关键字加双引号
                print("成功添加 order 列到 gantt_tasks 表")
    except Exception as e:
        print(f"迁移 gantt_tasks 表失败: {e}")


    result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='project_outcomes'")) # 更新表名
    if result.fetchone():
        result = connection.execute(text("PRAGMA table_info(project_outcomes)")) # 更新表名
        columns = [row[1] for row in result.fetchall()]
        
        if 'submit_date' not in columns:
            connection.execute(text("ALTER TABLE project_outcomes ADD COLUMN submit_date DATE")) # 更新表名

    result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"))
    if result.fetchone():
        result = connection.execute(text("PRAGMA table_info(projects)"))
        columns = [row[1] for row in result.fetchall()]
        if 'director' not in columns:
            try:
                connection.execute(text("ALTER TABLE projects ADD COLUMN director VARCHAR(50)"))
                print("成功添加 director 列到 projects 表")
            except Exception as e:
                print(f"添加 director 列失败: {e}")
                # 如果需要，可以在这里回滚事务或采取其他错误处理措施

    try:
        result = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")
        )
        if result.fetchone():
            result = connection.execute(text("PRAGMA table_info(expenses)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'voucher_path' not in columns:
                # 创建临时表
                connection.execute(text("""
                    CREATE TABLE expenses_temp (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        budget_id INTEGER NOT NULL,
                        category TEXT NOT NULL,
                        content TEXT NOT NULL,
                        specification TEXT,
                        supplier TEXT,
                        amount FLOAT,
                        date DATE,
                        remarks TEXT,
                        voucher_path TEXT
                    )
                """))
                
                # 复制数据到临时表
                connection.execute(text("""
                    INSERT INTO expenses_temp (
                        id, project_id, budget_id, category, content,
                        specification, supplier, amount, date, remarks
                    )
                    SELECT id, project_id, budget_id, category, content,
                           specification, supplier, amount, date, remarks
                    FROM expenses
                """))
                
                # 删除原表
                connection.execute(text("DROP TABLE expenses"))
                
                # 重命名临时表
                connection.execute(text("ALTER TABLE expenses_temp RENAME TO expenses"))
                
                # 提交事务
                transaction.commit()
                print("成功添加voucher_path列")
        
        result = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='activities'")
        )
        if result.fetchone():
            result = connection.execute(text("PRAGMA table_info(activities)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            # 需要迁移的情况：
            # 2. 缺少新增的字段
            needs_migration = (
                ('timestamp' in columns and columns['timestamp'] != 'DATETIME') or
                'old_data' not in columns or
                'new_data' not in columns or
                'category' not in columns or
                'amount' not in columns or
                'related_info' not in columns or
                'gantt_task_id' not in columns or # 检查新字段
                'project_document_id' not in columns or # 检查新字段
                'project_outcome_id' not in columns # 检查新字段
            )
            
            if needs_migration:
                # 创建临时表，包含所有新字段和外键
                connection.execute(text("""
                    CREATE TABLE activities_temp (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER,
                        budget_id INTEGER,
                        expense_id INTEGER,
                        gantt_task_id INTEGER,     -- 新增字段
                        project_document_id INTEGER, -- 新增字段
                        project_outcome_id INTEGER,  -- 新增字段
                        type TEXT NOT NULL,
                        action TEXT NOT NULL,
                        description TEXT NOT NULL,
                        operator TEXT NOT NULL,
                        timestamp DATETIME,
                        old_data TEXT,
                        new_data TEXT,
                        category TEXT,
                        amount FLOAT,
                        related_info TEXT,
                        FOREIGN KEY(project_id) REFERENCES projects (id),
                        FOREIGN KEY(budget_id) REFERENCES budgets (id),
                        FOREIGN KEY(expense_id) REFERENCES expenses (id),
                        FOREIGN KEY(gantt_task_id) REFERENCES gantt_tasks (id),
                        FOREIGN KEY(project_document_id) REFERENCES project_documents (id),
                        FOREIGN KEY(project_outcome_id) REFERENCES project_outcomes (id)
                    )
                """))
                
                # 复制数据到临时表，为新字段插入 NULL
                connection.execute(text("""
                    INSERT INTO activities_temp (
                        id, project_id, budget_id, expense_id, type,
                        action, description, operator, timestamp,
                        old_data, new_data, category, amount, related_info,
                        gantt_task_id, project_document_id, project_outcome_id
                    )
                    SELECT
                        id, project_id, budget_id, expense_id, type,
                        action, description, operator, datetime(timestamp),
                        old_data, new_data, category, amount, related_info,
                        NULL, NULL, NULL -- 为新字段插入 NULL
                    FROM activities
                """))
                
                # 删除原表
                connection.execute(text("DROP TABLE activities"))
                
                # 重命名临时表
                connection.execute(text("ALTER TABLE activities_temp RENAME TO activities"))
                
                # 提交事务
                transaction.commit()
                print("成功更新activities表结构，添加了新字段并修正了timestamp列类型")
            else:
                 print("activities 表结构无需更新") # 添加无需更新的提示
        
    except Exception as e:
        print(f"数据库迁移失败: {str(e)}")
        transaction.rollback()

    try:
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='project_outcomes'"))
        if result.fetchone():
            result = connection.execute(text("PRAGMA table_info(project_outcomes)"))
            columns = [row[1] for row in result.fetchall()]
            if 'attachment_path' not in columns:
                connection.execute(text("ALTER TABLE project_outcomes ADD COLUMN attachment_path VARCHAR(500)"))
                transaction.commit() # Commit this specific change
                print("成功添加 attachment_path 列到 project_outcomes 表")
            else:
                 print("project_outcomes 表结构无需更新") # 添加无需更新的提示
    except Exception as e:
        print(f"迁移 project_outcomes 表失败: {e}")

    # 检查并迁移 budget_plan_items 表
    try:
        result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='budget_plan_items'"))
        if result.fetchone():
            result = connection.execute(text("PRAGMA table_info(budget_plan_items)"))
            columns = [row[1] for row in result.fetchall()]
            needs_commit = False # 标记是否需要提交事务

            # 定义模型应有的列及其 SQLite 类型
            expected_columns = {
                "plan_id": "INTEGER",
                "parent_id": "INTEGER",
                "category": "TEXT", # SQLEnum maps to TEXT
                "name": "TEXT",     # String maps to TEXT
                "specification": "TEXT",
                "unit_price": "FLOAT", # Float maps to FLOAT or REAL
                "quantity": "INTEGER",
                "amount": "FLOAT",
                "remarks": "TEXT"
            }

            # 检查并添加所有缺失的列
            for col_name, col_type in expected_columns.items():
                if col_name not in columns:
                    print(f"尝试添加 {col_name} 列 ({col_type}) 到 budget_plan_items 表...")
                    try:
                        connection.execute(text(f"ALTER TABLE budget_plan_items ADD COLUMN {col_name} {col_type}"))
                        needs_commit = True
                    except Exception as alter_err:
                         print(f"添加列 {col_name} 失败: {alter_err}")
                         # 如果添加列失败，可能需要回滚并停止迁移
                         if transaction.is_active:
                              transaction.rollback()
                         raise alter_err # 重新抛出错误，中断迁移

            # 如果进行了修改，则提交事务
            if needs_commit:
                transaction.commit()
                print("budget_plan_items 表结构更新提交成功")
            else:
                print("budget_plan_items 表结构无需更新")
    except Exception as e:
        print(f"迁移 budget_plan_items 表失败: {e}")
        if transaction.is_active: # 如果事务仍然活跃，则回滚
             transaction.rollback()

    finally:
        if transaction.is_active:
             print("Warning: Transaction was still active during migration finalization. Rolling back.")
             transaction.rollback()
        connection.close()

def init_db(db_path):
    """初始化数据库"""
    # 获取程序根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(root_dir, db_path)
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine

def get_engine():
    """获取数据库引擎实例"""
    # 获取程序根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(root_dir, 'database', 'database.db')
    engine = create_engine(f'sqlite:///{db_path}')
    return engine

def add_project_to_db(engine, name, financial_code, project_code, project_type, start_date, end_date, total_budget=None):
    """添加项目到数据库"""
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        project = Project(
            name=name,
            financial_code=financial_code,
            project_code=project_code,
            project_type=project_type,
            start_date=start_date,
            end_date=end_date,
            total_budget=float(total_budget) if total_budget else 0.0
        )
        session.add(project)
        session.flush()  # 获取项目ID
        
        # 创建总预算记录
        total_budget = Budget(
            project_id=project.id,
            year=None,  # None表示总预算
            total_amount=0.0,  # 初始化为0，需要通过编辑来设置具体金额
            spent_amount=0.0
        )
        session.add(total_budget)
        session.flush()
        
        # 创建总预算子项（初始化为0）
        for category in BudgetCategory:
            budget_item = BudgetItem(
                budget_id=total_budget.id,
                category=category,
                amount=0.0,
                spent_amount=0.0
            )
            session.add(budget_item)
        
        session.commit()
        return project.id
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    # 初始化数据库
    db_path = "database/database.db"
    engine = create_engine(f'sqlite:///{db_path}')
    # 创建新表
    Base.metadata.create_all(engine)
    # 运行迁移脚本（如果需要更复杂的迁移）
    print("数据库初始化或迁移完成")
