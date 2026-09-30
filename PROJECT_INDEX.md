# 项目索引

> 本仓库文件职责与交付状态的唯一登记处。业务模块新增时使用治理工具登记。

## 当前阶段
- 阶段：P01-skill-delivery
- 目标：交付全局一份、项目知识本地化的 Planner / Reviewer 开发协议。
- 进度：已发布 main；40 项测试、结构/治理检查、独立评审与 Python 3.10 / 3.13 的远端 CI 均通过。

## 模块登记
| 模块 | 状态 | 说明 | 文档 |
|---|---|---|---|

状态取值：规划中 / 开发中 / 已完成 / 已退役

本项目不包含 src 业务模块。交付资源按下表维护，不为技能包装制造空业务模块。

## 资源职责

| 位置 | 职责 |
|---|---|
| SKILL.md | 共同规则、Planner / Reviewer 入口与完成条件 |
| references/ | 两种模式的细则与可选技能/插件协作 |
| assets/ | 功能设计、全局规则、项目知识模板 |
| agents/openai.yaml | 技能显示与默认调用元数据 |
| scripts/install.py | 安全安装唯一全局技能、可选全局规则、独立项目知识模板 |
| scripts/validate.py | 技能资源与受限元数据的结构校验 |
| scripts/governance.py | 项目文件治理工具，来源于本机 project-file-governance skill |
| tests/ | 安装与结构校验的临时目录测试 |
| config/governance.json | 技能目录布局的显式治理例外 |
| .github/workflows/validate.yml | CI 执行本地同样的检查 |

## 文档索引
- 项目指导：docs/guide/
- 模块说明：docs/modules/
- 阶段总结：docs/phases/
- 质量审计：docs/audits/
- 决策记录：docs/decisions/
- 冷区登记：_cold/COLD_LOG.md
- 主设计：docs/designs/skill-workflow.md
- 目录决策：docs/decisions/D001-skill-layout.md
- 交付审计：docs/audits/2026-09-30_skill-delivery.md
- 阶段总结：docs/phases/P01-skill-delivery.md
