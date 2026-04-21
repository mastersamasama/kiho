# Discovery Protocol — 动态项目环境探测

## 目的

/kiro 不假设任何特定项目、技术栈或技能集。本协议定义运行时如何自动探测项目环境，取代硬编码配置。

所有 Discovery 结果在首次探测后缓存于会话上下文中，后续步骤直接引用——无需重复探测。

---

## 1. Steering Discovery — 项目上下文探测

### 扫描规则

1. 列出 `.kiro/steering/` 目录下所有 `.md` 文件
2. 按文件名 + 首段内容启发式分类：

| 文件名模式 | 内容关键词 | 分类 | 用途 |
|-----------|-----------|------|------|
| `product*` | 产品、业务、用户、角色、愿景 | 产品上下文 | 业务规则、用户角色、数据模型 |
| `tech*`, `stack*` | 技术栈、版本、已批准、框架 | 技术栈定义 | 已批准技术和版本 |
| `coding*`, `rules*`, `conventions*` | 命名、约定、提交、格式 | 编码规则 | 命名约定、代码风格、提交标准 |
| `arch*`, `system*` | 架构、模块、边界、层 | 系统架构 | 系统架构、模块边界 |
| `test*` | 测试、覆盖率、断言、mock | 测试标准 | 测试模型、覆盖率目标、强制规则 |
| `security*`, `auth*` | 安全、认证、授权、加密 | 安全约束 | 安全需求和约束 |
| `frontend*`, `ui*`, `component*` | 组件、样式、响应式、主题 | 前端模式 | 组件和样式约定 |
| `structure*`, `project*` | 目录、文件、布局、组织 | 项目结构 | 目录布局、命名约定 |
| `backend*`, `api*`, `server*` | 路由、服务、数据库、中间件 | 后端模式 | API 和服务层约定 |
| 其他 | — | 补充文档 | 按内容判断 |

### 优先识别 Kiro 官方三文件

Kiro IDE 自动生成的标准 steering 文件：
- `product.md` — 产品愿景、功能、目标用户
- `tech.md` — 技术栈、框架、工具约束
- `structure.md` — 目录布局、命名约定、架构决策

如存在，优先加载这三个文件。

### 按功能范围加载

- **前端任务** → 加载：前端模式 + 产品上下文 + 编码规则 + 技术栈
- **后端任务** → 加载：后端模式 + 安全约束 + 编码规则 + 技术栈
- **全栈任务** → 加载所有已发现的 steering 文档

### Fallback

如果 `.kiro/steering/` 不存在或为空：

1. **扫描项目根目录** — 查找 `CLAUDE.md`、`AGENTS.md`、`README.md`、`package.json` 等推断项目上下文
2. **提问用户** — "未发现 `.kiro/steering/` 目录。请问：(a) 项目的核心技术栈是什么？(b) 是否有编码约定需要遵循？(c) 是否需要我帮你初始化 steering 文档？"

---

## 2. Tech Stack Discovery — 技术栈与命令探测

### 推断链（按优先级）

**优先级 1：Steering 文档中的明确定义**
读取已发现的"技术栈定义"类 steering 文档，提取：
- 包管理器及运行命令
- 类型检查命令
- Lint 命令
- 测试命令及框架
- 构建命令
- 验证库（如 Zod, Valibot, Yup 等）

**优先级 2：package.json scripts 字段**
如 steering 未明确定义命令，检查 `package.json`（根目录及 workspaces）的 `scripts` 字段：
- `typecheck` / `type-check` / `tsc` → 类型检查命令
- `lint` → lint 命令
- `test` → 测试命令
- `build` → 构建命令

**优先级 3：Lockfile 类型推断包管理器**

| 文件 | 包管理器 | 运行命令前缀 |
|------|---------|-------------|
| `bun.lockb` / `bun.lock` | bun | `bun run` |
| `pnpm-lock.yaml` | pnpm | `pnpm run` |
| `yarn.lock` | yarn | `yarn` |
| `package-lock.json` | npm | `npm run` |
| `Cargo.toml` + `Cargo.lock` | cargo | `cargo` |
| `pyproject.toml` + (`poetry.lock` / `uv.lock`) | poetry/uv | `poetry run` / `uv run` |
| `go.mod` | go modules | `go` |
| `Gemfile.lock` | bundler | `bundle exec` |

**优先级 4：提问用户**
如以上均无法推断："无法自动检测项目命令。请提供：(a) 类型检查命令 (b) Lint 命令 (c) 测试命令"

### 确认协议

首次推断完成后，向用户呈现确认：

> **项目环境探测结果：**
> - 包管理器: [检测到的]
> - 类型检查: `[命令]`
> - Lint: `[命令]`
> - 测试: `[命令]`
> - 验证库: [检测到的]
>
> 以上是否正确？如需调整请指出。

用户确认后，后续所有步骤中的"运行类型检查/lint/测试"均使用这些命令。

---

## 3. Skill Discovery — 可用技能探测

### 扫描方式

运行时扫描当前会话中所有可用的 skill，按领域分类：

| 领域 | 匹配关键词 | 用途 |
|------|-----------|------|
| 前端开发 | `frontend`, `前端`, `ui`, `component` | 组件模式、主题、响应式 |
| 后端开发 | `backend`, `后端`, `api`, `server` | 路由模式、服务层、数据库 |
| 代码审查 | `review`, `审查`, `code-review` | 增量审查 + loop-fix |
| 测试 | `test`, `测试`, `quality` | 测试模式、覆盖率 |

### Fallback 策略

如果某领域无专用 skill：

- **前端/后端开发**: 使用 steering 文档中的编码规则和模式约定指导实现
- **代码审查**: 使用内置审查协议（见 SKILL.md "内置审查协议"节）
- **测试**: 使用 steering 中的测试标准 + SKILL.md 内的测试类型决策树

### 呈现给用户

> **已发现的专用技能：**
> - 前端: [skill 名 或 "无，将使用 steering 指导"]
> - 后端: [skill 名 或 "无，将使用 steering 指导"]
> - 审查: [skill 名 或 "无，将使用内置审查协议"]
> - 测试: [skill 名 或 "无，将使用 steering + 决策树"]

---

## 4. Project Identity Discovery — 项目身份探测

### 构建流程

1. 从产品 steering（product.md 或同类文件）第一段提取项目名称和简述
2. 如无产品 steering → 从 `package.json` 的 `name` 字段推断
3. 如无 package.json → 从仓库名（git remote）推断
4. 如均无 → 使用"此项目"

项目身份仅用于规格文档中的上下文描述，不影响技术流程。

---

## 探测执行时机

所有 Discovery 在 SKILL.md **第一步（上下文加载）** 的 1a 子步骤中一次性执行：

```
1a. 项目环境探测
    ├── Steering Discovery → 分类加载 steering 文档
    ├── Tech Stack Discovery → 推断项目命令
    ├── Skill Discovery → 扫描可用技能
    └── Project Identity → 提取项目名称
    ↓
    呈现探测结果 → 用户确认 → 缓存到会话上下文
```

后续所有步骤中引用"项目命令"、"前端 skill"、"审查 skill"等，均指此处探测并确认的结果。
