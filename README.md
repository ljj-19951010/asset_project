# MDPI Asset Manager

基于 **FastAPI + MySQL 8.0 + Nginx** 的资产管理平台，通过 Docker Compose 一键部署，适配群晖 / 威联通等 NAS 环境。

---

## 📖 项目简介

本项目采用前后端分离架构：

- **后端**：FastAPI（Python 3.13），提供 RESTful API
- **数据库**：MySQL 8.0，数据持久化到宿主机
- **前端**：Nginx 托管静态页面，并反向代理后端 API

所有服务通过 Docker Compose 编排，运行在自定义桥接网络 `mynet` 中，服务之间通过服务名互相访问。

> TODO：补充一段业务功能描述（这个系统是做什么的、面向谁、核心模块有哪些）。

---

## 🧱 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | latest |
| 运行环境 | Python | 3.13 |
| ASGI 服务器 | Uvicorn | latest |
| 数据库 | MySQL | 8.0 |
| 前端 | Nginx + 静态页面 | alpine |
| 容器编排 | Docker Compose | v3.8 |

---

## 🏗️ 架构说明

```
                ┌─────────────────────────────────────┐
                │            NAS Host                 │
                │                                     │
   :8080  ────► │  nginx_frontend  ──┐                │
                │                    │ proxy_pass     │
                │                    ▼                │
   :9000  ────► │  fastapi_mdpi  ────┼──► mysql8.0    │
                │                    │    :3306        │
                │                    │                 │
                └────────────────────┴─────────────────┘
                          Docker network: mynet
```

| 服务 | 容器名 | 宿主机端口 | 容器端口 | 说明 |
|------|--------|-----------|----------|------|
| Nginx | `nginx_frontend` | 8080 | 80 | 前端页面 + API 反向代理 |
| FastAPI | `fastapi_mdpi` | 9000 | 9000 | 后端 API（调试可直接访问 `/docs`） |
| MySQL | `mysql8.0` | 3306 | 3306 | 数据库（建议生产改为 3307 避免冲突） |

---

## 📁 目录结构

```
asset_manager/
├── docker-compose.yml          # 服务编排文件
├── Dockerfile                  # FastAPI 镜像构建文件
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板（复制为 .env 使用）
├── mdpi_asset/                 # FastAPI 后端代码（挂载进容器）
│   ├── main.py
│   └── ...
├── mdpi_frontend/              # 前端静态文件（挂载进 Nginx）
│   └── index.html
├── nginx_conf/
│   └── default.conf            # Nginx 站点配置
└── mysql_init/                 # 首次启动自动执行的 SQL（可选）
    └── schema.sql
```

> 数据目录 `/volume1/docker/mysql8.0/data` 位于宿主机，**不在本仓库内**，请勿提交。

---

## 🚀 快速开始

### 1. 前置要求

- NAS 已安装 Docker 及 Docker Compose
- 已开启 SSH 访问
- 宿主机端口 `8080`、`9000`、`3306` 未被占用

### 2. 克隆项目

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

> TODO：替换为你的实际仓库地址。

### 3. 配置环境变量

```bash
cp .env.example .env
vim .env   # 修改数据库密码等敏感信息
```

`.env` 示例：

```env
MYSQL_ROOT_PASSWORD=your_strong_password
MYSQL_DATABASE=your_database_name
MYSQL_USER=your_db_user
MYSQL_PASSWORD=your_db_password
```

### 4. 创建 Docker 网络

`docker-compose.yml` 中声明了 `mynet` 为外部网络，**首次部署需手动创建**：

```bash
docker network create mynet
```

### 5. 构建并启动

```bash
docker-compose up -d --build
```

### 6. 验证部署

```bash
docker-compose ps
docker-compose logs -f fastapi_mdpi
```

访问：

- 前端页面：`http://<NAS_IP>:8080`
- API 文档：`http://<NAS_IP>:9000/docs`

---

## 🗄️ 数据库管理

### 导入现有数据库结构

**方式一：手动导入（容器已运行）**

```bash
docker exec -i mysql8.0 mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <数据库名> < schema.sql
```

**方式二：首次启动自动初始化（推荐全新部署）**

将 `.sql` 文件放入 `mysql_init/` 目录，并确保 `docker-compose.yml` 中已挂载：

```yaml
volumes:
  - /volume1/docker/mysql8.0/data:/var/lib/mysql
  - ./mysql_init:/docker-entrypoint-initdb.d
```

> ⚠️ 初始化脚本**仅在数据目录为空时执行**，已有数据的环境不会重复执行。

### 备份数据库

```bash
docker exec mysql8.0 mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" <数据库名> \
  > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 恢复数据库

```bash
docker exec -i mysql8.0 mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <数据库名> < backup.sql
```

---

## 🔄 日常运维

### 更新后端代码（未改依赖）

```bash
# 1. 备份旧代码
cp -r mdpi_asset mdpi_asset_bak_$(date +%Y%m%d)

# 2. 上传新代码（本地执行 rsync，或用 File Station）
# rsync -avz ./mdpi_asset/ user@NAS_IP:/volume1/asset_manager/mdpi_asset/

# 3. 清理 Python 缓存并重启
find mdpi_asset -name "__pycache__" -type d -exec rm -rf {} +
docker restart fastapi_mdpi
```

### 更新依赖（requirements.txt 有变化）

```bash
docker-compose build fastapi_mdpi
docker-compose up -d fastapi_mdpi
```

### 更新前端静态文件

```bash
docker restart nginx_frontend
```

### 更新 Nginx 配置

```bash
docker exec nginx_frontend nginx -t     # 先验证语法
docker restart nginx_frontend
```

### 查看日志

```bash
docker-compose logs -f                # 所有服务
docker logs -f --tail 100 fastapi_mdpi
docker logs -f --tail 100 mysql8.0
```

### 停止 / 重启

```bash
docker-compose stop                   # 停止所有服务（保留容器）
docker-compose restart fastapi_mdpi   # 只重启后端
docker-compose down                   # 删除容器（不删数据卷）
```

> ⚠️ **不要在生产环境随意执行 `docker-compose down`**，它会中断所有服务。仅更新代码时用 `docker restart` 或 `docker-compose up -d <服务名>`。

---

## ❓ 常见问题

### Q1：`network mynet declared as external, but could not be found`

外部网络未创建，执行：

```bash
docker network create mynet
```

### Q2：`sudo: cd: command not found`

`cd` 是 shell 内建命令，不能 `sudo cd`。正确做法：

```bash
sudo -i
cd /your/path/
```

### Q3：FastAPI 启动报数据库连接失败

- 确认 `DATABASE_URL` 中的 host 是**服务名 `mysql8.0`**，而不是 `localhost`
- 确认 MySQL 容器已就绪：`docker logs mysql8.0 | tail -20`
- compose 中已配置 `healthcheck` + `depends_on: condition: service_healthy`，确保启动顺序

### Q4：代码更新后没生效

```bash
find mdpi_asset -name "__pycache__" -type d -exec rm -rf {} +
docker restart fastapi_mdpi
```

### Q5：文件权限报 `Permission denied`

通过 File Station 上传的文件属主可能不对：

```bash
chmod -R 755 mdpi_asset
chown -R <你的用户>:users mdpi_asset
```

### Q6：端口 3306 被占用

修改 `docker-compose.yml`：

```yaml
ports:
  - "3307:3306"
```

---

## 🔐 安全建议

- `.env` 文件**不要提交到 Git**，已加入 `.gitignore`
- 生产环境请修改 MySQL root 密码为强密码
- 如无外部访问需求，**不要将 3306 端口暴露到宿主机**
- 建议为 FastAPI 配置 CORS 白名单，不要使用 `allow_origins=["*"]`
- 定期备份数据库与项目代码

---

## 📄 License

> TODO：选择并填写许可证，例如 MIT / Apache-2.0 / 内部私有。

---

## 👥 维护者

- TODO：填写维护者姓名 / 联系方式
