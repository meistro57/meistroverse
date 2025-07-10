from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio

from meistroverse.database import get_db, Task, Project
from meistroverse.core.task_router import task_router, TaskPriority, TaskStatus
from meistroverse.core.agent_chain import chain_manager, ChainExecutionMode
from meistroverse.core.semantic_journal import semantic_journal, JournalEntryType
from meistroverse.agents.prompt_qc_agent import PromptQCAgent
from meistroverse.agents.code_mutation_agent import CodeMutationAgent
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/launcher", tags=["task_launcher"])


# Pydantic models for API
class TaskCreate(BaseModel):
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    agent_type: str = Field(..., description="Type of agent to handle the task")
    project_id: int = Field(..., description="Project ID")
    priority: str = Field(default="medium", description="Task priority: low, medium, high")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional task metadata")


class ChainCreate(BaseModel):
    name: str = Field(..., description="Chain name")
    description: str = Field(..., description="Chain description")
    execution_mode: str = Field(default="sequential", description="Execution mode: sequential, parallel, conditional")
    initial_task: TaskCreate = Field(..., description="Initial task for the chain")


class JournalEntryCreate(BaseModel):
    content: str = Field(..., description="Journal entry content")
    entry_type: str = Field(..., description="Entry type: thought, decision, workflow, insight, reflection, goal, milestone, learning")
    title: Optional[str] = Field(None, description="Optional title")
    tags: Optional[List[str]] = Field(default_factory=list, description="Optional tags")
    context: Optional[str] = Field(None, description="Optional context for thoughts")
    reasoning: Optional[str] = Field(None, description="Reasoning for decisions")
    alternatives: Optional[List[str]] = Field(None, description="Alternatives considered for decisions")


@router.get("/", response_class=HTMLResponse)
async def launcher_home():
    """Serve the task launcher interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MEISTROVERSE Task Launcher</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a1a; color: #fff; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .launcher-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
            .launcher-card { background: #2a2a2a; padding: 20px; border-radius: 8px; border-left: 4px solid #00ff88; }
            .launcher-title { font-size: 1.3em; margin-bottom: 15px; color: #00ff88; }
            .form-group { margin-bottom: 15px; }
            .form-label { display: block; margin-bottom: 5px; color: #ccc; }
            .form-input, .form-select, .form-textarea { 
                width: 100%; padding: 10px; background: #333; color: #fff; 
                border: 1px solid #555; border-radius: 4px; box-sizing: border-box;
            }
            .form-textarea { min-height: 80px; resize: vertical; }
            .btn { background: #00ff88; color: #1a1a1a; border: none; padding: 12px 20px; 
                   border-radius: 4px; cursor: pointer; font-weight: bold; }
            .btn:hover { background: #00cc6a; }
            .btn-secondary { background: #555; color: #fff; }
            .btn-secondary:hover { background: #666; }
            .status-message { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .status-success { background: #004400; border: 1px solid #00ff88; }
            .status-error { background: #440000; border: 1px solid #ff4444; }
            .status-info { background: #004444; border: 1px solid #00aaff; }
            .task-presets { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 15px; }
            .preset-btn { padding: 8px 12px; background: #444; border: 1px solid #666; border-radius: 4px; 
                         cursor: pointer; text-align: center; font-size: 0.9em; }
            .preset-btn:hover { background: #555; border-color: #00ff88; }
            .preset-btn.active { background: #00ff88; color: #1a1a1a; }
            .toggle-section { cursor: pointer; user-select: none; }
            .toggle-section:hover { color: #00ff88; }
            .collapsible { max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
            .collapsible.expanded { max-height: 1000px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 MEISTROVERSE Task Launcher</h1>
                <p>Launch tasks, create agent chains, and manage your AI ecosystem</p>
            </div>
            
            <div class="launcher-grid">
                <!-- Quick Task Launch -->
                <div class="launcher-card">
                    <div class="launcher-title">⚡ Quick Task Launch</div>
                    
                    <div class="task-presets">
                        <div class="preset-btn" onclick="loadTaskPreset('prompt_qc')">Prompt QC</div>
                        <div class="preset-btn" onclick="loadTaskPreset('code_analysis')">Code Analysis</div>
                        <div class="preset-btn" onclick="loadTaskPreset('daily_analysis')">Daily Analysis</div>
                        <div class="preset-btn" onclick="loadTaskPreset('custom')">Custom</div>
                    </div>
                    
                    <form id="quick-task-form">
                        <div class="form-group">
                            <label class="form-label">Title</label>
                            <input type="text" id="task-title" class="form-input" placeholder="Task title">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Description</label>
                            <textarea id="task-description" class="form-textarea" placeholder="Task description"></textarea>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Agent Type</label>
                            <select id="task-agent-type" class="form-select">
                                <option value="prompt_qc_agent">Prompt QC Agent</option>
                                <option value="code_mutation_agent">Code Mutation Agent</option>
                                <option value="general">General Agent</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Priority</label>
                            <select id="task-priority" class="form-select">
                                <option value="low">Low</option>
                                <option value="medium" selected>Medium</option>
                                <option value="high">High</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <div class="toggle-section" onclick="toggleSection('task-metadata')">
                                📝 Advanced Options ▼
                            </div>
                            <div id="task-metadata" class="collapsible">
                                <label class="form-label">Metadata (JSON)</label>
                                <textarea id="task-metadata-json" class="form-textarea" placeholder='{"key": "value"}'></textarea>
                            </div>
                        </div>
                        
                        <button type="submit" class="btn">🚀 Launch Task</button>
                    </form>
                    
                    <div id="task-status"></div>
                </div>
                
                <!-- Agent Chain Builder -->
                <div class="launcher-card">
                    <div class="launcher-title">🔗 Agent Chain Builder</div>
                    
                    <form id="chain-form">
                        <div class="form-group">
                            <label class="form-label">Chain Name</label>
                            <input type="text" id="chain-name" class="form-input" placeholder="My Agent Chain">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Description</label>
                            <textarea id="chain-description" class="form-textarea" placeholder="Describe what this chain does"></textarea>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Execution Mode</label>
                            <select id="chain-mode" class="form-select">
                                <option value="sequential">Sequential</option>
                                <option value="parallel">Parallel</option>
                                <option value="conditional">Conditional</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <div class="toggle-section" onclick="toggleSection('chain-steps')">
                                🔧 Chain Steps ▼
                            </div>
                            <div id="chain-steps" class="collapsible">
                                <div id="chain-steps-container">
                                    <!-- Steps will be added here -->
                                </div>
                                <button type="button" class="btn-secondary" onclick="addChainStep()">+ Add Step</button>
                            </div>
                        </div>
                        
                        <button type="submit" class="btn">🔗 Create Chain</button>
                    </form>
                    
                    <div id="chain-status"></div>
                </div>
                
                <!-- Journal Entry -->
                <div class="launcher-card">
                    <div class="launcher-title">📚 Semantic Journal</div>
                    
                    <div class="task-presets">
                        <div class="preset-btn" onclick="loadJournalPreset('thought')">Thought</div>
                        <div class="preset-btn" onclick="loadJournalPreset('decision')">Decision</div>
                        <div class="preset-btn" onclick="loadJournalPreset('workflow')">Workflow</div>
                        <div class="preset-btn" onclick="loadJournalPreset('insight')">Insight</div>
                    </div>
                    
                    <form id="journal-form">
                        <div class="form-group">
                            <label class="form-label">Entry Type</label>
                            <select id="journal-type" class="form-select" onchange="updateJournalForm()">
                                <option value="thought">Thought</option>
                                <option value="decision">Decision</option>
                                <option value="workflow">Workflow</option>
                                <option value="insight">Insight</option>
                                <option value="reflection">Reflection</option>
                                <option value="goal">Goal</option>
                                <option value="milestone">Milestone</option>
                                <option value="learning">Learning</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Title (optional)</label>
                            <input type="text" id="journal-title" class="form-input" placeholder="Entry title">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Content</label>
                            <textarea id="journal-content" class="form-textarea" placeholder="Write your entry here..."></textarea>
                        </div>
                        
                        <div id="journal-specific-fields">
                            <!-- Type-specific fields will be added here -->
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">Tags (comma-separated)</label>
                            <input type="text" id="journal-tags" class="form-input" placeholder="tag1, tag2, tag3">
                        </div>
                        
                        <button type="submit" class="btn">📝 Save Entry</button>
                    </form>
                    
                    <div id="journal-status"></div>
                </div>
                
                <!-- System Actions -->
                <div class="launcher-card">
                    <div class="launcher-title">⚙️ System Actions</div>
                    
                    <div style="display: grid; gap: 10px;">
                        <button class="btn" onclick="triggerSystemAction('daily_analysis')">🔄 Run Daily Analysis</button>
                        <button class="btn" onclick="triggerSystemAction('rebuild_index')">🔍 Rebuild Knowledge Index</button>
                        <button class="btn" onclick="triggerSystemAction('export_journal')">📤 Export Journal</button>
                        <button class="btn-secondary" onclick="viewSystemStatus()">📊 View System Status</button>
                    </div>
                    
                    <div id="system-status"></div>
                </div>
            </div>
        </div>
        
        <script>
            let chainStepCount = 0;
            
            // Task preset configurations
            const taskPresets = {
                prompt_qc: {
                    title: "Prompt Quality Check Analysis",
                    description: "Analyze and improve prompt templates across the system",
                    agent_type: "prompt_qc_agent",
                    metadata: '{"qc_type": "performance_analysis"}'
                },
                code_analysis: {
                    title: "Code Mutation Analysis",
                    description: "Analyze codebase for improvements and security issues",
                    agent_type: "code_mutation_agent",
                    metadata: '{"mutation_type": "improvement", "target_path": "."}'
                },
                daily_analysis: {
                    title: "Daily System Analysis",
                    description: "Run comprehensive daily system analysis and suggestions",
                    agent_type: "general",
                    metadata: '{"analysis_type": "daily_loop"}'
                }
            };
            
            function loadTaskPreset(preset) {
                // Update preset button styles
                document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
                event.target.classList.add('active');
                
                if (preset === 'custom') {
                    // Clear form for custom task
                    document.getElementById('task-title').value = '';
                    document.getElementById('task-description').value = '';
                    document.getElementById('task-metadata-json').value = '';
                    return;
                }
                
                const config = taskPresets[preset];
                if (config) {
                    document.getElementById('task-title').value = config.title;
                    document.getElementById('task-description').value = config.description;
                    document.getElementById('task-agent-type').value = config.agent_type;
                    document.getElementById('task-metadata-json').value = config.metadata;
                }
            }
            
            function loadJournalPreset(type) {
                // Update preset button styles
                document.querySelectorAll('.launcher-card')[2].querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
                event.target.classList.add('active');
                
                document.getElementById('journal-type').value = type;
                updateJournalForm();
            }
            
            function updateJournalForm() {
                const type = document.getElementById('journal-type').value;
                const container = document.getElementById('journal-specific-fields');
                container.innerHTML = '';
                
                if (type === 'decision') {
                    container.innerHTML = `
                        <div class="form-group">
                            <label class="form-label">Reasoning</label>
                            <textarea id="journal-reasoning" class="form-textarea" placeholder="Why was this decision made?"></textarea>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Alternatives (one per line)</label>
                            <textarea id="journal-alternatives" class="form-textarea" placeholder="Alternative option 1\\nAlternative option 2"></textarea>
                        </div>
                    `;
                } else if (type === 'thought') {
                    container.innerHTML = `
                        <div class="form-group">
                            <label class="form-label">Context</label>
                            <textarea id="journal-context" class="form-textarea" placeholder="What triggered this thought?"></textarea>
                        </div>
                    `;
                }
            }
            
            function toggleSection(sectionId) {
                const section = document.getElementById(sectionId);
                section.classList.toggle('expanded');
            }
            
            function addChainStep() {
                chainStepCount++;
                const container = document.getElementById('chain-steps-container');
                const stepDiv = document.createElement('div');
                stepDiv.innerHTML = `
                    <div style="border: 1px solid #555; padding: 15px; margin: 10px 0; border-radius: 4px;">
                        <h4>Step ${chainStepCount}</h4>
                        <div class="form-group">
                            <label class="form-label">Agent Type</label>
                            <select class="form-select chain-step-agent">
                                <option value="prompt_qc_agent">Prompt QC Agent</option>
                                <option value="code_mutation_agent">Code Mutation Agent</option>
                                <option value="general">General Agent</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Step Description</label>
                            <input type="text" class="form-input chain-step-desc" placeholder="What should this step do?">
                        </div>
                        <button type="button" class="btn-secondary" onclick="removeChainStep(this)">Remove Step</button>
                    </div>
                `;
                container.appendChild(stepDiv);
            }
            
            function removeChainStep(button) {
                button.parentElement.remove();
            }
            
            // Form submission handlers
            document.getElementById('quick-task-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = {
                    title: document.getElementById('task-title').value,
                    description: document.getElementById('task-description').value,
                    agent_type: document.getElementById('task-agent-type').value,
                    project_id: 1, // Default project
                    priority: document.getElementById('task-priority').value,
                    metadata: {}
                };
                
                try {
                    const metadataText = document.getElementById('task-metadata-json').value.trim();
                    if (metadataText) {
                        formData.metadata = JSON.parse(metadataText);
                    }
                } catch (e) {
                    showStatus('task-status', 'Invalid JSON in metadata field', 'error');
                    return;
                }
                
                try {
                    const response = await fetch('/launcher/api/tasks', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showStatus('task-status', `Task created successfully! ID: ${result.task_id}`, 'success');
                    } else {
                        showStatus('task-status', `Error: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showStatus('task-status', `Network error: ${error.message}`, 'error');
                }
            });
            
            document.getElementById('journal-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = {
                    content: document.getElementById('journal-content').value,
                    entry_type: document.getElementById('journal-type').value,
                    title: document.getElementById('journal-title').value || null,
                    tags: document.getElementById('journal-tags').value.split(',').map(t => t.trim()).filter(t => t)
                };
                
                // Add type-specific fields
                const type = formData.entry_type;
                if (type === 'decision') {
                    formData.reasoning = document.getElementById('journal-reasoning')?.value || '';
                    const alts = document.getElementById('journal-alternatives')?.value || '';
                    formData.alternatives = alts ? alts.split('\\n').filter(a => a.trim()) : [];
                } else if (type === 'thought') {
                    formData.context = document.getElementById('journal-context')?.value || null;
                }
                
                try {
                    const response = await fetch('/launcher/api/journal', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showStatus('journal-status', 'Journal entry saved successfully!', 'success');
                        document.getElementById('journal-form').reset();
                        updateJournalForm();
                    } else {
                        showStatus('journal-status', `Error: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showStatus('journal-status', `Network error: ${error.message}`, 'error');
                }
            });
            
            function showStatus(containerId, message, type) {
                const container = document.getElementById(containerId);
                container.innerHTML = `<div class="status-message status-${type}">${message}</div>`;
                
                // Clear after 5 seconds for success messages
                if (type === 'success') {
                    setTimeout(() => {
                        container.innerHTML = '';
                    }, 5000);
                }
            }
            
            async function triggerSystemAction(action) {
                try {
                    const response = await fetch(`/launcher/api/system-actions/${action}`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showStatus('system-status', `${action} completed successfully!`, 'success');
                    } else {
                        showStatus('system-status', `Error: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showStatus('system-status', `Network error: ${error.message}`, 'error');
                }
            }
            
            async function viewSystemStatus() {
                try {
                    const response = await fetch('/dashboard/api/system-status');
                    const status = await response.json();
                    
                    const statusHtml = `
                        <div class="status-message status-info">
                            <strong>System Status:</strong><br>
                            Running Tasks: ${status.task_router_status.running_tasks}<br>
                            Registered Agents: ${status.task_router_status.registered_agents}<br>
                            Knowledge Entries: ${status.knowledge_indexer_status.total_entries}
                        </div>
                    `;
                    document.getElementById('system-status').innerHTML = statusHtml;
                } catch (error) {
                    showStatus('system-status', `Error fetching status: ${error.message}`, 'error');
                }
            }
            
            // Initialize form
            updateJournalForm();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/api/tasks")
async def create_task(task_data: TaskCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Create and launch a new task"""
    try:
        # Validate priority
        if task_data.priority not in ["low", "medium", "high"]:
            raise HTTPException(status_code=400, detail="Invalid priority. Must be low, medium, or high")
            
        priority_map = {
            "low": TaskPriority.LOW,
            "medium": TaskPriority.MEDIUM,
            "high": TaskPriority.HIGH
        }
        
        # Create task
        task = await task_router.create_task(
            title=task_data.title,
            description=task_data.description,
            agent_type=task_data.agent_type,
            project_id=task_data.project_id,
            priority=priority_map[task_data.priority],
            metadata=task_data.metadata,
            db=db
        )
        
        # Start task execution in background
        background_tasks.add_task(execute_task_background, task.id)
        
        return {
            "status": "success",
            "task_id": task.id,
            "message": f"Task '{task.title}' created and queued for execution"
        }
        
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def execute_task_background(task_id: int):
    """Execute task in background"""
    try:
        await task_router.execute_task(task_id)
    except Exception as e:
        logger.error(f"Error executing background task {task_id}: {e}")


@router.post("/api/chains")
async def create_chain(chain_data: ChainCreate, db: Session = Depends(get_db)):
    """Create and start an agent chain"""
    try:
        # Validate execution mode
        if chain_data.execution_mode not in ["sequential", "parallel", "conditional"]:
            raise HTTPException(status_code=400, detail="Invalid execution mode")
            
        mode_map = {
            "sequential": ChainExecutionMode.SEQUENTIAL,
            "parallel": ChainExecutionMode.PARALLEL,
            "conditional": ChainExecutionMode.CONDITIONAL
        }
        
        # Create chain
        chain = chain_manager.create_chain(chain_data.name, chain_data.description)
        
        # Create initial task
        task = await task_router.create_task(
            title=chain_data.initial_task.title,
            description=chain_data.initial_task.description,
            agent_type=chain_data.initial_task.agent_type,
            project_id=chain_data.initial_task.project_id,
            metadata=chain_data.initial_task.metadata,
            db=db
        )
        
        # TODO: Add chain steps based on frontend input
        # For now, just execute the initial task
        
        return {
            "status": "success",
            "chain_name": chain.name,
            "initial_task_id": task.id,
            "message": f"Chain '{chain.name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/journal")
async def create_journal_entry(entry_data: JournalEntryCreate, db: Session = Depends(get_db)):
    """Create a new journal entry"""
    try:
        # Validate entry type
        try:
            entry_type = JournalEntryType(entry_data.entry_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entry type: {entry_data.entry_type}")
            
        # Create appropriate journal entry based on type
        if entry_type == JournalEntryType.THOUGHT:
            entry = await semantic_journal.log_thought(
                thought=entry_data.content,
                context=entry_data.context,
                tags=entry_data.tags,
                db=db
            )
        elif entry_type == JournalEntryType.DECISION:
            entry = await semantic_journal.log_decision(
                decision=entry_data.content,
                reasoning=entry_data.reasoning or "",
                alternatives=entry_data.alternatives,
                tags=entry_data.tags,
                db=db
            )
        elif entry_type == JournalEntryType.WORKFLOW:
            # For workflow, expect content to contain steps
            steps = [step.strip() for step in entry_data.content.split('\n') if step.strip()]
            entry = await semantic_journal.log_workflow(
                workflow_name=entry_data.title or "Unnamed Workflow",
                steps=steps,
                tags=entry_data.tags,
                db=db
            )
        elif entry_type == JournalEntryType.INSIGHT:
            entry = await semantic_journal.log_insight(
                insight=entry_data.content,
                trigger=entry_data.context,
                tags=entry_data.tags,
                db=db
            )
        else:
            # For other types, use generic create_entry
            entry = await semantic_journal.create_entry(
                content=entry_data.content,
                entry_type=entry_type,
                title=entry_data.title,
                tags=entry_data.tags,
                db=db
            )
            
        return {
            "status": "success",
            "entry_id": entry.id,
            "title": entry.title,
            "message": "Journal entry created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating journal entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/system-actions/{action}")
async def trigger_system_action(action: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger various system actions"""
    try:
        if action == "daily_analysis":
            # Import here to avoid circular imports
            from meistroverse.core.suggestion_loop import suggestion_loop
            background_tasks.add_task(run_daily_analysis_background)
            return {"status": "success", "message": "Daily analysis started in background"}
            
        elif action == "rebuild_index":
            background_tasks.add_task(rebuild_knowledge_index)
            return {"status": "success", "message": "Knowledge index rebuild started"}
            
        elif action == "export_journal":
            # Create export task
            task = await task_router.create_task(
                title="Export Semantic Journal",
                description="Export journal entries to various formats",
                agent_type="general",
                project_id=1,
                metadata={"action": "export_journal", "format": "json"},
                db=db
            )
            return {"status": "success", "task_id": task.id, "message": "Journal export task created"}
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
            
    except Exception as e:
        logger.error(f"Error triggering system action {action}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_daily_analysis_background():
    """Run daily analysis in background"""
    try:
        from meistroverse.core.suggestion_loop import suggestion_loop
        await suggestion_loop.run_daily_analysis()
    except Exception as e:
        logger.error(f"Error in background daily analysis: {e}")


async def rebuild_knowledge_index():
    """Rebuild knowledge index in background"""
    try:
        from meistroverse.core.knowledge_indexer import knowledge_indexer
        db = next(get_db())
        knowledge_indexer.rebuild_index(db)
    except Exception as e:
        logger.error(f"Error rebuilding knowledge index: {e}")


@router.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: int, db: Session = Depends(get_db)):
    """Get status of a specific task"""
    try:
        status = await task_router.get_task_status(task_id, db)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tasks")
async def list_tasks(
    status: Optional[str] = None,
    agent_type: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """List tasks with optional filtering"""
    try:
        query = db.query(Task)
        
        if status:
            query = query.filter(Task.status == status)
        if agent_type:
            query = query.filter(Task.agent_type == agent_type)
            
        tasks = query.order_by(Task.created_at.desc()).limit(limit).all()
        
        return {
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "agent_type": task.agent_type,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat()
                }
                for task in tasks
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/agents")
async def list_available_agents():
    """List available agent types"""
    return {
        "agents": [
            {
                "type": "prompt_qc_agent",
                "name": "Prompt QC Agent",
                "description": "Analyzes and improves prompt templates"
            },
            {
                "type": "code_mutation_agent", 
                "name": "Code Mutation Agent",
                "description": "Analyzes code for improvements and issues"
            },
            {
                "type": "general",
                "name": "General Agent",
                "description": "General purpose task executor"
            }
        ]
    }