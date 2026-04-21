# 需求文档

## 简介

[功能简述、在项目中的定位、关联的 PRD/TRD、主要服务的用户角色]

## 范围

**包含**: [本次实现范围内的功能点]
**不包含**: [明确排除的功能点，避免范围蔓延]
**依赖**: [需要先完成的前置工作或已有功能]

## 术语表

[定义需求中引用的每个 UI 元素、数据概念和领域术语。组件名用 PascalCase。每条定义一句话。]

- **Component_Name**: [定义 — 是什么、做什么]
- **Data_Concept**: [定义 — 代表什么]

## 需求

### 需求 1: [功能/行为名称]

<!-- 用户故事为可选。对于显而易见的功能可省略。 -->
**用户故事:** 作为 [用户类型]，我希望 [目标]，以便 [收益]。

#### 验收标准

[使用 EARS (Easy Approach to Requirements Syntax) 格式:]

**模式参考:**
- 普遍性: `THE [组件] SHALL [行为]`
- 事件驱动: `WHEN [触发], THE [组件] SHALL [行为]`
- 状态驱动: `WHILE [状态], THE [组件] SHALL [行为]`
- 条件性: `IF [条件], THEN THE [组件] SHALL [行为]`
- 可选: `WHERE [功能支持], THE [组件] SHALL [行为]`

1. THE Component SHALL [行为]
2. WHEN [触发], THE Component SHALL [行为]
3. IF [条件], THEN THE Component SHALL [行为]

### 需求 N: [继续...]

---

<!-- 以下两个 section 为可选。如果功能涉及用户交互界面，建议包含。
     对于纯后端、schema 变更、配置调整等可省略。 -->

### 需求 A（可选）: 无障碍与键盘导航

#### 验收标准

[基线项 + 功能特定的无障碍需求:]

1. THE [交互元素] SHALL 使用适当的 ARIA 角色以支持屏幕阅读器
2. THE [弹窗/面板] SHALL 支持键盘导航和焦点陷阱
3. THE [可关闭元素] SHALL 支持 Escape 键关闭
4. THE [交互元素] SHALL 具有描述性 aria-label 属性
5. THE [列表/信息流] SHALL 使用语义化 HTML 元素
6. WHEN 新内容动态加载时, THE [容器] SHALL 通过 live region 通知屏幕阅读器

### 需求 B（可选）: 加载与错误状态

#### 验收标准

1. THE [页面] SHALL 在初始加载时显示与布局结构匹配的骨架屏
2. IF 初始数据请求失败, THEN THE [页面] SHALL 显示全屏错误状态（含插图、消息、重试按钮）
3. WHEN 用户点击重试按钮, THE [页面] SHALL 重新发起数据请求
4. IF 次要操作失败, THEN THE [页面] SHALL 显示错误 toast 并保留之前的结果

---

_此文档由 /kiro 生成。需求编号（如 1.1, 1.2）将在 tasks.md 中用于追踪。_
