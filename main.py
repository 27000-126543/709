import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app import database
from app.routers import get_routers
from app.services import WebSocketManager, get_ws_manager
from app.utils.scheduler import SchedulerManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("正在初始化数据库...")
    await database.init_db()
    logger.info("数据库初始化完成")

    logger.info("正在启动调度器...")
    scheduler = SchedulerManager()
    scheduler.register_all_tasks()
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("调度器启动完成，已注册4个定时任务")

    ws_mgr = get_ws_manager()
    app.state.ws_manager = ws_mgr
    logger.info("WebSocket 管理器已初始化")

    yield

    logger.info("正在关闭调度器...")
    scheduler.shutdown()
    logger.info("调度器已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description="全国器官捐献与移植协调调度平台 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in get_routers():
    app.include_router(router)


@app.get("/")
async def root() -> Dict:
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "start_time": datetime.utcnow().isoformat() + "Z",
        "description": "全国器官捐献与移植协调调度平台",
    }


@app.get("/health")
async def health() -> Dict:
    scheduler_status = "unknown"
    try:
        scheduler: SchedulerManager = app.state.scheduler
        scheduler_status = "running" if scheduler.scheduler.running else "stopped"
    except Exception:
        scheduler_status = "not_initialized"

    ws_count = 0
    try:
        ws_mgr: WebSocketManager = app.state.ws_manager
        ws_count = ws_mgr.get_connection_count()
    except Exception:
        ws_count = 0

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "scheduler": scheduler_status,
        "websocket_connections": ws_count,
    }


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str) -> None:
    await websocket.accept()
    ws_mgr: WebSocketManager = app.state.ws_manager
    recipient_type = "user"

    try:
        await ws_mgr.connect(recipient_type, user_id, websocket)
        logger.info(f"WebSocket 连接成功: user_id={user_id}")

        await websocket.send_text(
            __import__("json").dumps({
                "type": "connected",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }, ensure_ascii=False)
        )

        while True:
            data = await websocket.receive_text()
            try:
                msg = __import__("json").loads(data)
                msg_type = msg.get("type", "ping")
                if msg_type == "ping":
                    await websocket.send_text(
                        __import__("json").dumps({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }, ensure_ascii=False)
                    )
            except Exception:
                pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开连接: user_id={user_id}")
    except Exception as e:
        logger.error(f"WebSocket 异常: user_id={user_id}, error={e}")
    finally:
        await ws_mgr.disconnect(recipient_type, user_id, websocket)
