#!/usr/bin/env python3
"""
Docker 环境检测工具模块

提供检测当前是否在 Docker 容器中运行的功能。

作者：AI助手
创建时间：2024
"""

import os


def is_docker_environment() -> bool:
    """检测是否在 Docker 容器中运行
    
    通过多种方法检测当前环境是否为 Docker 容器：
    1. 检查环境变量 DOCKER_RUN
    2. 检查 /.dockerenv 文件是否存在
    3. 检查 /proc/1/cgroup 文件内容
    
    Returns:
        bool: 如果在 Docker 容器中运行返回 True，否则返回 False
        
    Examples:
        >>> is_docker_environment()
        False  # 在本地环境中
        
        >>> is_docker_environment()
        True   # 在 Docker 容器中
    """
    # 方法1: 检查环境变量
    # 如果设置了 DOCKER_RUN=true 环境变量，则认为在 Docker 中运行
    if os.getenv("DOCKER_RUN", "false").lower() == "true":
        return True
    
    # 方法2: 检查是否存在 /.dockerenv 文件
    # Docker 容器启动时会自动创建此文件
    if os.path.exists("/.dockerenv"):
        return True
    
    # 方法3: 检查 cgroup 信息
    # 通过检查 /proc/1/cgroup 文件内容来判断是否在容器中
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            # 如果包含 docker 或 containerd 关键字，说明在容器中
            if "docker" in content or "containerd" in content:
                return True
    except (FileNotFoundError, PermissionError):
        # 如果文件不存在或没有权限读取，忽略此方法
        pass
    
    # 所有检测方法都未发现 Docker 环境特征
    return False


def get_environment_info() -> dict:
    """获取当前环境的详细信息
    
    Returns:
        dict: 包含环境检测结果的字典
        
    Examples:
        >>> get_environment_info()
        {
            'is_docker': True,
            'docker_run_env': 'true',
            'dockerenv_file_exists': True,
            'cgroup_contains_docker': True
        }
    """
    info = {
        'is_docker': False,
        'docker_run_env': os.getenv("DOCKER_RUN", "false"),
        'dockerenv_file_exists': os.path.exists("/.dockerenv"),
        'cgroup_contains_docker': False
    }
    
    # 检查 cgroup 信息
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            info['cgroup_contains_docker'] = "docker" in content or "containerd" in content
    except (FileNotFoundError, PermissionError):
        info['cgroup_contains_docker'] = None
    
    # 综合判断
    info['is_docker'] = (
        info['docker_run_env'].lower() == "true" or
        info['dockerenv_file_exists'] or
        info['cgroup_contains_docker'] is True
    )
    
    return info


if __name__ == "__main__":
    """模块测试代码"""
    print("Docker 环境检测工具测试")
    print("=" * 40)
    
    # 测试基本检测功能
    is_docker = is_docker_environment()
    print(f"是否在 Docker 环境中: {'是' if is_docker else '否'}")
    
    # 显示详细环境信息
    env_info = get_environment_info()
    print("\n详细环境信息:")
    for key, value in env_info.items():
        print(f"  {key}: {value}")
    
    # 根据环境给出建议
    if is_docker:
        print("\n🐳 检测到 Docker 环境")
        print("建议使用端口: 7861")
    else:
        print("\n💻 检测到本地环境")
        print("建议使用端口: 7862")
