from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Date, DateTime, Enum as SQLEnum, UniqueConstraint, func, text
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
    budgets = relationship("Budget", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")

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

    # 添加唯一约束，但只对非None的year生效
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
    type = Column(String(50), nullable=False)  # 操作类型：项目/预算/支出
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
    from .project_task import migrate_project_tasks
    
    connection = engine.connect()
    transaction = connection.begin()
    
    # 执行项目任务表迁移
    migrate_project_tasks(engine)
    
    # 检查project_achievements表是否存在submit_date列
    result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='project_achievements'"))
    if result.fetchone():
        result = connection.execute(text("PRAGMA table_info(project_achievements)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'submit_date' not in columns:
            # 添加submit_date列
            connection.execute(text("ALTER TABLE project_achievements ADD COLUMN submit_date DATE"))
    
    try:
        # 检查expenses表是否存在
        result = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")
        )
        if result.fetchone():
            # 检查expenses表是否存在voucher_path列
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
        
        # 检查activities表是否存在
        result = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='activities'")
        )
        if result.fetchone():
            # 检查activities表中的列信息
            result = connection.execute(text("PRAGMA table_info(activities)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            # 需要迁移的情况：
            # 1. timestamp列不是DATETIME类型
            # 2. 缺少新增的字段
            needs_migration = (
                ('timestamp' in columns and columns['timestamp'] != 'DATETIME') or
                'old_data' not in columns or
                'new_data' not in columns or
                'category' not in columns or
                'amount' not in columns or
                'related_info' not in columns
            )
            
            if needs_migration:
                # 创建临时表，包含所有新字段
                connection.execute(text("""
                    CREATE TABLE activities_temp (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER,
                        budget_id INTEGER,
                        expense_id INTEGER,
                        type TEXT NOT NULL,
                        action TEXT NOT NULL,
                        description TEXT NOT NULL,
                        operator TEXT NOT NULL,
                        timestamp DATETIME,
                        old_data TEXT,
                        new_data TEXT,
                        category TEXT,
                        amount FLOAT,
                        related_info TEXT
                    )
                """))
                
                # 复制数据到临时表，对于新字段使用NULL值
                connection.execute(text("""
                    INSERT INTO activities_temp (
                        id, project_id, budget_id, expense_id, type,
                        action, description, operator, timestamp,
                        old_data, new_data, category, amount, related_info
                    )
                    SELECT 
                        id, project_id, budget_id, expense_id, type,
                        action, description, operator, datetime(timestamp),
                        NULL, NULL, NULL, NULL, NULL
                    FROM activities
                """))
                
                # 删除原表
                connection.execute(text("DROP TABLE activities"))
                
                # 重命名临时表
                connection.execute(text("ALTER TABLE activities_temp RENAME TO activities"))
                
                # 提交事务
                transaction.commit()
                print("成功更新activities表结构，添加了新字段并修正了timestamp列类型")
        
    except Exception as e:
        print(f"数据库迁移失败: {str(e)}")
        transaction.rollback()
        raise e
    
    finally:
        connection.close()

def init_db(db_path):
    """初始化数据库"""
    # 获取程序根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 确保使用程序根目录下的database路径
    db_path = os.path.join(root_dir, db_path)
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine

def get_engine():
    """获取数据库引擎实例"""
    # 获取程序根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 确保使用程序根目录下的database路径
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
    migrate_db(engine)
    print("数据库迁移完成")
