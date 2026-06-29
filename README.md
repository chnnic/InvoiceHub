# InvoiceHub

InvoiceHub 是一个面向中小企业的多租户发票、客户、产品与库存管理系统。项目默认适配印尼业务场景，支持中文、English、Bahasa Indonesia，可通过 Docker 快速部署到自己的 VPS。

当前版本：`1.0.38`

## 适合谁使用

- 需要开具销售发票、记录客户和收款的贸易公司
- 需要管理产品目录、库存流水、低库存预警的团队
- 需要多公司、多账号、不同权限隔离的业务系统
- 希望用 `IP:端口` 直接部署在 VPS 上，不依赖复杂反向代理配置的用户

## 核心功能

### 发票与收款

- 发票自动编号，可设置前缀和编号位数
- 发票明细支持从产品目录选择，也支持手动输入新产品
- 新产品可从发票明细直接保存到产品目录
- 发票打印页与保存 PDF 使用同一套版式，避免显示、打印和 PDF 不一致
- 发票模板支持公司 Logo、公司信息、客户信息、签名区
- 可登记收款，支持一键填入剩余货款
- 发票状态可手动修改：草稿、已发送、部分付款、已付款、逾期、作废
- 发货状态可手动修改：未发货、已发货
- 发票筛选：未付款、已付款、已发货、未发货、草稿
- 发票 CSV 导出
- 按客户、按月份、按状态统计销售额

### 库存管理

- 产品库存管理
- 手动入库、出库、库存调整
- 批量入库，支持一次性创建新产品
- 单个产品库存流水查看
- 低库存预警
- 支持负库存/超售，并提示及时补货
- 发货才扣库存：
  - 新建发票默认不扣库存
  - 改为“已发货”后扣库存
  - 已发货改回未发货会回滚库存
  - 已发货发票修改明细会按差额调整库存
  - 已发货发票作废或删除会自动回滚库存

### 印尼地区适配

- 默认货币：IDR
- 支持 NPWP 字段
- 支持 PPN / DPP
- 公司设置中可选择是否显示 PPN
- 如果关闭 PPN，发票税率会按 0 处理，页面、打印和保存 PDF 不显示 PPN 行

### 多租户与权限

- 公司数据隔离
- 多账号登录
- 子账号权限角色
- 超级管理员后台
- 可控制是否允许新公司注册
- 超级管理员可管理用户，但不查看租户业务内容

### 系统运维

- Docker / Docker Compose 部署
- VPS 一键安装脚本
- 从 GitHub 拉取更新并重建容器
- 本地版本号与 GitHub 版本号显示
- 备份、恢复、日志、状态检查脚本

## 技术栈

- Python 3.13
- Django 5.2
- PostgreSQL 17
- Docker / Docker Compose
- Noto CJK 字体，确保中文打印和保存 PDF 正常显示

## 快速开始：VPS 一键安装

推荐使用 Ubuntu / Debian VPS。先确保 VPS 已安装 Docker 和 Git。

```bash
curl -fsSL https://raw.githubusercontent.com/chnnic/InvoiceHub/main/scripts/install_vps.sh | bash
```

安装完成后访问：

```text
http://<你的VPS-IP>:18081
```

默认端口是 `18081`。脚本会自动检测端口是否被占用，如果被占用会向后寻找可用端口。

安装完成后终端会显示：

- 访问地址
- 超级管理员用户名
- 超级管理员密码

如果没有手动指定密码，脚本会自动生成一个安全密码。

## VPS 一键安装：带参数

你可以指定安装目录、端口、管理员账号：

```bash
curl -fsSL https://raw.githubusercontent.com/chnnic/InvoiceHub/main/scripts/install_vps.sh | bash -s -- \
  --dir /opt/invoicehub \
  --port 18081 \
  --username admin \
  --email admin@example.com \
  --password 'change-this-password'
```

非交互安装：

```bash
curl -fsSL https://raw.githubusercontent.com/chnnic/InvoiceHub/main/scripts/install_vps.sh | bash -s -- \
  --non-interactive \
  --port 18081
```

也可以通过环境变量指定：

```bash
APP_PORT=18081 \
SUPERUSER_USERNAME=admin \
SUPERUSER_EMAIL=admin@example.com \
SUPERUSER_PASSWORD='change-this-password' \
curl -fsSL https://raw.githubusercontent.com/chnnic/InvoiceHub/main/scripts/install_vps.sh | bash
```

## 本地 Docker 运行

```bash
git clone https://github.com/chnnic/InvoiceHub.git
cd InvoiceHub
cp .env.example .env
docker compose up -d --build
```

打开：

```text
http://localhost:18081
```

查看启动日志：

```bash
docker compose logs -f web
```

如果没有设置 `SUPERUSER_PASSWORD`，首次启动会在日志里打印自动生成的超级管理员密码。

## 本地预览脚本

```bash
bash scripts/run_local_preview.sh
```

或者使用统一入口：

```bash
bash scripts/ih.sh preview
```

## 环境变量

常用 `.env` 配置：

```env
SECRET_KEY=replace-with-a-long-random-string
DEBUG=0
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:18081
POSTGRES_DB=invoicehub
POSTGRES_USER=invoicehub
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql://invoicehub:change-me@db:5432/invoicehub
APP_PORT=18081
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=your-password
```

生产环境建议：

- 修改 `SECRET_KEY`
- 修改数据库密码
- 设置强密码的超级管理员账号
- 如果使用域名访问，设置正确的 `ALLOWED_HOSTS` 和 `CSRF_TRUSTED_ORIGINS`

## 更新旧版本

进入安装目录：

```bash
cd ~/invoicehub
```

执行：

```bash
bash scripts/update_from_github.sh
```

或者：

```bash
bash scripts/ih.sh update
```

更新脚本会执行：

```bash
git pull origin main
docker compose up -d --build
```

如果你的系统使用旧版 `docker-compose`，脚本会自动兼容。

注意：修改 `.env` 后不要只执行 `docker compose restart`。环境变量变更需要：

```bash
docker compose up -d --build
```

## Web 后台更新说明

超级管理员后台提供“从 GitHub 更新 InvoiceHub”的入口。

但很多 Docker 部署不会把宿主机 Docker socket 挂载进 Web 容器，这种情况下 Web 页面无法直接重建宿主机容器。页面会显示推荐 SSH 命令，你可以复制后在 VPS 执行。

推荐仍以 SSH 更新为准：

```bash
cd ~/invoicehub
bash scripts/update_from_github.sh
```

## 常用命令

统一入口：

```bash
bash scripts/ih.sh help
```

常用命令：

```bash
bash scripts/ih.sh status
bash scripts/ih.sh doctor
bash scripts/ih.sh logs --service web
bash scripts/ih.sh backup
bash scripts/ih.sh restore
bash scripts/ih.sh update
```

直接查看容器：

```bash
docker compose ps
docker compose logs -f web
docker compose logs -f db
```

## 备份与恢复

备份数据库和 media：

```bash
cd ~/invoicehub
bash scripts/backup.sh
```

默认备份到：

```text
~/invoicehub/backups
```

恢复最近备份：

```bash
cd ~/invoicehub
bash scripts/restore.sh
```

指定文件恢复：

```bash
bash scripts/restore.sh \
  --db backups/db-YYYYMMDD-HHMMSS.sql \
  --media backups/media-YYYYMMDD-HHMMSS.tar.gz
```

建议在每次升级前先备份。

## 版本管理

当前版本记录在：

```text
VERSION
```

升级 patch 版本：

```bash
bash scripts/ih.sh version
```

指定版本：

```bash
bash scripts/ih.sh version 1.0.38
```

开发规则：每次功能或脚本变更都应同步更新版本号。

## 目录结构

```text
InvoiceHub/
├── core/                    # Django 业务逻辑
├── core/migrations/         # 数据库迁移
├── locale/                  # 中文/印尼文翻译
├── scripts/                 # 安装、更新、备份、诊断脚本
├── templates/               # 页面模板
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── requirements.txt
├── VERSION
└── README.md
```

重要脚本：

| 脚本 | 作用 |
| --- | --- |
| `scripts/install_vps.sh` | VPS 一键安装 |
| `scripts/deploy_vps.sh` | 重新部署 |
| `scripts/update_from_github.sh` | 从 GitHub 更新 |
| `scripts/backup.sh` | 备份数据库和媒体文件 |
| `scripts/restore.sh` | 恢复备份 |
| `scripts/doctor.sh` | 检查部署环境 |
| `scripts/status.sh` | 查看版本和容器状态 |
| `scripts/logs.sh` | 查看日志 |
| `scripts/ih.sh` | 统一命令入口 |

## 发票状态说明

| 状态 | 说明 |
| --- | --- |
| 草稿 | 尚未正式发送 |
| 已发送 | 已发给客户 |
| 部分付款 | 已收到部分款项 |
| 已付款 | 已收齐款项 |
| 逾期 | 到期未付 |
| 作废 | 发票无效，库存会按规则回滚 |

发货状态：

| 状态 | 库存影响 |
| --- | --- |
| 未发货 | 不扣库存 |
| 已发货 | 扣库存 |

库存扣减规则：

- 发票创建后默认未发货，不扣库存
- 改为已发货时扣库存
- 已发货改回未发货时回滚库存
- 已发货发票编辑数量时按差额调整库存
- 已发货发票作废或删除时回滚库存

## 常见问题

### 1. 为什么访问不了 `localhost:10080`？

浏览器会拦截部分不安全端口，`10080` 属于容易被拦截的端口之一。InvoiceHub 默认使用：

```text
18081
```

### 2. 为什么更新后配置没生效？

如果改了 `.env`，需要重建容器：

```bash
docker compose up -d --build
```

不要只用：

```bash
docker compose restart
```

### 3. 忘记超级管理员密码怎么办？

如果你还能进入系统，可在超级管理员后台修改密码。

如果无法登录，可进入容器执行 Django 管理命令重置。示例：

```bash
docker compose exec web python manage.py changepassword admin
```

### 4. Web 更新失败怎么办？

优先 SSH 到 VPS 后执行：

```bash
cd ~/invoicehub
bash scripts/update_from_github.sh
```

然后检查：

```bash
bash scripts/doctor.sh
docker compose logs -f web
```

### 5. 数据库密码不匹配怎么办？

`.env` 里的 `POSTGRES_PASSWORD` 必须和 PostgreSQL 容器内用户密码一致。生产环境不要随意修改数据库密码；修改后需要同步更新数据库用户密码和 `DATABASE_URL`。

## 开发说明

本地开发建议使用 Docker，避免 Python/PostgreSQL 版本差异。

静态检查可运行：

```bash
python3 -m py_compile core/forms.py core/models.py core/urls.py core/views.py core/pdf.py
msgfmt --check locale/zh_Hans/LC_MESSAGES/django.po -o /tmp/zh.mo
msgfmt --check locale/id/LC_MESSAGES/django.po -o /tmp/id.mo
```

生成迁移后请确认：

```bash
docker compose exec web python manage.py migrate
```

## License

当前项目未声明开源许可证。如需公开商用或二次分发，请先补充 License。
