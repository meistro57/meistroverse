import uvicorn
import asyncio
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from meistroverse.config import settings
from meistroverse.database import create_tables, get_db
from meistroverse.api import dashboard_router, task_launcher_router
from meistroverse.core.task_router import task_router
from meistroverse.core.suggestion_loop import suggestion_loop
from meistroverse.agents.prompt_qc_agent import PromptQCAgent
from meistroverse.agents.code_mutation_agent import CodeMutationAgent
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Starting MEISTROVERSE application")
    
    # Create database tables
    logger.info("Creating database tables")
    create_tables()
    
    # Register agents with task router
    logger.info("Registering agents")
    prompt_qc_agent = PromptQCAgent()
    code_mutation_agent = CodeMutationAgent()
    
    task_router.register_agent("prompt_qc_agent", prompt_qc_agent)
    task_router.register_agent("code_mutation_agent", code_mutation_agent)
    
    # Start task queue processor
    logger.info("Starting task queue processor")
    asyncio.create_task(task_router.process_queue())
    
    # Start daily suggestion loop
    logger.info("Starting daily suggestion loop")
    suggestion_loop.start_daily_schedule()
    
    yield
    
    # Shutdown
    logger.info("Shutting down MEISTROVERSE application")
    suggestion_loop.stop_daily_schedule()


# Create FastAPI application
app = FastAPI(
    title="MEISTROVERSE",
    description="Omni-Behavioral Evolutionary Logic Interface for Synchronic Knowledge",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dashboard_router)
app.include_router(task_launcher_router)


@app.get("/")
async def root():
    """Redirect to dashboard"""
    return RedirectResponse(url="/dashboard/")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "MEISTROVERSE",
        "version": "0.1.0"
    }


@app.get("/api/info")
async def get_system_info(db=Depends(get_db)):
    """Get system information"""
    return {
        "name": "MEISTROVERSE",
        "description": "Omni-Behavioral Evolutionary Logic Interface for Synchronic Knowledge",
        "version": "0.1.0",
        "phase": "Phase 1: Embodied System",
        "components": {
            "persistent_agentic_core": "✅ Implemented",
            "semantic_journal": "✅ Implemented", 
            "knowledge_indexer": "✅ Implemented",
            "agent_chains": "✅ Implemented",
            "suggestion_loop": "✅ Implemented",
            "unified_dashboard": "✅ Implemented",
            "task_launcher": "✅ Implemented"
        },
        "agents": {
            "prompt_qc_agent": "✅ Active",
            "code_mutation_agent": "✅ Active"
        },
        "configuration": {
            "database_configured": bool(settings.database_url),
            "openai_configured": bool(settings.openai_api_key),
            "anthropic_configured": bool(settings.anthropic_api_key),
            "debug_mode": settings.debug
        }
    }


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )