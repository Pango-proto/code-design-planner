#!/usr/bin/env python3
"""项目文件治理工具（仅依赖 Python 标准库，需 Python 3.8+）

在项目根目录运行：
  python scripts/governance.py init                                  初始化目录结构（不覆盖已有文件）
  python scripts/governance.py check                                 门禁检查，有 ERROR 时退出码为 1
  python scripts/governance.py new-module NAME --desc "..."          按固定流程新增模块
  python scripts/governance.py retire PATH --reason "..." [--days N] 退役文件/目录到冷区
  python scripts/governance.py purge [--yes]                         删除到期的冷区内容

可选配置：config/governance.json（见 SKILL 的 references/templates.md）
"""
import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
SELF = Path(__file__).resolve()
TODAY = dt.date.today()

DEFAULTS = {
    "modules_root": "src",
    "cold_days": 14,
    "scratch_ttl_days": 7,
    "max_files_per_dir": 30,
    "root_files_extra": [],
    "root_dirs_extra": [],
    "doc_dirs_extra": [],
    "allow_names": [],
}

ROOT_FILE_GLOBS = [
    "README*", "PROJECT_INDEX.md", "LICENSE*", "CHANGELOG*", "CONTRIBUTING*",
    "CLAUDE.md", "AGENTS.md",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements*.txt", "Pipfile", "Pipfile.lock",
    "poetry.lock", "uv.lock", "environment.yml", "tox.ini", "noxfile.py", "MANIFEST.in",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "yarn.lock",
    "bun.lockb", "tsconfig*.json", "*.config.js", "*.config.ts", "*.config.mjs", "*.config.cjs",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "CMakeLists.txt", "Makefile", "justfile",
    "Dockerfile", "docker-compose*.yml", "docker-compose*.yaml", "compose*.yml", "compose*.yaml",
]
ROOT_DIRS = {"src", "tests", "config", "docs", "scripts", "data", "outputs", "scratch", "_cold"}
IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", "dist", "build", ".next", "target", ".ipynb_checkpoints",
    ".idea", ".vscode", ".eggs",
}
HOT_ZONES = ["src", "tests", "config", "docs", "scripts"]
DOC_RULES = {
    "guide": None,
    "modules": None,
    "phases": (re.compile(r"^P\d{2}-\S+\.md$"), "Pxx-<name>.md"),
    "audits": (re.compile(r"^\d{4}-\d{2}-\d{2}_\S+\.md$"), "YYYY-MM-DD_<scope>.md"),
    "decisions": (re.compile(r"^D\d{3}-\S+\.md$"), "Dxxx-<topic>.md"),
}
SKELETON = ["src", "tests", "config", "docs/guide", "docs/modules", "docs/phases",
            "docs/audits", "docs/decisions", "scripts", "outputs", "scratch", "_cold"]

TOKENS = r"(old|new|final|copy|backup|bak|tmp|temp|draft|fixed|v\d+|\d{6,8})"
SUFFIX_RE = re.compile(r"[_\-. ]" + TOKENS + r"$", re.I)
PREFIX_RE = re.compile(r"^(old|copy|backup|bak|tmp|draft|final)[_\-. ]", re.I)
CN_RE = re.compile(r"(副本|备份|新建|最终|最新版|修改版|改版|旧版|临时)")
DUP_RE = re.compile(r"(\(\d+\)|（\d+）| copy)$", re.I)
BAD_EXT = (".bak", ".orig", ".rej", ".swp", ".swo", ".tmp", "~")
JUNK_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
EXACT_BAD_FILE = {"tmp", "temp", "test1", "test2", "untitled", "new", "old", "backup", "misc", "foo", "bar"}
EXACT_BAD_DIR = {"misc", "other", "others", "stuff", "new", "old", "tmp", "temp", "backup", "backups",
                 "new_folder", "untitled", "test2", "archive_old", "unsorted"}
COMMON_NAMES = {"__init__.py", "README.md", "conftest.py", "mod.rs", "lib.rs", "__main__.py", ".gitkeep"}
REF_RE = re.compile(r"(?:^|[\"'`/\s(=:,])(_cold|scratch)[/\\]|(?:from|import|require\(|import\()\s*[\"']?\.*(_cold|scratch)\b")

INDEX_TEMPLATE = """# 项目索引

> 唯一登记处。新增模块必须通过 `python scripts/governance.py new-module` 登记。

## 当前阶段
- 阶段：P01-<name>
- 目标：
- 进度：

## 模块登记
| 模块 | 状态 | 说明 | 文档 |
|---|---|---|---|

状态取值：规划中 / 开发中 / 已完成 / 已退役

## 文档索引
- 项目指导：docs/guide/
- 模块说明：docs/modules/
- 阶段总结：docs/phases/
- 质量审计：docs/audits/
- 决策记录：docs/decisions/
- 冷区登记：_cold/COLD_LOG.md
"""

COLD_TEMPLATE = """# 冷区登记

由 governance.py retire / purge 自动维护。冷区内容不得被热区引用。

| 冷存路径 | 原路径 | 移入日期 | 计划删除 | 状态 | 原因 |
|---|---|---|---|---|---|
"""

MODULE_TEMPLATE = """# {name}

## 职责
{desc}

## 不负责


## 接口


## 依赖
- 依赖模块：
- 配置项：

## 文件
<src/{name}/ 下每个文件的作用。新增文件时同步更新>

## 变更记录
- {today} 创建
"""

GITIGNORE_LINES = ["outputs/", "scratch/", "_cold/*", "!_cold/COLD_LOG.md", ".env"]


# ---------------------------------------------------------------- helpers
def load_cfg():
    cfg = dict(DEFAULTS)
    p = ROOT / "config" / "governance.json"
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[WARN] config/governance.json 解析失败，使用默认值：{e}")
    return cfg


def rel(p):
    return Path(p).resolve().relative_to(ROOT.resolve()).as_posix()


def allowed(relpath, cfg):
    name = relpath.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(relpath, g) or fnmatch.fnmatch(name, g) for g in cfg["allow_names"])


def bad_name(name, is_dir):
    """返回违规原因，没有问题返回 None。"""
    if not is_dir:
        if name in JUNK_FILES:
            return "系统垃圾文件"
        if name.endswith(BAD_EXT):
            return "备份/临时扩展名"
    stem = name if is_dir else (name.rsplit(".", 1)[0] if "." in name.lstrip(".") else name)
    low = stem.lower()
    if is_dir and low in EXACT_BAD_DIR:
        return "目录名不表达内容"
    if not is_dir and low in EXACT_BAD_FILE:
        return "文件名不表达内容"
    if CN_RE.search(stem):
        return "含版本/副本类中文词"
    if DUP_RE.search(stem):
        return "系统副本命名"
    if SUFFIX_RE.search(stem):
        return "版本/状态后缀"
    if PREFIX_RE.search(stem):
        return "版本/状态前缀"
    return None


def walk(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        yield Path(dirpath), dirnames, filenames


def md_table_rows(text, section_title):
    """返回某个 '## ' 小节下表格的数据行（单元格列表）及其行号。"""
    lines = text.splitlines()
    rows, in_sec = [], False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_sec = line[3:].strip().startswith(section_title)
            continue
        if in_sec and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append((i, cells))
    return rows[1:] if rows else []  # 去掉表头


def read_index():
    p = ROOT / "PROJECT_INDEX.md"
    if not p.exists():
        return None
    mods = {}
    for _, cells in md_table_rows(p.read_text(encoding="utf-8"), "模块登记"):
        if cells and cells[0]:
            name = cells[0].strip("` ")
            mods[name] = cells[1] if len(cells) > 1 else ""
    return mods


def set_index_status(name, status):
    p = ROOT / "PROJECT_INDEX.md"
    if not p.exists():
        return False
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, cells in md_table_rows(text, "模块登记"):
        if cells[0].strip("` ") == name and len(cells) > 1:
            cells[1] = status
            lines[i] = "| " + " | ".join(cells) + " |"
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
    return False


def read_cold_log():
    p = ROOT / "_cold" / "COLD_LOG.md"
    if not p.exists():
        return p, [], []
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    rows = []
    header_seen = False
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        if not header_seen:
            header_seen = True
            continue
        if len(cells) >= 6:
            rows.append((i, cells))
    return p, lines, rows


def modules_root(cfg):
    return ROOT / cfg["modules_root"]


def actual_modules(cfg):
    mr = modules_root(cfg)
    if not mr.is_dir():
        return set()
    return {d.name for d in mr.iterdir()
            if d.is_dir() and d.name not in IGNORE_DIRS and not d.name.startswith((".", "_"))
            and not d.name.endswith(".egg-info")}


# ---------------------------------------------------------------- commands
def cmd_init(args):
    created = []
    for d in SKELETON:
        p = ROOT / d
        if not p.exists():
            p.mkdir(parents=True)
            created.append(d + "/")
    for path, content in [("PROJECT_INDEX.md", INDEX_TEMPLATE), ("_cold/COLD_LOG.md", COLD_TEMPLATE)]:
        p = ROOT / path
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            created.append(path)
    gi = ROOT / ".gitignore"
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    missing = [l for l in GITIGNORE_LINES if l not in existing]
    if missing:
        with gi.open("a", encoding="utf-8") as f:
            if existing and existing[-1].strip():
                f.write("\n")
            f.write("# 文件治理\n" + "\n".join(missing) + "\n")
        created.append(".gitignore（追加 %d 行）" % len(missing))
    target = ROOT / "scripts" / "governance.py"
    if not target.exists():
        shutil.copy2(SELF, target)
        created.append("scripts/governance.py")
    print("已创建：" if created else "结构已存在，无需创建。")
    for c in created:
        print("  +", c)
    if not (ROOT / ".git").exists():
        print("\n提示：项目还没有 git。先 `git init` 并提交一次，之后的退役和清理才有安全网。")
    print("下一步：把 SKILL.md 附录中的行为规则写入 CLAUDE.md / AGENTS.md，然后运行 check。")


def cmd_new_module(args):
    cfg = load_cfg()
    name = args.name
    if not re.fullmatch(r"[a-z][a-z0-9_\-]*", name):
        sys.exit("模块名只能用小写字母、数字、下划线、连字符，且以字母开头。")
    if bad_name(name, True):
        sys.exit(f"模块名不合规：{bad_name(name, True)}")
    idx = read_index()
    if idx is None:
        sys.exit("缺少 PROJECT_INDEX.md，先运行 init。")
    if name in idx:
        sys.exit(f"模块 {name} 已登记（状态：{idx[name]}）。修改已有模块，不要重复创建。")
    src = modules_root(cfg) / name
    if src.exists() and not args.adopt:
        sys.exit(f"{rel(src)} 已存在但未登记。先确认它是否在用：在用就加 --adopt 补登记，不用就 retire。")
    if args.adopt and not src.exists():
        sys.exit(f"--adopt 用于登记已存在的模块，但 {rel(src)} 不存在。")
    src.mkdir(parents=True, exist_ok=True)
    (ROOT / "tests" / name).mkdir(parents=True, exist_ok=True)
    doc = ROOT / "docs" / "modules" / f"{name}.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    if not doc.exists():
        doc.write_text(MODULE_TEMPLATE.format(name=name, desc=args.desc or "", today=TODAY.isoformat()),
                       encoding="utf-8")
    # 追加登记行
    p = ROOT / "PROJECT_INDEX.md"
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    rows = md_table_rows(text, "模块登记")
    # 找到表格最后一行（含表头/分隔线）
    insert_at = None
    in_sec = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_sec = line[3:].strip().startswith("模块登记")
            continue
        if in_sec and line.strip().startswith("|"):
            insert_at = i + 1
    if insert_at is None:
        sys.exit("PROJECT_INDEX.md 中找不到“## 模块登记”表格。")
    status = "开发中" if args.adopt else "规划中"
    row = f"| {name} | {status} | {(args.desc or '').replace('|', '/')} | docs/modules/{name}.md |"
    lines.insert(insert_at, row)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已{'接管' if args.adopt else '登记'}模块 {name}：")
    print(f"  + {rel(src)}/\n  + tests/{name}/\n  + docs/modules/{name}.md")
    print("下一步：先填写模块说明（职责/不负责/接口），再写代码；开始开发时把状态改为“开发中”。")


def cmd_retire(args):
    cfg = load_cfg()
    target = (ROOT / args.path).resolve()
    if not target.exists():
        sys.exit(f"路径不存在：{args.path}")
    try:
        r = rel(target)
    except ValueError:
        sys.exit("只能退役项目内的文件。")
    if r.startswith("_cold/") or r == "_cold":
        sys.exit("该路径已在冷区。")
    if r in ("PROJECT_INDEX.md", "_cold/COLD_LOG.md") or target == SELF:
        sys.exit("不能退役治理核心文件。")
    if not args.reason.strip():
        sys.exit("必须写明退役原因（--reason）。")
    stamp = TODAY.strftime("%Y%m%d")
    dest = ROOT / "_cold" / stamp / r
    n = 2
    while dest.exists():
        dest = ROOT / "_cold" / stamp / f"{r}__{n}"
        n += 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target), str(dest))
    log_p = ROOT / "_cold" / "COLD_LOG.md"
    if not log_p.exists():
        log_p.write_text(COLD_TEMPLATE, encoding="utf-8")
    days = args.days if args.days is not None else cfg["cold_days"]
    due = TODAY + dt.timedelta(days=days)
    reason = args.reason.replace("|", "/").replace("\n", " ")
    with log_p.open("a", encoding="utf-8") as f:
        f.write(f"| {rel(dest)} | {r} | {TODAY.isoformat()} | {due.isoformat()} | 待删除 | {reason} |\n")
    print(f"已退役：{r} → {rel(dest)}（计划 {due.isoformat()} 删除）")

    # 模块联动
    mr = cfg["modules_root"].strip("/")
    parts = r.split("/")
    if r.startswith(mr + "/") and len(parts) == len(mr.split("/")) + 1:
        name = parts[-1]
        if set_index_status(name, "已退役"):
            print(f"PROJECT_INDEX.md 中 {name} 的状态已改为“已退役”。")
        related = [p for p in [f"tests/{name}", f"docs/modules/{name}.md", f"config/{name}"]
                   if any((ROOT / p).parent.glob(Path(p).name + "*"))]
        if related:
            print("相关路径请一并处理（退役或更新）：", ", ".join(related))
        print("建议在 docs/decisions/ 写一条记录说明为什么退役这个模块。")

    # 残留引用提示
    needle = parts[-1].rsplit(".", 1)[0]
    hits = []
    if len(needle) >= 3:
        pat = re.compile(r"\b" + re.escape(needle) + r"\b")
        for zone in HOT_ZONES:
            zp = ROOT / zone
            if not zp.is_dir():
                continue
            for d, _, files in walk(zp):
                for fn in files:
                    fp = d / fn
                    if fp.resolve() == SELF:
                        continue
                    for ln, line in iter_text_lines(fp):
                        if pat.search(line):
                            hits.append(f"{rel(fp)}:{ln}")
                            break
    if hits:
        print(f"\n以下文件仍出现 “{needle}”，请检查并清除引用：")
        for h in hits[:30]:
            print("  -", h)
        if len(hits) > 30:
            print(f"  ...共 {len(hits)} 处")


def cmd_purge(args):
    log_p, lines, rows = read_cold_log()
    if not rows:
        print("冷区为空。")
        return
    due_rows = []
    for i, cells in rows:
        try:
            due = dt.date.fromisoformat(cells[3])
        except ValueError:
            continue
        if cells[4] == "待删除" and due <= TODAY:
            due_rows.append((i, cells))
    if not due_rows:
        print("没有到期的冷区内容。")
        return
    for i, cells in due_rows:
        p = ROOT / cells[0]
        if args.yes:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.is_symlink():
                p.unlink()
            elif p.exists():
                p.unlink()
            cells[4] = "已删除"
            lines[i] = "| " + " | ".join(cells) + " |"
            print("已删除：", cells[0])
        else:
            print(f"到期：{cells[0]}（{cells[5]}）")
    if args.yes:
        log_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cold = (ROOT / "_cold").resolve()
        for _, cells in due_rows:  # 只清理被删除项留下的空父目录
            parent = (ROOT / cells[0]).resolve().parent
            while parent != cold and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
    else:
        print(f"\n共 {len(due_rows)} 项。确认后运行：python scripts/governance.py purge --yes")


def iter_text_lines(fp, limit=1_000_000):
    try:
        if fp.stat().st_size > limit:
            return
        data = fp.read_bytes()
        if b"\0" in data[:4096]:
            return
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return
    for n, line in enumerate(text.splitlines(), 1):
        yield n, line


def cmd_check(args):
    cfg = load_cfg()
    errors, warns = [], []
    E = lambda m: errors.append(m)
    W = lambda m: warns.append(m)

    # 1. 根目录
    root_dirs = ROOT_DIRS | set(cfg["root_dirs_extra"]) | IGNORE_DIRS
    root_globs = ROOT_FILE_GLOBS + list(cfg["root_files_extra"])
    for entry in sorted(ROOT.iterdir()):
        n = entry.name
        if entry.is_dir():
            if n.startswith(".") or n in root_dirs or n.endswith(".egg-info"):
                continue
            E(f"根目录出现非标准目录：{n}/ → 归入标准目录，或在 root_dirs_extra 登记")
        else:
            if n in JUNK_FILES:
                W(f"根目录系统垃圾文件：{n}")
            elif n.startswith("."):
                continue
            elif not any(fnmatch.fnmatch(n, g) for g in root_globs):
                E(f"根目录散落文件：{n} → 移到合法位置或 retire")

    # 2. 热区命名、文件数、空目录、重复内容
    hashes = {}
    file_count = {}
    skeleton = {s for s in SKELETON}
    for zone in HOT_ZONES:
        zp = ROOT / zone
        if not zp.is_dir():
            continue
        count = 0
        for d, dirnames, files in walk(zp):
            rd = rel(d)
            for dn in dirnames:
                rp = f"{rd}/{dn}"
                why = bad_name(dn, True)
                if why and not allowed(rp, cfg):
                    E(f"冗余/不清晰目录名：{rp}/（{why}）")
            real_files = [f for f in files if f != ".gitkeep"]
            count += len(files)
            if len(real_files) > cfg["max_files_per_dir"]:
                W(f"目录文件过多：{rd}/ 直接包含 {len(real_files)} 个文件（阈值 {cfg['max_files_per_dir']}），考虑拆分或检查是否有未归档内容")
            if not dirnames and not real_files and rd not in skeleton:
                W(f"空目录：{rd}/")
            for fn in files:
                fp = d / fn
                rp = f"{rd}/{fn}"
                why = bad_name(fn, False)
                if why and not allowed(rp, cfg):
                    E(f"冗余命名：{rp}（{why}）→ 合并到正式文件或 retire")
                try:
                    if fn not in COMMON_NAMES and 0 < fp.stat().st_size < 5_000_000:
                        h = hashlib.sha1(fp.read_bytes()).hexdigest()
                        hashes.setdefault(h, []).append(rp)
                except OSError:
                    pass
        file_count[zone] = count
    for h, paths in hashes.items():
        if len(paths) > 1:
            W("内容完全相同的文件：" + "、".join(paths) + " → 保留一份")

    # 3. docs 结构与命名
    docs = ROOT / "docs"
    if docs.is_dir():
        doc_dirs = set(DOC_RULES) | set(cfg["doc_dirs_extra"])
        for entry in sorted(docs.iterdir()):
            if entry.is_file() and entry.name not in ("README.md", ".gitkeep"):
                E(f"docs/ 根目录散落文件：{entry.name} → 归入 guide/modules/phases/audits/decisions")
            elif entry.is_dir() and entry.name not in doc_dirs:
                E(f"docs/ 下非标准子目录：{entry.name}/")
        for sub, rule in DOC_RULES.items():
            if not rule or not (docs / sub).is_dir():
                continue
            regex, fmt = rule
            for f in sorted((docs / sub).iterdir()):
                if f.is_file() and f.name != ".gitkeep" and not regex.match(f.name) \
                        and not allowed(rel(f), cfg):
                    E(f"文档命名不符合格式：docs/{sub}/{f.name}（应为 {fmt}）")

    # 4. 模块登记
    idx = read_index()
    if idx is None:
        E("缺少 PROJECT_INDEX.md → 运行 init")
    else:
        actual = actual_modules(cfg)
        mr = cfg["modules_root"]
        for m in sorted(actual - set(idx)):
            E(f"未登记模块：{mr}/{m}/ → 在用就补登记，不用就 retire")
        for m, status in sorted(idx.items()):
            retired = "退役" in status
            if retired:
                if m in actual:
                    E(f"模块 {m} 已标记退役，但 {mr}/{m}/ 仍在热区")
                if (ROOT / "tests" / m).exists():
                    W(f"已退役模块仍有测试目录：tests/{m}/")
                continue
            if not (ROOT / "docs" / "modules" / f"{m}.md").exists():
                E(f"模块 {m} 缺少说明文档 docs/modules/{m}.md")
            if m not in actual and "规划" not in status:
                W(f"模块 {m} 已登记（{status}）但 {mr}/{m}/ 不存在")
        mrp = modules_root(cfg)
        if mrp.is_dir():
            entry_ok = {"__init__.py", "__main__.py", ".gitkeep", "py.typed"}
            for f in sorted(mrp.iterdir()):
                if f.is_file() and f.name not in entry_ok and not f.stem in ("main", "index", "app", "lib", "mod"):
                    W(f"模块外散落文件：{rel(f)} → 归入某个模块，或确认它是入口文件")
        mdir = ROOT / "docs" / "modules"
        if mdir.is_dir():
            for f in mdir.glob("*.md"):
                if f.stem not in idx and f.name != "README.md":
                    W(f"模块文档无对应登记：docs/modules/{f.name}")

    # 5. 热区对 scratch/_cold 的引用
    for zone in ["src", "tests", "config", "scripts"]:
        zp = ROOT / zone
        if not zp.is_dir():
            continue
        for d, _, files in walk(zp):
            for fn in files:
                fp = d / fn
                if fp.resolve() == SELF or fn == "governance.py":
                    continue
                for ln, line in iter_text_lines(fp):
                    if REF_RE.search(line):
                        E(f"热区引用了临时区/冷区：{rel(fp)}:{ln} → {line.strip()[:80]}")

    # 6. 冷区
    cold = ROOT / "_cold"
    _, _, rows = read_cold_log()
    if cold.is_dir():
        logged = [c[0] for _, c in rows if c[4] == "待删除"]
        for d, _, files in walk(cold):
            for fn in files:
                rp = rel(d / fn)
                if rp == "_cold/COLD_LOG.md":
                    continue
                if not any(rp == l or rp.startswith(l.rstrip("/") + "/") for l in logged):
                    E(f"冷区有未登记文件：{rp} → 请使用 retire 命令退役")
        expired = 0
        for _, c in rows:
            if c[4] != "待删除":
                continue
            if not (ROOT / c[0]).exists():
                W(f"冷区登记的路径不存在：{c[0]}（手动删除了？请把状态改为已删除/已恢复）")
                continue
            try:
                if dt.date.fromisoformat(c[3]) <= TODAY:
                    expired += 1
            except ValueError:
                W(f"COLD_LOG 日期格式错误：{c[3]}")
        if expired:
            W(f"冷区有 {expired} 项已到删除日期 → 运行 purge")

    # 7. 临时区过期
    scratch = ROOT / "scratch"
    stale = []
    if scratch.is_dir():
        limit = time.time() - cfg["scratch_ttl_days"] * 86400
        for d, _, files in walk(scratch):
            for fn in files:
                if (d / fn).stat().st_mtime < limit:
                    stale.append(rel(d / fn))
    if stale:
        W(f"scratch/ 中 {len(stale)} 个文件超过 {cfg['scratch_ttl_days']} 天未动 → 转正或 retire："
          + "、".join(stale[:10]) + ("…" if len(stale) > 10 else ""))

    # 8. gitignore
    if (ROOT / ".git").exists():
        gi = ROOT / ".gitignore"
        content = gi.read_text(encoding="utf-8") if gi.exists() else ""
        for l in ["outputs/", "scratch/", "_cold/*"]:
            if l not in content:
                W(f".gitignore 缺少 {l}")
    else:
        W("项目没有 git 仓库：退役和清理缺少安全网")

    # 输出
    print("文件分布：" + "，".join(f"{z}={n}" for z, n in file_count.items()) +
          f"，scratch={sum(len(f) for _, _, f in walk(scratch)) if scratch.is_dir() else 0}"
          f"，冷区待删除={sum(1 for _, c in rows if c[4] == '待删除')}")
    for m in errors:
        print("[ERROR]", m)
    for m in warns:
        print("[WARN] ", m)
    if errors:
        print(f"\n检查未通过：{len(errors)} 个错误，{len(warns)} 个警告。修复错误后再继续推进。")
        sys.exit(1)
    print(f"\n检查通过（{len(warns)} 个警告）。" + ("警告不阻塞，但应在阶段结束前处理。" if warns else ""))


def main():
    ap = argparse.ArgumentParser(description="项目文件治理工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="初始化目录结构")
    sub.add_parser("check", help="门禁检查")
    p = sub.add_parser("new-module", help="新增模块")
    p.add_argument("name")
    p.add_argument("--desc", default="")
    p.add_argument("--adopt", action="store_true", help="登记一个已存在但未登记的模块（接管旧项目时用）")
    p = sub.add_parser("retire", help="退役到冷区")
    p.add_argument("path")
    p.add_argument("--reason", required=True)
    p.add_argument("--days", type=int)
    p = sub.add_parser("purge", help="删除到期冷区内容")
    p.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    {"init": cmd_init, "check": cmd_check, "new-module": cmd_new_module,
     "retire": cmd_retire, "purge": cmd_purge}[args.cmd](args)


if __name__ == "__main__":
    main()
