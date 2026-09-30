# 本项目约定

## 项目知识

本仓库交付 `code-design-planner` 技能及 Python 标准库安装工具，不是业务应用。
技能唯一源码在根目录 `SKILL.md`；模式指导在 `references/`，发行模板在 `assets/`，
Codex 元数据在 `agents/`。项目设计在 `docs/designs/`，唯一状态入口为 `PROJECT_INDEX.md`。
推荐分发到用户级技能目录；不要向每个项目复制技能或通用流程。

## 本仓库的开发入口

维护技能时直接读取根 `SKILL.md`，按其中 Planner → Verification → Reviewer 闭环工作。
这是源码仓库的自举入口，消费项目不需要复制该文件。只设计/只评审请求遵守其范围。
命令：`python3 scripts/validate.py`、`python3 -m unittest discover -s tests -v`、
`python3 scripts/governance.py check`。验证器尚未建立时，明确其不可用，不伪报通过。

## 文件治理

推进前与阶段完成时执行治理检查；ERROR 修复后继续。创建文件前查找已有职责文件，原地更新。
不用版本或状态后缀复制文件；回退依赖 Git。文件位置由 PROJECT_INDEX.md 和治理配置确定。
一次性试验放临时区，发行代码不得依赖临时区或冷区；替换废弃实现时同步清理引用。
本仓库无 src 业务模块；将来增加业务模块时按 governance.py new-module 登记并先写职责。
进度更新到索引，阶段完成再写总结；失败路线先记录原因，再退役和检查，不随意删除用户文件。
不自动提交无关变更、清空临时区、添加标签或修改全局配置。
