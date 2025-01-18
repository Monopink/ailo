import asyncio
import websockets
import json
from database import save_message_to_db, get_user_context
from backend.app.llm_api import process_message_with_ai
from session_manager import SessionManager

# 会话管理
session_manager = SessionManager()

async def handle_message(websocket, path):
    user_id = None
    try:
        async for message in websocket:
            data = json.loads(message)
            user_id = data["user_id"]
            content = data["content"]

            # 保存消息到数据库
            save_message_to_db(user_id, content, from_user=True)

            # 获取用户上下文
            context = get_user_context(user_id)

            # 处理消息并生成回复
            reply = await process_message_with_ai(content, context)

            # 保存回复到数据库
            save_message_to_db(user_id, reply, from_user=False)

            # 发送回复给客户端
            await websocket.send(json.dumps({"user_id": user_id, "reply": reply}))

            # 更新会话状态
            session_manager.update_session(user_id)
    except websockets.ConnectionClosed:
        print(f"Connection with user {user_id} closed.")
    finally:
        if user_id:
            session_manager.end_session(user_id)

# 启动 WebSocket 服务
start_server = websockets.serve(handle_message, "0.0.0.0", 8000)

if __name__ == "__main__":
    asyncio.run(start_server)
