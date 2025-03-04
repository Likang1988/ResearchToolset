from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship, backref
from enum import Enum as PyEnum

Base = declarative_base()

class BudgetEditCategory(PyEnum):
    """预算类别枚举"""
    DIRECT = "直接费"
    INDIRECT = "间接费"

class BudgetEditSubCategory(PyEnum):
    """预算子类别枚举"""
    # 直接费用子类别
    EQUIPMENT = "设备费"
    MATERIAL = "材料费"
    OUTSOURCING = "外协费"
    FUEL = "燃动费"
    CONFERENCE = "会议差旅"
    PUBLICATION = "出版文献"
    LABOR = "劳务费"
    CONSULTING = "专家咨询费"
    MISCELLANEOUS = "其他支出"
    
    # 间接费用子类别
    MANAGEMENT = "管理费"
    PERFORMANCE = "绩效支出"

class BudgetEditProject(Base):
    """预算编制项目表"""
    __tablename__ = 'budget_edit_projects'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)  # 项目名称
    
    # 关联预算项
    budget_items = relationship('BudgetEditItem', back_populates='project', cascade='all, delete-orphan')

class BudgetEditItem(Base):
    """预算编制项目的预算项表"""
    __tablename__ = 'budget_edit_items'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('budget_edit_projects.id', ondelete='CASCADE'), nullable=False)
    parent_id = Column(Integer, ForeignKey('budget_edit_items.id', ondelete='CASCADE'), nullable=True)  # 父级预算项ID
    
    name = Column(String(200))  # 预算项名称
    specification = Column(String(200))  # 型号规格/简要内容
    unit_price = Column(Float, default=0.0)  # 单价
    quantity = Column(Integer, default=0)  # 数量
    amount = Column(Float, default=0.0)  # 经费数额
    remarks = Column(String(500))  # 备注
    
    # 预算类别和子类别
    category = Column(Enum(BudgetEditCategory), nullable=True)
    subcategory = Column(Enum(BudgetEditSubCategory), nullable=True)
    
    # 关联
    project = relationship('BudgetEditProject', back_populates='budget_items')
    children = relationship('BudgetEditItem', cascade='all, delete-orphan',
                          backref=backref('parent', remote_side=[id]))