# 本项目约定

本仓库交付一个全局复用的技能及 Python 标准库工具，不是业务应用。

- 技能唯一源码：`skills/code-design-planner/`；先读取其中的 `SKILL.md`，按 Planner / Reviewer 闭环维护。
- 工具与测试：`scripts/`、`tests/`；真实安装目标仍为用户级技能目录，不向每个项目复制。
- 使用说明和目录导航：`README.md`；设计、取舍、验证与进度：`docs/designs/skill-workflow.md`。

检查命令：

```sh
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
git diff --check
```

用户明确要求精简单技能仓库，采用以上轻量治理：不要重新生成 PROJECT_INDEX、通用
governance.py、冷区登记或每轮独立审计/总结。需要的记录原地更新到唯一设计文件。
新增文件先确认现有文件不能承担其职责；仅实际需要时建目录，不复制版本后缀文件。
废弃文件先检查引用，保留有价值的决策后通过 Git 删除；历史由 Git 保存。
一次性试验使用系统临时目录，发行资源不得依赖它们。不删除用户无关内容或改写 Git 历史。
