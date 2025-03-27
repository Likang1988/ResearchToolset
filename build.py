import os
import sys
import shutil
from PyInstaller.__main__ import run

def build_app():
    # 获取当前脚本所在目录作为项目根目录
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置输出目录
    dist_dir = os.path.join(root_dir, 'dist')
    build_dir = os.path.join(root_dir, 'build')
    
    # 清理之前的构建文件
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    
    # 设置图标路径
    icon_path = os.path.join(root_dir, 'app', 'assets', 'icon.ico')
    
    # PyInstaller参数配置
    pyinstaller_args = [
        'run.py',  # 主程序入口
        '--name=ResearchToolset',  # 输出文件名
        '--icon=' + icon_path,  # 应用图标
        '--noconfirm',  # 覆盖输出目录
        '--clean',  # 清理临时文件
        '--windowed',  # 不显示控制台窗口
        f'--add-data={os.path.join(root_dir, "app", "assets")};app/assets',  # 添加资源文件
        '--distpath=' + dist_dir,  # 指定输出目录
        '--workpath=' + build_dir,  # 指定构建目录
        '--specpath=' + dist_dir,  # spec文件位置
    ]
    
    # 运行PyInstaller
    run(pyinstaller_args)
    
    exe_dir = os.path.join(dist_dir, 'ResearchToolset')
    
    
    print('构建完成！输出目录：', exe_dir)

if __name__ == '__main__':
    build_app()