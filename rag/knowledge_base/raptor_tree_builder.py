"""
RAPTOR Tree Builder - Hierarchical Document Summarization

Creates a tree structure where:
- Level 0: Original semantic chunks
- Level 1: Cluster summaries (10-20 chunks → 1 summary)
- Level 2: Meta-summaries (summaries of summaries)
- Level N: Root summary

This enables retrieval at multiple abstraction levels.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from sklearn.mixture import GaussianMixture
import logging

logger = logging.getLogger(__name__)


@dataclass
class RAPTORNode:
    """A node in the RAPTOR tree."""
    node_id: str
    content: str
    level: int
    embedding: Optional[List[float]] = None
    children: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAPTORTree:
    """Complete RAPTOR tree structure."""
    doc_id: str
    nodes: Dict[str, RAPTORNode]  # node_id -> RAPTORNode
    levels: Dict[int, List[str]]  # level -> list of node_ids
    root_id: Optional[str] = None


class MedicalRAPTORBuilder:
    """
    RAPTOR tree builder adapted for medical documents.
    
    Key adaptations from original raptor.py:
    1. Uses our LLMGateway instead of ChatOpenAI
    2. Uses our EmbeddingService instead of OpenAIEmbeddings
    3. Stores in PostgreSQL/pgvector instead of FAISS
    4. Maintains citation anchoring (child references)
    """
    
    def __init__(
        self,
        llm_gateway,
        embedding_service,
        vector_store,
        max_levels: int = 3,
        min_cluster_size: int = 2
    ):
        self.llm = llm_gateway
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.max_levels = max_levels
        self.min_cluster_size = min_cluster_size
        
        # Collection for RAPTOR trees
        self.RAPTOR_COLLECTION = "raptor_tree"
    
    async def build_tree(
        self,
        chunks: List[Dict[str, Any]],  # From SemanticChunker
        doc_id: str
    ) -> RAPTORTree:
        """
        Build a RAPTOR tree from semantic chunks.
        
        Implements recursive_embed_cluster_summarize from raptor.py L127-177
        
        Args:
            chunks: List of dicts with 'content', 'chunk_id', 'metadata'
            doc_id: Document identifier
            
        Returns:
            RAPTORTree with all nodes and level mappings
        """
        logger.info(f"Building RAPTOR tree for {doc_id} with {len(chunks)} chunks")
        
        tree = RAPTORTree(doc_id=doc_id, nodes={}, levels={})
        
        # Level 0: Original chunks
        current_texts = [c['content'] for c in chunks]
        current_ids = [c['chunk_id'] for c in chunks]
        
        for chunk in chunks:
            node = RAPTORNode(
                node_id=chunk['chunk_id'],
                content=chunk['content'],
                level=0,
                metadata={
                    **chunk.get('metadata', {}),
                    "origin": "original_chunk",
                    "doc_id": doc_id
                }
            )
            tree.nodes[node.node_id] = node
        
        tree.levels[0] = current_ids.copy()
        
        # Build higher levels
        for level in range(1, self.max_levels + 1):
            if len(current_texts) <= 1:
                logger.info(f"Stopping at level {level-1} - only one node remaining")
                break
            
            logger.info(f"Building level {level} from {len(current_texts)} nodes")
            
            # Embed current level texts
            embeddings = self.embedding_service.embed_batch(current_texts)
            embeddings_np = np.array(embeddings)
            
            # Cluster using GMM (from raptor.py L48-52)
            n_clusters = min(10, max(2, len(current_texts) // self.min_cluster_size))
            gm = GaussianMixture(n_components=n_clusters, random_state=42)
            cluster_labels = gm.fit_predict(embeddings_np)
            
            # Create summaries for each cluster
            new_texts = []
            new_ids = []
            tree.levels[level] = []
            
            for cluster_id in range(n_clusters):
                cluster_mask = cluster_labels == cluster_id
                cluster_texts = [t for t, m in zip(current_texts, cluster_mask) if m]
                cluster_ids = [i for i, m in zip(current_ids, cluster_mask) if m]
                
                if not cluster_texts:
                    continue
                
                # Generate summary (from raptor.py L55-63)
                summary = await self._summarize_cluster(cluster_texts, doc_id)
                
                # Create summary node with citation anchoring
                summary_id = f"{doc_id}_L{level}_C{cluster_id}"
                summary_node = RAPTORNode(
                    node_id=summary_id,
                    content=summary,
                    level=level,
                    children=cluster_ids,  # CITATION ANCHORING
                    metadata={
                        "origin": f"summary_of_cluster_{cluster_id}_level_{level}",
                        "doc_id": doc_id,
                        "child_count": len(cluster_ids),
                        "level": level
                    }
                )
                
                # Update parent references for children
                for child_id in cluster_ids:
                    if child_id in tree.nodes:
                        tree.nodes[child_id].parent = summary_id
                
                tree.nodes[summary_id] = summary_node
                tree.levels[level].append(summary_id)
                
                new_texts.append(summary)
                new_ids.append(summary_id)
            
            current_texts = new_texts
            current_ids = new_ids
        
        # Set root
        if current_ids:
            tree.root_id = current_ids[0] if len(current_ids) == 1 else None
        
        logger.info(f"RAPTOR tree complete: {len(tree.nodes)} nodes, {len(tree.levels)} levels")
        return tree
    
    async def _summarize_cluster(
        self,
        texts: List[str],
        doc_id: str
    ) -> str:
        """Generate a medical summary of clustered texts."""
        combined = "\n\n".join(texts)
        
        prompt = f"""Summarize the following medical information concisely.
Preserve all dosage numbers, drug names, and contraindications exactly.

Content:
{combined[:4000]}

Summary:"""
        
        return await self.llm.generate(prompt, content_type="medical")
    
    async def store_tree(self, tree: RAPTORTree) -> int:
        """
        Store RAPTOR tree nodes in PostgreSQL/pgvector.
        
        Returns:
            Number of nodes stored
        """
        documents = []
        for node in tree.nodes.values():
            # Embed node content
            embedding = self.embedding_service.embed_text(node.content)
            node.embedding = embedding
            
            documents.append({
                "id": node.node_id,
                "content": node.content,
                "metadata": {
                    **node.metadata,
                    "level": node.level,
                    "children": ",".join(node.children) if node.children else "",
                    "parent": node.parent or "",
                    "tree_doc_id": tree.doc_id
                }
            })
        
        return self.vector_store.add_medical_documents_batch(
            documents,
            collection_name=self.RAPTOR_COLLECTION
        )
    
    def get_ancestors(self, node_id: str, tree: RAPTORTree) -> List[RAPTORNode]:
        """Get all ancestor nodes (for context expansion)."""
        ancestors = []
        current_id = node_id
        
        while current_id and current_id in tree.nodes:
            node = tree.nodes[current_id]
            if node.parent:
                ancestors.append(tree.nodes[node.parent])
                current_id = node.parent
            else:
                break
        
        return ancestors
    
    def get_descendants(self, node_id: str, tree: RAPTORTree) -> List[RAPTORNode]:
        """Get all descendant nodes (for citation anchoring)."""
        descendants = []
        to_visit = [node_id]
        
        while to_visit:
            current_id = to_visit.pop(0)
            if current_id in tree.nodes:
                node = tree.nodes[current_id]
                for child_id in node.children:
                    if child_id in tree.nodes:
                        descendants.append(tree.nodes[child_id])
                        to_visit.append(child_id)
        
        return descendants

