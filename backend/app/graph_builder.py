import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase, Driver, Session, Transaction
import re

logger = logging.getLogger(__name__)

class KnowledgeGraphBuilder:
    """
    Отвечает за построение и обновление графа знаний в Neo4j для поддержки участников СВО.
    """
    def __init__(self, uri: str, user: str, password: str, db_name: Optional[str] = None):
        """
        Инициализирует драйвер Neo4j.
        Args:
            uri: URI для подключения к Neo4j (e.g., "bolt://localhost:7687").
            user: Имя пользователя Neo4j.
            password: Пароль для Neo4j.
            db_name: Имя базы данных Neo4j (по умолчанию 'neo4j', если None).
        """
        try:
            self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
            self._driver.verify_connectivity()
            self._db_name: str = db_name if db_name is not None else "neo4j"
            logger.info(f"Successfully connected to Neo4j at {uri}, database: '{self._db_name}'")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Закрывает соединение с Neo4j."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed.")

    def _create_nodes_tx(self, tx: Transaction, nodes: List[Dict]):
        """
        Приватный метод для создания/обновления узлов в транзакции.
        Использует MERGE для идемпотентности.
        """
        for node_data in nodes:
            node_id = node_data.get("id")
            node_label = node_data.get("label")
            properties = node_data.get("properties", {})

            if not node_id or not node_label:
                logger.warning(f"Skipping node due to missing id or label: {node_data}")
                continue
            props_to_set = properties.copy()
            if 'id' not in props_to_set and 'node_id' not in props_to_set:
                 props_to_set['id'] = node_id

            if node_label == "Article":
                props_to_set['article_id'] = node_id
            elif node_label == "BenefitType":
                props_to_set['benefit_type_id'] = node_id

            query = (
                f"MERGE (n:{node_label} {{id: $id_param}})\n"
                f"SET n = $props_to_set\n"
                f"SET n.id = $id_param"
            )
            tx.run(query, id_param=node_id, props_to_set=props_to_set)
        logger.info(f"Processed {len(nodes)} nodes.")

    def _create_edges_tx(self, tx: Transaction, edges: List[Dict]):
        """
        Приватный метод для создания ребер в транзакции.
        """
        for edge_data in edges:
            source_id = edge_data.get("source_id")
            target_id = edge_data.get("target_id")
            edge_type = edge_data.get("type")
            properties = edge_data.get("properties", {})

            if not source_id or not target_id or not edge_type:
                logger.warning(f"Skipping edge due to missing source_id, target_id, or type: {edge_data}")
                continue

            if properties:
                final_query = (
                    f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}})\n"
                    f"MERGE (a)-[r:{edge_type}]->(b)\n"
                    f"SET r = $props"
                )
                tx.run(final_query, source_id=source_id, target_id=target_id, props=properties)
            else:
                query = (
                    f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}})\n"
                    f"MERGE (a)-[r:{edge_type}]->(b)"
                )
                tx.run(query, source_id=source_id, target_id=target_id)
        logger.info(f"Processed {len(edges)} edges.")

    def add_nodes_and_edges(self, nodes: List[Dict], edges: List[Dict]):
        """
        Добавляет узлы и ребра в граф Neo4j в рамках одной транзакции.
        """
        if not self._driver:
            logger.error("Driver not initialized. Cannot add data to Neo4j.")
            return

        with self._driver.session(database=self._db_name if hasattr(self, '_db_name') else None) as session:
            try:
                session.execute_write(self._create_nodes_tx, nodes)
                session.execute_write(self._create_edges_tx, edges)
                logger.info("Successfully added/updated nodes and edges.")
            except Exception as e:
                logger.error(f"Error during Neo4j transaction: {e}")

    def get_article_enrichment_data(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает данные для обогащения статьи из графа.
        Включает название статьи, связанные типы льгот и условия.
        """
        if not self._driver:
            logger.error("Neo4j driver not initialized.")
            return None

        try:
            with self._driver.session(database=self._db_name) as session:
                article_info_query = """
                MATCH (a:Article {article_id: $article_id})
                RETURN a.title AS article_title
                """
                article_result = session.run(article_info_query, article_id=article_id).single()
                if not article_result:
                    logger.warning(f"No article found with article_id: {article_id}")
                    return None
                
                article_title = article_result.get("article_title")
                
                benefit_types_query = """
                MATCH (a:Article {article_id: $article_id})-[:RELATES_TO_BENEFIT_TYPE]->(bt:BenefitType)
                RETURN collect(bt.name) AS related_benefit_types
                """
                bt_result = session.run(benefit_types_query, article_id=article_id).single()
                related_benefit_types = bt_result.get("related_benefit_types", []) if bt_result else []
                
                conditions_query = """
                MATCH (a:Article {article_id: $article_id})-[:DEFINES_CONDITION]->(ec:EligibilityCondition)
                MATCH (ec)-[:APPLIES_TO_BENEFIT_TYPE]->(bt:BenefitType)
                RETURN collect({
                    condition: ec.description, 
                    value: ec.value, 
                    benefit_type: bt.name
                }) AS conditions
                """
                cond_result = session.run(conditions_query, article_id=article_id).single()
                conditions = cond_result.get("conditions", []) if cond_result else []
                
                processed_conditions = [
                    cond for cond in conditions 
                    if cond.get("condition") is not None and cond.get("value") is not None
                ]
                
                return {
                    "article_title": article_title,
                    "related_benefit_types": related_benefit_types,
                    "conditions": processed_conditions,
                }
                
        except Exception as e:
            logger.error(f"Error querying graph for article enrichment data (article_id: {article_id}): {e}", exc_info=True)
            return None

    def get_articles_for_benefit_types(self, benefit_types: List[str], limit: int = 10) -> List[str]:
        """
        Получает список ID статей, связанных с указанными типами льгот.
        Сортирует по убыванию уверенности связи (свойства 'confidence' ребра).
        
        Args:
            benefit_types: Список идентификаторов типов льгот
            limit: Максимальное количество статей для возврата
            
        Returns:
            Список canonical_article_id статей, связанных с указанными типами льгот
        """
        if not self._driver:
            logger.error("KnowledgeGraphBuilder: Neo4j driver not available or not properly initialized.")
            return []
            
        if not benefit_types:
            logger.debug("KnowledgeGraphBuilder: No benefit types provided.")
            return []
            
        if not all(isinstance(bt, str) for bt in benefit_types):
            logger.error(f"KnowledgeGraphBuilder: benefit_types must be list of strings, got: {benefit_types}")
            return []

        try:
            db_name_to_use = self._db_name 
            
            with self._driver.session(database=db_name_to_use) as session:
                cleaned_benefit_types_for_log = [re.sub(r'[^\w-]', '', bt) for bt in benefit_types if bt]
                
                query = """
                MATCH (bt:BenefitType)-[r:RELATES_TO_BENEFIT_TYPE]-(a:Article)
                WHERE bt.id IN $benefit_types_param 
                RETURN DISTINCT a.id AS article_id, 
                                COALESCE(r.confidence, 0.0) AS relevance_score 
                ORDER BY relevance_score DESC
                LIMIT $limit_param
                """
                
                params = {"benefit_types_param": benefit_types, "limit_param": limit}
                logger.debug(f"Executing Cypher query: {query} with params: {params}")
                
                result = session.run(query, params)
                articles = [record["article_id"] for record in result]
                
                logger.info(f"Found {len(articles)} articles related to benefit types: {benefit_types} (limit: {limit})")
                return articles
        except Exception as e:
            logger.error(f"Error retrieving articles for benefit types {benefit_types}: {e}", exc_info=True)
            return []