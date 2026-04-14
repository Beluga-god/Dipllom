import os

# --- Пути ---
# Определяем базовую директорию относительно этого файла
CORE_DIR = os.path.dirname(os.path.abspath(__file__)) # .../backend/app/rag_core
APP_DIR = os.path.dirname(CORE_DIR)                   # .../backend/app
BACKEND_DIR = os.path.dirname(APP_DIR)                # .../backend
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)           # .../ (корень проекта, если backend не в корне)

PERSIST_DIR = os.path.join(BACKEND_DIR, "data") # Директория для хранения индекса (backend/data)
PARAMS_LOG_FILE = os.path.join(PERSIST_DIR, "index_params.log") # Файл лога параметров индекса (backend/data/index_params.log)
DOCUMENTS_DIR = os.path.join(BACKEND_DIR, "data") # Директория с документами (backend/data)

# --- Модели ---
HF_EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OLLAMA_LLM_MODEL_NAME = "qwen3:latest" # Замените на вашу модель, если нужно
OLLAMA_BASE_URL = "http://localhost:11434"

# Модель для реранкера
RERANKER_MODEL_NAME = 'DiTy/cross-encoder-russian-msmarco'

# --- Параметры RAG ---
# Количество изначальных кандидатов для ретривера
INITIAL_RETRIEVAL_TOP_K = 60
# Количество кандидатов для поиска С ФИЛЬТРАМИ
FILTERED_RETRIEVAL_TOP_K = 15

# --- Параметры гибридного поиска ---
BM25_TOP_K = 15  # Количество кандидатов от BM25
GRAPH_RETRIEVAL_TOP_K = 10  # Количество кандидатов от графового поиска

# Количество узлов после реранкинга для передачи в LLM
RERANKER_TOP_N = 25

# --- Параметры парсинга и индексации ---
METADATA_PARSER_VERSION = "v2_hierarchical_structure"
MAX_STRUCT_CHUNK_LENGTH = 2500
SECONDARY_CHUNK_SIZE = 812
SECONDARY_CHUNK_OVERLAP = 150
MAX_PDF_PAGES = 1000

# --- Параметры LLM ---
LLM_REQUEST_TIMEOUT = 300.0
LLM_CONTEXT_WINDOW = 100000 

# --- Параметры Реранкера ---
RERANKER_MAX_LENGTH = 512

# --- Общие параметры ---
LOGGING_LEVEL = "INFO"

# --- Neo4j Configuration ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_DATABASE = "neo4j"
NEO4J_PASSWORD = "testpassword123"  # ЗАМЕНИТЕ НА ВАШ ПАРОЛЬ NEO4J

# --- Мультимодальная LLM для анализа изображений ---
OLLAMA_MULTIMODAL_LLM_MODEL_NAME = "qwen2.5vl:latest"
MULTIMODAL_LLM_REQUEST_TIMEOUT = 9000.0

# --- Карта ключевых слов для определения типов льгот (СВО) ---
BENEFIT_KEYWORD_MAP = {
    # Ежемесячные выплаты
    'выплата': 'monthly_payment',
    'деньги': 'monthly_payment',
    'ежемесячно': 'monthly_payment',
    'ежемесячная выплата': 'monthly_payment',
    'единовременная выплата': 'monthly_payment',
    
    # Жилищные льготы
    'жилье': 'housing_benefits',
    'ипотека': 'housing_benefits',
    'квартира': 'housing_benefits',
    'жкх': 'housing_benefits',
    'коммунальные': 'housing_benefits',
    'коммунальные услуги': 'housing_benefits',
    
    # Земельные участки
    'земля': 'land_benefits',
    'участок': 'land_benefits',
    'земельный участок': 'land_benefits',
    'надел': 'land_benefits',
    
    # Медицинская помощь
    'медицина': 'medical_support',
    'лечение': 'medical_support',
    'реабилитация': 'medical_support',
    'больница': 'medical_support',
    'лекарства': 'medical_support',
    'медицинская помощь': 'medical_support',
    
    # Образовательные льготы
    'образование': 'educational_benefits',
    'школа': 'educational_benefits',
    'вуз': 'educational_benefits',
    'поступление': 'educational_benefits',
    'стипендия': 'educational_benefits',
    'детский сад': 'educational_benefits',
    
    # Налоговые льготы
    'налог': 'tax_benefits',
    'вычет': 'tax_benefits',
    'ндфл': 'tax_benefits',
    'налоговый вычет': 'tax_benefits',
    
    # Общие термины
    'льгота': 'monthly_payment',
    'поддержка': 'monthly_payment',
}

# --- Промпты для RAG (адаптированные под СВО) ---

RAG_SYSTEM_PROMPT = """
Вы — помощник участников специальной военной операции и их семей.
Ваша задача — отвечать на вопросы о положенных льготах, выплатах и мерах социальной поддержки.

ОСНОВНЫЕ ПРИНЦИПЫ РАБОТЫ:
1. **Точность и Обоснованность**: Все выводы должны базироваться ИСКЛЮЧИТЕЛЬНО на нормативно-правовых актах, содержащихся в предоставленном КОНТЕКСТЕ.
2. **Ссылочная Целостность**: ОБЯЗАТЕЛЬНО ссылайтесь на конкретные статьи, пункты и подпункты законов и указов (с указанием наименования документа, его номера и даты принятия).
3. **Человеческий язык**: Отвечайте понятным языком, избегая излишней бюрократизации. Объясняйте сложные вещи простыми словами.
4. **Практичность**: Давайте конкретные рекомендации, куда обращаться и какие документы нужны.

СТРОГО ЗАДАННЫЙ ФОРМАТ ОТВЕТА:

1. **Краткий ответ**:
   *   Одним-двумя предложениями дайте прямой ответ на вопрос.

2. **Подробное объяснение**:
   *   Детально объясните, какие льготы или выплаты положены.
   *   Укажите условия получения.
   *   Приведите ссылки на законы (например, "согласно статье 3 Федерального закона №75-ФЗ...").

3. **Необходимые документы**:
   *   Перечислите, какие документы нужны для получения льготы.

4. **Куда обращаться**:
   *   Укажите, в какой орган нужно обращаться (Социальный фонд, МФЦ, военкомат и т.д.).

**ОБЯЗАТЕЛЬНЫЙ ФИНАЛЬНЫЙ БЛОК:**
**ИТОГ: [СООТВЕТСТВУЕТ / НЕ СООТВЕТСТВУЕТ / ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ]**

КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ:
*   Предоставлять информацию, отсутствующую в КОНТЕКСТЕ.
*   Давать советы, не основанные на законах.
*   Игнорировать обязательный финальный блок "ИТОГ:".
"""

RAG_USER_INSTRUCTION_TEMPLATE = """
**Вопрос пользователя:**
{query}

**Информация о пользователе (если указана):**
{case_info}

**Контекст из законов и нормативных актов:**
[Ниже будут размещены фрагменты из законов]

**Задание:**
Ответьте на вопрос пользователя, используя только предоставленный контекст. Дайте четкий, понятный ответ с указанием конкретных льгот, условий получения, необходимых документов и ссылок на законы.
"""

# --- Функция для получения текущих параметров индекса ---
def get_current_index_params():
    return {
        "metadata_parser_version": METADATA_PARSER_VERSION,
        "hf_embed_model_name": HF_EMBED_MODEL_NAME,
        "max_struct_chunk_length": MAX_STRUCT_CHUNK_LENGTH,
        "secondary_chunk_size": SECONDARY_CHUNK_SIZE,
        "secondary_chunk_overlap": SECONDARY_CHUNK_OVERLAP,
    }

# --- Список ключей для кэширования ---
RETRIEVAL_CACHE_CONFIG_KEYS = [
    "INITIAL_RETRIEVAL_TOP_K",
    "FILTERED_RETRIEVAL_TOP_K",
    "BM25_TOP_K",
    "GRAPH_RETRIEVAL_TOP_K",
    "RERANKER_TOP_N",
    "HF_EMBED_MODEL_NAME",
    "RERANKER_MODEL_NAME",
    "BENEFIT_KEYWORD_MAP",
]

# --- Валидация параметров RAG ---
if FILTERED_RETRIEVAL_TOP_K > INITIAL_RETRIEVAL_TOP_K:
    raise ValueError(
        f"FILTERED_RETRIEVAL_TOP_K ({FILTERED_RETRIEVAL_TOP_K}) "
        f"must be <= INITIAL_RETRIEVAL_TOP_K ({INITIAL_RETRIEVAL_TOP_K})"
    )

if RERANKER_TOP_N > INITIAL_RETRIEVAL_TOP_K:
    raise ValueError(
        f"RERANKER_TOP_N ({RERANKER_TOP_N}) "
        f"must be <= INITIAL_RETRIEVAL_TOP_K ({INITIAL_RETRIEVAL_TOP_K})"
    )