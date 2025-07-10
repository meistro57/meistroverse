from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
import asyncio
from sqlalchemy.orm import Session

from meistroverse.database import get_db, Task, TaskExecution, Agent
from meistroverse.agents.base import BaseAgent
from meistroverse.core.task_router import TaskStatus
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


class ChainExecutionMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class AgentChainStep:
    """Represents a step in an agent chain"""
    
    def __init__(
        self,
        agent: BaseAgent,
        conditions: Optional[List[Callable[[Dict[str, Any]], bool]]] = None,
        dependencies: Optional[List[str]] = None,
        output_transform: Optional[Callable[[Any], Dict[str, Any]]] = None
    ):
        self.agent = agent
        self.conditions = conditions or []
        self.dependencies = dependencies or []
        self.output_transform = output_transform
        self.step_id = f"step_{agent.agent_id}"
        
    def should_execute(self, context: Dict[str, Any]) -> bool:
        """Check if this step should execute based on conditions"""
        return all(condition(context) for condition in self.conditions)
        
    def dependencies_satisfied(self, completed_steps: List[str]) -> bool:
        """Check if all dependencies are satisfied"""
        return all(dep in completed_steps for dep in self.dependencies)


class AgentChain:
    """Orchestrates execution of multiple agents in sequence or parallel"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.steps: List[AgentChainStep] = []
        self.context: Dict[str, Any] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.feedback_handlers: List[Callable] = []
        
    def add_step(
        self,
        agent: BaseAgent,
        conditions: Optional[List[Callable[[Dict[str, Any]], bool]]] = None,
        dependencies: Optional[List[str]] = None,
        output_transform: Optional[Callable[[Any], Dict[str, Any]]] = None
    ) -> AgentChainStep:
        """Add a step to the chain"""
        step = AgentChainStep(agent, conditions, dependencies, output_transform)
        self.steps.append(step)
        logger.info(f"Added step {step.step_id} to chain {self.name}")
        return step
        
    def add_feedback_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Add a feedback handler that processes execution results"""
        self.feedback_handlers.append(handler)
        
    async def execute(
        self,
        initial_task: Task,
        mode: ChainExecutionMode = ChainExecutionMode.SEQUENTIAL,
        max_retries: int = 3,
        db: Session = None
    ) -> Dict[str, Any]:
        """Execute the agent chain"""
        if db is None:
            db = next(get_db())
            
        logger.info(f"Starting chain execution: {self.name}")
        
        # Initialize context
        self.context = {
            "initial_task": initial_task,
            "chain_name": self.name,
            "started_at": datetime.utcnow().isoformat(),
            "step_results": {},
            "errors": []
        }
        
        execution_result = {
            "chain_name": self.name,
            "success": False,
            "completed_steps": [],
            "failed_steps": [],
            "total_steps": len(self.steps),
            "execution_time": None,
            "context": self.context
        }
        
        start_time = datetime.utcnow()
        
        try:
            if mode == ChainExecutionMode.SEQUENTIAL:
                await self._execute_sequential(initial_task, max_retries, db)
            elif mode == ChainExecutionMode.PARALLEL:
                await self._execute_parallel(initial_task, max_retries, db)
            elif mode == ChainExecutionMode.CONDITIONAL:
                await self._execute_conditional(initial_task, max_retries, db)
                
            execution_result["success"] = True
            execution_result["completed_steps"] = list(self.context["step_results"].keys())
            
        except Exception as e:
            logger.error(f"Chain execution failed: {str(e)}")
            execution_result["error"] = str(e)
            self.context["errors"].append({"error": str(e), "timestamp": datetime.utcnow().isoformat()})
            
        finally:
            execution_result["execution_time"] = (datetime.utcnow() - start_time).total_seconds()
            execution_result["context"] = self.context
            
            # Process feedback
            await self._process_feedback(execution_result)
            
            # Record execution history
            self.execution_history.append(execution_result)
            
        return execution_result
        
    async def _execute_sequential(self, initial_task: Task, max_retries: int, db: Session):
        """Execute steps sequentially"""
        for step in self.steps:
            if not step.should_execute(self.context):
                logger.info(f"Skipping step {step.step_id} due to conditions")
                continue
                
            await self._execute_step(step, initial_task, max_retries, db)
            
    async def _execute_parallel(self, initial_task: Task, max_retries: int, db: Session):
        """Execute steps in parallel where possible"""
        remaining_steps = self.steps.copy()
        completed_steps = []
        
        while remaining_steps:
            # Find steps that can be executed (dependencies satisfied)
            executable_steps = [
                step for step in remaining_steps
                if step.dependencies_satisfied(completed_steps) and step.should_execute(self.context)
            ]
            
            if not executable_steps:
                # No more steps can be executed
                break
                
            # Execute steps in parallel
            tasks = [
                self._execute_step(step, initial_task, max_retries, db)
                for step in executable_steps
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Update completed steps
            for step in executable_steps:
                completed_steps.append(step.step_id)
                remaining_steps.remove(step)
                
    async def _execute_conditional(self, initial_task: Task, max_retries: int, db: Session):
        """Execute steps based on conditions and dependencies"""
        remaining_steps = self.steps.copy()
        completed_steps = []
        
        while remaining_steps:
            executed_any = False
            
            for step in remaining_steps[:]:
                if (step.dependencies_satisfied(completed_steps) and 
                    step.should_execute(self.context)):
                    
                    await self._execute_step(step, initial_task, max_retries, db)
                    completed_steps.append(step.step_id)
                    remaining_steps.remove(step)
                    executed_any = True
                    
            if not executed_any:
                # No more steps can be executed
                break
                
    async def _execute_step(self, step: AgentChainStep, initial_task: Task, max_retries: int, db: Session):
        """Execute a single step with retry logic"""
        retries = 0
        last_error = None
        
        while retries <= max_retries:
            try:
                logger.info(f"Executing step {step.step_id} (attempt {retries + 1})")
                
                # Create a derived task for this step
                derived_task = Task(
                    title=f"Chain Step: {step.agent.name}",
                    description=f"Executing {step.agent.name} as part of chain {self.name}",
                    agent_type=step.agent.name,
                    project_id=initial_task.project_id,
                    status=TaskStatus.IN_PROGRESS.value,
                    metadata={
                        "chain_name": self.name,
                        "step_id": step.step_id,
                        "parent_task_id": initial_task.id,
                        "context": self.context
                    }
                )
                
                # Execute the step
                result = await step.agent.execute(derived_task)
                
                # Transform output if needed
                if step.output_transform:
                    result = step.output_transform(result)
                    
                # Store result in context
                self.context["step_results"][step.step_id] = {
                    "result": result,
                    "agent_name": step.agent.name,
                    "completed_at": datetime.utcnow().isoformat(),
                    "attempt": retries + 1
                }
                
                logger.info(f"Step {step.step_id} completed successfully")
                return result
                
            except Exception as e:
                last_error = e
                retries += 1
                logger.warning(f"Step {step.step_id} failed (attempt {retries}): {str(e)}")
                
                if retries <= max_retries:
                    await asyncio.sleep(2 ** retries)  # Exponential backoff
                    
        # All retries exhausted
        error_info = {
            "step_id": step.step_id,
            "agent_name": step.agent.name,
            "error": str(last_error),
            "attempts": retries,
            "failed_at": datetime.utcnow().isoformat()
        }
        
        self.context["errors"].append(error_info)
        raise Exception(f"Step {step.step_id} failed after {max_retries} retries: {str(last_error)}")
        
    async def _process_feedback(self, execution_result: Dict[str, Any]):
        """Process feedback from chain execution"""
        for handler in self.feedback_handlers:
            try:
                await handler(execution_result)
            except Exception as e:
                logger.error(f"Feedback handler error: {str(e)}")
                
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get statistics about chain executions"""
        if not self.execution_history:
            return {"total_executions": 0}
            
        total_executions = len(self.execution_history)
        successful_executions = sum(1 for exec in self.execution_history if exec["success"])
        
        avg_execution_time = sum(
            exec["execution_time"] for exec in self.execution_history if exec["execution_time"]
        ) / len(self.execution_history)
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": successful_executions / total_executions,
            "average_execution_time": avg_execution_time,
            "total_steps": len(self.steps),
            "last_execution": self.execution_history[-1]["started_at"] if self.execution_history else None
        }


class ChainManager:
    """Manages multiple agent chains"""
    
    def __init__(self):
        self.chains: Dict[str, AgentChain] = {}
        
    def create_chain(self, name: str, description: str = "") -> AgentChain:
        """Create a new agent chain"""
        chain = AgentChain(name, description)
        self.chains[name] = chain
        logger.info(f"Created chain: {name}")
        return chain
        
    def get_chain(self, name: str) -> Optional[AgentChain]:
        """Get a chain by name"""
        return self.chains.get(name)
        
    def list_chains(self) -> List[str]:
        """List all chain names"""
        return list(self.chains.keys())
        
    def get_chain_stats(self) -> Dict[str, Any]:
        """Get statistics for all chains"""
        return {
            name: chain.get_execution_stats()
            for name, chain in self.chains.items()
        }


# Global chain manager instance
chain_manager = ChainManager()