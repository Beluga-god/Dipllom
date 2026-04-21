import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    create_engine,
    Float,
    Boolean,
    DateTime,
    func,
    JSON,
    ForeignKey
)

# Определяем путь к файлу БД относительно текущего файла (database.py)
DATABASE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cases.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_FILE_PATH}"
SYNC_DATABASE_URL = f"sqlite:///{DATABASE_FILE_PATH}"

# Асинхронный движок SQLAlchemy
async_engine = create_async_engine(DATABASE_URL, echo=True)

# --- Используем SQLAlchemy Core для определения таблицы ---
metadata = MetaData()

cases_table = Table(
    "cases",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("personal_data", Text, nullable=False),
    Column("errors", Text, nullable=False),
    Column("benefit_type", String(100), nullable=True),  # <<< Тип поддержки / льготы
    Column("disability", Text, nullable=True),
    Column("work_experience", Text, nullable=True),
    Column("pension_points", Float, nullable=True),
    Column("benefits", Text, nullable=True),
    Column("documents", Text, nullable=True),
    Column("has_incorrect_document", Boolean, nullable=True),
    Column("final_status", String(50), nullable=True),
    Column("final_explanation", Text, nullable=True),
    Column("rag_confidence", Float, nullable=True),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("updated_at", DateTime, onupdate=func.now(), nullable=True),
    Column("other_documents_extracted_data", Text, nullable=True)
)

# Таблица для задач OCR
ocr_tasks_table = Table(
    "ocr_tasks",
    metadata,
    Column("id", String(50), primary_key=True),
    Column("document_type", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), onupdate=func.now(), nullable=True),
    Column("data", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("filename", String(255), nullable=True),
    Column("expire_at", DateTime(timezone=True), nullable=False)
)

# Таблица для пользователей
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("username", String, unique=True, index=True, nullable=False),
    Column("hashed_password", String, nullable=False),
    Column("role", String, nullable=False),
    Column("is_active", Boolean, default=True, nullable=False),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
)

# --- Функция для создания таблицы при старте (если не существует) ---
def create_db_and_tables():
    print(f"Database path: {DATABASE_FILE_PATH}")
    db_dir = os.path.dirname(DATABASE_FILE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    try:
        sync_engine = create_engine(SYNC_DATABASE_URL)
        metadata.create_all(bind=sync_engine)
        print("Tables checked/created successfully (sync method).")
    except Exception as e:
        print(f"Error creating database tables (sync method): {e}")
    finally:
        if 'sync_engine' in locals() and sync_engine:
            sync_engine.dispose()

# --- Асинхронная функция для получения соединения ---
async def get_db_connection():
    async with async_engine.connect() as connection:
        yield connection