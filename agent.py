from __future__ import annotations
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm
)
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
from dotenv import load_dotenv
from api import AssistantFnc
from prompts import WELCOME_MESSAGE, INSTRUCTIONS, LOOKUP_VIN_MESSAGE
import os

load_dotenv()

async def entrypoint(ctx: JobContext):
    # Kết nối và chờ người dùng vào phòng
    # Kết nối tới phòng LiveKit
    # Đợi ít nhất một người dùng kết nối (người nói)
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    await ctx.wait_for_participant()
    
    # Khởi tạo Realtime LLM model từ OpenAI
    # Có hướng dẫn (INSTRUCTIONS) và giọng nói "shimmer"
    # Hỗ trợ cả âm thanh và văn bản
    model = openai.realtime.RealtimeModel(
        instructions=INSTRUCTIONS,
        voice="shimmer",
        temperature=0.8,
        modalities=["audio", "text"]
    )
    
    # Khởi tạo trợ lý và khởi động
    # AssistantFnc() chứa logic xử lý thông tin bên ngoài (ví dụ tìm profile người dùng)
    # MultimodalAgent kết nối mô hình với phòng
    assistant_fnc = AssistantFnc()
    assistant = MultimodalAgent(model=model, fnc_ctx=assistant_fnc)
    assistant.start(ctx.room)
    
    # Tạo câu chào mừng
    # Lấy phiên trò chuyện đầu tiên (sessions[0])
    # Gửi tin nhắn chào mừng từ trợ lý ảo
    session = model.sessions[0]
    session.conversation.item.create(
        llm.ChatMessage(
            role="assistant",
            content=WELCOME_MESSAGE
        )
    )
    session.response.create()
    
    # Bắt sự kiện khi người dùng nói xong
    # Sự kiện được kích hoạt mỗi khi người dùng nói xong 1 đoạn
    @session.on("user_speech_committed")
    def on_user_speech_committed(msg: llm.ChatMessage):
        # Xử lý nội dung đầu vào
        # Nếu nội dung là danh sách các phần tử (ảnh + text), chuyển tất cả thành văn bản đơn giản để hiển thị
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg)
            
        if assistant_fnc.has_car():
            handle_query(msg)
        else:
            find_profile(msg)
        
    def find_profile(msg: llm.ChatMessage):
        session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=LOOKUP_VIN_MESSAGE(msg)
            )
        )
        session.response.create()
        
    def handle_query(msg: llm.ChatMessage):
        session.conversation.item.create(
            llm.ChatMessage(
                role="user",
                content=msg.content
            )
        )
        session.response.create()
    
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))