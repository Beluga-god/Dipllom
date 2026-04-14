import re
import logging
import os
from typing import List, Dict, Tuple, Optional, Any, Set

from llama_index.core import Document
from llama_index.core.schema import TextNode
from llama_index.core.node_parser import SimpleNodeParser

# Импортируем конфиг для доступа к параметрам парсинга
from . import config
# Импортируем Pydantic модели для типизации конфигурации
from ..config_models.config_models import BenefitTypeInfo

logger = logging.getLogger(__name__)

# Глобальный маппинг для атрибутов законов о поддержке СВО
LAW_ATTRIBUTES_MAP = {
    "FZ_75_2022.rtf": {
        "title": "Федеральный закон 'О внесении изменений в отдельные законодательные акты Российской Федерации' (о поддержке участников СВО)",
        "number": "75-ФЗ",
        "adoption_date": "2022-04-07",
    },
    "Ukaz_232_2022.pdf": {
        "title": "Указ Президента РФ 'О дополнительных мерах социальной поддержки отдельных категорий граждан в связи с проведением специальной военной операции'",
        "number": "Указ №232",
        "adoption_date": "2022-05-05",
    },
    "Ukaz_RB_176.pdf": {
        "title": "Указ Главы Республики Бурятия 'О дополнительных гарантиях участникам специальной военной операции'",
        "number": "Указ №176",
        "adoption_date": "2022-08-23",
    },
    "Postanovlenie_RB_339.pdf": {
        "title": "Постановление Правительства Республики Бурятия 'Об удостоверении Член семьи участника специальной военной операции'",
        "number": "Постановление №339",
        "adoption_date": "2023-06-15",
    },
}

def get_law_attributes(file_name: str) -> Dict[str, Optional[str]]:
    """
    Возвращает атрибуты закона на основе имени файла.
    """
    base_name = os.path.basename(file_name)
    return LAW_ATTRIBUTES_MAP.get(base_name, {
        "title": None,
        "number": None,
        "adoption_date": None
    })

def normalize_article_number(raw_text: Optional[str], is_main_article_header: bool = False) -> Optional[str]:
    """
    Нормализует текстовое представление номера статьи/пункта для использования в ID.
    """
    if not raw_text:
        return None

    processed_text = raw_text.strip()
    if is_main_article_header:
        match_article = re.search(r"Статья\s+(\d+(?:\.\d+)?)\s*(?:\.|Пункт|Часть|$)?", processed_text, re.IGNORECASE)
        if match_article:
            return match_article.group(1)
    else:
        match_point = re.match(r"^\s*(\d+(?:\.\d+)?)(?:\.|\))(?=\s|$)", processed_text)
        if match_point:
            return match_point.group(1).replace('.', '-')

    logger.debug(f"Could not normalize article/point number from: '{raw_text}' (is_main_article_header={is_main_article_header})")
    return None

def parse_document_hierarchical(doc: Document) -> List[TextNode]:
    """
    Разбивает текст одного документа иерархически.
    """
    file_name = doc.metadata.get("file_name", "unknown_file")
    text = doc.get_content()
    logger.debug(f"Parsing document: {file_name} (length: {len(text)}) using hierarchical parser v={config.METADATA_PARSER_VERSION}")

    final_nodes = []
    header_patterns = {
        'article': r"^\s*(Статья)\s+(\d+(?:\.\d+)*)\s*(?:\.|\s|$)",
        'chapter': r"^\s*(Глава)\s+([\dIVXLCDM]+(?:\.[\dIVXLCDM]+)*)\s*(?:\.|\s|$)",
        'section': r"^\s*(Раздел)\s+([\dIVXLCDM]+(?:\.[\dIVXLCDM]+)*)\s*(?:\.|\s|$)",
        'point': r"^\s*(\d{1,3}(?:\.\d{1,2})*)\s*(?:\.(?![\d])|\))(?=\s|$)",
    }
    
    all_matches = []
    for pattern_name, pattern_regex in header_patterns.items():
        for match in re.finditer(pattern_regex, text, re.MULTILINE | re.IGNORECASE):
            all_matches.append({
                "match_obj": match,
                "type": pattern_name,
                "start": match.start(),
                "end": match.end(),
                "content": match.group(2) if pattern_name in ['article', 'chapter', 'section'] else match.group(1)
            })
    
    all_matches.sort(key=lambda x: x["start"])

    start_pos = 0
    current_metadata = {
        "file_name": file_name, 
        "article": None, 
        "chapter": None, 
        "section": None, 
        "point": None, 
        "header": "Начало документа"
    }
    
    secondary_parser = SimpleNodeParser.from_defaults(
        chunk_size=config.SECONDARY_CHUNK_SIZE,
        chunk_overlap=config.SECONDARY_CHUNK_OVERLAP,
        paragraph_separator="\n\n\n"
    )

    struct_chunk_index = 0

    for i, match_info in enumerate(all_matches):
        match = match_info["match_obj"]
        header_type = match_info["type"]
        
        end_pos = match.start()
        struct_chunk_text = text[start_pos:end_pos].strip()
        full_header_text = match.group(0).strip()
        effective_header = current_metadata.get("header", "Начало документа")
        
        if struct_chunk_text:
            if len(struct_chunk_text) > config.MAX_STRUCT_CHUNK_LENGTH:
                logger.debug(f"Structural chunk {struct_chunk_index} ('{effective_header}') too long ({len(struct_chunk_text)} chars). Applying secondary splitting.")
                sub_docs = [Document(text=struct_chunk_text, metadata=current_metadata.copy())]
                sub_nodes = secondary_parser.get_nodes_from_documents(sub_docs, show_progress=False)
                
                for sub_idx, node in enumerate(sub_nodes):
                    node_id = f"{file_name}_struct_{struct_chunk_index}_sub_{sub_idx}"
                    if not isinstance(node, TextNode):
                        node = TextNode(
                            text=node.get_content(), 
                            id_=node_id, 
                            metadata=node.metadata
                        )
                    else:
                        node.id_ = node_id
                        
                    node.metadata["parent_header"] = effective_header
                    final_nodes.append(node)
            else:
                node_id = f"{file_name}_struct_{struct_chunk_index}_full"
                final_nodes.append(TextNode(
                    text=struct_chunk_text,
                    id_=node_id,
                    metadata=current_metadata.copy()
                ))
            struct_chunk_index += 1

        current_metadata["header"] = full_header_text 
        
        if header_type == "article":
            current_metadata["article"] = full_header_text
            article_number_normalized = match_info["content"]
            if article_number_normalized:
                base_file_name = os.path.basename(current_metadata.get("file_name", file_name))
                canonical_id = f"{base_file_name.replace('.pdf', '').replace('.rtf', '')}_Ст_{article_number_normalized.replace('.', '-')}"
                current_metadata["canonical_article_id"] = canonical_id
            else:
                current_metadata["canonical_article_id"] = None
            current_metadata["point"] = None
        elif header_type == "chapter":
            current_metadata["chapter"] = full_header_text
            current_metadata["article"] = None
            current_metadata["canonical_article_id"] = None
            current_metadata["point"] = None
        elif header_type == "section":
            current_metadata["section"] = full_header_text
            current_metadata["chapter"] = None
            current_metadata["article"] = None
            current_metadata["canonical_article_id"] = None
            current_metadata["point"] = None
        elif header_type == "point": 
            current_metadata["point"] = full_header_text

        start_pos = match.end()

    last_struct_chunk_text = text[start_pos:].strip()
    if last_struct_chunk_text:
        last_header = current_metadata.get("header", "Конец документа")
        if len(last_struct_chunk_text) > config.MAX_STRUCT_CHUNK_LENGTH:
            logger.debug(f"Last structural chunk ('{last_header}') too long ({len(last_struct_chunk_text)} chars). Applying secondary splitting.")
            sub_docs = [Document(text=last_struct_chunk_text, metadata=current_metadata.copy())]
            sub_nodes = secondary_parser.get_nodes_from_documents(sub_docs, show_progress=False)
            for sub_idx, node in enumerate(sub_nodes):
                node_id = f"{file_name}_struct_{struct_chunk_index}_end_sub_{sub_idx}"
                if not isinstance(node, TextNode):
                     node = TextNode(
                         text=node.get_content(), 
                         id_=node_id, 
                         metadata=node.metadata
                     )
                else:
                    node.id_ = node_id
                node.metadata["parent_header"] = last_header
                final_nodes.append(node)
        else:
            node_id = f"{file_name}_struct_{struct_chunk_index}_end_full"
            final_nodes.append(TextNode(
                text=last_struct_chunk_text,
                id_=node_id,
                metadata=current_metadata.copy()
            ))

    logger.debug(f"Parsed {len(final_nodes)} nodes from document {file_name}.")
    return final_nodes 

def find_benefit_type_keywords(text: str, benefit_keyword_map: Dict[str, str], 
                              log_results: bool = False) -> List[Tuple[str, str, str]]:
    """
    Поиск ключевых слов для определения типов льгот в тексте.
    """
    results = []
    
    if not text:
        return results
    
    text_lowercase = text.lower()
    text_normalized = re.sub(r'[^\w\s]', ' ', text_lowercase)
    text_normalized = re.sub(r'\s+', ' ', text_normalized).strip()
    
    if log_results:
        logger.debug(f"Анализ текста (первые 100 символов): '{text[:100]}...'")
    
    for keyword, benefit_type_id in benefit_keyword_map.items():
        keyword_lower = keyword.lower()
        regex_pattern = r'\b' + re.escape(keyword_lower) + r'\b'
        
        if re.search(regex_pattern, text_lowercase, re.IGNORECASE):
            if log_results:
                match_text = re.search(regex_pattern, text_lowercase, re.IGNORECASE).group(0)
                logger.info(f"Найдено точное совпадение для типа льготы '{benefit_type_id}': '{match_text}'")
            results.append((benefit_type_id, keyword, 'exact_match'))
            continue
        
        if len(keyword_lower.split()) > 1 and keyword_lower in text_lowercase:
            if log_results:
                logger.info(f"Найдено совпадение составной фразы для типа льготы '{benefit_type_id}': '{keyword_lower}'")
            results.append((benefit_type_id, keyword, 'phrase_match'))
            continue
        
        words = keyword_lower.split()
        if any(len(word) > 4 for word in words):
            word_stems = []
            for word in words:
                if len(word) > 4:
                    if word.endswith(("ая", "ий", "ой", "ых", "их", "ые", "ое")):
                        stem = word[:-2]
                    elif word.endswith(("а", "я", "е", "и", "ы", "у", "ю", "ь")):
                        stem = word[:-1]
                    else:
                        stem = word
                    word_stems.append(stem)
                else:
                    word_stems.append(word)
            
            stem_pattern = r'\b' + r'.*?\b'.join(re.escape(stem) for stem in word_stems) + r'.*?\b'
            if re.search(stem_pattern, text_normalized):
                match_text = re.search(stem_pattern, text_normalized).group(0)
                if log_results:
                    logger.info(f"Найдено сходство по основе слов для типа льготы '{benefit_type_id}': '{match_text}'")
                results.append((benefit_type_id, keyword, 'stem_match'))
                continue
    
    unique_results = []
    seen_benefit_types = set()
    
    for bt_id, keyword, method in results:
        if bt_id not in seen_benefit_types:
            unique_results.append((bt_id, keyword, method))
            seen_benefit_types.add(bt_id)
    
    return unique_results

def extract_graph_data_from_document(
    parsed_nodes: List[TextNode], 
    doc_metadata: Dict[str, Any], 
    benefit_keyword_map: Dict[str, str],
    benefit_types_config_list: List[BenefitTypeInfo]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Извлекает узлы и ребра для графа знаний из списка распарсенных TextNode документа.
    """
    nodes = []
    edges = []
    processed_graph_node_ids = set()

    file_name = doc_metadata.get("file_name", "unknown_file")
    file_path = doc_metadata.get("file_path", file_name)
    law_id_simple = file_name.replace(".pdf", "").replace(".rtf", "")
    
    law_attrs = get_law_attributes(file_name)

    if law_id_simple not in processed_graph_node_ids:
        law_node = {
            "id": law_id_simple, 
            "label": "Law",
            "properties": {
                "law_id": law_id_simple,
                "title": law_attrs.get("title", f"Закон {law_id_simple}"),
                "number": law_attrs.get("number"),
                "adoption_date": law_attrs.get("adoption_date"),
                "file_path": file_path 
            }
        }
        nodes.append(law_node)
        processed_graph_node_ids.add(law_id_simple)

    if benefit_types_config_list:
        for bt_info in benefit_types_config_list:
            if bt_info.id not in processed_graph_node_ids:
                nodes.append({
                    "id": bt_info.id,
                    "label": "BenefitType", 
                    "properties": {
                        "benefit_type_id": bt_info.id,
                        "name": bt_info.display_name, 
                        "description": bt_info.description,
                        "id": bt_info.id
                    }
                })
                processed_graph_node_ids.add(bt_info.id)
                logger.debug(f"Ensured BenefitType node exists: {bt_info.id} with name '{bt_info.display_name}'")
    else:
        logger.warning("benefit_types_config_list is empty or None. No BenefitType nodes will be created from it.")

    target_article_id_for_demo_condition = f"{law_id_simple}_Ст_8"
    demo_condition_created = False

    for text_node in parsed_nodes:
        chunk_text = text_node.get_content()
        
        current_canonical_article_id = text_node.metadata.get("canonical_article_id")
        article_title_from_meta = text_node.metadata.get("article")

        if current_canonical_article_id and current_canonical_article_id not in processed_graph_node_ids:
            default_number_text = f"Статья {current_canonical_article_id.split('_Ст_')[-1].replace('-', '.')}"
            
            article_node_props = {
                "article_id": current_canonical_article_id,
                "number_text": article_title_from_meta if article_title_from_meta else default_number_text,
            }
            
            if article_title_from_meta and len(chunk_text) < 500:
                lines = chunk_text.split('\n')
                if lines[0].strip().startswith(article_title_from_meta):
                    article_full_title_match = re.match(r"^Статья\s+\d+(?:\.\d+)?\s*\.?\s*(.*)", lines[0].strip())
                    if article_full_title_match and article_full_title_match.group(1):
                        article_node_props["title"] = article_full_title_match.group(1).strip()

            article_node = {
                "id": current_canonical_article_id,
                "label": "Article",
                "properties": article_node_props
            }
            nodes.append(article_node)
            processed_graph_node_ids.add(current_canonical_article_id)
            logger.debug(f"Created Article node: {current_canonical_article_id} with props: {article_node_props}")

            edges.append({
                "source_id": law_id_simple,
                "target_id": current_canonical_article_id,
                "type": "CONTAINS_ARTICLE",
                "properties": {}
            })
            logger.debug(f"Created edge Law '{law_id_simple}' -> Article '{current_canonical_article_id}'")

        if current_canonical_article_id:
            benefit_type_matches = find_benefit_type_keywords(
                chunk_text, 
                benefit_keyword_map=benefit_keyword_map,
                log_results=True
            )
            
            for benefit_type_id, keyword, method in benefit_type_matches:
                logger.info(f"Keyword '{keyword}' FOUND (method: {method}) in chunk for Article ID {current_canonical_article_id}. Attempting to create edge to BenefitType '{benefit_type_id}'.")
                edge_exists = any(
                    edge.get("source_id") == current_canonical_article_id and \
                    edge.get("target_id") == benefit_type_id and \
                    edge.get("type") == "RELATES_TO_BENEFIT_TYPE"
                    for edge in edges
                )
                if not edge_exists:
                    edges.append({
                        "source_id": current_canonical_article_id,
                        "target_id": benefit_type_id,
                        "type": "RELATES_TO_BENEFIT_TYPE",
                        "properties": {
                            "keyword": keyword,
                            "match_method": method,
                            "confidence": 0.9 if method == 'exact_match' else 0.8 if method == 'phrase_match' else 0.7
                        }
                    })
                    logger.debug(f"Created edge Article '{current_canonical_article_id}' -> BenefitType '{benefit_type_id}' based on keyword '{keyword}' (method: {method})")
                else:
                    logger.debug(f"Edge Article '{current_canonical_article_id}' -> BenefitType '{benefit_type_id}' already exists. Skipping.")
    
    final_node_count = len([n for n in nodes if n['id'] in processed_graph_node_ids])
    logger.info(f"Extracted {final_node_count} unique nodes and {len(edges)} edges from document {file_name}.")
    
    return nodes, edges