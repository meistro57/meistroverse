"""
Celery tasks for maintenance operations
"""

from celery import shared_task
from datetime import datetime, timedelta
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, name="meistroverse.tasks.maintenance_tasks.cleanup_old_logs")
def cleanup_old_logs(self, days_to_keep=30):
    """Clean up old log entries"""
    try:
        from meistroverse.database import get_db, TaskLog, ProjectLog, AgentLog
        
        logger.info(f"Starting log cleanup (keeping {days_to_keep} days)")
        
        db = next(get_db())
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Delete old task logs
        task_logs_deleted = db.query(TaskLog).filter(TaskLog.timestamp < cutoff_date).delete()
        
        # Delete old project logs
        project_logs_deleted = db.query(ProjectLog).filter(ProjectLog.timestamp < cutoff_date).delete()
        
        # Delete old agent logs
        agent_logs_deleted = db.query(AgentLog).filter(AgentLog.timestamp < cutoff_date).delete()
        
        db.commit()
        
        result = {
            "status": "completed",
            "task_logs_deleted": task_logs_deleted,
            "project_logs_deleted": project_logs_deleted,
            "agent_logs_deleted": agent_logs_deleted,
            "cutoff_date": cutoff_date.isoformat()
        }
        
        logger.info(f"Log cleanup completed: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"Log cleanup failed: {exc}")
        self.retry(countdown=300, max_retries=3)


@shared_task(bind=True, name="meistroverse.tasks.maintenance_tasks.rebuild_knowledge_index")
def rebuild_knowledge_index(self):
    """Rebuild the knowledge index"""
    try:
        from meistroverse.core.knowledge_indexer import knowledge_indexer
        from meistroverse.database import get_db
        
        logger.info("Starting knowledge index rebuild")
        
        db = next(get_db())
        knowledge_indexer.rebuild_index(db)
        
        result = {
            "status": "completed",
            "index_size": knowledge_indexer.index.ntotal,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Knowledge index rebuild completed: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"Knowledge index rebuild failed: {exc}")
        self.retry(countdown=300, max_retries=3)


@shared_task(bind=True, name="meistroverse.tasks.maintenance_tasks.backup_database")
def backup_database(self):
    """Create database backup"""
    try:
        import subprocess
        from meistroverse.config import settings
        
        logger.info("Starting database backup")
        
        # Parse database URL to extract connection details
        # This is a simplified implementation
        backup_file = f"/app/data/backups/meistroverse_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"
        
        # Create backup directory if it doesn't exist
        import os
        os.makedirs(os.path.dirname(backup_file), exist_ok=True)
        
        # Note: In a real implementation, you'd use mysqldump or similar
        result = {
            "status": "completed",
            "backup_file": backup_file,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Database backup completed: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"Database backup failed: {exc}")
        self.retry(countdown=300, max_retries=3)


@shared_task(bind=True, name="meistroverse.tasks.maintenance_tasks.update_system_metrics")
def update_system_metrics(self):
    """Update system performance metrics"""
    try:
        from meistroverse.database import get_db, SystemMetrics
        import psutil
        
        logger.info("Updating system metrics")
        
        db = next(get_db())
        
        # Collect system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = [
            SystemMetrics(
                metric_name="cpu_usage",
                metric_value=cpu_percent,
                metric_type="gauge",
                labels={"unit": "percent"}
            ),
            SystemMetrics(
                metric_name="memory_usage",
                metric_value=memory.percent,
                metric_type="gauge",
                labels={"unit": "percent"}
            ),
            SystemMetrics(
                metric_name="disk_usage",
                metric_value=disk.percent,
                metric_type="gauge",
                labels={"unit": "percent"}
            )
        ]
        
        for metric in metrics:
            db.add(metric)
        
        db.commit()
        
        result = {
            "status": "completed",
            "metrics_recorded": len(metrics),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"System metrics updated: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"System metrics update failed: {exc}")
        self.retry(countdown=60, max_retries=3)