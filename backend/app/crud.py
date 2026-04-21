import json
from sqlalchemy import insert, select, update, delete, text
from sqlalchemy.ext.asyncio import AsyncConnection
from datetime import datetime, timedelta
import sqlite3

from .database import cases_table, async_engine, ocr_tasks_table, users_table
from .models import CaseDataInput, UserCreate, OtherDocumentData, WorkExperience, DisabilityInfo, PersonalData
from typing import List, Dict, Any, Optional, Union
from .auth import get_password_hash


# Вспомогательная функция для безопасного дампа Pydantic моделей
def pydantic_to_json_str(data: Optional[Union[Dict, List, PersonalData, WorkExperience, DisabilityInfo, OtherDocumentData]]) -> Optional[str]:
    """Безопасно преобразует Pydantic модель или словарь в JSON строку.
    Использует default=str для сериализации date/datetime объектов."""
    if data is None:
        return None
    if isinstance(data, list):
        # Обрабатываем список моделей
        return json.dumps([item.model_dump() if hasattr(item, 'model_dump') else item for item in data], ensure_ascii=False, default=str)
    if hasattr(data, 'model_dump'):
        # Обрабатываем одну модель
        return json.dumps(data.model_dump(), ensure_ascii=False, default=str)
    # Для обычных словарей
    return json.dumps(data, ensure_ascii=False, default=str)


async def create_case(
    conn: AsyncConnection,
    case_data: CaseDataInput
):
    """Сохраняет данные дела, ошибки, тип поддержки и данные об инвалидности."""
    insert_stmt = insert(cases_table).values(
        personal_data=pydantic_to_json_str(case_data.personal_data),
        errors=json.dumps([], ensure_ascii=False, default=str),
        benefit_type=case_data.benefit_type,
        disability=pydantic_to_json_str(case_data.disability),
        work_experience=pydantic_to_json_str(case_data.work_experience),
        pension_points=case_data.pension_points,
        benefits=json.dumps(case_data.benefits, ensure_ascii=False, default=str) if case_data.benefits else None,
        documents=json.dumps(case_data.submitted_documents, ensure_ascii=False, default=str) if case_data.submitted_documents else None,
        has_incorrect_document=case_data.has_incorrect_document,
        final_status="PROCESSING",
        other_documents_extracted_data=pydantic_to_json_str(case_data.other_documents_extracted_data)
    )
    result = await conn.execute(insert_stmt)
    await conn.commit()
    return result.lastrowid


async def get_cases(conn: AsyncConnection, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """Получает список дел из базы данных."""
    select_stmt = select(cases_table).offset(skip).limit(limit)
    result = await conn.execute(select_stmt)
    rows = result.fetchall()

    cases = []
    for row in rows:
        case_data = row._mapping
        created_at_value = case_data.get("created_at")
        cases.append({
            "id": case_data["id"],
            "personal_data": json.loads(case_data["personal_data"]),
            "errors": json.loads(case_data["errors"]),
            "benefit_type": case_data["benefit_type"],
            "disability": json.loads(case_data["disability"]) if case_data["disability"] else None,
            "work_experience": json.loads(case_data["work_experience"]) if case_data["work_experience"] else None,
            "pension_points": case_data["pension_points"],
            "benefits": json.loads(case_data["benefits"]) if case_data["benefits"] else None,
            "documents": json.loads(case_data["documents"]) if case_data["documents"] else None,
            "has_incorrect_document": case_data["has_incorrect_document"],
            "final_status": case_data["final_status"],
            "final_explanation": case_data["final_explanation"],
            "rag_confidence": case_data["rag_confidence"],
            "created_at": created_at_value,
            "other_documents_extracted_data": json.loads(case_data["other_documents_extracted_data"]) if case_data.get("other_documents_extracted_data") else None
        })
    return cases


async def get_case_by_id(conn: AsyncConnection, case_id: int) -> Optional[Dict[str, Any]]:
    """Получает одно дело по ID из базы данных."""
    select_stmt = select(cases_table).where(cases_table.c.id == case_id)
    result = await conn.execute(select_stmt)
    row = result.fetchone()

    if row:
        case_data = row._mapping
        created_at_value = case_data.get("created_at")
        return {
            "id": case_data["id"],
            "personal_data": json.loads(case_data["personal_data"]),
            "errors": json.loads(case_data["errors"]),
            "benefit_type": case_data["benefit_type"],
            "disability": json.loads(case_data["disability"]) if case_data["disability"] else None,
            "work_experience": json.loads(case_data["work_experience"]) if case_data["work_experience"] else None,
            "pension_points": case_data["pension_points"],
            "benefits": json.loads(case_data["benefits"]) if case_data["benefits"] else None,
            "documents": json.loads(case_data["documents"]) if case_data["documents"] else None,
            "has_incorrect_document": case_data["has_incorrect_document"],
            "final_status": case_data["final_status"],
            "final_explanation": case_data["final_explanation"],
            "rag_confidence": case_data["rag_confidence"],
            "created_at": created_at_value,
            "other_documents_extracted_data": json.loads(case_data["other_documents_extracted_data"]) if case_data.get("other_documents_extracted_data") else None
        }
    return None


async def update_case_results(
    conn: AsyncConnection,
    case_id: int,
    final_status: str,
    final_explanation: str,
    rag_confidence: float
) -> bool:
    """Обновляет результаты анализа дела после фоновой обработки."""
    try:
        update_stmt = update(cases_table).where(
            cases_table.c.id == case_id
        ).values(
            final_status=final_status,
            final_explanation=final_explanation,
            rag_confidence=rag_confidence,
            updated_at=datetime.now()
        )
        result = await conn.execute(update_stmt)
        await conn.commit()
        return result.rowcount > 0
    except Exception as e:
        raise e


async def update_case_status_and_error(
    conn: AsyncConnection,
    case_id: int,
    status: str,
    explanation: Optional[str] = None
) -> bool:
    """Обновляет статус и объяснение дела, например, при ошибке обработки."""
    try:
        update_values = {
            "final_status": status,
            "updated_at": datetime.now()
        }

        if explanation is not None:
            update_values["final_explanation"] = explanation

        update_stmt = update(cases_table).where(
            cases_table.c.id == case_id
        ).values(**update_values)

        result = await conn.execute(update_stmt)
        await conn.commit()
        return result.rowcount > 0
    except Exception as e:
        raise e


# ---- Функции для работы с OCR задачами ----

async def create_ocr_task(
    conn: AsyncConnection,
    task_id: str,
    document_type: str,
    filename: Optional[str] = None,
    ttl_hours: int = 24
) -> str:
    """Создает новую OCR задачу в базе данных."""
    expire_at = datetime.now() + timedelta(hours=ttl_hours)

    insert_stmt = insert(ocr_tasks_table).values(
        id=task_id,
        document_type=document_type,
        status="PROCESSING",
        filename=filename,
        expire_at=expire_at
    )

    try:
        await conn.execute(insert_stmt)
        await conn.commit()
        return task_id
    except Exception as e:
        raise ValueError(f"Не удалось создать OCR задачу: {e}")


async def update_ocr_task_result(
    conn: AsyncConnection,
    task_id: str,
    status: str,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None
) -> bool:
    """Обновляет результат OCR задачи в базе данных."""
    update_values = {
        "status": status,
        "updated_at": datetime.now()
    }

    if data is not None:
        update_values["data"] = json.dumps(data, ensure_ascii=False, default=str)

    if error is not None:
        update_values["error"] = json.dumps(error, ensure_ascii=False, default=str)

    update_stmt = update(ocr_tasks_table).where(
        ocr_tasks_table.c.id == task_id
    ).values(**update_values)

    result = await conn.execute(update_stmt)
    await conn.commit()
    return result.rowcount > 0


async def get_ocr_task(conn: AsyncConnection, task_id: str) -> Optional[Dict[str, Any]]:
    """Получает OCR задачу по ID."""
    select_stmt = select(ocr_tasks_table).where(ocr_tasks_table.c.id == task_id)
    result = await conn.execute(select_stmt)
    row = result.fetchone()

    if not row:
        return None

    task_data = dict(row._mapping)

    if task_data.get("data"):
        try:
            task_data["data"] = json.loads(task_data["data"])
        except json.JSONDecodeError:
            task_data["data"] = None

    if task_data.get("error"):
        try:
            task_data["error"] = json.loads(task_data["error"])
        except json.JSONDecodeError:
            task_data["error"] = None

    return task_data


async def delete_expired_ocr_tasks(conn: AsyncConnection) -> int:
    """Удаляет просроченные OCR задачи из базы данных."""
    now = datetime.now()
    delete_stmt = delete(ocr_tasks_table).where(
        ocr_tasks_table.c.expire_at < now
    )

    result = await conn.execute(delete_stmt)
    await conn.commit()
    return result.rowcount


async def get_ocr_tasks_stats(conn: AsyncConnection) -> Dict[str, Any]:
    """Собирает статистику по статусам OCR задач."""
    status_counts_query_str = """
    SELECT status, COUNT(*) as count
    FROM ocr_tasks
    GROUP BY status
    """
    total_count_query_str = "SELECT COUNT(*) as total FROM ocr_tasks"

    pending_tasks_query_str = """
    SELECT COUNT(*) as pending_count
    FROM ocr_tasks
    WHERE status = 'PROCESSING' AND (expire_at IS NULL OR expire_at > datetime('now'))
    """

    expired_tasks_query_str = """
    SELECT COUNT(*) as expired_count
    FROM ocr_tasks
    WHERE status = 'PROCESSING' AND expire_at IS NOT NULL AND expire_at <= datetime('now')
    """

    try:
        status_counts_result = await conn.execute(text(status_counts_query_str))
        stats = {row[0]: row[1] for row in status_counts_result.fetchall()}

        total_count_result = await conn.execute(text(total_count_query_str))
        total_count = total_count_result.scalar_one_or_none() or 0
        stats["total"] = total_count

        pending_count_result = await conn.execute(text(pending_tasks_query_str))
        pending_count = pending_count_result.scalar_one_or_none() or 0
        stats["pending"] = pending_count

        expired_count_result = await conn.execute(text(expired_tasks_query_str))
        expired_count = expired_count_result.scalar_one_or_none() or 0
        stats["expired_processing"] = expired_count

        possible_statuses = ["PROCESSING", "COMPLETED", "FAILED"]
        for status_key in possible_statuses:
            if status_key not in stats:
                stats[status_key] = 0

        return stats
    except Exception as e:
        raise ValueError(f"Не удалось получить статистику по OCR задачам: {e}")


# ---- Функции для работы с пользователями (для аутентификации) ----

async def get_user_by_username(conn: AsyncConnection, username: str) -> Optional[Dict[str, Any]]:
    """Получает пользователя по имени пользователя."""
    query = select(users_table).where(users_table.c.username == username)
    result = await conn.execute(query)
    row = result.fetchone()
    return dict(row._mapping) if row else None


async def create_db_user(conn: AsyncConnection, user_data: UserCreate) -> Dict[str, Any]:
    """Создает нового пользователя в БД."""
    hashed_password = get_password_hash(user_data.password)
    insert_stmt = insert(users_table).values(
        username=user_data.username,
        hashed_password=hashed_password,
        role=user_data.role,
        is_active=user_data.is_active if user_data.is_active is not None else True
    )
    result = await conn.execute(insert_stmt)
    await conn.commit()

    created_user_id = result.lastrowid
    if created_user_id is None:
        query = select(users_table).where(users_table.c.username == user_data.username)
    else:
        query = select(users_table).where(users_table.c.id == created_user_id)

    new_user_row = await conn.execute(query)
    fetched_row = new_user_row.fetchone()
    if fetched_row:
        return dict(fetched_row._mapping)
    else:
        raise ValueError(f"Не удалось получить пользователя {user_data.username} после создания.")