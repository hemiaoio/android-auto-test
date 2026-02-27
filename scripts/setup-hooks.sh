#!/usr/bin/env bash
# 安装 Git Hooks 到本地仓库
# 用法: bash scripts/setup-hooks.sh

set -euo pipefail

HOOKS_DIR=".git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
    echo "错误: 不在 Git 仓库根目录"
    exit 1
fi

# post-merge hook: git pull 后自动检查 skills
cat > "$HOOKS_DIR/post-merge" << 'HOOK'
#!/usr/bin/env bash
python scripts/check-skills.py 2>/dev/null || python3 scripts/check-skills.py 2>/dev/null || true
HOOK
chmod +x "$HOOKS_DIR/post-merge"

# post-checkout hook: git checkout / git clone 后检查
cat > "$HOOKS_DIR/post-checkout" << 'HOOK'
#!/usr/bin/env bash
# $3=1 表示分支切换
if [ "$3" = "1" ]; then
    python scripts/check-skills.py 2>/dev/null || python3 scripts/check-skills.py 2>/dev/null || true
fi
HOOK
chmod +x "$HOOKS_DIR/post-checkout"

echo "Git hooks 已安装:"
echo "  - post-merge   (git pull 后检查 skills)"
echo "  - post-checkout (切换分支后检查 skills)"
