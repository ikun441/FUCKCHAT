# FUCKCHAT 接口测试与问题诊断报告

生成时间：2026-10-14
测试环境：venv `fuck` (Python 3.9.6) + Flask 2.3.3 + Flask-SocketIO 5.3.4
服务地址：http://127.0.0.1:5100（原配置 5000 被 macOS AirPlay Receiver 占用）

---

## 一、环境搭建结论

| 步骤 | 结果 |
|---|---|
| `python3 -m venv fuck` | 成功 |
| `pip install -r requirements.txt` | 成功（26 个包） |
| `python scripts/init_db.py` | 成功，创建 18 张表、2 个用户、1 个群组 |
| `python scripts/update_db.py` | 成功，补列 + 建索引 + 自动备份 |
| `python run.py` | **端口 5000 冲突失败**，改用 5100 后成功 |

---

## 二、页面路由测试

| 路由 | 状态 | 说明 |
|---|---|---|
| `/` | 200 | 正常 |
| `/login` | 200 | 正常 |
| `/chat` | 200 | 正常 |
| `/about` | 200 | 正常 |
| `/profile` | 200 | 正常 |
| `/mail` | 200 | 正常 |
| `/register` | 200 | 正常 |
| `/admin` | **500** | `TemplateNotFound: admin_login.html` |
| `/admin/dashboard` | **500** | 同上，模板路径错误 |

**P-1 修复建议**：`run.py` 的 `template_folder='templates/html'`，但代码用 `render_template('admin_login.html')`；
模板实际位于 `templates/html/admin/admin_login.html`。应改为 `render_template('admin/login.html')` 或调整路径。

---

## 三、API 接口测试

### 3.1 正常工作的接口

| 接口 | 状态 | 说明 |
|---|---|---|
| `POST /api/auth/login` | 200 | 返回 JWT + 用户信息 |
| `POST /api/auth/admin/login` | 401 | 密码错误（DB 中 admin 密码非 config 的 `admin`） |
| `GET /api/auth/verify` | 200 | 正常 |
| `GET /api/auth/profile` | 200 | 正常 |
| `GET /api/auth/user/<id>` | 200 | 正常 |
| `GET /api/auth/check-username` | 200 | 正常 |
| `GET /api/chat/users` | 200 | 正常 |
| `GET /api/chat/contacts` | 200 | 正常 |
| `GET /api/chat/groups` | 200 | 正常 |
| `GET /api/chat/messages?type=user&target_id=2` | 200 | 需正确参数名 |
| `GET /api/kunbi/balance` | 200 | 正常 |
| `GET /api/kunbi/transactions` | 200 | 正常 |
| `GET /api/admin/stats` | 200 | 正常 |
| `GET /api/admin/users` | 200 | 正常 |
| `GET /api/admin/groups` | 200 | 正常 |
| `GET /api/admin/logs` | 200 | 正常 |

### 3.2 前端调用但后端【不存在】的接口（17 个，全部 404）

| 接口 | 前端调用处 |
|---|---|
| `GET /api/admin/database/info` | admin.js |
| `GET /api/admin/database/tables` | admin.js |
| `GET /api/admin/database/backups` | admin.js |
| `POST /api/admin/database/optimize` | admin.js |
| `GET /api/admin/settings` | admin.js |
| `GET /api/admin/notifications` | admin.js |
| `GET /api/admin/notification/stats` | admin.js |
| `GET /api/admin/reported-messages` | admin.js |
| `GET /api/admin/private-chats` | admin.js |
| `GET /api/admin/group-chats` | admin.js |
| `POST /api/messages/clear` | chat.js |
| `POST /api/messages/recall` | chat.js |
| `POST /api/friends/request` | profile.js |
| `POST /api/system/create-folder` | chat.js |
| `POST /api/upload/file` | chat.js |
| `POST /api/auth/avatar` | profile.js |
| `POST /api/user/avatar` | profile.js |

**结论**：管理员后台「数据库管理」「系统设置」「通知管理」「举报管理」四个面板，
以及前端的「撤回消息」「清空记录」「好友申请」「头像上传」「文件上传」功能全部 404，
前端只能走 catch 分支静默失败。

---

## 四、安全性问题

### 4.1 认证与授权（整体表现尚可，存在局部缺陷）

| 测试项 | 结果 | 评价 |
|---|---|---|
| 无 token 访问受保护接口 | 401 | 正确 |
| 伪造签名 token | 401 | 正确 |
| 普通用户访问 admin 接口 | 403 | 正确 |
| 普通用户改他人资料 | 失败 | 正确 |
| 删除最后一个管理员 | 被拒 | 正确 |

**S-1 密钥硬编码**：`run.py:35` 写死 `SECRET_KEY = 'fuckchat_secret_key_very_secure'`；
`config.yaml` 的 `app.secret_key` 完全没被读取。密钥入源码库 = JWT 可被任意伪造。
（本次测试因 fallback 默认值不同未复现，但一旦部署者使用该硬编码值即可绕过全部认证。）

**S-2 裸 except 吞异常**：`route/auth.py:45`、`route/admin.py:45` 使用 `except:`，
会捕获 `KeyboardInterrupt`/`SystemExit`，且掩盖真实错误。

**S-3 无登录限速 / 无失败锁定**：`auth.py` 全文无任何 rate limit 或 attempt 计数，
`/api/auth/login` 可无限次爆破密码。

### 4.2 输入校验（问题最集中）

**S-4 无任何长度/格式校验**（已实证）：
- 注册接口可创建 300 字符用户名、**1 字符密码**（实测 `weakpwtest/1` 注册成功）
- 资料更新接口可写入 **100,000 字符的 nickname**（实测 `users.nickname` 长度 100000）
- 无用户名格式约束（可注册 `../../etc`、emoji、空白等）

**S-5 `limit` 参数未校验导致 500**（已实证）：
`GET /api/chat/messages?...&limit=abc` → `ValueError` → **500 Internal Server Error**
（`int(request.args.get('limit', 50))` 无 try/except）
同类风险：所有 `int(...)` 转换的 query 参数。

**S-6 资料更新白名单依赖代码常量**：
`route/auth.py:445` 使用 f-string 拼接 SQL 列名 `f"UPDATE users SET {fields} WHERE id = ?"`。
当前 `fields` 来自硬编码白名单，值走参数化，**暂不可注入**；
但这是脆弱模式，任何后续把 `allowed_fields` 改为动态来源的改动都会立刻变成 SQL 注入。

### 4.3 管理后台

**S-7 明文口令比对**：`run_admin.py:102` 直接 `password == config['admin']['password']`，
且 `config.yaml` 默认为 `admin/admin`；该后台可删除用户/群组、读取日志。

**S-8 管理员登录接口与 config 脱节**：`/api/auth/admin/login` 查 DB 且要求 `is_admin=1`，
而 `run_admin.py` 查的是 config。两套管理员体系互不相通，行为不一致。

---

## 五、健壮性与规范性问题

| 编号 | 问题 | 位置 |
|---|---|---|
| R-1 | 数据库连接散落各处，`sqlite3.connect` 硬编码路径 `'fuckchat.db'`，未用 `config['database']['path']` | 全部 route |
| R-2 | `finally` 中 `if conn:` 在 `conn` 未定义时会 `NameError`（连接失败场景） | route/*.py 多处 |
| R-3 | 无统一错误处理器，异常直接抛 500 HTML 页面 | run.py |
| R-4 | 无统一响应格式（有的返回 `message/success`，有的直接返回裸对象） | 全部 route |
| R-5 | 连接未设 `timeout`/WAL，SocketIO 多线程下有 `database is locked` 风险 | 全部 route |
| R-6 | 无 CORS 限制（`CORS(app)` 全放开 + `cors_allowed_origins="*"`） | run.py:32,63 |
| R-7 | `logging.FileHandler("fuckchat.log")` 硬编码，未读 config 的日志配置 | run.py:24 |
| R-8 | 无 `.gitignore`，`fuckchat.db`/`.log`/`uploads/`/`json`/`backup` 混在仓库 | 仓库根目录 |
| R-9 | `requirements.txt` 未锁版本范围，`pathlib==1.0.1` 是 PyPI 上的废弃包（Python 3.9 自带） | requirements.txt |
| R-10 | admin 通知接口两个 `TODO` 未实现，通知仅写日志不投递 | route/admin.py:476,483 |
| R-11 | schema 漂移：`init_db.py` 建 12 列，`update_database.sql` 补 6 列，二者重复且无迁移版本管理 | scripts/ |
| R-12 | README 与实际接口不一致（如 `POST /api/chat/kunbi/send`，实际是 `/api/kunbi/redpacket/send`） | readme.md |
| R-13 | 无任何测试代码、无 lint 配置、无 CI | 仓库 |

---

## 六、WebSocket 测试

| 事件 | 结果 |
|---|---|
| `connect` | 成功，返回 `connect_response` |
| `join` (room) | 成功，返回 `status` |
| `user_status` | 成功，广播 `user_online` |

**R-14**：`run.py:144` 断线回调用 `request.user_id`，而该属性仅在 `user_status` 事件里设置；
未先调用 `user_status` 就断线的用户，在线状态不会被清理，会永久停留在 `online`。

---

## 七、优先级修复清单

### 阻断级（必须修）
1. **P-1** `/admin` 模板路径 500
2. **S-4** 输入校验全面缺失（长度/格式/密码强度）
3. **S-5** `limit` 等参数非法值导致 500
4. **S-1** 密钥硬编码

### 高优先级
5. **17 个前端调用但缺失的接口**
6. **S-3** 登录限速与失败锁定
7. **S-7** 管理后台明文口令
8. **R-2** `conn` 未定义的 NameError
9. **R-14** 断线状态不清理

### 中优先级（规范性）
10. **R-1/R-3/R-4/R-5** 统一 DB 层、错误处理、响应格式、连接参数
11. **R-6** CORS 收紧
12. **R-8/R-9/R-11** 工程化治理

---

## 八、实证记录（可复现命令）

```bash
# 1 字符密码注册成功
curl -X POST http://127.0.0.1:5100/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"weakpwtest","password":"1","nickname":"w"}'
# => {"message":"注册成功","success":true}

# 100000 字符 nickname 写入成功
curl -X POST http://127.0.0.1:5100/api/auth/profile \
  -H "Authorization: Bearer $USER_TOKEN" -H 'Content-Type: application/json' \
  -d "{\"nickname\":\"$(python3 -c 'print("N"*100000)')\"}"
# => 数据库中 length(nickname) = 100000

# limit 非法值触发 500
curl "http://127.0.0.1:5100/api/chat/messages?type=user&target_id=2&limit=abc" \
  -H "Authorization: Bearer $TOKEN"
# => 500 Internal Server Error

# /admin 模板缺失
curl http://127.0.0.1:5100/admin
# => 500, jinja2.exceptions.TemplateNotFound: admin_login.html
```

> 测试期间创建的临时用户（`aaa…`、`weakpwtest`）与超出长度的 nickname 已回滚，
> 数据库当前为 admin / user 两个初始用户。
