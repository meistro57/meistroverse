from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime
import uuid

from meistroverse.database.models import Task
from meistroverse.utils.logger import get_logger


class BaseAgent(ABC):
    """Base class for all agents in the MEISTROVERSE system"""
    
    def __init__(self, agent_id: Optional[str] = None, name: Optional[str] = None):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name or self.__class__.__name__
        self.logger = get_logger(f"agent.{self.name}")
        self.created_at = datetime.utcnow()
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        
    @abstractmethod
    async def execute(self, task: Task) -> Any:
        """Execute the given task and return result"""
        pass
        
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of this agent"""
        pass
        
    async def pre_execute(self, task: Task) -> bool:
        """Called before execute(). Return False to skip execution."""
        self.logger.info(f"Starting execution of task {task.id}: {task.title}")
        self.execution_count += 1
        return True
        
    async def post_execute(self, task: Task, result: Any, success: bool):
        """Called after execute() completes"""
        if success:
            self.success_count += 1
            self.logger.info(f"Successfully completed task {task.id}")
        else:
            self.failure_count += 1
            self.logger.error(f"Failed to complete task {task.id}")
            
    def get_stats(self) -> Dict[str, Any]:
        """Return agent statistics"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_count / max(self.execution_count, 1),
        }
        
    def validate_task(self, task: Task) -> bool:
        """Validate if this agent can handle the given task"""
        return True  # Default implementation accepts all tasks
        
    async def handle_error(self, task: Task, error: Exception) -> Optional[Dict[str, Any]]:
        """Handle errors that occur during task execution"""
        self.logger.error(f"Error in task {task.id}: {str(error)}")
        return {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "recoverable": False
        }