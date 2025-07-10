"""
Celery tasks for notifications and alerts
"""

from celery import shared_task
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, name="meistroverse.tasks.notification_tasks.send_health_alert")
def send_health_alert(self, health_score, threshold=0.7):
    """Send health alert if system health is below threshold"""
    try:
        if health_score < threshold:
            logger.warning(f"System health alert: {health_score:.1%} (threshold: {threshold:.1%})")
            
            # In a real implementation, this would send notifications via:
            # - Email
            # - Slack
            # - Discord
            # - SMS
            # - etc.
            
            result = {
                "status": "alert_sent",
                "health_score": health_score,
                "threshold": threshold,
                "alert_type": "health_degradation"
            }
        else:
            result = {
                "status": "no_alert_needed",
                "health_score": health_score,
                "threshold": threshold
            }
            
        logger.info(f"Health alert check completed: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"Health alert failed: {exc}")
        self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, name="meistroverse.tasks.notification_tasks.send_daily_summary")
def send_daily_summary(self):
    """Send daily system summary"""
    try:
        from meistroverse.database import get_db, Task, TaskExecution
        from datetime import datetime, timedelta
        
        logger.info("Generating daily summary")
        
        db = next(get_db())
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        # Get daily statistics
        total_tasks = db.query(Task).filter(Task.created_at >= yesterday).count()
        completed_executions = db.query(TaskExecution).filter(
            TaskExecution.started_at >= yesterday,
            TaskExecution.success == True
        ).count()
        
        summary = {
            "date": yesterday.strftime("%Y-%m-%d"),
            "total_tasks": total_tasks,
            "completed_executions": completed_executions,
            "success_rate": completed_executions / max(total_tasks, 1)
        }
        
        # In a real implementation, this would format and send the summary
        logger.info(f"Daily summary generated: {summary}")
        
        result = {
            "status": "summary_sent",
            "summary": summary
        }
        
        return result
        
    except Exception as exc:
        logger.error(f"Daily summary failed: {exc}")
        self.retry(countdown=300, max_retries=3)


@shared_task(bind=True, name="meistroverse.tasks.notification_tasks.send_suggestion_digest")
def send_suggestion_digest(self):
    """Send digest of recent suggestions"""
    try:
        from meistroverse.database import get_db, Knowledge
        from datetime import datetime, timedelta
        
        logger.info("Generating suggestion digest")
        
        db = next(get_db())
        last_week = datetime.utcnow() - timedelta(days=7)
        
        # Get recent suggestions
        suggestions = (
            db.query(Knowledge)
            .filter(Knowledge.source == "daily_suggestion_loop")
            .filter(Knowledge.created_at >= last_week)
            .limit(10)
            .all()
        )
        
        digest = {
            "period": f"{last_week.strftime('%Y-%m-%d')} to {datetime.utcnow().strftime('%Y-%m-%d')}",
            "suggestion_count": len(suggestions),
            "suggestions": [
                {
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "preview": s.content[:200] + "..." if len(s.content) > 200 else s.content
                }
                for s in suggestions
            ]
        }
        
        logger.info(f"Suggestion digest generated: {digest}")
        
        result = {
            "status": "digest_sent",
            "digest": digest
        }
        
        return result
        
    except Exception as exc:
        logger.error(f"Suggestion digest failed: {exc}")
        self.retry(countdown=300, max_retries=3)