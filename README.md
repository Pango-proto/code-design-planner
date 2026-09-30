# Code Design Planner

一个支持 **Planner / Reviewer 双模式**的 Codex skill，让功能开发遵循：

```text
需求 → 分析 → 设计 → 实现 → 验证 → diff 审查 → 修复 → Done
```

全局只维护一份技能；项目只维护自身 `AGENTS.md` 和按需创建的 `docs/designs/`。
不绑定全栈技术栈，不需要额外插件。

## 从哪里开始

| 你要做什么 | 看这里 |
|---|---|
| 理解技能如何工作 | [SKILL.md](skills/code-design-planner/SKILL.md) |
| 安装或更新 | 本页下方的安装命令 |
| 了解可选技能 / 插件协作 | [协作说明](skills/code-design-planner/references/integrations.md) |
| 维护项目或查看验证证据 | [开发约定](AGENTS.md) · [设计记录](docs/designs/skill-workflow.md) |

## 仓库结构

```text
code-design-planner/
├── README.md                      使用入口
├── AGENTS.md                      本仓库开发约定
├── skills/
│   └── code-design-planner/        可安装的完整技能包（8 个文件）
│       ├── SKILL.md                Planner / Reviewer 入口
│       ├── agents/openai.yaml      Codex 显示配置
│       ├── references/             两种模式的指导与可选协作
│       └── assets/                 设计、全局规则、项目知识模板
├── scripts/                       安装器与结构校验器
├── tests/                         工具行为测试
└── docs/designs/                   唯一设计与验证记录
```

`.github/workflows/validate.yml` 负责 CI；`.gitignore` 排除缓存。技能运行文件全部在
`skills/code-design-planner/`，工具、测试和仓库文档不进入安装包。

## 安装一次

需要 Python 3.10+、Git，无额外 Python 包。从仓库根目录运行：

```sh
git clone https://github.com/Pango-proto/code-design-planner.git
cd code-design-planner
python3 scripts/install.py install --with-global-rules --dry-run
python3 scripts/install.py install --with-global-rules
```

默认安装到 `~/.agents/skills/code-design-planner/`；`--with-global-rules` 将触发规则合并到
`$CODEX_HOME/AGENTS.md`（默认 `~/.codex/AGENTS.md`）。仅安装技能时省略该选项。
安装后在新会话核对技能和规则是否加载；[官方路径与发现说明](https://learn.chatgpt.com/docs/build-skills)。

- 重复安装不重复写入；不同内容默认拒绝覆盖，检查后用 `--update` 更新发行文件和受管理规则区块。
- 现有规则及未知文件保留；非空 `AGENTS.override.md` 会使规则安装中止并提示人工合并。
- 通过 `--skills-dir` 指定明确使用旧路径的环境，例如 `"$HOME/.codex/skills"`，避免同名多份安装。
- 安装器拒绝路径中的非系统符号链接；先预检冲突，再逐文件原子替换。运行时写入失败后可修复原因并重跑。

从旧版仓库升级时先 `git pull`，原安装命令继续适用。若使用支持 GitHub 子目录的技能安装器，
源码路径改为 **`skills/code-design-planner`**；技能名称和用户级安装位置不变。

## 项目只记录自身知识

```sh
python3 scripts/install.py project --path /path/to/project
```

仅创建项目 `AGENTS.md` 模板，已有文件保持原样并提示人工合并；不复制技能，不预建空设计目录。
从项目实际配置填写技术栈、领域规则、架构边界和验证命令。

## 日常使用

在 Codex 消息中调用：

```text
$code-design-planner --full 实现订单取消功能，完成设计、实现、验证、评审与必要修复。
$code-design-planner --plan 先设计订单取消功能，不改代码，等我确认。
$code-design-planner --review 根据原需求和设计审阅完整变更，只报告问题。
```

这些参数是技能的提示词约定，不是终端命令或 Codex CLI 参数。仅评审默认只读。
三道门禁分别检查需求可行动、设计可实施、验证与必要修复完成；已有授权内连续推进。
无行为变化的微小修正可使用简短记录，一般功能写短设计，大型任务增加必要调研和独立评审。

Skill / AGENTS 是代理指令，不能保证所有工具都“绝对不可跳过”。本仓库 CI 只检查包结构和工具行为，
不能证明消费项目的设计语义、业务测试或审查已完成。硬性合并门禁由消费项目自己的 CI 和分支保护实现。

## 开发与验证

```sh
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
git diff --check
```

校验器默认读取 `skills/code-design-planner/`；显式 `--root` 指向要检查的技能包目录。
CI 使用 Python 3.10 / 3.13 执行包校验和工具测试。元数据校验只支持本项目所需的受限 YAML 结构。
新增记录优先更新已有文件；旧布局、审计和阶段记录由 Git 历史追溯，不另存副本。
