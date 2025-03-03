from sqlalchemy.orm import Session
from typing import TypeVar, Callable, Any
from functools import wraps
from PySide6.QtWidgets import QMessageBox

T = TypeVar('T')

class DBUtils:
    @staticmethod
    def with_session(engine, show_error: bool = True) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """数据库会话装饰器，统一处理会话的创建、提交、回滚和关闭
        
        Args:
            engine: SQLAlchemy引擎实例
            show_error: 是否显示错误消息框
            
        Returns:
            装饰器函数
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> T:
                session = Session(engine)
                try:
                    result = func(*args, session=session, **kwargs)
                    session.commit()
                    return result
                except Exception as e:
                    session.rollback()
                    error_msg = f"数据库操作失败：\n错误类型：{type(e).__name__}\n错误信息：{str(e)}"
                    print(error_msg)  # 打印错误信息到控制台
                    if show_error:
                        QMessageBox.critical(None, "错误", error_msg)
                    raise
                finally:
                    session.close()
            return wrapper
        return decorator

    @staticmethod
    def handle_db_error(func: Callable[..., T]) -> Callable[..., T]:
        """数据库错误处理装饰器，用于非会话管理的数据库操作
        
        Args:
            func: 要装饰的函数
            
        Returns:
            装饰器函数
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"数据库操作失败：\n错误类型：{type(e).__name__}\n错误信息：{str(e)}"
                print(error_msg)  # 打印错误信息到控制台
                QMessageBox.critical(None, "错误", error_msg)
                raise
        return wrapper