# backend/app/rag_core/engine.py
import asyncio
import os
import glob
import json
import logging
import re
from typing import List, Optional, Dict, Any, Tuple, Set
from datetime import datetime, date

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Document,
    QueryBundle
)
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.retrievers import BaseRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.storage.docstore import BaseDocumentStore
from llama_index.llms.ollama import Ollama
from llama_index.core.vector_stores import MetadataFilter, ExactMatchFilter, MetadataFilters
from sentence_transformers import CrossEncoder
import torch
from cachetools import TTLCache

from . import config
from . import document_parser
from ..graph_builder import KnowledgeGraphBuilder
from .document_parser import extract_graph_data_from_document

logging.basicConfig(level=config.LOGGING_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from .loader import load_documents
from .embeddings import JinaV3Embedding

# Импорт моделей Pydantic из родительского пакета app
try:
    from ..models import CaseDataInput
    from ..config_models.config_models import BenefitTypeInfo, BenefitTypeDocuments
except ImportError:
    logger.error("Не удалось импортировать CaseDataInput или модели конфигурации из ..models. Проверьте структуру проекта и PYTHONPATH.", exc_info=True)
    raise RuntimeError("Критическая ошибка импорта: CaseDataInput или модели конфигурации не найдены. Проверьте структуру проекта.")


class GraphRetriever(BaseRetriever):
    """
    Custom retriever to fetch relevant TextNode objects based on graph search results.
    """
    def __init__(
        self,
        graph_builder: KnowledgeGraphBuilder,
        docstore: BaseDocumentStore, 
        all_nodes_list: List[TextNode], 
        top_k: int,
        benefit_keyword_map: Dict[str, str],
        benefit_types_config_list: List[BenefitTypeInfo],
        **kwargs: Any,
    ):
        self._graph_builder = graph_builder
        self._docstore = docstore
        self._all_nodes_list = all_nodes_list 
        self._top_k = top_k
        self._benefit_keyword_map = benefit_keyword_map
        self._benefit_types_config_list = benefit_types_config_list
        self._sentence_splitter = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=50,
        )
        super().__init__(**kwargs)
        logger.info(f"GraphRetriever initialized with top_k={top_k}")

    def _extract_benefit_types_from_query_sync(self, query_str: str) -> List[str]:
        """Извлекает возможные типы льгот из текста запроса."""
        matched_benefit_types = set()
        query_lower = query_str.lower()
        
        for keyword, benefit_type in self._benefit_keyword_map.items():
            if keyword.lower() in query_lower:
                matched_benefit_types.add(benefit_type)
                
        for bt_info in self._benefit_types_config_list:
            if bt_info.id.lower() in query_lower or (bt_info.display_name and bt_info.display_name.lower() in query_lower):
                matched_benefit_types.add(bt_info.id)
                
        return list(matched_benefit_types)

    def _get_nodes_by_canonical_article_ids_sync(self, article_ids: List[str]) -> List[TextNode]:
        """По списку ID статей возвращает соответствующие TextNode."""
        matched_nodes = []
        id_set = set(article_ids)
        
        if self._docstore:
            for node_id, node in self._docstore.docs.items():
                if isinstance(node, TextNode) and node.metadata.get('canonical_article_id') in id_set:
                    matched_nodes.append(node)
            
            logger.debug(f"Found {len(matched_nodes)} nodes in docstore by canonical_article_id")
            if len(matched_nodes) == len(id_set):
                return matched_nodes
        
        if len(matched_nodes) < len(id_set) and self._all_nodes_list:
            found_ids = {node.metadata.get('canonical_article_id') for node in matched_nodes}
            missing_ids = id_set - found_ids
            
            for node in self._all_nodes_list:
                if node.metadata.get('canonical_article_id') in missing_ids:
                    matched_nodes.append(node)
                    missing_ids.remove(node.metadata.get('canonical_article_id'))
                    if not missing_ids:
                        break
            
            logger.debug(f"After checking all nodes, found {len(matched_nodes)} nodes by canonical_article_id")
        
        return matched_nodes[:self._top_k] if len(matched_nodes) > self._top_k else matched_nodes

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        return self._retrieve_sync(query_bundle)

    def _retrieve_sync(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        if not self._graph_builder or not self._all_nodes_list:
            logger.warning("GraphRetriever: graph_builder or nodes list is None, returning empty list")
            return []
        
        query_text = query_bundle.query_str
        
        benefit_types = self._extract_benefit_types_from_query_sync(query_text)
        if not benefit_types:
            logger.debug(f"GraphRetriever: No benefit types found in query, returning empty list")
            return []
            
        logger.debug(f"GraphRetriever: Found benefit types in query: {benefit_types}")
        
        article_ids = self._graph_builder.get_articles_for_benefit_types(
            benefit_types=benefit_types, 
            limit=self._top_k
        )
        
        if not article_ids:
            logger.debug(f"GraphRetriever: No articles found for benefit types {benefit_types}")
            return []
            
        logger.debug(f"GraphRetriever: Found {len(article_ids)} articles for benefit types {benefit_types}")
        
        nodes = self._get_nodes_by_canonical_article_ids_sync(article_ids)
        
        node_with_scores: List[NodeWithScore] = []
        for i, node in enumerate(nodes):
            relevance_score = 1.0 - (i / (len(nodes) + 1))
            
            node.metadata["retrieval_source"] = "graph_retriever"
            node.metadata["benefit_types_matched"] = ",".join(benefit_types)
            
            node_with_scores.append(NodeWithScore(node=node, score=relevance_score))
            
        logger.info(f"GraphRetriever: Returning {len(node_with_scores)} nodes with scores")
        return node_with_scores

    async def _aretrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        return await asyncio.to_thread(self._retrieve_sync, query_bundle)


def calculate_age(birth_date: date) -> int:
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age

class SVORAG:
    """
    Класс, инкапсулирующий логику RAG для помощи участникам СВО.
    Отвечает за загрузку данных, создание/загрузку индекса,
    инициализацию моделей и обработку запросов.
    """
    def __init__(self):
        self.config = config
        self.llm: Optional[Ollama] = None
        self.embed_model: Optional[JinaV3Embedding] = None
        self.reranker: Optional[CrossEncoder] = None
        self.index: Optional[VectorStoreIndex] = None
        self.graph_builder: Optional[KnowledgeGraphBuilder] = None
        self.retrieval_cache = TTLCache(maxsize=100, ttl=3600)
        
        self.all_parsed_nodes: Optional[List[TextNode]] = None
        self.bm25_retriever: Optional[BM25Retriever] = None
        self.graph_retriever: Optional[GraphRetriever] = None

        self.benefit_types_config: Optional[List[BenefitTypeInfo]] = None
        self.document_requirements_config: Optional[Dict[str, BenefitTypeDocuments]] = None
        
        logger.info("SVORAG synchronous __init__ completed.")

    async def async_init(self, 
                         benefit_types_config: List[BenefitTypeInfo], 
                         document_requirements_config: Dict[str, BenefitTypeDocuments]):
        """Асинхронная инициализация компонентов RAG."""
        logger.info("SVORAG async_init called...")
        
        self.benefit_types_config = benefit_types_config
        self.document_requirements_config = document_requirements_config
        if self.benefit_types_config:
            logger.info(f"{len(self.benefit_types_config)} benefit types loaded into RAG engine.")
        if self.document_requirements_config:
            logger.info(f"{len(self.document_requirements_config)} document requirement sets loaded into RAG engine.")

        self.llm = await self._initialize_llm_async()
        self.embed_model = await self._initialize_embedder_async()
        self.reranker = await self._initialize_reranker_async()
        
        try:
            self.graph_builder = await asyncio.to_thread(
                KnowledgeGraphBuilder,
                uri=self.config.NEO4J_URI,
                user=self.config.NEO4J_USER,
                password=self.config.NEO4J_PASSWORD,
                db_name=self.config.NEO4J_DATABASE
            )
            logger.info("KnowledgeGraphBuilder initialized via to_thread.")
        except Exception as e:
            logger.error(f"Failed to initialize KnowledgeGraphBuilder: {e}", exc_info=True)
            logger.warning("SVORAG will operate without KnowledgeGraphBuilder.")
            self.graph_builder = None

        self.index = await self._load_or_create_index_async()
        logger.info("SVORAG async_init completed successfully.")

    async def _initialize_llm_async(self) -> Ollama:
        try:
            llm = Ollama(
                model=self.config.OLLAMA_LLM_MODEL_NAME,
                base_url=self.config.OLLAMA_BASE_URL,
                request_timeout=self.config.LLM_REQUEST_TIMEOUT,
            )
            logger.info(f"LLM initialized asynchronously. Model: {self.config.OLLAMA_LLM_MODEL_NAME}")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize LLM asynchronously: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize LLM asynchronously: {e}") from e

    async def _initialize_embedder_async(self) -> JinaV3Embedding:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        try:
            embed_model = await asyncio.to_thread(
                JinaV3Embedding,
                model_name=self.config.HF_EMBED_MODEL_NAME,
                device=device,
            )
            logger.info(f"Embeddings model initialized asynchronously: {self.config.HF_EMBED_MODEL_NAME} on {device}")
            return embed_model
        except Exception as e:
            logger.error(f"Failed to initialize JinaV3Embedding asynchronously: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize JinaV3Embedding asynchronously: {e}") from e

    async def _initialize_reranker_async(self) -> Optional[CrossEncoder]:
        if not self.config.RERANKER_MODEL_NAME:
            logger.warning("Reranker model name is not configured. Skipping reranker initialization.")
            return None
        try:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            reranker_model = await asyncio.to_thread(
                CrossEncoder,
                self.config.RERANKER_MODEL_NAME, 
                max_length=self.config.RERANKER_MAX_LENGTH,
                device=device,
            )
            logger.info(f"Reranker model initialized asynchronously: {self.config.RERANKER_MODEL_NAME} on {device}")
            return reranker_model
        except Exception as e:
            logger.error(f"Failed to initialize Reranker model '{self.config.RERANKER_MODEL_NAME}' asynchronously: {e}", exc_info=True)
            logger.warning("Proceeding without reranker due to asynchronous initialization error.")
            return None

    async def _check_and_handle_reindex_async(self, force: bool = False) -> bool:
        logger.debug("Checking if reindexing is required (async)...")
        current_params = self.config.get_current_index_params()
        
        current_params["bm25_top_k"] = self.config.BM25_TOP_K
        current_params["graph_retrieval_top_k"] = self.config.GRAPH_RETRIEVAL_TOP_K
        
        params_log_file = self.config.PARAMS_LOG_FILE
        persist_dir = self.config.PERSIST_DIR
        force_reindex = force

        if not await asyncio.to_thread(os.path.exists, params_log_file):
            logger.warning(f"Parameter log file {params_log_file} not found. Forcing reindex.")
            force_reindex = True
        else:
            try:
                def read_params_sync():
                    with open(params_log_file, 'r') as f:
                        return json.load(f)
                logged_params = await asyncio.to_thread(read_params_sync)
                
                if "bm25_top_k" not in logged_params or "graph_retrieval_top_k" not in logged_params:
                    logger.warning("Hybrid search parameters not found in saved params. Forcing reindex.")
                    force_reindex = True
                elif current_params != logged_params:
                    logger.warning("Index parameters have changed. Forcing reindex.")
                    force_reindex = True
                else:
                    logger.info("Index parameters match. No reindex needed based on parameters.")
            except Exception as e:
                logger.error(f"Error reading parameter log file {params_log_file}: {e}. Forcing reindex.", exc_info=True)
                force_reindex = True

        if force_reindex:
            logger.info(f"Reindexing required. Removing old index files from {persist_dir} (async)...")
            
            def remove_files_sync():
                deleted_count = 0
                index_files = glob.glob(os.path.join(persist_dir, "*store.json"))
                for f_path in index_files:
                    try:
                        os.remove(f_path)
                        deleted_count += 1
                    except OSError as e_del:
                        logger.error(f"Error deleting file {f_path}: {e_del}", exc_info=True)
                
                deleted_log = False
                if os.path.exists(params_log_file):
                    try:
                        os.remove(params_log_file)
                        deleted_log = True
                    except OSError as e_log_del:
                        logger.error(f"Error deleting log file {params_log_file}: {e_log_del}", exc_info=True)
                return deleted_count + (1 if deleted_log else 0)
            
            total_deleted = await asyncio.to_thread(remove_files_sync)
            if total_deleted > 0:
                logger.info(f"Deleted {total_deleted} old index-related file(s) (async).")
            else:
                logger.info("No old index files found to delete (async).")
        return force_reindex

    async def _write_index_params_async(self):
        params_log_file = self.config.PARAMS_LOG_FILE
        persist_dir = self.config.PERSIST_DIR
        current_params = self.config.get_current_index_params()
        
        current_params["bm25_top_k"] = self.config.BM25_TOP_K
        current_params["graph_retrieval_top_k"] = self.config.GRAPH_RETRIEVAL_TOP_K
        
        try:
            await asyncio.to_thread(os.makedirs, persist_dir, exist_ok=True)
            def write_params_sync():
                with open(params_log_file, 'w') as f:
                    json.dump(current_params, f, indent=4)
            await asyncio.to_thread(write_params_sync)
            logger.info(f"Index parameters saved to {params_log_file} (async)")
        except Exception as e:
            logger.error(f"Error writing index parameters to {params_log_file} (async): {e}", exc_info=True)

    async def _parse_documents_async(self, graph_builder_instance: Optional[KnowledgeGraphBuilder]) -> List[TextNode]:
        logger.info(f"Starting _parse_documents_async. Will use graph_builder: {graph_builder_instance is not None}")
        
        raw_documents = await asyncio.to_thread(load_documents, self.config.DOCUMENTS_DIR)
        all_parsed_nodes_list: List[TextNode] = [] 
        count_docs_with_graph_data = 0

        if not raw_documents:
            logger.warning(f"No documents found in {self.config.DOCUMENTS_DIR}. Index will be empty.")
            self.all_parsed_nodes = all_parsed_nodes_list
            logger.info(f"Finished parsing all documents. Total nodes: 0. Extracted graph data for 0 documents.")
            return all_parsed_nodes_list

        current_benefit_type_map = {bt.id: bt.display_name for bt in self.benefit_types_config} if self.benefit_types_config else {}
        if not current_benefit_type_map:
            logger.warning("benefit_types_config is not loaded or empty. Graph data extraction might be affected.")

        for doc in raw_documents:
            try:
                logger.debug(f"Parsing document: {doc.metadata.get('file_name', 'Unknown')} with document_parser (async)")
                parsed_nodes_for_doc = await asyncio.to_thread(
                    document_parser.parse_document_hierarchical,
                    doc 
                )
                all_parsed_nodes_list.extend(parsed_nodes_for_doc)
                logger.debug(f"Parsed {len(parsed_nodes_for_doc)} nodes from {doc.metadata.get('file_name', 'Unknown')}")

                if graph_builder_instance and parsed_nodes_for_doc: 
                    logger.debug(f"Extracting graph data for {doc.metadata.get('file_name', 'Unknown')} (async)")
                    
                    nodes_data, edges_data = await asyncio.to_thread(
                        document_parser.extract_graph_data_from_document,
                        parsed_nodes_for_doc,       
                        doc.metadata,               
                        self.config.BENEFIT_KEYWORD_MAP, 
                        self.benefit_types_config    
                    )
                    if nodes_data or edges_data:
                        logger.debug(f"Graph data extracted: {len(nodes_data)} nodes, {len(edges_data)} edges. Adding to Neo4j (async)...")
                        await asyncio.to_thread(graph_builder_instance.add_nodes_and_edges, nodes_data, edges_data)
                        count_docs_with_graph_data += 1
                    else:
                        logger.debug("No graph data extracted from document.")
            except Exception as e_parse:
                doc_name = doc.metadata.get('file_name', '[Unknown Document]')
                logger.error(f"Failed to parse or extract graph data from document '{doc_name}': {e_parse}", exc_info=True)
                continue
        
        self.all_parsed_nodes = all_parsed_nodes_list
        logger.info(f"Finished parsing all documents. Total nodes: {len(self.all_parsed_nodes)}. Extracted graph data for {count_docs_with_graph_data} documents.")
        return self.all_parsed_nodes

    async def _load_or_create_index_async(self) -> VectorStoreIndex:
        persist_dir = self.config.PERSIST_DIR
        force_reindex = await self._check_and_handle_reindex_async()

        if not force_reindex and await asyncio.to_thread(os.path.exists, os.path.join(persist_dir, "docstore.json")):
            logger.info(f"Loading existing index from {persist_dir} (async)...")
            try:
                storage_context = await asyncio.to_thread(StorageContext.from_defaults, persist_dir=persist_dir)
                index = await asyncio.to_thread(load_index_from_storage, storage_context, embed_model=self.embed_model)
                logger.info("Successfully loaded index from storage (async).")
                
                if self.all_parsed_nodes is None:
                    logger.info("Loading all_parsed_nodes for BM25 and GraphRetriever...")
                    self.all_parsed_nodes = await self._parse_documents_async(graph_builder_instance=self.graph_builder)
                
                await self._initialize_hybrid_retrievers(index)
                
                return index
            except Exception as e_load:
                logger.error(f"Failed to load index from {persist_dir}: {e_load}. Forcing reindex (async).", exc_info=True)
                force_reindex = True
        
        logger.info("Creating new index (async)...")
        if force_reindex and self.graph_builder:
            logger.info("Force reindex: Cleaning Neo4j database before parsing documents (async)...")
            await asyncio.to_thread(self._clean_neo4j_database_sync, self.graph_builder)

        if self.all_parsed_nodes is None: 
            logger.info("self.all_parsed_nodes is None, calling _parse_documents_async now.")
            self.all_parsed_nodes = await self._parse_documents_async(graph_builder_instance=self.graph_builder)

        if not self.all_parsed_nodes:
            logger.error("Cannot create index: No text nodes available after parsing (async).")
            raise RuntimeError("Index creation failed: No documents were successfully parsed into nodes.")

        logger.info(f"Creating VectorStoreIndex with {len(self.all_parsed_nodes)} nodes (async)...")
        index = await asyncio.to_thread(VectorStoreIndex, self.all_parsed_nodes, embed_model=self.embed_model)
        logger.info("VectorStoreIndex created (async). Persisting to disk...")
        await asyncio.to_thread(index.storage_context.persist, persist_dir=persist_dir)
        await self._write_index_params_async()
        
        await self._initialize_hybrid_retrievers(index)
        
        return index
    
    async def _initialize_hybrid_retrievers(self, index: VectorStoreIndex) -> None:
        if self.all_parsed_nodes: 
            logger.info(f"Initializing BM25Retriever with {len(self.all_parsed_nodes)} nodes...")
            self.bm25_retriever = await asyncio.to_thread(
                BM25Retriever.from_defaults,
                nodes=self.all_parsed_nodes,
                similarity_top_k=self.config.BM25_TOP_K
            )
            logger.info("BM25Retriever initialized.")
        else:
            logger.warning("Could not initialize BM25Retriever as no parsed nodes are available.")

        if self.graph_builder and index and index.docstore and self.all_parsed_nodes:
            logger.info("Initializing GraphRetriever...")
            self.graph_retriever = GraphRetriever(
                graph_builder=self.graph_builder,
                docstore=index.docstore,
                all_nodes_list=self.all_parsed_nodes,
                top_k=self.config.GRAPH_RETRIEVAL_TOP_K,
                benefit_keyword_map=self.config.BENEFIT_KEYWORD_MAP,
                benefit_types_config_list=self.benefit_types_config
            )
            logger.info("GraphRetriever initialized.")
        else:
            logger.warning("Could not initialize GraphRetriever due to missing graph_builder, index.docstore, or all_parsed_nodes.")

    def _clean_neo4j_database_sync(self, graph_builder: KnowledgeGraphBuilder) -> None:
        logger.info("Cleaning Neo4j database (sync wrapper for async call)...")
        try:
            if hasattr(graph_builder, 'clean_database') and callable(getattr(graph_builder, 'clean_database')):
                graph_builder.clean_database()
                logger.info("Neo4j database cleaned successfully (sync wrapper).")
            else:
                logger.warning("Method clean_database not found in KnowledgeGraphBuilder, using alternative cleaning method.")
                with graph_builder._driver.session(database=graph_builder._db_name) as session:
                    session.run("MATCH (n) DETACH DELETE n")
                logger.info("Neo4j database cleaned using direct Cypher query.")
        except Exception as e:
            logger.error(f"Error cleaning Neo4j database (sync wrapper): {e}", exc_info=True)
            logger.warning("Failed to clean Neo4j database (sync wrapper).")

    async def _get_retriever_async(self, filters: Optional[List[MetadataFilter]] = None, similarity_top_k: Optional[int] = None) -> BaseRetriever:
        if not self.index:
            logger.error("Index is not initialized. Cannot get retriever.")
            raise RuntimeError("RAG Index not available.")
        actual_top_k = similarity_top_k if similarity_top_k is not None else self.config.INITIAL_RETRIEVAL_TOP_K
        retriever = await asyncio.to_thread(
            self.index.as_retriever,
            similarity_top_k=actual_top_k,
            filters=MetadataFilters(filters=filters) if filters else None
        )
        return retriever

    async def _apply_filters_async(self, query_bundle: QueryBundle, benefit_type: Optional[str]) -> Tuple[List[MetadataFilter], bool]:
        return await asyncio.to_thread(self._apply_filters_sync, query_bundle, benefit_type)

    def _apply_filters_sync(self, query_bundle: QueryBundle, benefit_type: Optional[str]) -> Tuple[List[MetadataFilter], bool]:
        filters = []
        filters_applied = False

        if not self.document_requirements_config:
            logger.warning("Document requirements config not loaded in RAG, cannot apply filters based on it.")
            return filters, filters_applied

        if benefit_type and benefit_type in self.document_requirements_config:
            filters_applied = True 
            logger.debug(f"Benefit type '{benefit_type}' found in document_requirements_config. Setting filters_applied=True.")
        
        if filters:
            logger.info(f"Applied {len(filters)} metadata filters for benefit type '{benefit_type}'.")
        elif filters_applied:
            logger.info(f"Filters considered for benefit type '{benefit_type}', but no specific rules were added.")
        else:
            logger.debug(f"No specific metadata filters applied for benefit type '{benefit_type}'. Will use general retrieval.")
            
        return filters, filters_applied

    async def _retrieve_nodes_async(self, query_bundle: QueryBundle, benefit_type: Optional[str], effective_config: Dict) -> List[NodeWithScore]:
        cache_config_list = []
        if hasattr(self.config, 'RETRIEVAL_CACHE_CONFIG_KEYS'):
            for key in self.config.RETRIEVAL_CACHE_CONFIG_KEYS:
                if hasattr(self.config, key):
                    cache_config_list.append((key, getattr(self.config, key)))
                elif key in effective_config:
                     cache_config_list.append((key, effective_config[key]))
        else:
            logger.warning("RETRIEVAL_CACHE_CONFIG_KEYS not found in config. Cache key might be incomplete.")

        cache_config_subset = dict(cache_config_list)

        if self.benefit_types_config:
            cache_config_subset['benefit_types_config_digest'] = json.dumps([bt.model_dump() for bt in self.benefit_types_config], sort_keys=True, default=str)
        if self.document_requirements_config:
            cache_config_subset['document_requirements_config_digest'] = json.dumps({k: v.model_dump() for k, v in self.document_requirements_config.items()}, sort_keys=True, default=str)

        cache_key_config_json = json.dumps(cache_config_subset, sort_keys=True, default=str)
        cache_key = (query_bundle.query_str, benefit_type, cache_key_config_json)
        
        logger.debug(f"Retrieving nodes for query: '{query_bundle.query_str[:100]}...', benefit_type: {benefit_type}, config_hash: {hash(cache_key_config_json)}")

        cached_result = self.retrieval_cache.get(cache_key)
        if cached_result:
            logger.debug("Retrieved from cache.")
            return cached_result
        
        logger.debug("Cache miss. Performing actual hybrid retrieval.")

        filters, filters_applied = await self._apply_filters_async(query_bundle, benefit_type)
        
        vector_retrieval_top_k = effective_config.get('FILTERED_RETRIEVAL_TOP_K') if filters_applied else effective_config.get('INITIAL_RETRIEVAL_TOP_K')
        if vector_retrieval_top_k is None:
            logger.warning("Vector retrieval_top_k not found in config. Defaulting to 10.")
            vector_retrieval_top_k = 10

        bm25_retrieval_top_k = effective_config.get('BM25_TOP_K', 10)
        graph_retrieval_top_k = effective_config.get('GRAPH_RETRIEVAL_TOP_K', 5)

        vector_retriever = await self._get_retriever_async(filters=filters, similarity_top_k=vector_retrieval_top_k)
        vector_nodes: List[NodeWithScore] = []
        if hasattr(vector_retriever, 'aretrieve'):
            vector_nodes = await vector_retriever.aretrieve(query_bundle.query_str)
        else:
            vector_nodes = await asyncio.to_thread(vector_retriever.retrieve, query_bundle.query_str)
        logger.debug(f"Retrieved {len(vector_nodes)} nodes from vector search.")

        bm25_nodes: List[NodeWithScore] = []
        if self.bm25_retriever:
            bm25_nodes = await asyncio.to_thread(self.bm25_retriever.retrieve, query_bundle.query_str)
            logger.debug(f"Retrieved {len(bm25_nodes)} nodes from BM25 search (top_k={bm25_retrieval_top_k}).")
        else:
            logger.warning("BM25 retriever not initialized. Skipping BM25 search.")

        graph_nodes: List[NodeWithScore] = []
        if self.graph_retriever:
            graph_nodes = await self.graph_retriever.aretrieve(query_bundle)
            logger.debug(f"Retrieved {len(graph_nodes)} nodes from graph search (top_k={graph_retrieval_top_k}).")
        else:
            logger.warning("Graph retriever not initialized. Skipping graph search.")
            
        all_retrieved_nodes: Dict[str, NodeWithScore] = {}

        def add_nodes_to_combined(nodes_list: List[NodeWithScore], source_priority: int):
            for nws in nodes_list:
                node_id = nws.node.id_
                if node_id not in all_retrieved_nodes:
                    nws.node.metadata['retrieval_source'] = f"{source_priority}_{type(nws.node).__name__}"
                    all_retrieved_nodes[node_id] = nws

        add_nodes_to_combined(graph_nodes, 1)
        add_nodes_to_combined(vector_nodes, 2)
        add_nodes_to_combined(bm25_nodes, 3)
        
        combined_nodes_list = list(all_retrieved_nodes.values())
        logger.info(f"Total unique nodes after combining Vector, BM25, and Graph search: {len(combined_nodes_list)}")

        self.retrieval_cache[cache_key] = combined_nodes_list
        logger.debug(f"Stored combined result in cache for query: '{query_bundle.query_str[:100]}...', benefit_type: {benefit_type}, config_hash: {hash(cache_key_config_json)}")
        return combined_nodes_list

    async def _rerank_nodes_async(self, query_bundle: QueryBundle, nodes: List[NodeWithScore], effective_config: Dict) -> Tuple[List[NodeWithScore], float]:
        reranker_top_n = effective_config.get('RERANKER_TOP_N', len(nodes))
        if not self.reranker or not nodes:
            return nodes[:reranker_top_n], 0.0
        
        query_and_docs = [(query_bundle.query_str, node.get_content()) for node in nodes]
        rerank_scores = await asyncio.to_thread(self.reranker.predict, query_and_docs, convert_to_tensor=False, batch_size=16)
        reranked_node_with_scores: List[NodeWithScore] = []
        for i, score in enumerate(rerank_scores):
            reranked_node_with_scores.append(NodeWithScore(node=nodes[i].node, score=float(score)))
        reranked_node_with_scores.sort(key=lambda x: x.score, reverse=True)
        top_n_reranked = reranked_node_with_scores[:reranker_top_n]
        highest_rerank_score = top_n_reranked[0].score if top_n_reranked else 0.0
        return top_n_reranked, float(highest_rerank_score)

    async def _build_prompt_async(self, query_text: str, context_nodes: List[NodeWithScore], case_data: Optional[CaseDataInput], disability_info: Optional[dict]) -> str:
        return await asyncio.to_thread(self._build_prompt_sync, query_text, context_nodes, case_data, disability_info)

    def _build_prompt_sync(self, query_text: str, context_nodes: List[NodeWithScore], case_data: Optional[CaseDataInput], disability_info: Optional[dict]) -> str:
        context_str_parts = []
        for i, node_obj in enumerate(context_nodes):
            doc_content = node_obj.get_content().strip()
            source_file = node_obj.metadata.get("file_name", "N/A")
            source_page = node_obj.metadata.get("page_label", "N/A")
            
            context_str_parts.append(f"### Фрагмент документа {i+1} (Источник: {source_file}, Стр. {source_page}, релевантность: {node_obj.score:.4f}) ###")
            context_str_parts.append(doc_content)
            context_str_parts.append("### Конец фрагмента ###\n")
        
        context_string = "\n".join(context_str_parts)

        system_prompt = self.config.RAG_SYSTEM_PROMPT
        user_instruction_template = self.config.RAG_USER_INSTRUCTION_TEMPLATE
        
        case_details_str = ""
        if case_data:
            pd = case_data.personal_data
            full_name_parts = [pd.last_name, pd.first_name, pd.middle_name]
            full_name = " ".join(filter(None, full_name_parts))
            age = calculate_age(pd.birth_date)
            
            benefit_type_display = case_data.pension_type
            if self.benefit_types_config:
                for bt_info in self.benefit_types_config:
                    if bt_info.id == case_data.pension_type:
                        benefit_type_display = bt_info.display_name
                        break
            else:
                logger.warning("Benefit types config not loaded in RAG, cannot get display name for prompt.")

            case_details_str += f"Тип запрашиваемой льготы: {benefit_type_display}.\n"
            case_details_str += f"Возраст заявителя: {age} лет.\n"
            if case_data.work_experience:
                total_years_val = case_data.work_experience.calculated_total_years
                total_years_str = f"{total_years_val:.1f}" if total_years_val is not None else "не указан"
                case_details_str += f"Общий стаж: {total_years_str} лет.\\n"
                
                if case_data.work_experience.records:
                    case_details_str += "Периоды работы:\\n"
            case_details_str += f"Пенсионные баллы (ИПК): {case_data.pension_points if case_data.pension_points is not None else 'не указаны'}.\n"
            if case_data.benefits:
                case_details_str += f"Заявленные льготы: {', '.join(case_data.benefits)}.\n"

        if disability_info:
            group_raw = disability_info.get('group')
            group_display = self.config.DISABILITY_GROUP_MAP.get(group_raw, group_raw if group_raw else "не указана")
            dis_date_str = disability_info.get('date', "не указана")
            if isinstance(dis_date_str, date):
                dis_date_str = dis_date_str.strftime('%d.%m.%Y')

            case_details_str += f"Наличие инвалидности: Группа {group_display}, дата установления {dis_date_str}.\n"

        if not case_details_str:
            case_details_str = "Дополнительная информация о пользователе отсутствует в запросе."
        
        user_instruction = user_instruction_template.format(
            case_info=case_details_str,
            query=query_text
        )
        
        final_prompt = f"{system_prompt}\n\nКонтекст извлеченный из документов:\n{context_string}\n\n{user_instruction}"
        return final_prompt

    async def query(self, 
              case_description: str, 
              benefit_type: Optional[str] = None, 
              disability_info: Optional[dict] = None,
              case_data: Optional[CaseDataInput] = None,
              config_override: Optional[dict] = None
              ) -> Tuple[str, float]:
        logger.info(f"Received RAG query. Benefit type: {benefit_type}, Query: '{case_description[:50]}...'")
        if not self.index or not self.llm:
            logger.error("RAG engine not fully initialized (index or LLM missing).")
            return "Ошибка: RAG движок не инициализирован.", 0.0

        base_config_vars = {k: v for k, v in vars(self.config).items() if not callable(v) and not isinstance(v, type)}
        
        current_override = config_override or {}
        effective_config = {**base_config_vars, **current_override}
        if current_override:
            effective_config['_config_override_applied'] = True 

        query_bundle = QueryBundle(query_str=case_description)
        
        try:
            retrieved_nodes = await self._retrieve_nodes_async(query_bundle, benefit_type, effective_config)
            if not retrieved_nodes:
                logger.warning("No nodes retrieved from RAG. Aborting query.")
                return "Не удалось найти релевантную информацию по вашему запросу.", 0.0

            if self.graph_builder and effective_config.get('USE_GRAPH_ENRICHMENT', True):
                logger.debug("Attempting to enrich nodes with graph data.")
                retrieved_nodes = await self._enrich_nodes_with_graph_data_async(retrieved_nodes)
                logger.debug(f"Nodes after graph enrichment: {len(retrieved_nodes)}")

            ranked_nodes, confidence_score_from_reranker = await self._rerank_nodes_async(query_bundle, retrieved_nodes, effective_config)
            if not ranked_nodes:
                logger.warning("No nodes left after reranking. Aborting query.")
                return "Не удалось найти достаточно релевантной информации после дополнительной фильтрации.", 0.0
            
            final_prompt = await self._build_prompt_async(case_description, ranked_nodes, case_data, disability_info)
            
            logger.debug(f"Final prompt for LLM (first 300 chars): {final_prompt[:300]}...")
            
            original_temperature = self.llm.temperature
            self.llm.temperature = 0.1
            logger.info(f"Calling LLM with temporarily set temperature: {self.llm.temperature}")
            
            completion_response = await self.llm.acomplete(final_prompt)

            self.llm.temperature = original_temperature
            logger.debug(f"Restored LLM temperature to {self.llm.temperature}")
            
            llm_output_text = completion_response.text
            
            logger.debug(f"LLM raw response: {llm_output_text[:300]}...")
            cleaned_response_text = self._clean_llm_response(llm_output_text)
            final_confidence_score = confidence_score_from_reranker 
            logger.info(f"RAG query successful. Final confidence: {final_confidence_score:.4f}")
            return cleaned_response_text, final_confidence_score

        except Exception as e:
            logger.error(f"Error during RAG query processing: {e}", exc_info=True)
            return f"Ошибка обработки запроса в RAG: {str(e)}", 0.0

    def _clean_llm_response(self, text: str) -> str:
        text = re.sub(r"^```json\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
        text = re.sub(r"<think>.*?</think>\n?", "", text, flags=re.DOTALL)
        text = text.strip()
        
        if "ИТОГ:" not in text:
            logger.warning("LLM response does not contain 'ИТОГ:'. This might indicate an incomplete or malformed response.")
        return text

    async def _enrich_nodes_with_graph_data_async(self, nodes: List[NodeWithScore]) -> List[NodeWithScore]:
        if not self.graph_builder:
            return nodes
        enriched_nodes = []
        for node_with_score in nodes:
            doc_node = node_with_score.node
            article_id_for_graph = doc_node.metadata.get('canonical_article_id') 
            if article_id_for_graph:
                try:
                    enrichment_data = await asyncio.to_thread(self.graph_builder.get_article_enrichment_data, article_id_for_graph)
                    if enrichment_data:
                        original_content = doc_node.get_content()
                        enriched_content = original_content + "\n\n--- Дополнительная информация из графа знаний ---\n"
                        if enrichment_data.get('related_benefit_types'):
                            enriched_content += f"Связанные типы льгот: {', '.join(enrichment_data['related_benefit_types'])}\n"
                        if enrichment_data.get('law_source'):
                            enriched_content += f"Источник: Закон {enrichment_data['law_source']}\n"
                        doc_node.set_content(enriched_content)
                        doc_node.metadata['graph_enriched'] = True 
                except Exception as e_graph_enrich:
                    logger.warning(f"Failed to enrich node for article_id '{article_id_for_graph}' from graph: {e_graph_enrich}", exc_info=True)
            enriched_nodes.append(node_with_score) 
        return enriched_nodes

    async def force_rebuild_index_async(self):
        logger.info("Starting forced rebuild of the RAG index...")
        await self._check_and_handle_reindex_async(force=True)
        self.all_parsed_nodes = None
        self.bm25_retriever = None
        self.graph_retriever = None
        self.retrieval_cache.clear()
        try:
            self.index = await self._load_or_create_index_async()
            logger.info("Forced RAG index rebuild completed successfully.")
        except Exception as e:
            logger.error(f"Error during forced RAG index rebuild: {e}", exc_info=True)
            raise RuntimeError(f"Failed to rebuild RAG index: {e}") from e