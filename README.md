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
- ReportLab PDF

## 安装方式

### 方式一：本地预览

适合开发调试。

```bash
bash scripts/run_local_preview.sh
```

打开：

- `http://localhost:18081/`

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

先保证 VPS 已安装 Docker、git。

```bash
curl -fsSL https://raw.githubusercontent.com/chnnic/InvoiceHub/main/scripts/install_vps.sh | bash
```

它会：

1. 从 GitHub 克隆 InvoiceHub
2. 自动生成 `SECRET_KEY` 和数据库密码
3. 写入 VPS 端口、启动数据库和应用
4. 直接通过 `http://<你的VPS IP>:18081` 访问

安装完成后，如要更新现有 VPS：

```bash
cd ~/invoicehub
bash scripts/update_from_github.sh
```

## 超级管理员

超级管理员可：

- 控制是否允许公司注册
- 触发从 GitHub 更新 InvoiceHub

## 从 GitHub 更新

超级管理员页面里的更新按钮会执行固定流程：

1. `git pull origin main`
2. `docker compose up -d --build`

也可以直接用统一入口：

```bash
bash scripts/ih.sh update
bash scripts/ih.sh status
bash scripts/ih.sh doctor
bash scripts/ih.sh logs --service web
```

## 版本管理

每次功能或脚本更新后，都建议同步更新版本号。

自动升级一个 patch 版本：

```bash
bash scripts/ih.sh version
```

指定版本号：

```bash
bash scripts/ih.sh version 1.0.4
```

## 脚本说明

- `scripts/ih.sh`：统一入口（install/update/deploy/status/doctor/logs/backup/restore/preview）
- `scripts/lib.sh`：公共脚本函数（compose 兼容、端口检测、`.env` 写入）
- `scripts/run_local_preview.sh`：本地预览
- `scripts/install_vps.sh`：VPS 一键安装
- `scripts/update_from_github.sh`：从 GitHub 更新
- `scripts/deploy_vps.sh`：VPS 重新部署
- `scripts/status.sh`：查看版本与容器状态
- `scripts/backup.sh`：备份数据库和 media
- `scripts/restore.sh`：恢复备份
- `scripts/doctor.sh`：环境和部署检查
- `scripts/logs.sh`：快速查看容器日志

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
- `scripts/lib.sh`：脚本公共函数
- `scripts/run_local_preview.sh`：本地预览脚本
- `scripts/install_vps.sh`：VPS 一键安装
- `scripts/update_from_github.sh`：从 GitHub 更新
- `scripts/deploy_vps.sh`：VPS 重新部署
- `scripts/status.sh`：状态查看
- `scripts/backup.sh`：备份脚本
- `scripts/restore.sh`：恢复脚本
- `scripts/doctor.sh`：环境检查脚本
- `scripts/logs.sh`：日志查看脚本

## 说明

- 所有金额默认千分位显示
- 印尼地区默认已考虑 IDR、NPWP、PPN、DPP
- 生产部署前建议先测试 IP、端口、备份和数据库连接
