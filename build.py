import os
import sys
import shutil
from PyInstaller.__main__ import run

def build_app():
    # 判断操作系统类型
    is_windows = sys.platform.startswith('win')
    is_macos = sys.platform.startswith('darwin')
    # 获取当前脚本所在目录作为项目根目录
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置输出目录
    dist_dir = os.path.join(root_dir, 'build', 'dist')
    build_dir = os.path.join(root_dir, 'build', 'build')
    spec_dir = os.path.join(root_dir, 'build')
    
    # 清理之前的构建文件
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    
    # 根据操作系统设置图标路径
    if is_windows:
        icon_path = os.path.join(root_dir, 'app', 'assets', 'icon.ico')
    else:
        icon_path = os.path.join(root_dir, 'app', 'assets', 'icon.icns')
    
    pyinstaller_args = [
        'run.py',  # 主程序入口
        '--name=ResearchToolset',  # 输出文件名
        '--icon=' + icon_path,  # 应用图标
        '--noconfirm',  # 覆盖输出目录
        '--clean',  # 清理临时文件
        '--windowed',  # 不显示控制台窗口
        f'--add-data={os.path.join(root_dir, "app", "assets")}{";"}app/assets' if is_windows else f'--add-data={os.path.join(root_dir, "app", "assets")}:app/assets',  # 添加资源文件
        f'--add-data={os.path.join(root_dir, "app", "integration", "jQueryGantt")}{";"}app/integration/jQueryGantt' if is_windows else f'--add-data={os.path.join(root_dir, "app", "integration", "jQueryGantt")}:app/integration/jQueryGantt', # 添加jQueryGantt资源
        '--distpath=' + dist_dir,  # 指定输出目录
        '--workpath=' + build_dir,  # 指定构建目录
        '--specpath=' + spec_dir,  # spec文件位置
        '--upx-dir=D:/Environments/upx-5.0.1-win64',  # 使用 UPX 压缩
        '--exclude-module=matplotlib',  # 排除 matplotlib 模块
    ]
    
    run(pyinstaller_args)
    
    exe_dir = os.path.join(dist_dir, 'ResearchToolset')
    
    
    print('构建完成！输出目录：', exe_dir)

if __name__ == '__main__':
    build_app()