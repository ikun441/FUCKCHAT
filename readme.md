# FUCKCHAT - 局域网聊天应用

FUCKCHAT 是一个基于 Python 和 Web 技术开发的局域网聊天应用，支持私聊、群聊、表情、图片、语音消息以及坤币红包等功能。

> **当前版本：v2.0.0（后端重构版）**
> 本次为大版本重构，重点提升安全性、规范性与健壮性。
> 完整的重构说明、问题修复对照与接口清单见下方 [v2.0.0 重构说明](#v200-重构说明)。

---

## 功能特点

- 🔒 **局域网安全通信**：数据仅在局域网内传输，保障通信安全性
- 👤 **用户管理**：支持注册、登录、管理个人信息
- 💬 **实时聊天**：支持一对一私聊和多人群聊
- 🌈 **多媒体消息**：支持发送文本、表情、图片、语音等消息类型
- 🧧 **坤币红包**：内置虚拟货币系统，可发送红包增加互动乐趣
- 📱 **响应式设计**：适配电脑和手机等不同尺寸的设备
- 👮 **管理员后台**：提供系统管理、用户管理、聊天管理等功能
- ✨ **动画效果**：丰富的界面动画，提升用户体验
- 🛡️ **安全加固**：输入校验、登录限速、失败锁定、统一错误处理（v2.0.0 新增）

## 技术栈

- **前端**：HTML, CSS, JavaScript, 动画效果
- **后端**：Python, Flask, Flask-SocketIO（应用工厂 + 蓝图架构）
- **数据库**：SQLite（WAL 模式 + 连接池化管理）
- **通信**：WebSocket, HTTP
- **安全**：JWT (HS256) + bcrypt(rounds=12) + 限速与失败锁定

---

## 快速开始

### 环境要求

- Python 3.8+
- 网络浏览器（推荐 Chrome, Firefox, Edge 等现代浏览器）

### 1. 创建虚拟环境

```bash
python3 -m venv fuck
source fuck/bin/activate          # macOS / Linux
# fuck\Scripts\activate.bat       # Windows
```

使用 Conda 也可以：

```bash
conda create -n fuckchat python=3.9
conda activate fuckchat
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python scripts/init_db.py       # 建基础表 + 初始数据（admin / user）
python scripts/migrate_db.py    # 补齐全部业务表、字段与索引
```

> 这两步是**幂等**的，可以安全重复执行。
> `migrate_db.py` 会自动把数据库备份到 `backups/` 目录后再迁移，
> 并且会补齐 `init_db.py` 未覆盖的表（notifications / friends / mail 等 10 张）。
> 执行完共 17 张表，无需再手工运行旧的 `update_db.py`。

### 4. 启动服务

```bash
# 主服务（默认 http://localhost:5000）
python run.py

# 指定端口启动（macOS 上 5000 常被 AirPlay 占用）
python run.py --port 5100

# 独立管理员后台（默认 http://127.0.0.1:5004/admin）
python run_admin.py
python run_admin.py --daemon     # 后台守护进程模式（仅 Unix）
start_admin.bat                  # Windows 批处理启动
```

### 5. 测试用户

| 角色 | 用户名 | 密码 |
|---|---|---|
| 管理员 | `admin` | `admin123` |
| 普通用户 | `user` | `user123` |

> 独立管理后台（5004 端口）可直接使用上述管理员账号登录，也可在 `config.yaml` 的 `admin` 段配置独立口令。

---

## v2.0.0 重构说明

本次重构以前端接口契约为准，对后端做了系统性重建。核心动机来自一次全量接口测试：**测试发现 17 个前端调用但后端不存在的接口，以及多处输入校验缺失导致的安全问题**。

### 一、架构重构

原先 `run.py` 混杂了配置、日志、路由注册、WebSocket 事件等职责，且各路由文件重复实现数据库连接与错误处理。现改为分层架构：

```
app/
├── __init__.py          # 包入口，暴露 create_app
├── factory.py           # 应用工厂：装配配置/日志/DB/蓝图/页面路由
├── config.py            # 配置加载、深度合并、环境变量覆盖、密钥解析
├── database.py          # 数据访问层：连接复用、事务、WAL
├── validators.py        # 统一输入校验
├── security.py          # JWT、密码哈希、限速、认证装饰器
├── responses.py         # 统一响应格式与业务异常
├── errors.py            # 全局错误处理
├── logging_config.py    # 日志配置（轮转）
├── socket_events.py     # WebSocket 事件
└── routes/
    ├── auth.py          # 认证
    ├── chat.py          # 聊天
    ├── kunbi.py         # 坤币与红包
    ├── admin.py         # 管理后台
    ├── files.py         # 文件上传
    └── misc.py          # 好友/通知/消息管理
```

原有的 `route/` 目录已被 `app/routes/` 取代并移除。

### 二、安全性修复

| 编号 | 原问题 | 修复方式 |
|---|---|---|
| S-1 | `run.py` 硬编码 `SECRET_KEY = 'fuckchat_secret_key_very_secure'`，`config.yaml` 的密钥从未生效 | 密钥解析优先级：环境变量 `FUCKCHAT_SECRET_KEY` > 配置文件 > 本地 `.secret_key` 文件（自动生成、权限 600、已 gitignore） |
| S-2 | `auth.py`/`admin.py` 使用裸 `except:`，吞掉所有异常 | 明确区分 `ExpiredSignatureError` / `InvalidTokenError`，分别返回对应错误码 |
| S-3 | 登录接口无任何限速与失败锁定，可无限爆破 | 新增 `RateLimiter`，按「用户名 + IP」维度计数，连续失败 5 次锁定 300 秒；所有敏感接口（注册/登录/转账/上传等）均加限速 |
| S-4 | **无任何长度与格式校验**：实测可注册 1 字符密码、300 字符用户名，可写入 100000 字符昵称 | `validators.py` 统一校验：密码 ≥8 位且含字母数字、用户名 3–32 位且格式受限、昵称 ≤32 字符、消息 ≤1000 字符，并对所有文本做 HTML 标签清洗 |
| S-5 | `int(request.args.get('limit'))` 遇非法值直接抛 500 | `validate_int()` 统一转换，非法值返回 400 并说明原因；分页参数带上限保护 |
| S-6 | 资料更新用 f-string 拼接 SQL 列名 | 保留白名单常量的同时，显式过滤列名并全部参数化，消除拼接模式 |
| S-7 | `run_admin.py` 明文比对配置口令，默认 `admin/admin` | 改为 bcrypt 哈希 + 常量时间比对；支持数据库管理员账号登录；配置口令留空则关闭该入口 |
| S-8 | 管理员登录接口查数据库、独立后台查配置，两套体系互不相通 | 统一支持两种来源，独立后台也可用数据库管理员账号登录 |
| S-9 | WebSocket 私聊/房间消息直接透传客户端传入的 `sender`，可伪造身份 | 发送者一律取自服务端会话映射，客户端传入的 `sender` 被忽略 |
| S-10 | CORS 全放开（`CORS(app)` + `cors_allowed_origins="*"`） | 改为白名单配置 `server.cors_origins`，默认留空即不启用跨域 |
| S-11 | 文件上传无扩展名校验、无文件名重写 | 扩展名白名单 + 服务端生成随机文件名，杜绝路径穿越与覆盖 |

### 三、健壮性修复

| 编号 | 原问题 | 修复方式 |
|---|---|---|
| R-1 | `sqlite3.connect('fuckchat.db')` 硬编码散落在每个函数 | 统一 `database.py`，路径读配置，支持 WAL 与 `busy_timeout` |
| R-2 | `finally` 中 `if conn:` 在连接失败时抛 `NameError` | 改用请求级连接与上下文管理器，自动关闭 |
| R-3 | 无统一错误处理，异常返回 HTML 500 页面 | `errors.py` 全局接管，所有 API 错误返回结构化 JSON |
| R-4 | 各接口响应格式不一致 | 统一为 `{success, message, data}`，分页统一 `{items, pagination}` |
| R-5 | SocketIO 多线程下有 `database is locked` 风险 | 启用 WAL + `busy_timeout=5000` + 写事务 `BEGIN IMMEDIATE` |
| R-6 | 日志硬编码 `FileHandler("fuckchat.log")` | 读配置，支持大小轮转与保留数量 |
| R-7 | 管理后台的统计/用户/群组/日志接口返回**硬编码假数据**（"用户1..用户10"），删除用户只写日志不真删 | `run_admin.py` 全部改为真实数据库查询与真实删除 |
| R-8 | 通知接口两个 `TODO` 未实现，通知只写日志从不投递 | 写入 `notifications` 表并通过 WebSocket 实时推送 |
| R-9 | 断线时用 `request.user_id` 清理在线状态，该属性在断线回调不可靠，导致用户永久显示在线 | 维护 `sid -> user_id` 映射，支持多设备登录，仅当所有连接断开才置为离线 |
| R-10 | README 接口路径与实际不符 | README 已按实际路由更新 |
| R-11 | `init_db.py` 与 `update_database.sql` 重复且无版本管理，SQL 按分号切分会误伤语句 | 新增 `scripts/migrate_db.py`，幂等迁移 + 迁移前自动备份 |
| R-12 | `requirements.txt` 含废弃包 `pathlib==1.0.1` 与未使用的 `eventlet` | 已移除，并锁定兼容版本区间 |
| R-13 | 无 `.gitignore`，数据库、日志、上传内容混入版本库 | 新增 `.gitignore`，排除数据库/日志/备份/上传/密钥 |

### 四、接口修复与补齐

**修复的既有接口问题：**

| 接口 | 原问题 | 现状 |
|---|---|---|
| `/admin`、`/admin/dashboard` | 模板路径错误，**返回 500** | 已修复，正常返回 200 |
| `GET /api/chat/messages` | `limit=abc` 触发 **500** | 返回 400 并提示参数错误 |
| `GET /api/chat/history` | 只认 `type`/`target_id`，前端传 `chat_id` 必然 **400** | 同时支持 `chat_id=user_2` 与 `group_1` 两种写法 |
| `POST /api/chat/messages` | 前端调用但**不存在** | 已实现，作为 WebSocket 的 HTTP 回退通道 |
| `POST /api/chat/history` | 存在但契约不清 | 明确 `{chat_id, messages}` 结构，服务端校验发送者归属 |

**补齐的 17 个缺失接口（原先全部 404）：**

*管理后台：*
- `GET /api/admin/database/info` — 数据库信息
- `GET /api/admin/database/tables` — 表清单与行数
- `GET /api/admin/database/backups` — 备份列表
- `POST /api/admin/database/optimize` — VACUUM/ANALYZE
- `POST /api/admin/database/backup` — 创建备份（自动清理旧备份）
- `GET /api/admin/settings` — 系统设置（**密钥字段脱敏**）
- `GET /api/admin/notifications` — 通知列表
- `GET /api/admin/notification/stats` — 通知统计
- `GET /api/admin/reported-messages` — 举报消息
- `GET /api/admin/private-chats` — 私聊概览
- `GET /api/admin/group-chats` — 群聊概览

*用户侧：*
- `POST /api/messages/recall` — 撤回消息（限 2 分钟内）
- `POST /api/messages/clear` — 清空会话
- `POST /api/messages/report` — 举报消息
- `POST /api/messages/forward` — 转发消息
- `GET /api/messages/search` — 搜索消息（仅自己可见范围）
- `POST /api/friends/request` — 好友申请
- `GET /api/friends` — 好友列表
- `GET /api/friends/requests` — 收到的申请
- `POST /api/friends/respond` — 处理申请
- `GET /api/notifications` — 我的通知
- `POST /api/notifications/read` — 标记已读
- `POST /api/system/create-folder` — 创建用户目录（防路径穿越）
- `POST /api/upload/file` `/image` `/voice` `/avatar` `/json` — 文件上传
- `POST /api/user/avatar`、`POST /api/auth/avatar` — 头像上传（兼容前端既有调用）
- `GET /api/health` — 健康检查

### 五、业务正确性修复

**坤币金额一致性**
- 所有余额变动置于单事务，扣款使用条件更新 `UPDATE users SET kunbi = kunbi - ? WHERE id = ? AND kunbi >= ?`，从数据库层面杜绝并发双花与负余额。
- 转出与转入各记一条流水，便于双方各自查询。

**红包算法重写**
- 原实现按「剩余平均值 ×2」随机，最后一人可能拿到 0 或超出剩余金额。
- 现改为服务端**一次性预分配**：每份预留 1 坤币，余量随机分配后打乱，保证「每份 ≥1」且「总和精确等于总额」。
- 已通过全量枚举验证：`total ∈ [1, 10000]`、`count ∈ [1, min(total,100)]` 全部满足约束。

**并发抢红包竞态修复**
- 测试中发现：同一用户并发发起多个领取请求时，多个请求都能通过事务外的「是否已领取」查重，导致**一人抢到多份**（实测 16 并发下 3 人抢到 5 份，其中一人拿到 3 份）。
- 修复：把查重移入写事务，并使用 `BEGIN IMMEDIATE` 立即获取写锁，使「查重 + 抢占份额」整体互斥。
- 修复后回归：3 个用户 × 6 并发 = 18 请求，**恰好 3 次成功、15 次正确拒绝**，每人各得 1 份。

### 六、前端适配

后端统一响应格式后，前端 JS 需相应调整取值路径。本次已完成全部适配：

| 文件 | 改动 |
|---|---|
| `common.js` | 新增 `unwrapResponse()` 与 `apiFetch()`，统一解包 `data` 字段 |
| `login.js` | 登录成功后从 `data.token` / `data.user` 取值 |
| `register.js` | 注册与用户名查重改用解包结果 |
| `chat.js` | 12 处接口调用改为从 `data.*` 取值（用户/联系人/群组/记录/上传等） |
| `admin.js` | 20 处调用改为解包取值；补齐缺失的 `renderGroupsTable()` 与 `deleteGroup()` |
| `profile.js` | 资料更新、改密、注销、头像上传改用解包结果 |
| `admin_login.js` | 兼容独立后台（扁平结构）与主服务（`data` 结构）两种响应 |

同时修复了后端字段命名与前端期望不一致的问题（`stats.user_count`、
`created_at`、`data.reports`、`data.messages`、`data.backups` 等）。

### 七、测试与验证

新增 `scripts/test_api.py` 回归测试脚本，覆盖重构前诊断出的全部问题：

```bash
python scripts/test_api.py --url http://127.0.0.1:5100          # 接口回归（93 项）
python scripts/audit_contract.py --url http://127.0.0.1:5100    # 前后端字段契约审计（45 项）
python scripts/test_integration.py --url http://127.0.0.1:5100  # 前后端连通性（61 项）
```

**测试结果：三个套件共 199 项全部通过**

覆盖范围：
1. 健康检查与页面路由（含原 500 的 `/admin` 修复验证）
2. 认证与授权（无令牌 401、伪造令牌 401、越权 403）
3. 输入校验（弱密码、超长用户名、超长昵称、非法邮箱均被拒）
4. 参数健壮性（非法 `limit`/`target_id`/`type` 返回 400 而非 500）
5. 补齐接口可用性（原 404 的接口全部 200）
6. 安全设置（密钥不泄漏、路径穿越被拒）
7. 业务功能（余额、流水、转账、余额不足拦截、余额精确扣减）
8. 响应格式一致性（含 404/401 返回 JSON 而非 HTML）
9. 前端兼容层（v1 扁平字段与 v2 `data` 嵌套的双向可用性、保留键不被覆盖）

另有两个专项脚本：

- `scripts/audit_contract.py`（45 项）：把前端 JS 实际消费的字段与后端真实返回逐一比对，
  用于发现「后端有数据但字段名对不上」的静默故障。
- `scripts/test_integration.py`（61 项）：复刻前端 `unwrapResponse` 解包逻辑，
  按 `login.js` / `chat.js` / `admin.js` 的真实取值路径验证连通性。

另有独立的 WebSocket 与并发领取验证：
- 断线后在线状态被正确清理（原缺陷为永久停留在线）
- 红包并发领取无重复、无超发

### 八、配置变更

新增配置项（均有默认值，旧配置可直接使用）：

```yaml
server:
  cors_origins: []          # CORS 白名单，默认不启用跨域
  legacy_response_aliases: true   # 顶层展开 data 字段，兼容 v1 前端

app:
  secret_key: ""            # 留空自动生成到 .secret_key
  token_ttl_hours: 24
  admin_token_ttl_hours: 12

security:
  password_min_length: 8
  username_min_length: 3
  username_max_length: 32
  nickname_max_length: 32
  login_max_attempts: 5         # 失败几次锁定
  login_lockout_seconds: 300    # 锁定时长
  rate_limit_window_seconds: 60
  rate_limit_max_requests: 120
  trust_proxy: false            # 有反向代理时才开启

chat:
  max_page_size: 100

database:
  timeout: 10.0
  backup_keep: 5

admin:
  password: ""              # 留空则关闭配置口令登录，改用数据库管理员账号
```

**密钥配置（重要）**：生产环境请通过环境变量注入，不要写进配置文件：

```bash
export FUCKCHAT_SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
```

### 九、破坏性变更

以下变更影响既有部署，升级前请留意：

1. **响应格式统一**：成功响应数据规整进 `data`，并统一带 `success`/`message`，
   例如 `{"success":true,"message":"登录成功","data":{"token":"...","user":{...}}}`。

   > **前端已完成适配**：`templates/js/*.js` 已全部改为通过 `data.*` 取值，
   > 由 `common.js` 提供的 `unwrapResponse()` / `apiFetch()` 统一解包。
   > 响应顶层仍保留一份展开字段作为过渡兼容，
   > 可通过 `server.legacy_response_aliases: false` 关闭。

2. **管理后台独立服务**：`run_admin.py` 的接口改为真实数据，不再返回模拟结构。
3. **`route/` 目录移除**：如需引用路由，请改从 `app.routes` 导入。
4. **数据库迁移**：升级后需运行 `python scripts/migrate_db.py`（会新增 `user_logs.detail`、`kunbi_transactions.packet_count` 等字段与索引）。
5. **加密方式**：新密码使用 bcrypt rounds=12（原为默认 12 轮，兼容）；已有账号密码无需重置。

### 十、升级步骤

```bash
git pull
source fuck/bin/activate
pip install -r requirements.txt
cp config.yaml config.yaml.bak          # 备份现有配置
python scripts/migrate_db.py            # 迁移（自动备份数据库）
python run.py --port 5100               # 启动验证
python scripts/test_api.py --url http://127.0.0.1:5100   # 回归测试
```

### 十一、已知待办

- 前端已迁移至 `data.*` 取值，响应顶层的兼容别名目前仅为过渡保留；
  确认无外部调用方依赖后，可将 `server.legacy_response_aliases` 置为 `false`
  并移除 `responses.py` 中的兼容分支。
- 限速器为进程内存实现，多进程/多机部署需要替换为 Redis。
- 管理后台的数据库备份/恢复尚未提供 Web 端恢复入口。
- 尚未引入自动化单元测试框架（当前为端到端脚本验证）。

---

## 目录结构

```
FUCKCHAT/
├── app/                    # 应用包（v2.0.0 新增）
│   ├── __init__.py         # create_app 入口
│   ├── factory.py          # 应用工厂
│   ├── config.py           # 配置管理
│   ├── database.py         # 数据访问层
│   ├── validators.py       # 输入校验
│   ├── security.py         # JWT/哈希/限速/装饰器
│   ├── responses.py        # 统一响应
│   ├── errors.py           # 全局错误处理
│   ├── logging_config.py   # 日志配置
│   ├── socket_events.py    # WebSocket 事件
│   └── routes/             # 路由蓝图
│       ├── auth.py         # 认证
│       ├── chat.py         # 聊天
│       ├── kunbi.py        # 坤币红包
│       ├── admin.py        # 管理接口
│       ├── files.py        # 文件上传
│       └── misc.py         # 好友/通知/消息
├── config.yaml             # 配置文件
├── .secret_key             # 自动生成的密钥（不入版本库）
├── .gitignore              # 忽略规则
├── fuckchat.db             # SQLite 数据库（不入版本库）
├── backups/                # 数据库备份
├── logs/                   # 日志目录
├── md/                     # 文档目录
│   ├── api.md              # API 文档
│   ├── diagnosis.md        # 接口测试与问题诊断报告
│   ├── usage.md            # 使用指南
│   └── version.md          # 版本历史
├── readme.md               # 项目说明
├── requirements.txt        # 依赖列表
├── run.py                  # 主服务入口
├── run_admin.py            # 管理后台入口
├── start_admin.bat         # Windows 启动脚本
├── scripts/                # 脚本目录
│   ├── init_db.py          # 数据库初始化
│   ├── migrate_db.py       # 数据库迁移（v2.0.0 新增）
│   ├── test_api.py         # 接口回归测试（v2.0.0 新增）
│   └── update_db.py        # 旧版更新脚本（保留兼容）
├── src/                    # 静态资源
│   └── images/             # 图片资源
├── uploads/                # 用户上传内容（不入版本库）
└── templates/              # 前端模板
    ├── css/                # CSS 样式
    ├── html/               # HTML 页面
    └── js/                 # JavaScript 脚本
```

---

## 贡献团队

项目由以下成员开发:

- ChatGPT - 架构设计师
- Claude - 全栈工程师
- Cursor - 前端开发
- ikun441 - 技术顾问

---

## 接口说明

### 认证接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 用户注册（带校验与限速） |
| POST | `/api/auth/login` | 用户登录（带失败锁定） |
| POST | `/api/auth/admin/login` | 管理员登录 |
| GET | `/api/auth/verify` | 验证令牌 |
| GET | `/api/auth/profile` | 获取当前用户信息 |
| POST | `/api/auth/profile` | 更新个人资料 |
| GET | `/api/auth/user/<id>` | 获取指定用户公开信息 |
| POST | `/api/auth/password` | 修改密码 |
| POST | `/api/auth/logout` | 退出登录 |
| POST | `/api/auth/account/delete` | 注销账号 |
| GET | `/api/auth/check-username` | 检查用户名可用性 |
| POST | `/api/auth/avatar` | 上传头像（兼容别名） |

### 聊天接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/chat/users` | 在线用户列表 |
| GET | `/api/chat/contacts` | 最近联系人 |
| GET | `/api/chat/groups` | 我的群组 |
| POST | `/api/chat/groups` | 创建群组 |
| GET | `/api/chat/groups/<id>/members` | 群成员列表 |
| POST | `/api/chat/groups/<id>/join` | 加入群组 |
| GET | `/api/chat/messages` | 获取聊天记录（`type` + `target_id`） |
| POST | `/api/chat/messages` | 发送消息（HTTP 回退通道） |
| DELETE | `/api/chat/messages/<id>` | 撤回消息 |
| GET | `/api/chat/history` | 按 `chat_id` 获取记录 |
| POST | `/api/chat/history` | 保存聊天记录 |
| DELETE | `/api/chat/conversations/<id>/messages` | 清空会话 |

### 坤币接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/kunbi/balance` | 查询余额 |
| GET | `/api/kunbi/transactions` | 坤币流水 |
| POST | `/api/kunbi/transfer` | 转账 |
| POST | `/api/kunbi/redpacket/send` | 发送单人红包 |
| POST | `/api/kunbi/redpacket/send_multi` | 发送拼手气红包 |
| POST | `/api/kunbi/redpacket/grab/<txid>` | 领取红包 |
| GET | `/api/kunbi/redpacket/<txid>` | 红包详情 |

### 消息与社交接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/messages/recall` | 撤回消息 |
| POST | `/api/messages/clear` | 清空会话 |
| POST | `/api/messages/report` | 举报消息 |
| POST | `/api/messages/forward` | 转发消息 |
| GET | `/api/messages/search` | 搜索消息 |
| GET | `/api/friends` | 好友列表 |
| POST | `/api/friends/request` | 发送好友申请 |
| GET | `/api/friends/requests` | 收到的申请 |
| POST | `/api/friends/respond` | 处理申请 |
| GET | `/api/notifications` | 我的通知 |
| POST | `/api/notifications/read` | 标记已读 |
| POST | `/api/system/create-folder` | 创建用户目录 |

### 上传接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/upload/file` | 通用文件上传 |
| POST | `/api/upload/image` | 图片上传 |
| POST | `/api/upload/voice` | 语音上传 |
| POST | `/api/upload/avatar` | 头像上传 |
| POST | `/api/user/avatar` | 头像上传（兼容别名） |
| POST | `/api/upload/json` | JSON 文件上传 |

### 管理接口（需管理员令牌）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/stats` | 系统统计 |
| GET | `/api/admin/users` | 用户列表 |
| PUT | `/api/admin/users/<id>` | 更新用户 |
| DELETE | `/api/admin/users/<id>` | 删除用户 |
| GET | `/api/admin/groups` | 群组列表 |
| DELETE | `/api/admin/groups/<id>` | 删除群组 |
| GET | `/api/admin/logs` | 系统日志 |
| POST | `/api/admin/notification` | 发送系统通知 |
| GET | `/api/admin/notifications` | 通知列表 |
| GET | `/api/admin/notification/stats` | 通知统计 |
| GET | `/api/admin/reported-messages` | 举报消息 |
| GET | `/api/admin/private-chats` | 私聊概览 |
| GET | `/api/admin/group-chats` | 群聊概览 |
| GET | `/api/admin/database/info` | 数据库信息 |
| GET | `/api/admin/database/tables` | 表清单 |
| GET | `/api/admin/database/backups` | 备份列表 |
| POST | `/api/admin/database/backup` | 创建备份 |
| POST | `/api/admin/database/optimize` | 数据库优化 |
| GET | `/api/admin/settings` | 系统设置（密钥脱敏） |

### 系统接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |

> 完整 API 文档见 [md/api.md](md/api.md)，问题诊断报告见 [md/diagnosis.md](md/diagnosis.md)。

---

## WebSocket 事件

| 事件 | 方向 | 说明 |
|---|---|---|
| `connect` / `disconnect` | 双向 | 连接建立与断开（断线自动清理在线状态） |
| `user_status` | 客户端→服务端 | 上报在线状态，建立会话映射 |
| `request_all_statuses` | 客户端→服务端 | 请求所有在线用户状态 |
| `join` / `leave` | 客户端→服务端 | 加入/离开房间（含权限校验） |
| `message` | 双向 | 房间消息（发送者由服务端判定） |
| `private_message` | 双向 | 私聊消息（含黑名单校验） |
| `new_message` | 服务端→客户端 | 新消息推送 |
| `message_recalled` | 服务端→客户端 | 消息撤回通知 |
| `user_online` / `user_offline` | 服务端→客户端 | 用户状态变更 |
| `kunbi_redpacket` | 服务端→客户端 | 红包通知 |
| `system_notification` | 服务端→客户端 | 系统通知 |
| `typing` | 双向 | 正在输入 |
| `ping_server` / `pong` | 双向 | 心跳 |

---

## 贡献指南

欢迎贡献代码、提交问题和改进建议！

## 加入社群
![Uploading 微信图片_20261030190348_75_72.jpg…]()



## 许可证

MIT License

## 版本历史

完整的版本更新历史见 [md/version.md](md/version.md)。

## API 文档

完整的 API 接口文档见 [md/api.md](md/api.md)。

## 使用指南

详细的使用说明见 [md/usage.md](md/usage.md)，或者访问[我的博客](https://ilovefirefly.club)。
