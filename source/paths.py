# -*- coding: utf-8 -*-
"""路径解析：让脚本在任何机器上都能跑，不再硬编码本机绝对路径。

用法
----
    import paths
    BLEND  = paths.blend("warm_bedroom_v2.blend")      # 项目根下的 .blend
    FRAMES = paths.scratch("video/frames")             # 临时产物
    TEX    = paths.root("textures")                    # 项目内任意子目录

优先级
------
1. 环境变量 `WARM_BEDROOM_ROOT` 指定项目根（推荐在别的机器上用）
2. 否则按本文件位置推导：<项目根>/source/paths.py -> 上一级即项目根

临时产物目录同样支持 `WARM_BEDROOM_SCRATCH` 覆盖，默认 <项目根>/.scratch。
注意：`.scratch/` 已在 .gitignore 中，不会被提交。
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_ROOT = os.path.dirname(_HERE)

ROOT = os.path.abspath(os.environ.get("WARM_BEDROOM_ROOT") or _DEFAULT_ROOT)
SCRATCH = os.path.abspath(
    os.environ.get("WARM_BEDROOM_SCRATCH") or os.path.join(ROOT, ".scratch")
)


def root(*parts):
    """项目根下的路径。"""
    return os.path.join(ROOT, *parts)


def scratch(*parts):
    """临时产物目录下的路径（不会提交）。"""
    return os.path.join(SCRATCH, *parts)


def blend(name="warm_bedroom_v2.blend"):
    """项目根下的 .blend 工程。"""
    return root(name)


def ensure(path):
    """创建目录（若 path 看起来是目录）并返回它。"""
    os.makedirs(path, exist_ok=True)
    return path


if __name__ == "__main__":
    print("ROOT   :", ROOT)
    print("SCRATCH:", SCRATCH)
    print("blend  :", blend())
