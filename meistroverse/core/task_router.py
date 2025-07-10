from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import json
import asyncio
from sqlalchemy.orm import Session

from meistroverse.database import get_db, Task, TaskExecution, Agent
from meistroverse.agents.base import BaseAgent
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRouter:
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.task_queue: List[Task] = []
        self.running_tasks: Dict[int, asyncio.Task] = {}
        
    def register_agent(self, agent_type: str, agent: BaseAgent):
        """Register an agent for a specific task type"""
        self.agents[agent_type] = agent
        logger.info(f"Registered agent {agent_type}: {agent.__class__.__name__}")
        
    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """Get an agent by type"""
        return self.agents.get(agent_type)
        
    async def create_task(
        self,
        title: str,
        description: str,
        agent_type: str,
        project_id: int,
        priority: TaskPriority = TaskPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> Task:
        """Create a new task"""
        if db is None:
            db = next(get_db())
            
        task = Task(
            title=title,
            description=description,
            agent_type=agent_type,
            project_id=project_id,
            priority=priority.value,
            status=TaskStatus.PENDING.value,
            metadata=metadata or {}
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        logger.info(f"Created task {task.id}: {task.title}")
        return task
        
    async def execute_task(self, task_id: int, db: Session = None) -> TaskExecution:
        """Execute a specific task"""
        if db is None:
            db = next(get_db())
            
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
            
        agent = self.get_agent(task.agent_type)
        if not agent:
            raise ValueError(f"No agent registered for type: {task.agent_type}")
            
        # Update task status
        task.status = TaskStatus.IN_PROGRESS.value
        task.updated_at = datetime.utcnow()
        db.commit()
        
        # Create execution record
        execution = TaskExecution(
            task_id=task.id,
            agent_id=agent.agent_id,
            execution_data={"started_at": datetime.utcnow().isoformat()},
            started_at=datetime.utcnow()
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        try:
            logger.info(f"Executing task {task.id} with agent {agent.agent_id}")
            
            # Execute the task
            result = await agent.execute(task)
            
            # Update execution record
            execution.result = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.success = True
            execution.completed_at = datetime.utcnow()
            
            # Update task status
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.utcnow()
            
            logger.info(f"Task {task.id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task.id} failed: {str(e)}")
            
            # Update execution record
            execution.success = False
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            
            # Update task status
            task.status = TaskStatus.FAILED.value
            
        finally:
            db.commit()
            
        return execution
        
    async def process_queue(self, max_concurrent: int = 5, db: Session = None):
        """Process tasks from the queue"""
        if db is None:
            db = next(get_db())
            
        while True:
            # Get pending tasks
            pending_tasks = (
                db.query(Task)
                .filter(Task.status == TaskStatus.PENDING.value)
                .order_by(Task.priority.desc(), Task.created_at)
                .limit(max_concurrent - len(self.running_tasks))
                .all()
            )
            
            # Start new tasks
            for task in pending_tasks:
                if len(self.running_tasks) >= max_concurrent:
                    break
                    
                # Create async task for execution
                async_task = asyncio.create_task(self.execute_task(task.id, db))
                self.running_tasks[task.id] = async_task
                
            # Clean up completed tasks
            completed_task_ids = []
            for task_id, async_task in self.running_tasks.items():
                if async_task.done():
                    completed_task_ids.append(task_id)
                    
            for task_id in completed_task_ids:
                del self.running_tasks[task_id]
                
            # Wait a bit before checking again
            await asyncio.sleep(1)
            
    async def get_task_status(self, task_id: int, db: Session = None) -> Dict[str, Any]:
        """Get the status of a task"""
        if db is None:
            db = next(get_db())
            
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
            
        executions = db.query(TaskExecution).filter(TaskExecution.task_id == task_id).all()
        
        return {
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "executions": [
                {
                    "execution_id": exec.id,
                    "success": exec.success,
                    "started_at": exec.started_at.isoformat(),
                    "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                    "error_message": exec.error_message
                }
                for exec in executions
            ]
        }
        
    async def cancel_task(self, task_id: int, db: Session = None):
        """Cancel a task"""
        if db is None:
            db = next(get_db())
            
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
            
        # Cancel running task if it exists
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]
            
        # Update task status
        task.status = TaskStatus.CANCELLED.value
        task.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Cancelled task {task_id}")


# Global task router instance
task_router = TaskRouter()