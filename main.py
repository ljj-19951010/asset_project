from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles


from app.admin import user, user_logs, snake
from app.core.database import engine, Base
from app.logs.loggers import logger
from app.router import assets, computers, monitors, stats, search, employees, scrapped


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # logger.info('生命周期函数:数据库初始化完成')
    yield
    await engine.dispose()
    # logger.info('生命周期函数:引擎关闭')


app = FastAPI(
    title='MDPI资产管理系统',
    version='1.0',
    lifespan=lifespan
)


# CORS（跨域资源共享）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应替换为具体域名，如 ["https://example.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安全中间件：限制 Host 头（防止 Host 欺骗攻击）
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 生产环境应填写允许的域名列表
)

# 挂载本地static文件夹
app.mount('/static', StaticFiles(directory='static'), name='static')

# 路由控制
app.include_router(user.router, prefix='/api/user', tags=['用户管理'])
app.include_router(assets.router, prefix='/api/assets', tags=['资产管理'])
app.include_router(computers.router, prefix='/api/computers', tags=['电脑管理'])
app.include_router(monitors.router, prefix='/api/monitors', tags=['显示器管理'])
app.include_router(employees.router, prefix='/api/employees', tags=['员工管理'])
app.include_router(scrapped.router, prefix='/api/scrapped', tags=['报废管理'])
app.include_router(stats.router, prefix='/api/stats', tags=['统计'])
app.include_router(search.router, prefix='/api/search', tags=['搜索'])
app.include_router(user_logs.router, prefix='/api/user/user_logs', tags=['操作日志'])
app.include_router(snake.router, prefix='/api/game', tags=['贪吃蛇'])

@app.get("/health", tags=["Start-CONN"])
async def health_check():
    logger.debug('log:数据库连接检查成功，服务器运行正常!')
    return {"status": "ok", "message": "服务运行正常"}


@app.get("/", tags=["Start"])
async def root():
    return {"message": "欢迎使用本系统!", "docs": "/api/docs"}