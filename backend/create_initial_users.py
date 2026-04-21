import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.database import DATABASE_URL, users_table
from app.auth import get_password_hash

async def create_initial_users():
    engine = create_async_engine(DATABASE_URL)
    
    users = [
        {"username": "admin", "password": "admin", "role": "admin"},
        {"username": "manager", "password": "manager", "role": "manager"},
    ]
    
    async with engine.begin() as conn:
        for user in users:
            hashed_password = get_password_hash(user["password"])
            query = users_table.insert().values(
                username=user["username"],
                hashed_password=hashed_password,
                role=user["role"],
                is_active=True
            )
            try:
                await conn.execute(query)
                print(f"Создан пользователь {user['username']} (роль: {user['role']})")
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    print(f"Пользователь {user['username']} уже существует")
                else:
                    print(f"Ошибка при создании {user['username']}: {e}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_initial_users())