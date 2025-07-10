from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    tasks = relationship("Task", back_populates="project")
    logs = relationship("ProjectLog", back_populates="project")


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    title = Column(String(255), index=True)
    description = Column(Text)
    status = Column(String(50), default="pending")  # pending, in_progress, completed, failed
    priority = Column(String(20), default="medium")  # low, medium, high
    agent_type = Column(String(100))  # Which agent handles this task
    task_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    project = relationship("Project", back_populates="tasks")
    executions = relationship("TaskExecution", back_populates="task")
    logs = relationship("TaskLog", back_populates="task")


class TaskExecution(Base):
    __tablename__ = "task_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    agent_id = Column(String(100))
    execution_data = Column(JSON)
    result = Column(Text)
    success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    task = relationship("Task", back_populates="executions")


class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)
    agent_type = Column(String(100))  # task_router, code_mutation, prompt_qc, etc.
    description = Column(Text)
    system_prompt = Column(Text)
    configuration = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    logs = relationship("AgentLog", back_populates="agent")


class ProjectLog(Base):
    __tablename__ = "project_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    log_type = Column(String(50))  # info, warning, error, debug
    message = Column(Text)
    log_metadata = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="logs")


class TaskLog(Base):
    __tablename__ = "task_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    log_type = Column(String(50))
    message = Column(Text)
    log_metadata = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    task = relationship("Task", back_populates="logs")


class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    log_type = Column(String(50))
    message = Column(Text)
    log_metadata = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("Agent", back_populates="logs")


class Knowledge(Base):
    __tablename__ = "knowledge"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    content = Column(Text)
    content_type = Column(String(50))  # thought, decision, workflow, code, etc.
    tags = Column(JSON)
    embedding = Column(Text)  # Serialized vector embedding
    source = Column(String(255))  # Where this knowledge came from
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True)
    template = Column(Text)
    variables = Column(JSON)
    agent_type = Column(String(100))
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    performance_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemMetrics(Base):
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), index=True)
    metric_value = Column(Float)
    metric_type = Column(String(50))  # counter, gauge, histogram
    labels = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)


class WorkflowState(Base):
    __tablename__ = "workflow_states"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String(100), index=True)
    state_data = Column(JSON)
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)