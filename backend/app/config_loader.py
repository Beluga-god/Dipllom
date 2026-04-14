import json
import os
from pathlib import Path
from typing import Dict, List, Optional
import logging
from .config_models.config_models import (
    BenefitTypeInfo, 
    BenefitTypeDocuments,
    load_benefit_types_config,
    load_document_requirements_config
)


logger = logging.getLogger(__name__)

# Определение путей к конфигурационным файлам
APP_DIR = Path(__file__).resolve().parent
CONFIG_DATA_DIR = APP_DIR.parent / "config_data"
BENEFIT_TYPES_FILE = CONFIG_DATA_DIR / "benefit_types.json"
DOCUMENT_REQUIREMENTS_FILE = CONFIG_DATA_DIR / "document_requirements.json"

# Для отладки: добавляем глобальную переменную, чтобы избежать повторной загрузки
_config_cache = None

def load_configuration() -> tuple[List[BenefitTypeInfo], Dict[str, BenefitTypeDocuments]]:
    """
    Загружает конфигурации типов льгот и требований к документам из JSON-файлов.
    
    Returns:
        Кортеж из (список типов льгот, словарь требований к документам)
    
    Raises:
        FileNotFoundError: Если файлы конфигурации не найдены
        json.JSONDecodeError: Если файлы содержат некорректный JSON
        ValueError: Если данные в файлах не соответствуют схеме
    """
    global _config_cache
    if _config_cache:
        logger.info("Using cached configuration.")
        return _config_cache

    logger.info(f"Attempting to load configuration files.")
    logger.info(f"APP_DIR: {APP_DIR}")
    logger.info(f"CONFIG_DATA_DIR: {CONFIG_DATA_DIR}")
    logger.info(f"BENEFIT_TYPES_FILE path: {BENEFIT_TYPES_FILE.resolve()}")
    logger.info(f"DOCUMENT_REQUIREMENTS_FILE path: {DOCUMENT_REQUIREMENTS_FILE.resolve()}")

    try:
        # Загрузка типов льгот
        if not BENEFIT_TYPES_FILE.exists():
            logger.error(f"Файл конфигурации типов льгот не найден: {BENEFIT_TYPES_FILE.resolve()}")
            raise FileNotFoundError(f"Файл конфигурации типов льгот не найден: {BENEFIT_TYPES_FILE.resolve()}")
            
        with open(BENEFIT_TYPES_FILE, "r", encoding="utf-8") as f:
            benefit_types_content = f.read()
            benefit_types_data = json.loads(benefit_types_content)
        benefit_types = load_benefit_types_config(benefit_types_data)
        logger.info(f"Successfully loaded and parsed {BENEFIT_TYPES_FILE.name}")
        
        # Загрузка требований к документам
        if not DOCUMENT_REQUIREMENTS_FILE.exists():
            logger.error(f"Файл конфигурации требований к документам не найден: {DOCUMENT_REQUIREMENTS_FILE.resolve()}")
            raise FileNotFoundError(f"Файл конфигурации требований к документам не найден: {DOCUMENT_REQUIREMENTS_FILE.resolve()}")
            
        with open(DOCUMENT_REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            doc_requirements_content = f.read()
            doc_requirements_data = json.loads(doc_requirements_content)
        doc_requirements = load_document_requirements_config(doc_requirements_data)
        logger.info(f"Successfully loaded and parsed {DOCUMENT_REQUIREMENTS_FILE.name}")
        
        # Проверка соответствия типов льгот и требований к документам
        benefit_type_ids = {bt.id for bt in benefit_types}
        doc_requirement_ids = set(doc_requirements.keys())
        
        # Проверка на наличие типов льгот, для которых нет требований к документам
        missing_doc_requirements = benefit_type_ids - doc_requirement_ids
        if missing_doc_requirements:
            logger.warning(f"Для следующих типов льгот не заданы требования к документам: {missing_doc_requirements}")
            
        # Проверка на наличие требований к документам для несуществующих типов льгот
        unknown_benefit_types = doc_requirement_ids - benefit_type_ids
        if unknown_benefit_types:
            logger.warning(f"Заданы требования к документам для несуществующих типов льгот: {unknown_benefit_types}")
        
        _config_cache = (benefit_types, doc_requirements)
        return benefit_types, doc_requirements
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка в формате JSON файла конфигурации: {e}")
        raise
    except ValueError as e:
        logger.error(f"Ошибка в структуре данных конфигурации: {e}")
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при загрузке конфигурации: {e}")
        raise 

def get_standard_document_names_from_config(
    doc_requirements: Dict[str, BenefitTypeDocuments]
) -> List[str]:
    """Извлекает уникальные имена документов из конфигурации document_requirements."""
    unique_doc_names: set[str] = set()
    if not doc_requirements:
        return []
    for _, benefit_docs in doc_requirements.items():
        for doc_detail in benefit_docs.documents:
            if doc_detail.name:
                unique_doc_names.add(doc_detail.name)
    return sorted(list(unique_doc_names))