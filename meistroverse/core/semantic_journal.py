from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from meistroverse.database import get_db, Knowledge, Task, ProjectLog
from meistroverse.core.knowledge_indexer import knowledge_indexer
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


class JournalEntryType(Enum):
    THOUGHT = "thought"
    DECISION = "decision"
    WORKFLOW = "workflow"
    INSIGHT = "insight"
    REFLECTION = "reflection"
    GOAL = "goal"
    MILESTONE = "milestone"
    LEARNING = "learning"


class SemanticJournal:
    """Captures and organizes thoughts, decisions, and workflows with semantic understanding"""
    
    def __init__(self):
        self.indexer = knowledge_indexer
        
    async def create_entry(
        self,
        content: str,
        entry_type: JournalEntryType,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> Knowledge:
        """Create a new journal entry"""
        if db is None:
            db = next(get_db())
            
        # Generate title if not provided
        if not title:
            title = self._generate_title(content, entry_type)
            
        # Add entry type to tags
        entry_tags = tags or []
        entry_tags.append(entry_type.value)
        entry_tags.append("journal")
        
        # Create knowledge entry
        knowledge = self.indexer.add_knowledge(
            title=title,
            content=content,
            content_type=entry_type.value,
            tags=entry_tags,
            source="semantic_journal",
            db=db
        )
        
        # Add metadata if provided
        if metadata:
            knowledge.metadata = metadata
            db.commit()
            
        logger.info(f"Created journal entry: {title}")
        return knowledge
        
    def _generate_title(self, content: str, entry_type: JournalEntryType) -> str:
        """Generate a title for the journal entry"""
        # Take first 50 characters or first sentence
        lines = content.split('\n')
        first_line = lines[0] if lines else content
        
        if len(first_line) > 50:
            title = first_line[:47] + "..."
        else:
            title = first_line
            
        return f"{entry_type.value.title()}: {title}"
        
    async def log_thought(
        self,
        thought: str,
        context: Optional[str] = None,
        tags: Optional[List[str]] = None,
        db: Session = None
    ) -> Knowledge:
        """Log a thought with optional context"""
        content = thought
        if context:
            content = f"Context: {context}\n\nThought: {thought}"
            
        return await self.create_entry(
            content=content,
            entry_type=JournalEntryType.THOUGHT,
            tags=tags,
            db=db
        )
        
    async def log_decision(
        self,
        decision: str,
        reasoning: str,
        alternatives: Optional[List[str]] = None,
        outcome: Optional[str] = None,
        tags: Optional[List[str]] = None,
        db: Session = None
    ) -> Knowledge:
        """Log a decision with reasoning and alternatives"""
        content = f"Decision: {decision}\n\nReasoning: {reasoning}"
        
        if alternatives:
            content += f"\n\nAlternatives considered:\n" + "\n".join(f"- {alt}" for alt in alternatives)
            
        if outcome:
            content += f"\n\nOutcome: {outcome}"
            
        return await self.create_entry(
            content=content,
            entry_type=JournalEntryType.DECISION,
            tags=tags,
            db=db
        )
        
    async def log_workflow(
        self,
        workflow_name: str,
        steps: List[str],
        tools_used: Optional[List[str]] = None,
        duration: Optional[float] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        db: Session = None
    ) -> Knowledge:
        """Log a workflow with steps and tools used"""
        content = f"Workflow: {workflow_name}\n\nSteps:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))
        
        if tools_used:
            content += f"\n\nTools used: {', '.join(tools_used)}"
            
        if duration:
            content += f"\n\nDuration: {duration} seconds"
            
        if notes:
            content += f"\n\nNotes: {notes}"
            
        return await self.create_entry(
            content=content,
            entry_type=JournalEntryType.WORKFLOW,
            tags=tags,
            db=db
        )
        
    async def log_insight(
        self,
        insight: str,
        trigger: Optional[str] = None,
        implications: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        db: Session = None
    ) -> Knowledge:
        """Log an insight with trigger and implications"""
        content = f"Insight: {insight}"
        
        if trigger:
            content += f"\n\nTriggered by: {trigger}"
            
        if implications:
            content += f"\n\nImplications:\n" + "\n".join(f"- {imp}" for imp in implications)
            
        return await self.create_entry(
            content=content,
            entry_type=JournalEntryType.INSIGHT,
            tags=tags,
            db=db
        )
        
    async def find_related_entries(
        self,
        query: str,
        entry_types: Optional[List[JournalEntryType]] = None,
        limit: int = 5,
        db: Session = None
    ) -> List[Tuple[Knowledge, float]]:
        """Find journal entries related to a query"""
        if db is None:
            db = next(get_db())
            
        # Search using semantic similarity
        all_results = self.indexer.search_knowledge(query, top_k=limit*2, db=db)
        
        # Filter by entry types if specified
        if entry_types:
            entry_type_values = [et.value for et in entry_types]
            filtered_results = [
                (knowledge, score) for knowledge, score in all_results
                if knowledge.content_type in entry_type_values
            ]
        else:
            # Only include journal entries
            filtered_results = [
                (knowledge, score) for knowledge, score in all_results
                if "journal" in (knowledge.tags or [])
            ]
            
        return filtered_results[:limit]
        
    async def get_daily_summary(
        self,
        date: Optional[datetime] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """Get a summary of journal entries for a specific day"""
        if db is None:
            db = next(get_db())
            
        if date is None:
            date = datetime.utcnow()
            
        # Get start and end of day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # Query entries for the day
        entries = (
            db.query(Knowledge)
            .filter(Knowledge.source == "semantic_journal")
            .filter(Knowledge.created_at >= start_of_day)
            .filter(Knowledge.created_at < end_of_day)
            .all()
        )
        
        # Group by entry type
        entries_by_type = {}
        for entry in entries:
            entry_type = entry.content_type
            if entry_type not in entries_by_type:
                entries_by_type[entry_type] = []
            entries_by_type[entry_type].append(entry)
            
        # Generate summary
        summary = {
            "date": date.strftime("%Y-%m-%d"),
            "total_entries": len(entries),
            "entries_by_type": {
                entry_type: len(entries_list)
                for entry_type, entries_list in entries_by_type.items()
            },
            "entries": []
        }
        
        # Add entry details
        for entry in entries:
            summary["entries"].append({
                "id": entry.id,
                "title": entry.title,
                "content_type": entry.content_type,
                "created_at": entry.created_at.isoformat(),
                "tags": entry.tags,
                "content_preview": entry.content[:100] + "..." if len(entry.content) > 100 else entry.content
            })
            
        return summary
        
    async def get_weekly_insights(
        self,
        weeks_back: int = 1,
        db: Session = None
    ) -> Dict[str, Any]:
        """Get insights from the past week(s)"""
        if db is None:
            db = next(get_db())
            
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(weeks=weeks_back)
        
        # Get entries from the period
        entries = (
            db.query(Knowledge)
            .filter(Knowledge.source == "semantic_journal")
            .filter(Knowledge.created_at >= start_date)
            .filter(Knowledge.created_at < end_date)
            .all()
        )
        
        # Analyze patterns
        insights = {
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_entries": len(entries),
            "daily_counts": {},
            "most_common_tags": {},
            "entry_types": {},
            "trending_topics": []
        }
        
        # Daily counts
        for entry in entries:
            day = entry.created_at.strftime("%Y-%m-%d")
            insights["daily_counts"][day] = insights["daily_counts"].get(day, 0) + 1
            
        # Entry types
        for entry in entries:
            entry_type = entry.content_type
            insights["entry_types"][entry_type] = insights["entry_types"].get(entry_type, 0) + 1
            
        # Most common tags
        for entry in entries:
            if entry.tags:
                for tag in entry.tags:
                    if tag not in ["journal"]:  # Exclude meta tags
                        insights["most_common_tags"][tag] = insights["most_common_tags"].get(tag, 0) + 1
                        
        # Sort by frequency
        insights["most_common_tags"] = dict(
            sorted(insights["most_common_tags"].items(), key=lambda x: x[1], reverse=True)[:10]
        )
        
        return insights
        
    async def search_patterns(
        self,
        pattern_query: str,
        time_range_days: int = 30,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """Search for patterns in journal entries over time"""
        if db is None:
            db = next(get_db())
            
        # Get related entries
        related_entries = await self.find_related_entries(
            query=pattern_query,
            limit=20,
            db=db
        )
        
        # Filter by time range
        cutoff_date = datetime.utcnow() - timedelta(days=time_range_days)
        filtered_entries = [
            (entry, score) for entry, score in related_entries
            if entry.created_at >= cutoff_date
        ]
        
        # Group by time periods
        patterns = []
        for entry, score in filtered_entries:
            patterns.append({
                "entry_id": entry.id,
                "title": entry.title,
                "content_type": entry.content_type,
                "similarity_score": score,
                "created_at": entry.created_at.isoformat(),
                "tags": entry.tags,
                "content_preview": entry.content[:200] + "..." if len(entry.content) > 200 else entry.content
            })
            
        return patterns
        
    async def export_journal(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entry_types: Optional[List[JournalEntryType]] = None,
        format: str = "json",
        db: Session = None
    ) -> str:
        """Export journal entries to various formats"""
        if db is None:
            db = next(get_db())
            
        # Build query
        query = db.query(Knowledge).filter(Knowledge.source == "semantic_journal")
        
        if start_date:
            query = query.filter(Knowledge.created_at >= start_date)
        if end_date:
            query = query.filter(Knowledge.created_at <= end_date)
        if entry_types:
            entry_type_values = [et.value for et in entry_types]
            query = query.filter(Knowledge.content_type.in_(entry_type_values))
            
        entries = query.order_by(desc(Knowledge.created_at)).all()
        
        # Export based on format
        if format == "json":
            return self._export_json(entries)
        elif format == "markdown":
            return self._export_markdown(entries)
        elif format == "csv":
            return self._export_csv(entries)
        else:
            raise ValueError(f"Unsupported export format: {format}")
            
    def _export_json(self, entries: List[Knowledge]) -> str:
        """Export entries as JSON"""
        export_data = []
        for entry in entries:
            export_data.append({
                "id": entry.id,
                "title": entry.title,
                "content": entry.content,
                "content_type": entry.content_type,
                "tags": entry.tags,
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat()
            })
        return json.dumps(export_data, indent=2)
        
    def _export_markdown(self, entries: List[Knowledge]) -> str:
        """Export entries as Markdown"""
        md_content = "# Semantic Journal Export\n\n"
        
        for entry in entries:
            md_content += f"## {entry.title}\n\n"
            md_content += f"**Type:** {entry.content_type}\n"
            md_content += f"**Created:** {entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            if entry.tags:
                md_content += f"**Tags:** {', '.join(entry.tags)}\n"
            md_content += f"\n{entry.content}\n\n---\n\n"
            
        return md_content
        
    def _export_csv(self, entries: List[Knowledge]) -> str:
        """Export entries as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["ID", "Title", "Content Type", "Created At", "Tags", "Content"])
        
        # Write entries
        for entry in entries:
            writer.writerow([
                entry.id,
                entry.title,
                entry.content_type,
                entry.created_at.isoformat(),
                ",".join(entry.tags) if entry.tags else "",
                entry.content.replace("\n", " ").replace("\r", " ")
            ])
            
        return output.getvalue()


# Global semantic journal instance
semantic_journal = SemanticJournal()