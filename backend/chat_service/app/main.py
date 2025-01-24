from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from event_bus import event_bus
from services.websocket import websocket_manager
from database import DatabaseManager, DatabaseConnectionError
import logging
import uvicorn
from message_router import message_router

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI()

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该指定具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.on_event("startup")
async def startup_event():
    """
    应用启动时的初始化
    """
    try:
        logger.info("Starting application initialization...")
        
        # 启动事件总线
        logger.info("Starting event bus...")
        await event_bus.start()
        logger.info("Event bus started successfully")
        
        # 初始化数据库连接
        global db_manager
        db_manager = DatabaseManager()
        await db_manager._init_task
        logger.info("Database initialized successfully")

        # 确保 message_router 已经创建并订阅了事件
        logger.info("Initializing message router...")
        if not hasattr(app.state, 'message_router'):
            app.state.message_router = message_router
        logger.info("Message router initialized successfully")

        # 初始化 WebSocket 管理器
        logger.info("Initializing WebSocket manager...")
        logger.info("WebSocket manager initialized successfully")

        logger.info("Application startup complete")
    except DatabaseConnectionError as e:
        logger.critical(f"Failed to start application due to database connection error: {str(e)}")
        # 可以选择优雅地关闭应用
        import sys
        sys.exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    """
    应用关闭时的清理
    """
    try:
        # 停止事件总线
        await event_bus.stop()
        logger.info("Event bus stopped")

        # 关闭所有 WebSocket 连接
        for client_id in list(websocket_manager.active_connections.keys()):
            await websocket_manager.disconnect(client_id)
        logger.info("All WebSocket connections closed")

        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket 连接端点
    """
    try:
        logger.info(f"New WebSocket connection request from client {client_id}")
        await websocket_manager.connect(websocket, client_id)
        await websocket_manager.receive_message(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {str(e)}")
        await websocket_manager.disconnect(client_id)

@app.get("/health")
async def health_check():
    """
    健康检查端点
    """
    return {
        "status": "healthy",
        "database": "connected" if db_manager._init_task.done() else "initializing",
        "event_bus": "running" if event_bus._running else "stopped"
    }

@app.get("/")
async def root():
    """
    根路径响应
    """
    return {
        "message": "Welcome to Says API",
        "version": "1.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug",
        ws_ping_interval=20,
        ws_ping_timeout=20,
        access_log=True
    )