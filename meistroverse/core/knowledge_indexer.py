import json
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sentence_transformers import SentenceTransformer
import faiss
from sqlalchemy.orm import Session

from meistroverse.database import get_db, Knowledge, ProjectLog, TaskLog, Task
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeIndexer:
    """Semantic search and indexing for project knowledge"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
        self.knowledge_ids = []  # Track which knowledge entries correspond to which index positions
        
    def encode_text(self, text: str) -> np.ndarray:
        """Convert text to embedding vector"""
        return self.model.encode([text], normalize_embeddings=True)[0]
        
    def add_knowledge(
        self,
        title: str,
        content: str,
        content_type: str,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        db: Session = None
    ) -> Knowledge:
        """Add knowledge to the database and index"""
        if db is None:
            db = next(get_db())
            
        # Create embedding
        embedding = self.encode_text(f"{title} {content}")
        embedding_str = json.dumps(embedding.tolist())
        
        # Create knowledge entry
        knowledge = Knowledge(
            title=title,
            content=content,
            content_type=content_type,
            tags=tags or [],
            embedding=embedding_str,
            source=source or "manual"
        )
        
        db.add(knowledge)
        db.commit()
        db.refresh(knowledge)
        
        # Add to FAISS index
        self.index.add(embedding.reshape(1, -1))
        self.knowledge_ids.append(knowledge.id)
        
        logger.info(f"Added knowledge entry {knowledge.id}: {title}")
        return knowledge
        
    def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        content_type: Optional[str] = None,
        db: Session = None
    ) -> List[Tuple[Knowledge, float]]:
        """Search for similar knowledge entries"""
        if db is None:
            db = next(get_db())
            
        # Encode query
        query_embedding = self.encode_text(query)
        
        # Search in FAISS index
        scores, indices = self.index.search(query_embedding.reshape(1, -1), top_k)
        
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < len(self.knowledge_ids):
                knowledge_id = self.knowledge_ids[idx]
                knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
                
                if knowledge and (content_type is None or knowledge.content_type == content_type):
                    results.append((knowledge, float(score)))
                    
        return results
        
    def rebuild_index(self, db: Session = None):
        """Rebuild the entire FAISS index from database"""
        if db is None:
            db = next(get_db())
            
        logger.info("Rebuilding knowledge index...")
        
        # Clear existing index
        self.index.reset()
        self.knowledge_ids = []
        
        # Get all knowledge entries
        knowledge_entries = db.query(Knowledge).all()
        
        embeddings = []
        for knowledge in knowledge_entries:
            if knowledge.embedding:
                # Load existing embedding
                embedding = np.array(json.loads(knowledge.embedding))
            else:
                # Generate new embedding
                embedding = self.encode_text(f"{knowledge.title} {knowledge.content}")
                knowledge.embedding = json.dumps(embedding.tolist())
                
            embeddings.append(embedding)
            self.knowledge_ids.append(knowledge.id)
            
        if embeddings:
            # Add all embeddings to index
            embeddings_matrix = np.vstack(embeddings)
            self.index.add(embeddings_matrix)
            
        db.commit()
        logger.info(f"Rebuilt index with {len(embeddings)} entries")
        
    def index_project_logs(self, project_id: int, db: Session = None):
        """Index all logs for a specific project"""
        if db is None:
            db = next(get_db())
            
        # Get project logs
        project_logs = db.query(ProjectLog).filter(ProjectLog.project_id == project_id).all()
        
        for log in project_logs:
            if log.log_type in ["info", "warning", "error"]:
                self.add_knowledge(
                    title=f"Project Log - {log.log_type.title()}",
                    content=log.message,
                    content_type="project_log",
                    tags=[log.log_type, "project_log"],
                    source=f"project_{project_id}_log_{log.id}",
                    db=db
                )
                
        # Get task logs for this project
        task_logs = (
            db.query(TaskLog)
            .join(Task)
            .filter(Task.project_id == project_id)
            .all()
        )
        
        for log in task_logs:
            if log.log_type in ["info", "warning", "error"]:
                self.add_knowledge(
                    title=f"Task Log - {log.log_type.title()}",
                    content=log.message,
                    content_type="task_log",
                    tags=[log.log_type, "task_log"],
                    source=f"task_{log.task_id}_log_{log.id}",
                    db=db
                )
                
        logger.info(f"Indexed logs for project {project_id}")
        
    def get_related_knowledge(
        self,
        knowledge_id: int,
        top_k: int = 3,
        db: Session = None
    ) -> List[Tuple[Knowledge, float]]:
        """Find knowledge entries related to a given knowledge entry"""
        if db is None:
            db = next(get_db())
            
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
        if not knowledge:
            return []
            
        # Use the content to find similar entries
        query = f"{knowledge.title} {knowledge.content}"
        results = self.search_knowledge(query, top_k + 1, db=db)
        
        # Filter out the original knowledge entry
        return [(k, score) for k, score in results if k.id != knowledge_id][:top_k]
        
    def get_knowledge_stats(self, db: Session = None) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        if db is None:
            db = next(get_db())
            
        total_count = db.query(Knowledge).count()
        
        # Count by content type
        from sqlalchemy import func
        content_types = db.query(Knowledge.content_type, func.count(Knowledge.id)).group_by(Knowledge.content_type).all()
        
        # Recent additions
        from datetime import timedelta
        recent_count = db.query(Knowledge).filter(
            Knowledge.created_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        return {
            "total_entries": total_count,
            "index_size": self.index.ntotal,
            "content_types": {content_type: count for content_type, count in content_types},
            "recent_additions": recent_count,
            "model_name": self.model._model_name,
            "embedding_dimension": self.dimension
        }


# Global knowledge indexer instance
knowledge_indexer = KnowledgeIndexer()