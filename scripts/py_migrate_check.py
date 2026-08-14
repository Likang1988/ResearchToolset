"""迁移对照验证（Python 侧）：对 legacy 库副本执行 init_db + migrate_db 等价操作"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402
from app.models.database import Base, migrate_db  # noqa: E402

# 对齐真实启动顺序：ProjectDocument/ProjectOutcome/AcademicActivity 模型
# 定义在视图文件中，由 main_window 导入后注册进 Base.metadata
import app.views.projecting_interface.project_document  # noqa: E402,F401
import app.views.projecting_interface.project_outcome  # noqa: E402,F401
import app.views.activity_interface  # noqa: E402,F401

if __name__ == "__main__":
    db = Path(sys.argv[1]).resolve()
    engine = create_engine(f"sqlite:///{db.as_posix()}")
    Base.metadata.create_all(engine)  # init_db 等价
    migrate_db(engine)  # migrate_db 等价
    print(f"Python migration done: {db}")
