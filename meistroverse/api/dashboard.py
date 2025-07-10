from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import asyncio

from meistroverse.database import get_db, Task, TaskExecution, Agent, Knowledge, SystemMetrics
from meistroverse.core.task_router import task_router
from meistroverse.core.knowledge_indexer import knowledge_indexer
from meistroverse.core.semantic_journal import semantic_journal
from meistroverse.core.suggestion_loop import suggestion_loop
from meistroverse.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
                
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


@router.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Serve the main dashboard HTML page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MEISTROVERSE Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a1a; color: #fff; }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .metric-card { background: #2a2a2a; padding: 20px; border-radius: 8px; border-left: 4px solid #00ff88; }
            .metric-value { font-size: 2em; font-weight: bold; color: #00ff88; }
            .metric-label { color: #ccc; margin-top: 5px; }
            .section { background: #2a2a2a; margin-bottom: 20px; padding: 20px; border-radius: 8px; }
            .section-title { font-size: 1.4em; margin-bottom: 15px; color: #00ff88; }
            .status-indicator { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
            .status-healthy { background: #00ff88; }
            .status-warning { background: #ffaa00; }
            .status-critical { background: #ff4444; }
            .task-list { max-height: 300px; overflow-y: auto; }
            .task-item { padding: 10px; margin: 5px 0; background: #333; border-radius: 4px; }
            .task-pending { border-left: 4px solid #ffaa00; }
            .task-running { border-left: 4px solid #00aaff; }
            .task-completed { border-left: 4px solid #00ff88; }
            .task-failed { border-left: 4px solid #ff4444; }
            .refresh-btn { background: #00ff88; color: #1a1a1a; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
            #status { position: fixed; top: 10px; right: 10px; padding: 10px; background: #333; border-radius: 4px; }
            .chart-container { width: 100%; height: 200px; background: #333; border-radius: 4px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 MEISTROVERSE Dashboard</h1>
                <p>Omni-Behavioral Evolutionary Logic Interface for Synchronic Knowledge</p>
                <button class="refresh-btn" onclick="refreshDashboard()">Refresh Dashboard</button>
            </div>
            
            <div id="status">🔄 Connecting...</div>
            
            <div class="metrics-grid" id="metrics-grid">
                <!-- Metrics will be populated here -->
            </div>
            
            <div class="section">
                <div class="section-title">📊 System Health</div>
                <div id="system-health">Loading...</div>
            </div>
            
            <div class="section">
                <div class="section-title">🎯 Active Tasks</div>
                <div class="task-list" id="active-tasks">Loading...</div>
            </div>
            
            <div class="section">
                <div class="section-title">🤖 Agent Status</div>
                <div id="agent-status">Loading...</div>
            </div>
            
            <div class="section">
                <div class="section-title">📚 Knowledge Base</div>
                <div id="knowledge-stats">Loading...</div>
            </div>
            
            <div class="section">
                <div class="section-title">💡 Recent Suggestions</div>
                <div id="suggestions">Loading...</div>
            </div>
        </div>
        
        <script>
            let ws = null;
            
            function connectWebSocket() {
                ws = new WebSocket(`ws://${window.location.host}/dashboard/ws`);
                
                ws.onopen = function(event) {
                    document.getElementById('status').innerHTML = '🟢 Connected';
                    document.getElementById('status').style.background = '#004400';
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                };
                
                ws.onclose = function(event) {
                    document.getElementById('status').innerHTML = '🔴 Disconnected';
                    document.getElementById('status').style.background = '#440000';
                    // Reconnect after 5 seconds
                    setTimeout(connectWebSocket, 5000);
                };
                
                ws.onerror = function(event) {
                    document.getElementById('status').innerHTML = '⚠️ Error';
                    document.getElementById('status').style.background = '#444400';
                };
            }
            
            function updateDashboard(data) {
                if (data.type === 'dashboard_update') {
                    updateMetrics(data.metrics);
                    updateSystemHealth(data.system_health);
                    updateActiveTasks(data.active_tasks);
                    updateAgentStatus(data.agent_status);
                    updateKnowledgeStats(data.knowledge_stats);
                    updateSuggestions(data.suggestions);
                }
            }
            
            function updateMetrics(metrics) {
                const grid = document.getElementById('metrics-grid');
                grid.innerHTML = '';
                
                metrics.forEach(metric => {
                    const card = document.createElement('div');
                    card.className = 'metric-card';
                    card.innerHTML = `
                        <div class="metric-value">${metric.value}</div>
                        <div class="metric-label">${metric.label}</div>
                    `;
                    grid.appendChild(card);
                });
            }
            
            function updateSystemHealth(health) {
                const container = document.getElementById('system-health');
                const statusClass = health.score > 0.8 ? 'status-healthy' : 
                                  health.score > 0.6 ? 'status-warning' : 'status-critical';
                
                container.innerHTML = `
                    <div><span class="status-indicator ${statusClass}"></span>Health Score: ${(health.score * 100).toFixed(1)}%</div>
                    <div>Success Rate: ${(health.success_rate * 100).toFixed(1)}%</div>
                    <div>Avg Execution Time: ${health.avg_execution_time.toFixed(1)}s</div>
                    <div>Pending Tasks: ${health.pending_tasks}</div>
                `;
            }
            
            function updateActiveTasks(tasks) {
                const container = document.getElementById('active-tasks');
                container.innerHTML = '';
                
                tasks.forEach(task => {
                    const item = document.createElement('div');
                    item.className = `task-item task-${task.status.replace('_', '-')}`;
                    item.innerHTML = `
                        <strong>${task.title}</strong><br>
                        <small>Status: ${task.status} | Priority: ${task.priority} | Agent: ${task.agent_type}</small>
                    `;
                    container.appendChild(item);
                });
                
                if (tasks.length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: #888;">No active tasks</div>';
                }
            }
            
            function updateAgentStatus(agents) {
                const container = document.getElementById('agent-status');
                container.innerHTML = '';
                
                agents.forEach(agent => {
                    const statusClass = agent.is_active ? 'status-healthy' : 'status-critical';
                    const item = document.createElement('div');
                    item.style.padding = '10px 0';
                    item.innerHTML = `
                        <span class="status-indicator ${statusClass}"></span>
                        <strong>${agent.name}</strong> (${agent.agent_type})
                        <small style="float: right;">Updated: ${new Date(agent.updated_at).toLocaleString()}</small>
                    `;
                    container.appendChild(item);
                });
            }
            
            function updateKnowledgeStats(stats) {
                const container = document.getElementById('knowledge-stats');
                container.innerHTML = `
                    <div>Total Entries: ${stats.total_entries}</div>
                    <div>Index Size: ${stats.index_size}</div>
                    <div>Recent Additions: ${stats.recent_additions}</div>
                    <div>Content Types: ${Object.keys(stats.content_types).length}</div>
                `;
            }
            
            function updateSuggestions(suggestions) {
                const container = document.getElementById('suggestions');
                container.innerHTML = '';
                
                suggestions.forEach(suggestion => {
                    const item = document.createElement('div');
                    item.style.padding = '10px';
                    item.style.margin = '5px 0';
                    item.style.background = '#333';
                    item.style.borderRadius = '4px';
                    item.innerHTML = `
                        <strong>${suggestion.title}</strong><br>
                        <small>${suggestion.description}</small><br>
                        <span style="color: #00ff88;">Priority: ${suggestion.priority}</span>
                    `;
                    container.appendChild(item);
                });
                
                if (suggestions.length === 0) {
                    container.innerHTML = '<div style="text-align: center; color: #888;">No recent suggestions</div>';
                }
            }
            
            function refreshDashboard() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({action: 'refresh'}));
                }
            }
            
            // Initialize WebSocket connection
            connectWebSocket();
            
            // Auto-refresh every 30 seconds
            setInterval(refreshDashboard, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    await manager.connect(websocket)
    try:
        # Send initial dashboard data
        await send_dashboard_update(websocket)
        
        while True:
            # Wait for client messages
            data = await websocket.receive_json()
            
            if data.get("action") == "refresh":
                await send_dashboard_update(websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def send_dashboard_update(websocket: WebSocket = None):
    """Send dashboard update to client(s)"""
    try:
        db = next(get_db())
        
        # Gather all dashboard data
        dashboard_data = {
            "type": "dashboard_update",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": await get_key_metrics(db),
            "system_health": await get_system_health(db),
            "active_tasks": await get_active_tasks(db),
            "agent_status": await get_agent_status(db),
            "knowledge_stats": await get_knowledge_stats(db),
            "suggestions": await get_recent_suggestions(db)
        }
        
        if websocket:
            await websocket.send_json(dashboard_data)
        else:
            await manager.broadcast(dashboard_data)
            
    except Exception as e:
        logger.error(f"Error sending dashboard update: {e}")


@router.get("/api/metrics")
async def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Get key dashboard metrics"""
    return {
        "metrics": await get_key_metrics(db),
        "system_health": await get_system_health(db),
        "active_tasks": await get_active_tasks(db),
        "agent_status": await get_agent_status(db),
        "knowledge_stats": await get_knowledge_stats(db),
        "suggestions": await get_recent_suggestions(db)
    }


async def get_key_metrics(db: Session) -> List[Dict[str, Any]]:
    """Get key system metrics for the dashboard"""
    # Get metrics for last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    # Total tasks executed
    total_tasks = db.query(TaskExecution).filter(TaskExecution.started_at >= yesterday).count()
    
    # Success rate
    successful_tasks = db.query(TaskExecution).filter(
        TaskExecution.started_at >= yesterday,
        TaskExecution.success == True
    ).count()
    success_rate = (successful_tasks / max(total_tasks, 1)) * 100
    
    # Active agents
    active_agents = db.query(Agent).filter(Agent.is_active == True).count()
    
    # Knowledge entries
    total_knowledge = db.query(Knowledge).count()
    
    # Pending tasks
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    
    return [
        {"label": "Tasks (24h)", "value": f"{total_tasks}"},
        {"label": "Success Rate", "value": f"{success_rate:.1f}%"},
        {"label": "Active Agents", "value": f"{active_agents}"},
        {"label": "Knowledge Entries", "value": f"{total_knowledge}"},
        {"label": "Pending Tasks", "value": f"{pending_tasks}"}
    ]


async def get_system_health(db: Session) -> Dict[str, Any]:
    """Get overall system health status"""
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    # Get recent executions
    executions = db.query(TaskExecution).filter(TaskExecution.started_at >= yesterday).all()
    
    if not executions:
        return {
            "score": 1.0,
            "success_rate": 1.0,
            "avg_execution_time": 0.0,
            "pending_tasks": 0,
            "status": "healthy"
        }
    
    # Calculate metrics
    successful = sum(1 for e in executions if e.success)
    success_rate = successful / len(executions)
    
    # Average execution time
    completed = [e for e in executions if e.completed_at and e.started_at]
    avg_time = 0.0
    if completed:
        avg_time = sum((e.completed_at - e.started_at).total_seconds() for e in completed) / len(completed)
    
    # Pending tasks
    pending_tasks = db.query(Task).filter(Task.status == "pending").count()
    
    # Calculate health score
    health_score = success_rate * 0.6 + (1.0 - min(avg_time / 30, 1.0)) * 0.3 + (1.0 - min(pending_tasks / 10, 1.0)) * 0.1
    
    status = "healthy" if health_score > 0.8 else "warning" if health_score > 0.6 else "critical"
    
    return {
        "score": health_score,
        "success_rate": success_rate,
        "avg_execution_time": avg_time,
        "pending_tasks": pending_tasks,
        "status": status
    }


async def get_active_tasks(db: Session) -> List[Dict[str, Any]]:
    """Get currently active and recent tasks"""
    # Get tasks from last hour or pending/in_progress tasks
    hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    tasks = (
        db.query(Task)
        .filter(
            (Task.status.in_(["pending", "in_progress"])) |
            (Task.updated_at >= hour_ago)
        )
        .order_by(Task.updated_at.desc())
        .limit(10)
        .all()
    )
    
    return [
        {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "agent_type": task.agent_type,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat()
        }
        for task in tasks
    ]


async def get_agent_status(db: Session) -> List[Dict[str, Any]]:
    """Get status of all agents"""
    agents = db.query(Agent).all()
    
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "agent_type": agent.agent_type,
            "is_active": agent.is_active,
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat()
        }
        for agent in agents
    ]


async def get_knowledge_stats(db: Session) -> Dict[str, Any]:
    """Get knowledge base statistics"""
    return knowledge_indexer.get_knowledge_stats(db)


async def get_recent_suggestions(db: Session) -> List[Dict[str, Any]]:
    """Get recent suggestions from the suggestion loop"""
    # Get recent analysis entries
    recent_analysis = (
        db.query(Knowledge)
        .filter(Knowledge.source == "daily_suggestion_loop")
        .order_by(Knowledge.created_at.desc())
        .limit(5)
        .all()
    )
    
    suggestions = []
    for analysis in recent_analysis:
        # Extract suggestions from content (simple text parsing)
        if "suggestions" in analysis.content.lower():
            suggestions.append({
                "title": analysis.title,
                "description": analysis.content[:200] + "..." if len(analysis.content) > 200 else analysis.content,
                "priority": "medium",  # Default priority
                "created_at": analysis.created_at.isoformat()
            })
    
    return suggestions[:5]


@router.get("/api/system-status")
async def get_system_status(db: Session = Depends(get_db)):
    """Get detailed system status"""
    return {
        "task_router_status": {
            "running_tasks": len(task_router.running_tasks),
            "registered_agents": len(task_router.agents)
        },
        "suggestion_loop_status": suggestion_loop.get_status(),
        "knowledge_indexer_status": {
            "total_entries": knowledge_indexer.index.ntotal,
            "dimension": knowledge_indexer.dimension
        }
    }


@router.post("/api/actions/run-analysis")
async def trigger_analysis(analysis_type: str, db: Session = Depends(get_db)):
    """Trigger specific analysis manually"""
    if analysis_type == "daily":
        # Trigger daily suggestion loop
        result = await suggestion_loop.run_daily_analysis()
        await send_dashboard_update()  # Broadcast update
        return {"status": "success", "result": result}
    
    elif analysis_type == "prompt_qc":
        # Create prompt QC task
        task = await task_router.create_task(
            title="Manual Prompt QC Analysis",
            description="Manually triggered prompt quality check",
            agent_type="prompt_qc_agent",
            project_id=1,
            metadata={"qc_type": "performance_analysis"},
            db=db
        )
        return {"status": "success", "task_id": task.id}
    
    elif analysis_type == "code_mutation":
        # Create code mutation task
        task = await task_router.create_task(
            title="Manual Code Mutation Analysis",
            description="Manually triggered code analysis",
            agent_type="code_mutation_agent", 
            project_id=1,
            metadata={"mutation_type": "improvement", "target_path": "."},
            db=db
        )
        return {"status": "success", "task_id": task.id}
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown analysis type: {analysis_type}")


# Background task to periodically update dashboard
async def periodic_dashboard_updates():
    """Send periodic updates to connected clients"""
    while True:
        try:
            if manager.active_connections:
                await send_dashboard_update()
            await asyncio.sleep(30)  # Update every 30 seconds
        except Exception as e:
            logger.error(f"Error in periodic dashboard updates: {e}")
            await asyncio.sleep(60)  # Wait longer if error


# Start background task when module is imported
asyncio.create_task(periodic_dashboard_updates())