# <功能名称>

- 状态：proposed | designed | implementing | verifying | reviewing | needs-fix | blocked | done
- 规模：normal | large（无行为变化的 trivial 可使用简短记录）
- 需求来源：<用户请求 / issue>
- 设计记录：事前设计 / 追溯设计（如追溯，说明缺失情况）
- 审阅范围：<基线来源、merge-base、HEAD、工作区与未跟踪文件>

## Requirement

目标、非目标、约束、假设、尚未关闭的关键问题。

| AC | 输入 / 操作 | 预期结果 | 计划验证 |
|---|---|---|---|
| AC-01 | <用户操作> | <可观察结果> | <测试或实际检查> |

## Current state

已读取的入口、模块、调用方、现有测试及相关事实；避免凭空描述。

## Design

职责、系统边界、依赖方向、接口/契约、数据流、错误处理和副作用。
只写涉及的前端、API、数据和运行层；不涉及的层标 N/A 并说明理由。
记录兼容、迁移、回滚等实际需要考虑的内容。

## Change budget

| 操作 | 文件 / 模块 | 原因 |
|---|---|---|
| add / modify / delete | <路径> | <需求关联> |

实际范围变化时在此记录原因与设计更新，不静默扩大范围。

## Alternatives and trade-offs

选择的方案、舍弃的替代方案及具体原因；哪些抽象暂时不需要。

## Implementation and verification plan

实施顺序；每个 AC 的成功/失败路径；真实的测试、lint、类型检查与 build 命令；
所需环境与外部依赖。记录哪些检查不适用及理由。

## Gate record

- G1：需求可行动的依据 / 阻塞项。
- G2：设计就绪与授权依据；只有明确要求人工批准才等待，记录实际批准而非猜测。
- G3：最终验证与必要修复证据；不能预填通过。

## Verification evidence

| AC / 检查 | 实际命令或操作 | 结果 | 对应版本 / 限制 |
|---|---|---|---|
| <编号> | <实际执行内容> | passed / failed / not-run | <版本与原因> |

## Review / Fix

### Findings

ID、严重性、是否 blocking、文件:行、触发与影响、修复及复验状态。

### Design drift

与原设计及预算的差异、原因和需求符合性。

### Simplification opportunities

有证据的可简化结构，或未发现。

### Verdict

pass / needs-fix / incomplete；覆盖范围、检查证据、未关闭项与限制。

## Handoff

实际完成的内容、剩余非阻塞项；是否涉及另行授权的合并或部署。
