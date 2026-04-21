# 设计文档

## 概述

[技术方案概述。包括可复用的现有组件、需要新建的组件、关键架构模式（如 URL 状态管理、无限滚动、SSR）。]

[说明是否遵循 AI-Native Semantic Component Protocol (ANSCP)，如适用。]

## 架构

### 组件层级

```
FeaturePage (路由: /path)
├── ComponentA                    # [简述]
├── ComponentB                    # [简述，标注 "复用现有 X"]
├── [区域内容]
│   ├── SubComponentA             # [简述]
│   │   └── ItemComponent[]       # [简述]
│   └── FooterStates              # 加载 / 结束 / 错误 / 空状态
└── SharedComponent               # [复用现有组件]
```

### 数据流

```
[数据源] ──▶ [派生状态] ──▶ [服务端状态管理]
                  │                    │
                  ▼                    ▼
           [UI 控件]            [数据展示]
```

[描述数据流模式。例如："过滤状态存储在 URL search params 中，通过项目的路由库管理。确保 URL 可分享、浏览器前进/后退保留状态、单一数据源。"参照项目 steering 中的状态管理策略。]

### 状态管理策略

[哪些状态在 URL？哪些在组件本地状态？哪些在服务端缓存？参照项目 steering 中的状态管理策略。]

- **URL 状态**: 可分享/可导航的状态（过滤、分页、排序）
- **组件本地状态**: 临时 UI 状态（弹窗开关、hover 状态）
- **服务端缓存**: 通过项目的数据获取库管理

### 响应式策略

| 断点 | 布局变化 | 关键调整 |
|------|---------|---------|
| < 375px | [描述] | [字体、间距、隐藏元素] |
| 375-768px | [描述] | [默认移动端布局] |
| 768-1024px | [描述] | [平板适配] |
| > 1024px | [描述] | [桌面端布局] |

### 动画 Token

| 交互 | 动画类型 | 时长 | 缓动函数 |
|------|---------|------|---------|
| [如: 下拉展开] | [如: height + opacity] | [如: 200ms] | [如: ease-out] |
| [如: Tab 切换] | [如: transform slide] | [如: 150ms] | [如: ease-in-out] |
| [如: 列表项进入] | [如: fade-in + slide-up] | [如: 300ms] | [如: spring] |

## 组件与接口

### 1. ComponentName

**文件:** `[根据项目 structure.md 或代码库探测确定路径]/ComponentName.tsx`

[组件功能简述。]

```typescript
interface ComponentNameProps {
  propA: string;
  propB?: number;
  onAction: (value: string) => void;
  className?: string;
}
```

[行为说明、ARIA 角色、使用的动画 token 等。]

### 2. [继续...]

## 数据模型

### 数据验证 Schema

**文件:** `[根据项目结构确定 schema 文件路径]`

<!-- 以下示例使用 Valibot，实际使用项目 steering 指定的验证库（如 Zod, Valibot, Yup, io-ts 等） -->

```typescript
// 示例（Valibot）：
import * as v from 'valibot';

export const FeatureItemSchema = v.object({
  id: v.pipe(v.string(), v.uuid()),
  // 所有字段含验证约束
});

export type FeatureItem = v.InferOutput<typeof FeatureItemSchema>;
```

### API 响应格式

```typescript
// 列表响应
{
  success: true,
  data: FeatureItem[],
  meta: { page: number, limit: number, total: number, hasMore: boolean }
}

// 详情响应
{
  success: true,
  data: FeatureItem
}
```

## 错误处理

| 场景 | 用户看到 | 技术处理 |
|------|---------|---------|
| 网络超时 | [如: Toast "网络超时，请重试"] | [如: retry 3 次，exponential backoff] |
| API 400 | [如: 表单字段错误提示] | [如: 解析 error.details 映射到字段] |
| API 500 | [如: 全屏错误 + 重试按钮] | [如: Sentry 上报 + 用户可重试] |
| 数据为空 | [如: 空状态插图 + 引导文案] | [如: 检查 data.length === 0] |

## ANSCP 标注

<!-- 如果此功能包含 AI-native 页面，定义语义标注。否则删除此节。 -->

```typescript
const routeSemantic: RouteSemantic = {
  intent: ['user-intent-1', 'user-intent-2'],
  stateControl: { /* 可读/可写状态键 */ },
};

const componentSemantic: ComponentSemantic = {
  role: 'component-role',
  capabilities: ['read', 'write', 'highlight'],
};
```

## 决策记录

### 决策 1: [标题]

**背景**: [需要回答什么问题]
**考虑的方案**:
1. [方案 A] — [优劣]
2. [方案 B] — [优劣]

**决策**: [选择的方案]
**理由**: [为什么适合本项目]

### 决策 N: [继续...]

## 正确性属性

[定义实现必须满足的形式属性，用于指导属性测试。]

1. **属性: [名称]** — `forall [输入]. [条件] => [属性]`
   _验证: 需求 X.Y_

2. **属性: [名称]** — `[不变量声明]`
   _验证: 需求 X.Y_

## 文件结构

```
[根据项目 structure.md 或代码库探测确定路径结构]

示例：
src/
├── components/feature/
│   ├── ComponentA.tsx
│   ├── ComponentB.tsx
│   └── ...
├── hooks/
│   ├── useFeatureState.ts
│   └── useFeatureData.ts
└── routes/feature/
    └── route.tsx
```

## 测试策略

参照项目测试标准（`.kiro/steering/testing.md`），本功能的测试覆盖：

### 测试层级

| 层级 | 测试内容 | 工具（参照 steering） |
|------|---------|---------------------|
| Static | [类型检查 + Lint] | [steering/testing.md 指定] |
| Unit + Property | [列出需要测试的纯函数、Schema、安全函数] | [steering 指定] |
| Integration | [列出需要集成测试的组件/路由/Hook] | [steering 指定] |
| E2E | [仅关键用户旅程，如有] | [steering 指定] |

### 强制测试项（从 steering/testing.md 的强制规则推导）

- [ ] [列出此功能中触发强制测试的代码]
- [ ] [如：新增 Schema → property test]
- [ ] [如：新增 API 路由 → integration test]

### 属性测试（链接到正确性属性）

| 属性 | 描述 | runs | 验证需求 |
|-----|------|------|---------|
| 属性 1: [名称] | `forall [输入]. [条件] => [属性]` | [按 steering 规则] | 需求 X.Y |

### 覆盖率目标（从 steering/testing.md 引用受影响包的目标）

| 受影响包 | Line 目标 | Branch 目标 | 级别 |
|---------|----------|------------|-----|

### 测试计划

- **单元测试**: [列出需要单元测试的函数/工具]
- **组件/集成测试**: [列出需要集成测试的组件/Hook/路由]
- **E2E 测试**: [仅列出关键用户旅程（如适用）]

---

<!-- Bugfix 模式设计变体：以下 section 替代上方的完整设计。
     仅保留：概述、变更影响分析、修复方案、测试策略。

## Bugfix 设计变体

### 变更影响分析

| 文件 | 变更 | 影响范围 | 风险 |
|------|------|---------|------|
| `path/to/file.ts` | [变更描述] | [影响的其他文件/功能] | [低/中/高] |

### 修复方案

[技术修复策略，含代码级描述]

### 测试策略

- **探索测试**: [验证缺陷已修复]
- **保持测试**: [验证无回归]
- **既有测试**: [确认全部通过]
-->

---

_此文档由 /kiro 生成。组件接口和正确性属性将在 tasks.md 中引用。_
