import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import sys
sys.path.insert(0, '/app')

from core.database import SessionLocal
from models.ai.character import AICharacter


async def check():
    async with SessionLocal() as db:
        result = await db.execute(
            select(AICharacter)
            .where(AICharacter.id == 223788765171154946)
            .options(selectinload(AICharacter.personality))
        )
        char = result.scalar_one_or_none()
        
        if not char:
            print("Character not found")
            return
            
        print(f"Character ID: {char.id}")
        print(f"Character qiao_id: {char.qiao_id}")
        print(f"Personality ID: {char.personality_id}")
        print(f"Personality: {char.personality}")
        if char.personality:
            print(f"Personality display_name: {char.personality.display_name}")
        print(f"Algorithm: {char.score_offset_algorithm}")
        print(f"Variables: {char.prompt_variables}")
        print(f"Params: {char.score_offset_params}")


asyncio.run(check())

