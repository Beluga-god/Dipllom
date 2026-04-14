from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class DocumentDetail(BaseModel):
    """Модель для описания требуемых документов."""
    id: str
    name: str
    description: str
    is_critical: bool
    condition_text: Optional[str] = None
    ocr_type: Optional[str] = None


class BenefitTypeDocuments(BaseModel):
    """Модель для списка документов, требуемых для определенного типа льготы."""
    documents: List[DocumentDetail]


class BenefitTypeInfo(BaseModel):
    """Модель для информации о типе льготы."""
    id: str
    display_name: str
    description: str


class BenefitTypesConfig(BaseModel):
    """Модель для списка всех типов льгот."""
    benefit_types: List[BenefitTypeInfo]
    

class DocumentRequirementsConfig(BaseModel):
    """Модель для требований к документам по всем типам льгот."""
    requirements: Dict[str, BenefitTypeDocuments]
    
    
def load_benefit_types_config(data: List[Dict[str, Any]]) -> List[BenefitTypeInfo]:
    """
    Загружает и валидирует конфигурацию типов льгот.
    
    Args:
        data: Данные из JSON-файла benefit_types.json
        
    Returns:
        Список валидированных объектов BenefitTypeInfo
    """
    return [BenefitTypeInfo(**item) for item in data]


def load_document_requirements_config(data: Dict[str, Dict[str, Any]]) -> Dict[str, BenefitTypeDocuments]:
    """
    Загружает и валидирует конфигурацию требований к документам.
    
    Args:
        data: Данные из JSON-файла document_requirements.json
        
    Returns:
        Словарь с требованиями к документам для каждого типа льготы
    """
    return {benefit_type_id: BenefitTypeDocuments(**reqs) for benefit_type_id, reqs in data.items()}