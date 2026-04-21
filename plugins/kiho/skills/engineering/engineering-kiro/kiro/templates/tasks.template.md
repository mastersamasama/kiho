# 实现计划: [Feature/Bugfix/Refactor Name]

## 概述

[实现内容概述、复用组件列表、任务总数、主要技术决策]

**模式**: [Feature / Bugfix / Refactor]
**涉及包**: [列出受影响的包/模块/目录]
**任务总数**: [N 个任务，含 M 个检查点]

## 任务依赖顺序

```
[依赖图，例如:]
schemas → mocks → hooks → 组件 → 集成 → 验证
```

## 任务执行 SOP（每个任务遵循）

```
实现子任务 → 内联测试 → typecheck + lint + test → 自审修复 → 循环直到清洁
                                                          ↓
                                                  [检查点处触发]
                                               代码审查 (已发现的审查 skill 或内置审查协议)
                                                      → 修复发现
                                                      → 重新审查
                                                      → 循环直到无 Blockers
```

**每个任务必须运行测试：** 实现 + 编写测试后，运行项目测试命令（参见第一步探测）确认通过，再标记完成。

---

## 任务（Feature 模式示例）

- [ ] 1. [基础任务 — schemas/types/数据层]
  - [ ] 1.1 创建 `path/to/schema.ts` — [描述，遵循项目验证库模式]
    - _需求: X.Y, X.Z_
  - [ ] 1.2 创建 `path/to/mock.ts` — [Mock 数据，遵循现有模式]
    - _需求: X.Y_
  - [ ] 1.3 单元测试: Schema 验证
    - 测试类型: Unit test (.test.ts)
    - **属性 1: [Schema 名] 接受合法输入**
    - **属性 2: [Schema 名] 拒绝非法输入**
    - **验证: 需求 X.Y**

- [ ] 2. [Hook/服务层任务]
  - [ ] 2.1 创建 `path/to/useXxx.ts` — [描述，状态管理策略]
    - _需求: X.Y_
    - (复用: useExistingHook)
  - [ ] 2.2 属性测试: Hook 状态转换
    - 测试类型: Property test（使用项目指定的属性测试库）
    - **属性 1: [属性名]** — `forall input. condition => property`
    - **验证: 需求 X.Y**

- [ ] 3. **检查点** — [里程碑名，如 "数据层就绪"]
  - [ ] 3.1 验证: 项目类型检查命令通过
  - [ ] 3.2 验证: 项目 lint 命令通过
  - [ ] 3.3 验证: 运行此阶段所有测试通过
  - [ ] 3.4 代码审查: 触发 已发现的审查 skill 或内置审查协议 skill
    - 审查范围: 此检查点涉及的所有文件
    - 加载: core-checklist + 领域 checklist
    - 输出: Blockers / Suggestions / Nitpicks
  - [ ] 3.5 修复: 处理所有 🔴 Blockers 和 🟡 Suggestions
  - [ ] 3.6 重新验证: typecheck + lint + 测试 + 再次审查
  - [ ] 3.7 循环: 重复 3.4-3.6 直到无 Blockers
  - 如有问题，向用户报告

- [ ] 4. [组件任务]
  - [ ] 4.1 创建 `path/to/Component.tsx` — [描述，遵循前端模式]
    - _需求: X.Y, X.Z_
    - (复用: ExistingComponent)
  - [ ] 4.2 组件测试: [组件名] 交互行为
    - 测试类型: Component test (.test.tsx)
    - **属性 1: [行为名]** — [测试描述]
    - **验证: 需求 X.Y**
  - [ ] 4.3 单元测试: ARIA 角色正确性
    - 测试类型: Unit test
    - _需求: [无障碍需求编号]_

[继续按依赖顺序...]

- [ ] N. 最终验证
  - [ ] N.1 运行项目类型检查命令 — 全部受影响包
  - [ ] N.2 运行项目 lint 命令
  - [ ] N.3 运行所有测试 — 受影响包
  - [ ] N.4 覆盖率验证 — 运行覆盖率命令（参照 steering 测试标准）
    - 检查是否满足 `.kiro/steering/testing.md` 定义的覆盖率目标
  - [ ] N.5 响应式验证 (320px, 375px, 768px, 1024px) — 如前端
  - [ ] N.6 暗色模式验证 — 如前端
  - [ ] N.7 SSR 输出验证 — 如适用
  - [ ] N.8 最终代码审查 (已发现的审查 skill 或内置审查协议)
    - 全量 diff 审查: `git diff` 所有变更
    - 安全审查: security-checklist
    - 可扩展性审查: scalability-checklist
  - [ ] N.9 处理审查发现 → loop-fix 直到清洁

---

## 任务（Bugfix 模式示例）

- [ ] 1. 探索测试 — 编码缺陷条件
  - [ ] 1.1 编写探索测试: [缺陷行为描述]
    - 测试编码预期行为，在未修复代码上必须 **FAIL**
    - 测试类型: [Unit/Component/Integration]
    - 文件: `path/to/__tests__/xxx.test.ts`
  - ⚠️ 不要修复测试或代码，只记录失败

- [ ] 2. 保持测试 — 确认基线行为
  - [ ] 2.1 编写保持属性测试: [不变行为描述]
    - 验证修复不应破坏的行为
    - 在未修复代码上必须 **PASS**
    - 测试类型: [Unit/Property]
    - 文件: `path/to/__tests__/xxx.test.ts`

- [ ] 3. 修复实现
  - [ ] 3.1 修改 `path/to/file.ts` — [具体修复描述]
    - _需求: bugfix.md 预期行为 1_
  - [ ] 3.2 修改 `path/to/file.ts` — [具体修复描述]
    - _需求: bugfix.md 预期行为 2_
  - [ ] 3.3 验证: 探索测试现在 **PASS**（缺陷已修复）
  - [ ] 3.4 验证: 保持测试仍然 **PASS**（无回归）

- [ ] 4. **检查点** — 修复验证
  - [ ] 4.1 验证: 项目类型检查命令通过
  - [ ] 4.2 验证: 项目 lint 命令通过
  - [ ] 4.3 验证: 全部测试通过（探索 + 保持 + 既有）
  - [ ] 4.4 代码审查 (已发现的审查 skill 或内置审查协议)
  - [ ] 4.5 loop-fix: 修复发现 → 重新审查 → 直到清洁

- [ ] 5. 最终验证
  - [ ] 5.1-5.8 [同 Feature 模式最终验证]

---

## 任务（Refactor 模式示例）

- [ ] 1. 基线快照
  - [ ] 1.1 运行现有测试，记录通过/失败状态
  - [ ] 1.2 补充保持测试: 覆盖关键公共接口
    - 测试类型: [Unit/Integration]
    - 确保重构后行为不变

- [ ] 2. [重构任务 — 按步骤拆分]
  - [ ] 2.1 [具体重构步骤] — `path/to/file.ts`
    - _需求: requirements.md X.Y_
  - [ ] 2.2 验证: 所有保持测试仍然 PASS

- [ ] 3. **检查点** — [里程碑]
  - [同 Feature 模式检查点 SOP]

[继续...]

- [ ] N. 最终验证
  - [同 Feature 模式最终验证]

---

## 测试类型决策树

```
代码是否为无 I/O 的纯函数？
├── YES → Unit test (.test.ts)
│   是否为 Schema 验证？
│   ├── YES → 追加 property test（按 steering 强制规则）
│   └── 是否为安全/加密函数？
│       ├── YES → 追加 property test（高 runs 数，按 steering 强制规则）
│       └── 多边界值/不变量？ → 推荐追加 property test
└── NO
    UI 组件？
    ├── YES → Component test (.test.tsx)
    │   涉及 API 调用？ → Integration test + API mock
    └── 状态管理 Hook？
        ├── 全局 Store → renderHook + state 快照
        ├── 数据获取 Hook → renderHook + API mock
        └── 纯状态 → renderHook unit test
    API 路由处理器？ → Integration test + route client
    RPC Procedure？ → Integration test + caller
    中间件？ → Integration test + route client
    关键用户旅程？ → E2E test
```

**加载项目测试 skill（参见 `steering/testing.md`）获取完整模式和代码示例。**

## 任务规范

**编号**: 顶层 `N.`，子任务 `N.M`。检查点加粗。

**文件路径**: 每个实现子任务必须指定精确文件路径。

**需求追踪**: 每个任务通过 `_需求: X.Y_` 链接到需求文档。

**复用标记**: 复用现有组件时标注 `(复用: ComponentName)`。

**属性测试引用**: 测试任务引用设计文档中的正确性属性。

**检查点**: 放在逻辑边界处（如 "schema 就绪"、"组件完成"、"集成完成"）。每个检查点包含完整的验证 + 审查 + loop-fix 循环。

**依赖顺序**: schemas → mocks → hooks → 组件 → 集成 → E2E → 验证。

**内联测试**: 测试任务紧跟对应的实现任务，不分离到独立阶段。
