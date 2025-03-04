from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from enum import Enum
from .database import Base

class BudgetEditCategory(Enum):
    """预算编制类别"""
    DIRECT = "直接费"
    INDIRECT = "间接费"

class BudgetEditSubCategory(Enum):
    """预算编制子类别"""
    # 直接费子项
    EQUIPMENT = "设备费"
    MATERIAL = "材料费"
    OUTSOURCING = "外协费"
    FUEL = "燃动费"
    CONFERENCE = "会议差旅"
    PUBLICATION = "出版文献"
    LABOR = "劳务费"
    CONSULTING = "专家咨询费"
    MISCELLANEOUS = "其他支出"
    # 间接费子项
    MANAGEMENT = "管理费用"
    PERFORMANCE = "绩效津贴"

class BudgetEditProject(Base):
    """预算编制项目"""
    __tablename__ = 'budget_edit_projects'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    budget_items = relationship('BudgetEditItem', back_populates='project', cascade='all, delete-orphan')

class BudgetEditItem(Base):
    """预算编制条目"""
    __tablename__ = 'budget_edit_items'
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('budget_edit_projects.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('budget_edit_items.id'))
    name = Column(String(100))
    specification = Column(String(200))
    unit_price = Column(Float)
    quantity = Column(Integer)
    amount = Column(Float)
    remarks = Column(String(500))
    category = Column(SQLEnum(BudgetEditCategory))
    subcategory = Column(SQLEnum(BudgetEditSubCategory))
    
    project = relationship('BudgetEditProject', back_populates='budget_items')
    parent = relationship('BudgetEditItem', remote_side=[id], backref='children')