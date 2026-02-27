#!/usr/bin/env python3
"""检查 skills-lock.json 中声明的所有 skills 是否已安装。

用法:
    python scripts/check-skills.py          # 检查并提示
    python scripts/check-skills.py --install  # 自动安装缺失的 skills
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

LOCK_FILE = "skills-lock.json"
SKILLS_DIR = Path(".agents/skills")

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"


def check_skills() -> list[tuple[str, str]]:
    """检查缺失的 skills，返回 [(name, source), ...]"""
    lock_path = Path(LOCK_FILE)
    if not lock_path.exists():
        return []

    with open(lock_path, encoding="utf-8") as f:
        data = json.load(f)

    missing: list[tuple[str, str]] = []
    for name, info in data.get("skills", {}).items():
        skill_dir = SKILLS_DIR / name
        source = info.get("source", "unknown")
        if skill_dir.is_dir():
            print(f"  {GREEN}[OK]{NC} {name}")
        else:
            print(f"  {RED}[MISSING]{NC} {name}  (来源: {source})")
            missing.append((name, source))

    return missing


def install_skills(missing: list[tuple[str, str]]) -> None:
    """自动安装缺失的 skills。"""
    for name, source in missing:
        cmd = f"npx skills add https://github.com/{source} --skill {name} --yes"
        print(f"\n{YELLOW}正在安装: {name}{NC}")
        print(f"  $ {cmd}")
        result = subprocess.run(cmd, shell=True)
        if result.returncode == 0:
            print(f"  {GREEN}安装成功{NC}")
        else:
            print(f"  {RED}安装失败 (exit code: {result.returncode}){NC}")


def main() -> None:
    auto_install = "--install" in sys.argv

    print("检查 skills 安装状态...\n")
    missing = check_skills()

    if not missing:
        print(f"\n{GREEN}所有 skills 已安装{NC}")
        return

    print(f"\n{RED}发现 {len(missing)} 个未安装的 skills{NC}\n")

    if auto_install:
        install_skills(missing)
    else:
        print("请运行以下命令安装:\n")
        for name, source in missing:
            print(f"  npx skills add https://github.com/{source} --skill {name} --yes")
        print(f"\n或运行: python scripts/check-skills.py --install 自动安装")
        sys.exit(1)


if __name__ == "__main__":
    main()
