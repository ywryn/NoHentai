#!/usr/bin/env python3
"""
同步 .env 到 GitHub Secrets 和 Vercel Environment Variables。
依赖：gh CLI（已登录）、vercel CLI（已 link 项目）。
"""

import os
import re
import subprocess
import sys

REPO = "ywryn/NoHentai"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, "..", ".env")

# 同步到 GitHub Secrets 的变量
GITHUB_VARS = {
    "EXHENTAI_BASE_URL",
    "EXHENTAI_COOKIE_MEMBER_ID",
    "EXHENTAI_COOKIE_PASS_HASH",
    "EXHENTAI_COOKIE_IGNEOUS",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
}

# 同步到 Vercel 的变量
VERCEL_VARS = {
    "EXHENTAI_COOKIE_MEMBER_ID",
    "EXHENTAI_COOKIE_PASS_HASH",
    "EXHENTAI_COOKIE_IGNEOUS",
    "TRANS_PASSWORD",
    "PADDLEOCR_API_TOKEN",
    "LLM_API_BASE",
    "LLM_API_KEY",
    "LLM_MODEL",
}

# ── .env 解析（支持多行 value，如 GOOGLE_SERVICE_ACCOUNT_JSON）────────────────

def parse_env(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    result = {}
    # 匹配 KEY=...(直到下一个 KEY= 或文件末尾)
    pattern = re.compile(
        r"^([A-Z_][A-Z0-9_]*)=(.+?)(?=\n[A-Z_][A-Z0-9_]*=|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for m in pattern.finditer(content):
        key = m.group(1)
        value = m.group(2).strip()
        # 去掉首尾引号（如有）
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value
    return result


def find_cli(name):
    """返回可用的 CLI 路径，优先全局，其次 node_modules/.bin。"""
    import shutil
    if shutil.which(name):
        return name
    local = os.path.join(SCRIPT_DIR, "..", "web-static", "node_modules", ".bin", name)
    if os.path.isfile(local):
        return local
    return None


def check_cli(name):
    return find_cli(name) is not None


# ── GitHub Secrets ────────────────────────────────────────────────────────────

def sync_github(env):
    if not check_cli("gh"):
        print("  [跳过] gh CLI 未安装或未登录")
        return

    synced = 0
    for key in sorted(GITHUB_VARS):
        value = env.get(key)
        if not value:
            print(f"  [跳过] {key}（.env 中为空）")
            continue
        result = subprocess.run(
            ["gh", "secret", "set", key, "--body", value, "--repo", REPO],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  ✓ GitHub  {key}")
            synced += 1
        else:
            print(f"  ✗ GitHub  {key}: {result.stderr.strip()}")
    print(f"  → GitHub Secrets 同步 {synced}/{len(GITHUB_VARS)} 个")


# ── Vercel Env Vars ───────────────────────────────────────────────────────────

def vercel_upsert(key, value, cli="vercel"):
    cwd = os.path.join(SCRIPT_DIR, "..")
    subprocess.run(
        [cli, "env", "rm", key, "production", "--yes"],
        capture_output=True, cwd=cwd,
    )
    result = subprocess.run(
        [cli, "env", "add", key, "production"],
        input=value, capture_output=True, text=True, cwd=cwd,
    )
    return result.returncode == 0, result.stderr.strip()


def sync_vercel(env):
    cli = find_cli("vercel")
    if not cli:
        print("  [跳过] vercel CLI 未安装（运行 npm i -g vercel 安装，然后 vercel link）")
        return

    synced = 0
    for key in sorted(VERCEL_VARS):
        value = env.get(key)
        if not value:
            print(f"  [跳过] {key}（.env 中为空）")
            continue
        ok, err = vercel_upsert(key, value, cli)
        if ok:
            print(f"  ✓ Vercel  {key}")
            synced += 1
        else:
            print(f"  ✗ Vercel  {key}: {err}")
    print(f"  → Vercel Env 同步 {synced}/{len(VERCEL_VARS)} 个")


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if not os.path.exists(ENV_FILE):
        print(f"错误：找不到 {ENV_FILE}")
        sys.exit(1)

    print(f"读取 {os.path.relpath(ENV_FILE)} ...")
    env = parse_env(ENV_FILE)
    print(f"解析到 {len(env)} 个变量\n")

    if target in ("all", "github"):
        print("── GitHub Secrets ──")
        sync_github(env)
        print()

    if target in ("all", "vercel"):
        print("── Vercel Env Vars ──")
        sync_vercel(env)
        print()

    print("完成。")


if __name__ == "__main__":
    main()
