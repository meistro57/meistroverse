# MEISTROVERSE

**Omni-Behavioral Evolutionary Logic Interface for Synchronic Knowledge**

A living system that evolves with the creator - an advanced AI agent ecosystem that captures thoughts, automates tasks, and continuously improves itself.

## 🚀 Overview

MEISTROVERSE is a comprehensive AI agent system designed to:

- **Capture & Index**: Thoughts, decisions, and workflows in persistent memory
- **Automate Tasks**: Using intelligent agent chains and task routing
- **Self-Improve**: Through daily analysis loops and prompt/code optimization
- **Evolve**: With feedback mechanisms and learning capabilities

## 🏗️ Architecture

### Phase 1: Embodied System (Current)

#### Core Components

1. **Persistent Agentic Core**
   - Task router and executor
   - Agent chain orchestration with feedback
   - Persistent memory and state management

2. **Semantic Journal Module**
   - Captures thoughts, decisions, workflows, insights
   - Vector-based semantic search and indexing
   - Knowledge relationship mapping

3. **Self-Updating Subsystems**
   - Prompt QC Agent: Monitors and improves prompt quality
   - Code Mutation Agent: Analyzes and suggests code improvements
   - Daily suggestion loop: Automated system analysis and recommendations

4. **Unified Dashboard & Task Launcher**
   - Real-time system monitoring and status
   - Interactive task creation and management
   - Agent chain builder interface

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.9+
- MySQL database
- Redis (for task queuing)
- OpenAI API key (optional)
- Anthropic API key (optional)

### Installation

1. **Clone and setup**:
   ```bash
   git clone <repository>
   cd meistroverse_test_claude
   pip install -e .
   ```

2. **Environment Configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Database Setup**:
   ```bash
   # Create MySQL database
   mysql -u root -p -e "CREATE DATABASE meistroverse;"
   ```

4. **Run the System**:
   ```bash
   python main.py
   ```

5. **Access the Interface**:
   - Dashboard: http://localhost:8000/dashboard/
   - Task Launcher: http://localhost:8000/launcher/
   - API Docs: http://localhost:8000/docs

## 🎯 Key Features

### Intelligent Task Routing
- Automatic agent selection based on task type
- Priority-based queue management
- Concurrent execution with failure handling

### Semantic Knowledge Management
- Vector-based semantic search across all content
- Automatic knowledge extraction from logs and activities
- Relationship mapping between concepts and decisions

### Self-Improvement Loops
- Daily analysis of system performance and patterns
- Automatic prompt optimization based on success rates
- Code quality analysis with improvement suggestions

### Agent Chains
- Sequential, parallel, and conditional execution modes
- Feedback mechanisms between agents
- Dynamic chain modification based on results

## 🤖 Available Agents

### Prompt QC Agent
- Analyzes prompt templates for quality and effectiveness
- Monitors success rates and execution times
- Suggests improvements and optimizations
- Performs security and best practices checks

### Code Mutation Agent
- Static code analysis for multiple languages
- Security vulnerability detection
- Performance optimization suggestions
- Refactoring recommendations with confidence scores

## 📊 Dashboard Features

### Real-time Monitoring
- System health scoring with live metrics
- Task execution status and queue management
- Agent performance tracking
- Knowledge base growth analytics

### Interactive Controls
- Manual task creation and launching
- Agent chain builder with visual interface
- System action triggers (analysis, exports, etc.)
- Configuration management

## 📚 Semantic Journal

### Entry Types
- **Thoughts**: Capture ideas with context
- **Decisions**: Document reasoning and alternatives
- **Workflows**: Record step-by-step processes
- **Insights**: Log discoveries and implications
- **Reflections**: Analyze outcomes and learnings

### Features
- Automatic semantic indexing
- Related content discovery
- Time-based pattern analysis
- Export capabilities (JSON, Markdown, CSV)

## 🔄 Daily Suggestion Loop

Automated daily analysis that:

1. **System Health Check**: Monitors task success rates, execution times, error patterns
2. **Performance Trends**: Analyzes week-over-week improvements and degradations  
3. **Code Quality**: Reviews recent code changes and suggests improvements
4. **Knowledge Patterns**: Identifies trending topics and knowledge gaps
5. **Action Items**: Creates prioritized tasks for system improvements

## 🛡️ Security & Best Practices

- Environment variable configuration for secrets
- Input validation and sanitization
- SQL injection prevention through ORM
- Rate limiting and timeout handling
- Comprehensive logging and monitoring

## 🚧 Development

### Project Structure
```
meistroverse/
├── core/           # Core system components
├── agents/         # AI agents and processors
├── api/           # Web API and interfaces
├── database/      # Data models and connections
├── utils/         # Utilities and helpers
└── config/        # Configuration management
```

### Adding New Agents

1. Inherit from `BaseAgent`
2. Implement required methods (`execute`, `get_capabilities`)
3. Register with task router
4. Add to available agents list

### Extending Functionality

The system is designed for extensibility:
- Plugin-based agent architecture
- Configurable task routing
- Modular knowledge indexing
- Flexible chain execution modes

## 📈 Future Roadmap

### Phase 2: Living Ecosystem
- Modular microservice architecture
- Cross-project memory sharing
- Enhanced AI personalities per agent
- Weekly self-improvement cycles

### Phase 3: Creator's Dominion
- Local model fine-tuning on personal data
- Auto-generated content pipelines
- Public impact scaling tools
- Distributed discovery network

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Built with:
- FastAPI for web framework
- SQLAlchemy for database ORM
- FAISS for vector similarity search
- Sentence Transformers for embeddings
- OpenAI/Anthropic APIs for LLM integration

---

*"A living system that evolves with the creator"* - MEISTROVERSE represents the fusion of human creativity with AI capability, creating a symbiotic intelligence that grows stronger over time.