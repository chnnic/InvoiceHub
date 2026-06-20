# InvoiceHub

多租户 Invoice + 客户 + 库存管理系统，支持中文、English、Bahasa Indonesia。

## 模块

- 登录 / 公司账号 / 子账号权限
- 客户管理
- 产品目录
- 发票
- 收款
- PDF 下载 / 网页打印
- 自动编号
- 销售统计
- 库存管理
- 批量入库
- 低库存预警
- 超售（负库存）
- 系统设置
- 超级管理员

## 技术栈

- Django 5.2
- PostgreSQL
- Docker / Docker Compose
- Caddy（VPS HTTPS）
- ReportLab PDF

## 安装方式

### 方式一：本地预览

适合开发调试。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=sqlite:///work/preview.sqlite3 python3 manage.py migrate --noinput
DATABASE_URL=sqlite:///work/preview.sqlite3 python3 manage.py runserver 0.0.0.0:10081
```

打开：

- `http://localhost:10081/`

### 方式二：Docker 一键安装

适合自己的电脑。

```bash
cp .env.example .env
docker compose up -d --build
```

第一次启动会自动创建超级管理员。

如果你想自定义超级管理员账号和密码，在 `.env` 里设置：

```bash
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=your-password
```

如果不设置 `SUPERUSER_PASSWORD`，系统会自动生成一个随机密码并打印到容器日志里。

## VPS 一键安装

先保证 VPS 已安装 Docker、git，且域名已经解析到服务器。

```bash
curl -fsSL https://raw.githubusercontent.com/chnnic/InvoiceHub/main/scripts/install_vps.sh | bash
```

它会：

1. 从 GitHub 克隆 InvoiceHub
2. 自动生成 `SECRET_KEY` 和数据库密码
3. 检查并安装 Caddy（apt-based 系统）
4. 写入域名、启动数据库、应用、Caddy
5. 自动申请 HTTPS 证书

安装完成后，如要更新现有 VPS：

```bash
cd ~/invoicehub
bash scripts/deploy_vps.sh
```

## 超级管理员

超级管理员可：

- 控制是否允许公司注册
- 触发从 GitHub 更新 InvoiceHub

## 从 GitHub 更新

超级管理员页面里的更新按钮会执行固定流程：

1. `git pull origin main`
2. `docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build`

## 主要功能

- 公司独立数据隔离
- 多账号多角色
- 账单 / 发票 / PDF
- 客户销售统计
- 月度销售额统计
- 库存流水
- 手动入库 / 出库 / 调整
- 批量入库
- 低库存预警
- 新产品可从发票明细直接加入产品库

## 目录说明

- `core/`：业务逻辑
- `templates/`：网页模板
- `scripts/`：安装、更新脚本
- `docker-compose.yml`：本地 / 标准 Docker 启动
- `docker-compose.vps.yml`：VPS + Caddy 反代

## 说明

- 所有金额默认千分位显示
- 印尼地区默认已考虑 IDR、NPWP、PPN、DPP
- 生产部署前建议先测试域名、HTTPS、备份和数据库连接
