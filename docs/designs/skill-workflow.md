# Code Design Planner：设计先行的功能开发闭环

- 日期：2026-09-30（Australia/Sydney）
- 状态：done
- 评审范围：本空仓库的初始交付；不存在已有业务代码或基线提交

## User Requirement / Requirement Analysis

用户希望将全栈功能开发固定为：User Requirement → Requirement Analysis →
code-design-planner → docs/designs/xxx.md → Implementation → Tests → git diff →
code-design-planner --review → Fix → Done，并发布到 Pango-proto/code-design-planner。

| ID | 可观察的验收条件 | 验证方式 |
|---|---|---|
| AC-01 | 一个 SKILL.md 入口，明确 Planner 与 Reviewer 的选择和转换 | 独立技能行为演练 |
| AC-02 | 实现前形成需求、验收、全栈边界、测试计划和取舍；一个功能一份活设计 | 设计模板与 Planner 演练 |
| AC-03 | Review 基于设计、当前代码、完整变更范围和测试证据，Fix 后重新验证 | Reviewer 演练，包括未跟踪文件与缺失设计 |
| AC-04 | 跨项目可安装，保留既有技能与 AGENTS.md，重复运行不重复插入规则 | 临时项目安装测试 |
| AC-05 | 说明当前技能/插件协作及能力边界，不要求额外插件或虚构命令 | 官方文档核对与人工审阅 |
| AC-06 | 源码、设计、验证、使用文档落入指定 GitHub 仓库 | 远端提交内容核对 |

## Scope / Non-goals

交付中文为主的可移植 Codex skill、全局流程与项目知识模板、安全的安装脚本、验证脚本与 CI。
根据用户追加规划，推荐全局一份技能、全局通用流程规则，项目只维护项目知识和按需设计记录。
不做业务全栈脚手架，不绑定前后端技术栈；本次构建安装工具，不直接改写本机全局配置，
不自动部署、合并或申请付费服务。
`--review` 是传给技能的自然语言模式约定，不是 Codex 或 shell 的新 CLI。
Skill 与 AGENTS.md 是代理执行约定；不能保证所有工具都服从，也不能代替分支保护或语义审查。

## Design

根 SKILL.md 保留共同约束和两种模式；详细规则分别进入 references/planner.md 与
references/reviewer.md。references/integrations.md 记录可选的现有 skill/plugin 协作。
assets/design-template.md 是唯一功能设计模板，评审与修复记录原地追加。
assets/global-agents.md 是安装器插入全局 AGENTS.md 的受管理区块。
assets/project-agents.md 只承载技术栈、目录、领域边界、测试命令等项目知识。

安装器用 Python 标准库，复制 SKILL.md、agents、references、assets 至用户级
`~/.agents/skills/code-design-planner/`，可显式指定兼容现有环境的技能目录。
全局规则注入须显式选项，默认位置 `$CODEX_HOME/AGENTS.md` 或 `~/.codex/AGENTS.md`。
不能覆盖既有规则；已有技能内容不一致时拒绝覆盖，除非用户显式选择更新。
预检所有冲突和路径，拒绝有风险的符号链接；禁止在半安装后才发现 AGENTS.md 冲突。
只复制发行清单中的 8 个资源文件，不携带仓库治理、Git 元数据或测试缓存。project 子命令仅建立项目
知识模板；已有 AGENTS.md 内容不同时保留并提示人工合并，不复制技能或整套流程。

五阶段为 Requirement、Design、Implementation、Verification、Review；G1 是需求可行动，
G2 是设计就绪且在已有授权内，G3 是验证和必要修复完成。只有用户要求先设计再确认、
项目明确要求人工批准，或超出授权范围时，G2 才等待人工。Done 不等同自动合并。
Trivial 仅无行为变化的轻微修改可走精简路径；行为性配置不能按行数认定 trivial。
一般功能遵循完整闭环；大型/高风险功能增加调研与独立设计评审。所有路径均检查 diff。

Planner 在有足够信息时继续已授权的实现；只做设计或只做评审的请求保留其边界。
Reviewer 对照 AC，检查 staged、unstaged、untracked 和分支已提交内容；无法确认基线时
报告范围限制。缺失设计不能伪装成事前设计；补建时标注追溯来源。无法运行测试不得标记 Done。
非阻塞观察可以记录；未关闭的必要修复与验收阻塞必须保持 needs-fix / blocked 状态。

## Full-stack applicability

前端：状态、可访问性与交互验收；API：契约、校验、错误与授权；数据：迁移、兼容性、
一致性；运行：配置、观测、回滚。按实际功能选择相关层，N/A 要给简短理由。
本技能项目没有 UI、运行中的 API 或数据库；相应层为 N/A。

## Alternatives / Risks

只写长提示词无法跨项目持续发现；因此提供用户级安装和全局 AGENTS 规则。
自动写入所有仓库会扩大授权范围；因此只对显式选定的安装目标生效。
复制整套现有插件会增加依赖；因此只提供按需路由及无插件时的降级方式。
自动语义判定 Done 不可靠；CI 验证包结构与安装行为，最终完成仍依赖证据与评审。

## Implementation / Tests

1. 编写技能入口、模式指导、模板与元数据。
2. 完成无依赖安装与包校验工具；在临时项目测试保护和幂等性。
3. README 说明安装、触发、全流程、可选协作、限制；CI 跑同一组检查。
4. 独立 agent 对真实场景做 forward-test；依据发现修复、重跑受影响检查。
5. 检查完整 git diff，记录审阅范围与证据，发布并核对远端。

## Validation evidence

2026-09-30 本地实际执行：

| 检查 | 结果 | 覆盖 / 限制 |
|---|---|---|
| `python3 scripts/validate.py` | passed | 8 个发行文件、受限 YAML、包内链接与发行清单 |
| `python3 -m unittest discover -s tests -v` | 40 tests passed | 19 个安装测试 + 21 个校验测试，含真实源码安装后的包校验 |
| `python3 scripts/governance.py check` | passed，0 warnings | 当前仓库文件治理 |
| skill-creator 的 `quick_validate.py .` | Skill is valid | 官方脚本的 PyYAML 仅安装在临时目录；不加入本项目依赖 |
| 独立 Planner 演练 | 符合范围 | 只新增设计，保留原业务文件；遇到未知元素模型时标 blocked，未猜测核心契约 |
| 独立 Reviewer 演练 | 找到 P1 blocking | 读取 staged 与 untracked 文件；1 个 happy-path 测试通过，但实际探针复现非所有者取消，未误判 Done |
| 缺失设计的 Reviewer 演练 | 正确报告范围限制 | 依据原需求识别越权问题，不声称设计一致性通过，不补写文档；既有文件哈希不变 |
| GitHub Actions | passed | [初始实现提交的 CI](https://github.com/Pango-proto/code-design-planner/actions/runs/36691821783)：Python 3.10 / 3.13 均完成相同校验与 40 项测试 |

行为演练在仓库外临时项目执行；其业务文件不作为本项目交付。本机运行版本为 Python 3.12。

## Actual scope / Change budget

本次是初始技能项目，按技能、资源、工具、测试、文档五组交付，未添加业务应用或额外服务。
用户补充分层要求后，将原项目级默认安装改为用户级默认安装；这是已记录的需求变更。
发行包只有 8 个文件；仓库额外保留安装/校验/治理工具、测试、CI、README 和项目设计。
两项评审修复只修改对应工具与回归测试，未扩大产品范围。

## Review / Fix

| ID | 严重性 / 是否阻塞交付 | 发现与修复 | 状态 |
|---|---|---|---|
| R-01 | P2 / blocking | 全局 override 静默屏蔽规则；安装前预检非空 override，保留文件并提示人工合并，覆盖拒绝与空文件场景 | fixed / 独立复审关闭 |
| R-02 | P2 / blocking | 源码存在的链接目标不一定进入发行包；校验发行目标、两份清单一致性及真实安装后的资源闭环 | fixed / 独立复审关闭 |
| R-03 | P2 / blocking | review-only 是否可写回设计存在歧义；入口和指导统一为默认只读，完整开发或已授权才回写 | fixed / 独立复审关闭 |

Design drift：全局/项目分层按追加需求调整；其余在设计范围内。无未解释的业务变更。
Simplification：不引入 MCP 服务、CLI agent runner、技术栈脚手架或额外项目技能副本。
Verdict：`pass`；初始文件集已审阅、40 项回归检查通过，R-01—R-03 关闭。
AC-06 已通过 GitHub main 提交匹配与成功的远端 CI 核验。

## Gate record / Delivery

- G1：用户原始闭环要求与追加的全局/项目分层均已纳入。
- G2：在代码前建立本设计；本任务已授权实现与写入指定仓库，不需要逐阶段重复批准。
- G3：本地必要验证和修复已完成；没有开放的阻塞代码问题。
- 发布：GitHub 插件曾返回 403，未产生远端文件；用户随后完成 gh 登录，已核验 Pango-proto 对仓库有 ADMIN 权限。
  初始实现提交 `b1d162ecf0e2edc575a063fa343618576525fede` 已推送 main，远端 SHA 匹配且 CI 成功。
- 未执行：本机全局技能安装、全局规则改写、分支保护配置和自动部署均不属于本次仓库交付。
