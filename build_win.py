import os
import sys
import shutil
from pathlib import Path

def clean_build_dir():
    """清理构建目录"""
    build_dirs = ['build', 'dist', '__pycache__']
    for dir_name in build_dirs:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)

def get_project_root():
    """获取项目根目录"""
    return os.path.dirname(os.path.abspath(__file__))

def build_app():
    """使用Nuitka打包应用程序"""
    try:
        # 清理旧的构建文件
        clean_build_dir()

        # 设置项目根目录
        project_root = get_project_root()
        os.chdir(project_root)

        # 确保输出目录存在
        output_dir = 'C:\\Compile'
        os.makedirs(output_dir, exist_ok=True)

        # 构建命令
        build_command = [
            'python', '-m', 'nuitka',
            '--standalone',  # 独立可执行文件
            '--windows-disable-console',  # 禁用控制台
            '--mingw64',  # 使用mingw64编译器
            '--show-progress',  # 显示编译进度
            '--show-memory',  # 显示内存使用情况
            '--plugin-enable=pyside6',  # 启用PySide6插件
            '--include-data-dir=app/assets=app/assets',  # 包含资源文件
            '--output-dir=' + output_dir,  # 输出目录
            '--output-filename=ResearchToolset',  # 输出文件名
            '--follow-imports',  # 自动跟踪导入
            '--prefer-source-code',  # 优先使用源代码
            '--assume-yes-for-downloads',  # 自动下载依赖
            'run.py'  # 入口文件
        ]

        # 执行构建命令
        os.system(' '.join(build_command))

        print('\n构建完成！输出目录：' + output_dir)
        return True

    except Exception as e:
        print(f'构建失败：{str(e)}')
        return False

if __name__ == '__main__':
    build_app()