# InvoiceHub

多租户 Invoice + 客户 + 库存管理系统，支持中文、English、Bahasa Indonesia。

## Features

- 公司账号独立数据隔离
- 子账号与权限：Owner / Admin / Finance / Sales / Viewer
- 客户管理、产品目录、发票、收款
- 发票 PDF 下载与网页打印
- 自动发票编号
- 月度销售额、客户销售额统计
- 库存管理：批量入库、手动入库/出库、库存调整、库存流水、低库存预警
- 支持超售（可配置负库存）
- 新明细可一键加入产品库
- 印度尼西亚本地化：IDR、NPWP、PPN、DPP

## Tech Stack

- Django 5.2
- PostgreSQL
- Docker / Docker Compose
- ReportLab PDF output

## Local preview

```bash
DATABASE_URL=sqlite:///work/preview.sqlite3 python3 manage.py migrate --noinput
DATABASE_URL=sqlite:///work/preview.sqlite3 python3 manage.py runserver 0.0.0.0:8000
```

Open `http://localhost:8000/`.

## Docker

```bash
cp .env.example .env
docker compose up -d --build
```

## GitHub deploy

1. Create or use repo: `https://github.com/chnnic/InvoiceHub`
2. Push the `main` branch
3. Deploy with Docker on your server

## Notes

- Data is scoped by company, so different accounts are independent.
- Invoice numbering, stock policy, tax, and branding are configurable in company settings.
- For Indonesian tax/invoice compliance, verify final rules before live use.
