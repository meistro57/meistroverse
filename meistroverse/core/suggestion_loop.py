import asyncio
import schedule
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from meistroverse.database import (
    get_db, Task, TaskExecution, PromptTemplate, 
    SystemMetrics, Knowledge, Agent, ProjectLog
)
from meistroverse.core.task_router import task_router, TaskPriority
from meistroverse.core.knowledge_indexer import knowledge_indexer
from meistroverse.core.semantic_journal import semantic_journal, JournalEntryType
from meistroverse.agents.prompt_qc_agent import PromptQCAgent
from meistroverse.agents.code_mutation_agent import CodeMutationAgent
from meistroverse.utils.logger import get_logger
from meistroverse.config import settings

logger = get_logger(__name__)


class DailySuggestionLoop:
    """Automated daily loop that analyzes system performance and suggests improvements"""
    
    def __init__(self):
        self.prompt_qc_agent = PromptQCAgent()
        self.code_mutation_agent = CodeMutationAgent()
        self.is_running = False
        self.last_run = None
        
    async def run_daily_analysis(self) -> Dict[str, Any]:
        """Run the complete daily analysis and suggestion loop"""
        logger.info("Starting daily suggestion loop analysis")
        
        start_time = datetime.utcnow()
        db = next(get_db())
        
        results = {
            "timestamp": start_time.isoformat(),
            "system_health": {},
            "performance_analysis": {},
            "code_analysis": {},
            "knowledge_insights": {},
            "suggestions": [],
            "action_items": []
        }
        
        try:
            # 1. System Health Check
            results["system_health"] = await self._check_system_health(db)
            
            # 2. Performance Analysis
            results["performance_analysis"] = await self._analyze_performance_trends(db)
            
            # 3. Code Quality Analysis
            results["code_analysis"] = await self._analyze_code_quality(db)
            
            # 4. Knowledge Base Insights
            results["knowledge_insights"] = await self._analyze_knowledge_patterns(db)
            
            # 5. Generate Suggestions
            results["suggestions"] = await self._generate_suggestions(results, db)
            
            # 6. Create Action Items
            results["action_items"] = await self._create_action_items(results, db)
            
            # 7. Log Analysis Results
            await self._log_analysis_results(results, db)
            
            # 8. Schedule Follow-up Tasks
            await self._schedule_followup_tasks(results, db)
            
            self.last_run = start_time
            
        except Exception as e:
            logger.error(f"Error in daily suggestion loop: {e}")
            results["error"] = str(e)
            
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        results["execution_time"] = execution_time
        
        logger.info(f"Daily suggestion loop completed in {execution_time:.2f} seconds")
        return results
        
    async def _check_system_health(self, db: Session) -> Dict[str, Any]:
        """Check overall system health and performance"""
        logger.info("Checking system health")
        
        # Get recent task executions (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_executions = (
            db.query(TaskExecution)
            .filter(TaskExecution.started_at >= yesterday)
            .all()
        )
        
        # Calculate metrics
        total_tasks = len(recent_executions)
        successful_tasks = sum(1 for e in recent_executions if e.success)
        success_rate = successful_tasks / max(total_tasks, 1)
        
        # Average execution time
        completed_tasks = [e for e in recent_executions if e.completed_at and e.started_at]
        avg_execution_time = 0
        if completed_tasks:
            avg_execution_time = sum(
                (e.completed_at - e.started_at).total_seconds() 
                for e in completed_tasks
            ) / len(completed_tasks)
            
        # Error analysis
        failed_tasks = [e for e in recent_executions if not e.success]
        error_patterns = self._analyze_error_patterns(failed_tasks)
        
        # System metrics
        active_agents = db.query(Agent).filter(Agent.is_active == True).count()
        pending_tasks = db.query(Task).filter(Task.status == "pending").count()
        
        health_score = self._calculate_health_score(success_rate, avg_execution_time, len(error_patterns))
        
        return {
            "health_score": health_score,
            "total_tasks_24h": total_tasks,
            "success_rate": success_rate,
            "avg_execution_time": avg_execution_time,
            "active_agents": active_agents,
            "pending_tasks": pending_tasks,
            "error_patterns": error_patterns,
            "status": "healthy" if health_score > 0.8 else "degraded" if health_score > 0.6 else "critical"
        }
        
    def _analyze_error_patterns(self, failed_tasks: List[TaskExecution]) -> List[Dict[str, Any]]:
        """Analyze patterns in failed tasks"""
        if not failed_tasks:
            return []
            
        error_counts = {}
        for task in failed_tasks:
            if task.error_message:
                # Extract error type
                error_type = self._extract_error_type(task.error_message)
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                
        return [
            {"error_type": error_type, "count": count, "percentage": count / len(failed_tasks)}
            for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
    def _extract_error_type(self, error_message: str) -> str:
        """Extract error type from error message"""
        error_message = error_message.lower()
        
        if "timeout" in error_message:
            return "timeout"
        elif "rate limit" in error_message or "rate_limit" in error_message:
            return "rate_limit"
        elif "connection" in error_message:
            return "connection_error"
        elif "authentication" in error_message or "unauthorized" in error_message:
            return "auth_error"
        elif "invalid" in error_message or "validation" in error_message:
            return "validation_error"
        elif "memory" in error_message or "out of memory" in error_message:
            return "memory_error"
        else:
            return "unknown_error"
            
    def _calculate_health_score(self, success_rate: float, avg_time: float, error_types: int) -> float:
        """Calculate overall system health score"""
        # Base score from success rate (0-60 points)
        score = success_rate * 60
        
        # Time efficiency (0-30 points)
        if avg_time <= 5:
            score += 30
        elif avg_time <= 10:
            score += 20
        elif avg_time <= 20:
            score += 10
        elif avg_time <= 30:
            score += 5
            
        # Error diversity penalty (0-10 points)
        if error_types == 0:
            score += 10
        elif error_types <= 2:
            score += 5
            
        return min(score / 100.0, 1.0)
        
    async def _analyze_performance_trends(self, db: Session) -> Dict[str, Any]:
        """Analyze performance trends over time"""
        logger.info("Analyzing performance trends")
        
        # Get data for the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Daily success rates
        daily_success = []
        for i in range(7):
            day_start = week_ago + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            
            day_executions = (
                db.query(TaskExecution)
                .filter(TaskExecution.started_at >= day_start)
                .filter(TaskExecution.started_at < day_end)
                .all()
            )
            
            if day_executions:
                success_rate = sum(1 for e in day_executions if e.success) / len(day_executions)
                avg_time = sum(
                    (e.completed_at - e.started_at).total_seconds() 
                    for e in day_executions 
                    if e.completed_at and e.started_at
                ) / len(day_executions)
            else:
                success_rate = 0
                avg_time = 0
                
            daily_success.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "success_rate": success_rate,
                "avg_execution_time": avg_time,
                "total_tasks": len(day_executions)
            })
            
        # Calculate trends
        success_trend = self._calculate_trend([d["success_rate"] for d in daily_success])
        time_trend = self._calculate_trend([d["avg_execution_time"] for d in daily_success])
        
        # Agent performance comparison
        agent_performance = self._analyze_agent_performance(db, week_ago)
        
        return {
            "daily_metrics": daily_success,
            "success_rate_trend": success_trend,
            "execution_time_trend": time_trend,
            "agent_performance": agent_performance,
            "improvement_areas": self._identify_improvement_areas(daily_success, agent_performance)
        }
        
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a list of values"""
        if len(values) < 2:
            return "stable"
            
        # Simple linear regression slope
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        if slope > 0.01:
            return "improving"
        elif slope < -0.01:
            return "declining"
        else:
            return "stable"
            
    def _analyze_agent_performance(self, db: Session, since: datetime) -> List[Dict[str, Any]]:
        """Analyze performance of individual agents"""
        agents = db.query(Agent).filter(Agent.is_active == True).all()
        
        performance = []
        for agent in agents:
            executions = (
                db.query(TaskExecution)
                .join(Task)
                .filter(Task.agent_type == agent.agent_type)
                .filter(TaskExecution.started_at >= since)
                .all()
            )
            
            if executions:
                success_rate = sum(1 for e in executions if e.success) / len(executions)
                avg_time = sum(
                    (e.completed_at - e.started_at).total_seconds() 
                    for e in executions 
                    if e.completed_at and e.started_at
                ) / len(executions)
            else:
                success_rate = 0
                avg_time = 0
                
            performance.append({
                "agent_name": agent.name,
                "agent_type": agent.agent_type,
                "success_rate": success_rate,
                "avg_execution_time": avg_time,
                "total_executions": len(executions),
                "needs_attention": success_rate < 0.8 or avg_time > 30
            })
            
        return sorted(performance, key=lambda x: x["success_rate"])
        
    def _identify_improvement_areas(self, daily_metrics: List[Dict], agent_performance: List[Dict]) -> List[str]:
        """Identify areas for improvement based on metrics"""
        areas = []
        
        # Check for declining trends
        recent_success = [d["success_rate"] for d in daily_metrics[-3:]]
        if sum(recent_success) / len(recent_success) < 0.8:
            areas.append("Overall success rate is below 80%")
            
        # Check for slow agents
        slow_agents = [a for a in agent_performance if a["avg_execution_time"] > 30]
        if slow_agents:
            areas.append(f"{len(slow_agents)} agents have slow execution times")
            
        # Check for unreliable agents
        unreliable_agents = [a for a in agent_performance if a["success_rate"] < 0.7]
        if unreliable_agents:
            areas.append(f"{len(unreliable_agents)} agents have low success rates")
            
        return areas
        
    async def _analyze_code_quality(self, db: Session) -> Dict[str, Any]:
        """Analyze code quality trends and issues"""
        logger.info("Analyzing code quality")
        
        # Get recent code mutation analysis results
        recent_analysis = (
            db.query(Knowledge)
            .filter(Knowledge.content_type == "code_analysis")
            .filter(Knowledge.created_at >= datetime.utcnow() - timedelta(days=7))
            .order_by(desc(Knowledge.created_at))
            .all()
        )
        
        if not recent_analysis:
            return {"status": "no_recent_analysis", "recommendation": "Run code mutation analysis"}
            
        # Analyze patterns in code issues
        issue_patterns = self._extract_code_issue_patterns(recent_analysis)
        
        return {
            "analyses_count": len(recent_analysis),
            "issue_patterns": issue_patterns,
            "most_common_issues": self._get_most_common_issues(issue_patterns),
            "recommendations": self._generate_code_quality_recommendations(issue_patterns)
        }
        
    def _extract_code_issue_patterns(self, analyses: List[Knowledge]) -> Dict[str, int]:
        """Extract patterns from code analysis results"""
        patterns = {}
        
        for analysis in analyses:
            content = analysis.content.lower()
            
            # Look for common issue types
            if "unused import" in content:
                patterns["unused_imports"] = patterns.get("unused_imports", 0) + 1
            if "security" in content:
                patterns["security_issues"] = patterns.get("security_issues", 0) + 1
            if "performance" in content:
                patterns["performance_issues"] = patterns.get("performance_issues", 0) + 1
            if "complexity" in content:
                patterns["complexity_issues"] = patterns.get("complexity_issues", 0) + 1
            if "style" in content or "formatting" in content:
                patterns["style_issues"] = patterns.get("style_issues", 0) + 1
                
        return patterns
        
    def _get_most_common_issues(self, patterns: Dict[str, int]) -> List[Dict[str, Any]]:
        """Get the most common code issues"""
        return [
            {"issue_type": issue_type, "count": count}
            for issue_type, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
    def _generate_code_quality_recommendations(self, patterns: Dict[str, int]) -> List[str]:
        """Generate code quality recommendations"""
        recommendations = []
        
        if patterns.get("security_issues", 0) > 0:
            recommendations.append("Address security vulnerabilities in codebase")
            
        if patterns.get("performance_issues", 0) > 3:
            recommendations.append("Focus on performance optimizations")
            
        if patterns.get("complexity_issues", 0) > 2:
            recommendations.append("Refactor complex functions to improve maintainability")
            
        if patterns.get("unused_imports", 0) > 5:
            recommendations.append("Clean up unused imports across the codebase")
            
        return recommendations
        
    async def _analyze_knowledge_patterns(self, db: Session) -> Dict[str, Any]:
        """Analyze patterns in the knowledge base"""
        logger.info("Analyzing knowledge patterns")
        
        # Get knowledge statistics
        stats = knowledge_indexer.get_knowledge_stats(db)
        
        # Get recent journal entries
        recent_entries = await semantic_journal.get_weekly_insights(weeks_back=1, db=db)
        
        # Find trending topics
        trending_topics = self._find_trending_topics(db)
        
        return {
            "knowledge_stats": stats,
            "weekly_insights": recent_entries,
            "trending_topics": trending_topics,
            "knowledge_growth": self._calculate_knowledge_growth(db)
        }
        
    def _find_trending_topics(self, db: Session) -> List[Dict[str, Any]]:
        """Find trending topics in knowledge base"""
        # Get recent knowledge entries
        recent_knowledge = (
            db.query(Knowledge)
            .filter(Knowledge.created_at >= datetime.utcnow() - timedelta(days=7))
            .all()
        )
        
        # Count tag frequency
        tag_counts = {}
        for knowledge in recent_knowledge:
            if knowledge.tags:
                for tag in knowledge.tags:
                    if tag not in ["journal", "code_analysis"]:  # Exclude meta tags
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
                        
        # Return top trending topics
        return [
            {"topic": topic, "frequency": count}
            for topic, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
    def _calculate_knowledge_growth(self, db: Session) -> Dict[str, Any]:
        """Calculate knowledge base growth rate"""
        # Get entries from last 30 days
        month_ago = datetime.utcnow() - timedelta(days=30)
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        total_entries = db.query(Knowledge).count()
        last_month = db.query(Knowledge).filter(Knowledge.created_at >= month_ago).count()
        last_week = db.query(Knowledge).filter(Knowledge.created_at >= week_ago).count()
        
        return {
            "total_entries": total_entries,
            "monthly_growth": last_month,
            "weekly_growth": last_week,
            "daily_average": last_week / 7
        }
        
    async def _generate_suggestions(self, analysis_results: Dict[str, Any], db: Session) -> List[Dict[str, Any]]:
        """Generate actionable suggestions based on analysis"""
        logger.info("Generating suggestions")
        
        suggestions = []
        
        # System health suggestions
        health = analysis_results["system_health"]
        if health["health_score"] < 0.8:
            suggestions.append({
                "category": "system_health",
                "priority": "high",
                "title": "Improve system reliability",
                "description": f"System health score is {health['health_score']:.1%}, below optimal threshold",
                "actions": [
                    "Review and fix error patterns",
                    "Optimize slow-performing agents",
                    "Increase monitoring and alerting"
                ]
            })
            
        # Performance suggestions
        performance = analysis_results["performance_analysis"]
        if "declining" in str(performance.get("success_rate_trend")):
            suggestions.append({
                "category": "performance",
                "priority": "medium",
                "title": "Address declining success rate trend",
                "description": "Success rate has been declining over the past week",
                "actions": [
                    "Analyze recent failures",
                    "Update prompt templates",
                    "Review agent configurations"
                ]
            })
            
        # Code quality suggestions
        code_analysis = analysis_results["code_analysis"]
        if code_analysis.get("recommendations"):
            suggestions.append({
                "category": "code_quality",
                "priority": "medium",
                "title": "Improve code quality",
                "description": "Multiple code quality issues identified",
                "actions": code_analysis["recommendations"]
            })
            
        # Knowledge base suggestions
        knowledge = analysis_results["knowledge_insights"]
        if knowledge["knowledge_stats"]["total_entries"] < 50:
            suggestions.append({
                "category": "knowledge",
                "priority": "low",
                "title": "Expand knowledge base",
                "description": "Knowledge base is still small, consider adding more content",
                "actions": [
                    "Document more workflows and decisions",
                    "Add more learning insights",
                    "Import existing documentation"
                ]
            })
            
        return suggestions
        
    async def _create_action_items(self, analysis_results: Dict[str, Any], db: Session) -> List[Dict[str, Any]]:
        """Create specific action items based on suggestions"""
        logger.info("Creating action items")
        
        action_items = []
        suggestions = analysis_results["suggestions"]
        
        for suggestion in suggestions:
            if suggestion["priority"] == "high":
                # Create immediate action items for high priority suggestions
                action_items.append({
                    "title": f"Address: {suggestion['title']}",
                    "description": suggestion["description"],
                    "category": suggestion["category"],
                    "priority": "high",
                    "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                    "actions": suggestion["actions"][:3]  # Limit to top 3 actions
                })
                
        # Add recurring maintenance tasks
        action_items.extend([
            {
                "title": "Run prompt QC analysis",
                "description": "Analyze and improve prompt templates",
                "category": "maintenance",
                "priority": "medium",
                "due_date": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                "actions": ["Run prompt performance analysis", "Update low-performing prompts"]
            },
            {
                "title": "Code mutation analysis",
                "description": "Analyze codebase for improvements",
                "category": "maintenance", 
                "priority": "low",
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "actions": ["Run code analysis on main modules", "Address high-confidence suggestions"]
            }
        ])
        
        return action_items
        
    async def _log_analysis_results(self, results: Dict[str, Any], db: Session) -> None:
        """Log analysis results to knowledge base and journal"""
        logger.info("Logging analysis results")
        
        # Create knowledge entry
        summary = f"Daily System Analysis - {results['timestamp'][:10]}\n\n"
        summary += f"System Health Score: {results['system_health']['health_score']:.1%}\n"
        summary += f"Suggestions Generated: {len(results['suggestions'])}\n"
        summary += f"Action Items Created: {len(results['action_items'])}\n\n"
        
        # Add key insights
        if results['suggestions']:
            summary += "Key Suggestions:\n"
            for suggestion in results['suggestions'][:3]:
                summary += f"- {suggestion['title']}\n"
                
        knowledge_indexer.add_knowledge(
            title=f"Daily Analysis - {results['timestamp'][:10]}",
            content=summary,
            content_type="system_analysis",
            tags=["daily_analysis", "system_health", "suggestions"],
            source="daily_suggestion_loop",
            db=db
        )
        
        # Create journal entry
        await semantic_journal.log_insight(
            insight=f"Daily system analysis completed with health score of {results['system_health']['health_score']:.1%}",
            trigger="automated daily analysis",
            implications=[s['title'] for s in results['suggestions'][:3]],
            tags=["daily_analysis", "system_insights"],
            db=db
        )
        
    async def _schedule_followup_tasks(self, results: Dict[str, Any], db: Session) -> None:
        """Schedule follow-up tasks based on analysis results"""
        logger.info("Scheduling follow-up tasks")
        
        # Schedule high-priority action items as tasks
        for action_item in results["action_items"]:
            if action_item["priority"] == "high":
                await task_router.create_task(
                    title=action_item["title"],
                    description=action_item["description"],
                    agent_type="prompt_qc_agent" if "prompt" in action_item["title"].lower() else "general",
                    project_id=1,  # Default project
                    priority=TaskPriority.HIGH,
                    metadata={
                        "source": "daily_suggestion_loop",
                        "action_item": action_item,
                        "due_date": action_item["due_date"]
                    },
                    db=db
                )
                
    def start_daily_schedule(self):
        """Start the daily scheduled analysis"""
        logger.info("Starting daily suggestion loop schedule")
        
        # Schedule daily run at 6 AM
        schedule.every().day.at("06:00").do(self._run_scheduled_analysis)
        
        # Also run immediately if no recent run
        if not self.last_run or self.last_run < datetime.utcnow() - timedelta(hours=23):
            schedule.every().minute.do(self._run_once_then_cancel)
            
        self.is_running = True
        
        # Run scheduler in background
        asyncio.create_task(self._scheduler_loop())
        
    async def _scheduler_loop(self):
        """Run the scheduler loop"""
        while self.is_running:
            schedule.run_pending()
            await asyncio.sleep(60)  # Check every minute
            
    def _run_scheduled_analysis(self):
        """Wrapper for scheduled analysis"""
        asyncio.create_task(self.run_daily_analysis())
        
    def _run_once_then_cancel(self):
        """Run analysis once then cancel this scheduled job"""
        asyncio.create_task(self.run_daily_analysis())
        schedule.clear('minute')  # Cancel minute-based jobs
        
    def stop_daily_schedule(self):
        """Stop the daily scheduled analysis"""
        logger.info("Stopping daily suggestion loop schedule")
        self.is_running = False
        schedule.clear()
        
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the suggestion loop"""
        return {
            "is_running": self.is_running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_scheduled_run": "06:00 daily" if self.is_running else None,
            "scheduled_jobs": len(schedule.jobs)
        }


# Global suggestion loop instance
suggestion_loop = DailySuggestionLoop()