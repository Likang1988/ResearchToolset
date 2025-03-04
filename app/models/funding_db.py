from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Date, Enum as SQLEnum, UniqueConstraint, func, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
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
    total_budget = Column(Float, default=0.0)
    budgets = relationship("Budget", back_populates="project", cascade="all, delete-orphan")

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
            raise ValueError("项目总预算不存在")

        # 查询年度预算
        annual_budgets = session.query(Budget).filter(
            Budget.project_id == project_id,
            Budget.year.isnot(None)
        ).all()

        # 计算总支出
        total_spent = sum(b.spent_amount for b in annual_budgets)

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
        
    except Exception as e:
        print(f"数据库迁移失败: {str(e)}")
        transaction.rollback()
        raise e
    
    finally:
        connection.close()

def init_db(db_path):
    """初始化数据库"""
    db_path = os.path.abspath(db_path)  # 获取绝对路径
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
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
    db_path = "database/funds.db"
    engine = create_engine(f'sqlite:///{db_path}')
    migrate_db(engine)
    print("数据库迁移完成")