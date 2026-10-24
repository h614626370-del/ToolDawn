# 支付、积分与语言

新版支持易支付、支付宝直连、微信 Native、Stripe 和 Airwallex。供应商配置、回调和接入边界见 [支付供应商接入](payment-providers.md)。

## 当前能力

- 账户 `/account/credits` 展示余额、积分流水和充值订单，流水与订单可分页。
- 管理后台 `/admin/orders` 查看订单；用户列表的钱包按钮查看余额和流水，按原因增加或扣减积分，禁止扣成负数。
- 积分余额与流水使用同一 PostgreSQL 事务；同一用户的写入通过用户行锁串行执行。管理员调整和创建订单均支持幂等键，同键不同内容拒绝执行。
- 订单创建时保存套餐、积分、金额与币种快照；只接受服务端配置中的套餐，不接受浏览器指定价格或积分。
- Stripe Checkout 托管支付。回调校验原始请求签名、时间窗口、测试/正式环境、订单、金额、币种和 Checkout Session。回调重复或并发到达只入账一次，已支付订单不会被迟到的过期事件覆盖。
- 中文/英文覆盖导航、现有种子工具介绍、登录、账户和后台；右上角切换，Cookie 保存选择，刷新与服务端渲染保持一致。URL 不增加语言前缀。

## 原有 Stripe 配置（兼容入口）

在被忽略的 `services/api/.env` 私下配置并重启 API：

```dotenv
TOOLDAWN_STRIPE_SECRET_KEY=sk_test_REPLACE_PRIVATELY
TOOLDAWN_STRIPE_WEBHOOK_SECRET=whsec_REPLACE_PRIVATELY
TOOLDAWN_BILLING_ORIGIN=http://127.0.0.1:3000
TOOLDAWN_CREDIT_PACKAGES=[{"id":"test-100","credits":100,"unit_amount":500,"currency":"usd"}]
```

以上是测试套餐示例，不代表正式定价。`unit_amount` 使用最小货币单位，500 USD 分为 5 美元；当前允许 USD/EUR/CNY。套餐 ID 唯一，修改套餐配置不改变已有订单。

`BILLING_ORIGIN` 必须属于 `TOOLDAWN_PUBLIC_ORIGINS`。开发与测试环境只允许 `sk_test_` 密钥。生产需要独立正式密钥、HTTPS 页面、真实 SMTP 及现有生产配置。

在 Stripe 配置回调地址 `https://你的域名/api/v1/billing/webhook`，订阅：

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `checkout.session.expired`

本地可用 Stripe CLI 将测试事件转发到 `http://127.0.0.1:8000/api/v1/billing/webhook`，使用该 CLI 返回的独立 webhook secret。反向代理应保留原始 body 和 `Stripe-Signature` 请求头，并允许 webhook POST。该接口无需浏览器 Cookie，也不做浏览器 Origin 校验。

执行 `uv run alembic upgrade head` 应用全部迁移（包括 `0008_payment_providers`）。未配置商户时套餐为空、充值不可用，已有积分和记录仍可查看。项目不会自动启用示例价格或模拟实际支付成功。

## 当前边界

尚未配置真实商户密钥，尚未进行各支付平台测试环境或正式环境的真实收款联调；自动化使用 SDK mock 和签名测试事件，不会扣款。

本次实现一次性充值。订阅、优惠券、自动退款/争议扣回、发票、主动向 Stripe 对账和回调补偿任务尚未实现。迟迟未收到回调的订单可能继续显示待支付，应在 Stripe 核实后人工处理，不能仅凭浏览器返回成功增加积分。

工具执行和 Worker 尚未上线，积分尚未接入工具消费、预扣、结算与失败返还。管理员扣减仅用于人工调整，不等同于完整工具计费。

管理员新建的任意工具文案按原文显示；目前翻译覆盖现有种子内容，尚未提供内容翻译编辑器或按语言独立的目录搜索索引。英文搜索依赖工具已有的名称和关键词。默认语言为中文，不按浏览器语言自动切换。

## 验证

在 `services/api` 运行 `uv run python ../../scripts/check_remote.py`：专用测试库迁移、种子重复导入、完整测试和远程 Redis 检查。测试覆盖权限、来源、订单归属、价格篡改、签名、回调重复/并发、非负余额和并发扣减。

## 后台支付管理

`/admin/orders` 提供统计、订单列表、供应商配置三个二级页签，`?tab=statistics|list|config` 可以直接定位页签。继续使用后台的浅色／深色切换。

- 统计展示订单总数、已支付数量、支付率、已发放积分、分币种实收金额和状态分布；点击状态进入相应订单列表。
- 订单支持邮箱、订单号、套餐标识模糊查询，以及状态、创建日期组合筛选和分页。点击订单号查看套餐、金额、积分、创建／到期／支付时间。
- 日期输入按浏览器本地时区转换，开始时间包含、结束时间不包含；页面的结束日期包含当天。统计与列表使用相同条件。收入表示所选创建日期内订单的已支付金额，不是按到账日期计算的结算报表；不同币种不汇总。
- 超级管理员可维护五种支付供应商实例和积分套餐，原有 Stripe 配置保留兼容入口。密钥留空保留，勾选清除才删除；接口仅返回是否配置。就绪状态表示字段齐全，不代表已验证上游连通性。
- 支付专用保存接口只修改支付字段，并使用系统设置共享的 revision 和事务锁，旧版本保存返回 409。各渠道均仅由签名验证通过的回调确认支付入账。

接口：`GET /api/v1/admin/billing/orders`、`GET /api/v1/admin/billing/statistics` 接受 `q/status/start/end`；配置 `GET/PUT /api/v1/admin/billing/config` 仅超级管理员可调用，PUT 同时检查 Origin。

相关后台补充：用户列表新增 `role/disabled` 筛选；操作日志的 `q` 支持操作类型、操作者邮箱和目标，新增 `start/end` 日期范围。日志仍只记录字段名。
