# Code Design Planner

给 vibe-coding 一个可追溯的全栈开发流程：先理解需求和设计，再实现、验证、审阅和修复。
**全局维护一份技能，项目只维护项目知识。** 不绑定前端框架、后端语言或特定插件。

```text
User Requirement
  ↓
Requirement Analysis         G1：需求可行动
  ↓
code-design-planner           Planner Mode
  ↓
docs/designs/<feature>.md     G2：设计就绪，属于已有授权
  ↓
Implementation
  ↓
Tests / lint / typecheck / build（按项目实际需要）
  ↓
git diff + 分支提交 + 暂存 / 未暂存 / 未跟踪文件
  ↓
code-design-planner --review  Reviewer Mode
  ↓
Fix → 复验 / 复审             G3：验收、验证与必要修复完成
  ↓
Done
```

五阶段是 Requirement → Design → Implementation → Verification → Review。
三道门禁依据实际证据推进；用户明确要求“先设计、等确认”时才停在设计阶段。
Done 不代表自动获准合并或部署。

## 全局流程，项目知识

```text
用户级配置
├── ~/.agents/skills/code-design-planner/
│   ├── SKILL.md
│   │   ├── Planner Mode
│   │   └── Reviewer Mode
│   ├── references/
│   ├── assets/
│   └── agents/openai.yaml
└── ~/.codex/AGENTS.md                  通用流程触发规则

项目 A/                                项目 B/
├── AGENTS.md                           ├── AGENTS.md
├── docs/designs/（按需）                ├── docs/designs/（按需）
└── 现有源代码目录                      └── 现有源代码目录
```

全局 AGENTS 负责触发，技能负责具体方法。项目 AGENTS 只写真实技术栈、目录、领域规则、
架构边界和测试命令，不复制一整套技能。一个功能维护一份设计，测试和 Review / Fix 记录在同一文件。

当前官方用户级技能路径是 `~/.agents/skills/`；全局指令是 `$CODEX_HOME/AGENTS.md`，
未设置时为 `~/.codex/AGENTS.md`。既有环境可能使用 `~/.codex/skills/`，安装器支持显式指定。
参见 [官方 Skills 文档](https://learn.chatgpt.com/docs/build-skills) 与
[官方 AGENTS.md 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。

## 安装一次

要求 Python 3.10+ 与 Git，无额外 Python 包。以下从仓库根目录运行：

```sh
git clone https://github.com/Pango-proto/code-design-planner.git
cd code-design-planner

# 先预览：不会写入文件
python3 scripts/install.py install --with-global-rules --dry-run

# 安装一份用户级技能，并向全局 AGENTS.md 合并受管理的流程区块
python3 scripts/install.py install --with-global-rules
```

只安装技能、不写全局规则时省略 `--with-global-rules`。需要兼容明确使用旧目录的客户端时，
使用 `--skills-dir "$HOME/.codex/skills"`；不要同时在多个发现路径安装同名副本。
`--codex-home` 可指定全局指令目录，不改变技能目录。

安装器只分发 8 个技能资源文件，保留全局 AGENTS 的其他内容。重复执行不重复添加规则；
发现不同内容时默认拒绝覆盖，检查后加 `--update` 更新已登记资源和受管理区块。
未知文件保留。若全局存在非空 `AGENTS.override.md`，它会屏蔽同级 AGENTS.md，安装器会拒绝
写入并提示人工合并有效规则。写入前检查冲突与符号链接，每个文件原子替换；磁盘/权限等运行时错误仍可能
中断多文件安装，修复原因后重跑即可。安装器不修改所有项目、不注册终端命令，也不安装插件。

在新的 Codex 会话检查技能列表及全局规则是否实际加载。发现行为依赖客户端版本和实际配置；
符号链接安装虽然受到 Codex 支持，本安装器为防止误写会拒绝目标中的符号链接。

## 项目只初始化知识

```sh
python3 scripts/install.py project --path /path/to/project
```

这只创建 `AGENTS.md` 模板，不复制技能，不预建空的 `docs/designs/`。
从实际代码和配置填入技术栈、架构与验证命令。已有不同内容的 AGENTS 会被保留，
安装器提示手工合并 [项目知识模板](assets/project-agents.md)；不要整文件替换。

## 日常调用

在 Codex 消息中输入，而非终端：

```text
$code-design-planner --full
实现订单取消功能。先明确需求和验收，完成设计后在当前授权内实现，验证、评审并修复必要问题。
```

仅设计、先讨论方案：

```text
$code-design-planner --plan
设计订单取消功能。先不要改业务代码，等我确认。
```

审阅已有变更：

```text
$code-design-planner --review
依据 docs/designs/order-cancellation.md 审阅相对目标分支的完整变更与工作区，只报告问题。
```

`--plan` / `--review` / `--full` 是本技能定义的提示词约定，**不是 Codex CLI 参数或可执行命令**。
完整开发请求会自动走 Planner → 实现与验证 → Reviewer；只设计或只审查请求不会扩大成实现任务。

## 按任务大小使用

| 类型 | 处理 |
|---|---|
| Trivial：不改行为的拼写、文案、格式 | 简短需求记录 → 修改 → 必要验证 → diff 检查，可无设计文件 |
| Normal：功能、行为修复、API/数据变化、新依赖 | 完整闭环，短设计即可 |
| Large：跨系统、权限、支付、重要迁移、大重构 | 完整闭环 + 必要调研、设计评审、兼容/回滚分析；优先独立 reviewer |

不能按行数把行为性配置修改认定为 trivial。全栈检查覆盖受影响的 UI、API、数据和运行层，
不涉及的部分注明 N/A。设计预测新增/修改/删除文件；实际范围显著扩大时先解释和更新设计。

Reviewer 输出 Findings、Design drift、Simplification opportunities、Verdict。
结论为 `pass` / `needs-fix` / `incomplete`，不打分。无法执行必要验证时不能标记 Done。

## 与已有技能和插件协作

核心流程只需要仓库文件、代码工具和 Git。已有的文件治理、官方文档、可视化、浏览器、
GitHub 等能力按需使用，缺少某个可选插件不会阻塞整个流程。
完整映射与边界见 [协作说明](references/integrations.md)。普通 Web 项目不会因此迁移到 Sites。

Skill 和 AGENTS 是代理指令，不能使所有开发工具“绝对不可跳过”。本仓库 CI 校验技能包结构、
资源链接、安装行为与文件治理，**不自动验证消费项目的设计语义、业务测试或审查是否真实发生**。
需要硬性合并门禁时，应在消费项目配置自己的 CI 必需检查和分支保护；本项目不会替用户开启这些设置。

## 开发与验证

```sh
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/governance.py check
```

[本项目设计](docs/designs/skill-workflow.md) 记录需求、取舍与实际验证证据。
[项目索引](PROJECT_INDEX.md) 说明文件职责。安装代码与校验器只依赖标准库；
CI 与本地执行相同检查。`validate.py` 检查本项目使用的受限 YAML 结构，不是通用 YAML 验证器。
