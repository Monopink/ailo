from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio
from typing import Dict
import json
from datetime import datetime

from sender import message_sender
from database import db_manager
import transfer
from bot_model import BotManager

# 创建FastAPI应用
app = FastAPI(title="AI Chat Backend")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(transfer.router, prefix="/api")

# 存储活跃的WebSocket连接
active_connections: Dict[str, WebSocket] = {}

# 创建bot_manager实例并注入message_sender
bot_manager = BotManager(message_sender)

# 将bot_manager注入到transfer模块
transfer.init_bot_manager(bot_manager)

@app.on_event("startup")
async def startup_event():
    """
    应用启动时的初始化操作
    """
    try:
        # 初始化数据库连接
        await db_manager.get_session()
        print("Database connection initialized successfully")
    except Exception as e:
        print(f"Error initializing database connection: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """
    应用关闭时的清理操作
    """
    try:
        # 关闭所有WebSocket连接
        for user_id in list(active_connections.keys()):
            await active_connections[user_id].close()
        active_connections.clear()
        
        # 关闭数据库连接
        await db_manager.close_session()
        print("Cleanup completed successfully")
    except Exception as e:
        print(f"Error during cleanup: {e}")

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    处理WebSocket连接的主要端点
    """
    await websocket.accept()
    active_connections[user_id] = websocket
    message_sender.register_connection(user_id, websocket)
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                # 解析消息内容
                message_data = json.loads(data)
                bot_id = message_data.get("bot_id")
                content = message_data.get("content")
                
                if not bot_id or not content:
                    await websocket.send_text(
                        json.dumps({
                            "error": "Invalid message format. Must include bot_id and content."
                        })
                    )
                    continue
                
                # 处理消息
                await bot_manager.process_message(
                    user_id=user_id,
                    bot_id=bot_id,
                    message=content
                )
                
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({
                        "error": "Invalid JSON format"
                    })
                )
            except Exception as e:
                print(f"Error processing message: {e}")
                await websocket.send_text(
                    json.dumps({
                        "error": "Error processing message"
                    })
                )
    
    except WebSocketDisconnect:
        # 处理连接断开
        if user_id in active_connections:
            del active_connections[user_id]
        message_sender.remove_connection(user_id)
        print(f"Client {user_id} disconnected")
    
    except Exception as e:
        print(f"Unexpected error in websocket connection: {e}")
        if user_id in active_connections:
            del active_connections[user_id]
        message_sender.remove_connection(user_id)

@app.get("/health")
async def health_check():
    """
    健康检查端点
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(active_connections)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )