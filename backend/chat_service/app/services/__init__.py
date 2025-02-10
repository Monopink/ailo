from .websocket import websocket

__all__ = [
    "websocket",
]

"""
Received Message Args:
    message: 消息字典，包含以下字段：
        - from_entity: str, 发送者ID
        - to_entity: str, 接收者ID
        - content: str, 消息内容，可选
        - message_type: int, 消息类型
            0: chat 聊天消息
            1: typing 开始输入
            2: typing_end 输入结束
            8: chat_notyping 无输入信息的聊天消息
        - message_service: str, 消息服务类型
        - timestamp: str, 时间戳
Send Message Args:
    message: 消息字典，包含以下字段：
        - from_entity: str, 发送者ID
        - to_entity: str, 接收者ID
        - content: str, 消息内容，可选
        - message_type: int, 消息类型
            0: chat 聊天消息
            1: typing 输入中消息
            9: system 系统消息
        - message_service: str, 消息服务类型
        - timestamp: str, 时间戳
"""
