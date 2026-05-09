#!/usr/bin/env bash
# 安装 git hooks：pre-push 时自动同步 .env → GitHub Secrets + Vercel

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/../.git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
  echo "错误：找不到 .git/hooks 目录，请在项目根目录运行此脚本"
  exit 1
fi

cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/usr/bin/env bash
# 自动同步 .env 到 GitHub Secrets 和 Vercel

REPO_ROOT="$(git rev-parse --show-toplevel)"
SYNC_SCRIPT="$REPO_ROOT/scripts/sync-secrets.py"

if [ ! -f "$SYNC_SCRIPT" ]; then
  exit 0
fi

echo ""
echo "🔑 pre-push: 同步 .env secrets..."
python3 "$SYNC_SCRIPT" all
echo ""
EOF

chmod +x "$HOOKS_DIR/pre-push"
echo "✓ pre-push hook 已安装：$HOOKS_DIR/pre-push"
echo "  每次 git push 前将自动同步 .env → GitHub Secrets + Vercel"
echo ""
echo "也可以手动运行："
echo "  python3 scripts/sync-secrets.py           # 同步全部"
echo "  python3 scripts/sync-secrets.py github    # 仅 GitHub"
echo "  python3 scripts/sync-secrets.py vercel    # 仅 Vercel"
