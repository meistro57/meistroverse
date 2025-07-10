import ast
import os
import sys
import json
import subprocess
import tempfile
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from sqlalchemy.orm import Session

from meistroverse.agents.base import BaseAgent
from meistroverse.database import get_db, Task, Knowledge
from meistroverse.core.knowledge_indexer import knowledge_indexer
from meistroverse.utils.logger import get_logger
from meistroverse.config import settings

logger = get_logger(__name__)


@dataclass
class CodeMutation:
    """Represents a code mutation and its metadata"""
    file_path: str
    original_code: str
    mutated_code: str
    mutation_type: str
    line_number: int
    confidence: float
    reasoning: str
    test_results: Optional[Dict[str, Any]] = None


class CodeMutationAgent(BaseAgent):
    """Agent that identifies and suggests code improvements through mutations"""
    
    def __init__(self):
        super().__init__(name="CodeMutationAgent")
        self.anthropic_client = None
        self.openai_client = None
        self._init_llm_clients()
        
    def _init_llm_clients(self):
        """Initialize LLM clients for code analysis"""
        try:
            if settings.anthropic_api_key:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                
            if settings.openai_api_key:
                import openai
                self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
                
        except ImportError as e:
            logger.warning(f"Could not initialize LLM clients: {e}")
            
    async def execute(self, task: Task) -> Dict[str, Any]:
        """Execute code mutation analysis"""
        logger.info(f"Starting code mutation analysis for task: {task.title}")
        
        # Get task parameters
        mutation_type = task.metadata.get("mutation_type", "improvement")
        target_path = task.metadata.get("target_path", ".")
        language = task.metadata.get("language", "python")
        
        if mutation_type == "improvement":
            return await self._suggest_improvements(target_path, language)
        elif mutation_type == "security":
            return await self._security_audit(target_path, language)
        elif mutation_type == "performance":
            return await self._performance_optimization(target_path, language)
        elif mutation_type == "refactor":
            return await self._refactor_suggestions(target_path, language)
        else:
            raise ValueError(f"Unknown mutation type: {mutation_type}")
            
    async def _suggest_improvements(self, target_path: str, language: str) -> Dict[str, Any]:
        """Suggest general code improvements"""
        logger.info(f"Analyzing {target_path} for improvement opportunities")
        
        # Find code files
        code_files = self._find_code_files(target_path, language)
        
        mutations = []
        
        for file_path in code_files:
            try:
                # Analyze file
                file_mutations = await self._analyze_file(file_path, language, "improvement")
                mutations.extend(file_mutations)
                
                # Store analysis in knowledge base
                await self._store_analysis(file_path, file_mutations)
                
            except Exception as e:
                logger.error(f"Error analyzing {file_path}: {e}")
                continue
                
        return {
            "mutation_type": "improvement",
            "files_analyzed": len(code_files),
            "mutations_found": len(mutations),
            "mutations": [self._mutation_to_dict(m) for m in mutations],
            "summary": self._generate_mutation_summary(mutations)
        }
        
    async def _security_audit(self, target_path: str, language: str) -> Dict[str, Any]:
        """Perform security audit and suggest fixes"""
        logger.info(f"Performing security audit of {target_path}")
        
        code_files = self._find_code_files(target_path, language)
        security_issues = []
        
        for file_path in code_files:
            try:
                # Check for common security issues
                issues = await self._check_security_issues(file_path, language)
                security_issues.extend(issues)
                
            except Exception as e:
                logger.error(f"Error in security audit of {file_path}: {e}")
                continue
                
        return {
            "mutation_type": "security",
            "files_analyzed": len(code_files),
            "security_issues": len(security_issues),
            "issues": [self._mutation_to_dict(issue) for issue in security_issues],
            "risk_level": self._calculate_risk_level(security_issues)
        }
        
    async def _performance_optimization(self, target_path: str, language: str) -> Dict[str, Any]:
        """Identify performance optimization opportunities"""
        logger.info(f"Analyzing {target_path} for performance optimizations")
        
        code_files = self._find_code_files(target_path, language)
        optimizations = []
        
        for file_path in code_files:
            try:
                # Analyze for performance issues
                perf_issues = await self._analyze_performance(file_path, language)
                optimizations.extend(perf_issues)
                
            except Exception as e:
                logger.error(f"Error in performance analysis of {file_path}: {e}")
                continue
                
        return {
            "mutation_type": "performance",
            "files_analyzed": len(code_files),
            "optimizations_found": len(optimizations),
            "optimizations": [self._mutation_to_dict(opt) for opt in optimizations],
            "potential_impact": self._estimate_performance_impact(optimizations)
        }
        
    async def _refactor_suggestions(self, target_path: str, language: str) -> Dict[str, Any]:
        """Suggest refactoring opportunities"""
        logger.info(f"Analyzing {target_path} for refactoring opportunities")
        
        code_files = self._find_code_files(target_path, language)
        refactoring_suggestions = []
        
        for file_path in code_files:
            try:
                # Analyze code structure
                suggestions = await self._analyze_code_structure(file_path, language)
                refactoring_suggestions.extend(suggestions)
                
            except Exception as e:
                logger.error(f"Error in refactoring analysis of {file_path}: {e}")
                continue
                
        return {
            "mutation_type": "refactor",
            "files_analyzed": len(code_files),
            "suggestions_found": len(refactoring_suggestions),
            "suggestions": [self._mutation_to_dict(s) for s in refactoring_suggestions],
            "complexity_reduction": self._estimate_complexity_reduction(refactoring_suggestions)
        }
        
    def _find_code_files(self, target_path: str, language: str) -> List[str]:
        """Find code files in the target path"""
        extensions = {
            "python": [".py"],
            "javascript": [".js", ".jsx", ".ts", ".tsx"],
            "java": [".java"],
            "cpp": [".cpp", ".cc", ".cxx", ".c++"],
            "c": [".c", ".h"],
            "go": [".go"],
            "rust": [".rs"],
            "php": [".php"],
            "ruby": [".rb"]
        }
        
        target_extensions = extensions.get(language, [".py"])
        code_files = []
        
        path = Path(target_path)
        if path.is_file():
            if any(str(path).endswith(ext) for ext in target_extensions):
                code_files.append(str(path))
        else:
            for ext in target_extensions:
                code_files.extend(path.rglob(f"*{ext}"))
                
        return [str(f) for f in code_files]
        
    async def _analyze_file(self, file_path: str, language: str, analysis_type: str) -> List[CodeMutation]:
        """Analyze a single file for mutations"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        mutations = []
        
        if language == "python":
            mutations.extend(await self._analyze_python_file(file_path, content, analysis_type))
        elif language in ["javascript", "typescript"]:
            mutations.extend(await self._analyze_js_file(file_path, content, analysis_type))
        else:
            # Generic analysis using LLM
            mutations.extend(await self._analyze_generic_file(file_path, content, language, analysis_type))
            
        return mutations
        
    async def _analyze_python_file(self, file_path: str, content: str, analysis_type: str) -> List[CodeMutation]:
        """Analyze Python file using AST and pattern matching"""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return []
            
        mutations = []
        
        # Find various patterns
        mutations.extend(self._find_unused_imports(tree, content, file_path))
        mutations.extend(self._find_inefficient_loops(tree, content, file_path))
        mutations.extend(self._find_code_smells(tree, content, file_path))
        mutations.extend(self._find_security_issues_python(tree, content, file_path))
        
        # Use LLM for more complex analysis
        if self.anthropic_client or self.openai_client:
            llm_mutations = await self._llm_analyze_python(file_path, content, analysis_type)
            mutations.extend(llm_mutations)
            
        return mutations
        
    def _find_unused_imports(self, tree: ast.AST, content: str, file_path: str) -> List[CodeMutation]:
        """Find unused imports"""
        mutations = []
        
        # Get all imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, alias.asname or alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports.append((f"{node.module}.{alias.name}" if node.module else alias.name, 
                                  alias.asname or alias.name, node.lineno))
                    
        # Check usage
        lines = content.split('\n')
        for full_name, used_name, line_no in imports:
            if not self._is_name_used(tree, used_name, line_no):
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=lines[line_no - 1],
                    mutated_code="",  # Remove the line
                    mutation_type="unused_import",
                    line_number=line_no,
                    confidence=0.8,
                    reasoning=f"Import '{used_name}' appears to be unused"
                ))
                
        return mutations
        
    def _is_name_used(self, tree: ast.AST, name: str, import_line: int) -> bool:
        """Check if a name is used in the AST after import"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == name:
                if hasattr(node, 'lineno') and node.lineno > import_line:
                    return True
        return False
        
    def _find_inefficient_loops(self, tree: ast.AST, content: str, file_path: str) -> List[CodeMutation]:
        """Find inefficient loop patterns"""
        mutations = []
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # Check for range(len(x)) pattern
                if (isinstance(node.iter, ast.Call) and 
                    isinstance(node.iter.func, ast.Name) and 
                    node.iter.func.id == 'range' and
                    len(node.iter.args) == 1 and
                    isinstance(node.iter.args[0], ast.Call) and
                    isinstance(node.iter.args[0].func, ast.Name) and
                    node.iter.args[0].func.id == 'len'):
                    
                    original_code = lines[node.lineno - 1]
                    # Suggest enumerate instead
                    mutations.append(CodeMutation(
                        file_path=file_path,
                        original_code=original_code,
                        mutated_code=original_code.replace('range(len(', 'enumerate(').replace('))', ')'),
                        mutation_type="inefficient_loop",
                        line_number=node.lineno,
                        confidence=0.9,
                        reasoning="Use enumerate() instead of range(len()) for better readability"
                    ))
                    
        return mutations
        
    def _find_code_smells(self, tree: ast.AST, content: str, file_path: str) -> List[CodeMutation]:
        """Find code smells and suggest improvements"""
        mutations = []
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            # Long functions
            if isinstance(node, ast.FunctionDef):
                func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if func_lines > 50:
                    mutations.append(CodeMutation(
                        file_path=file_path,
                        original_code=f"def {node.name}(...):",
                        mutated_code=f"# Consider breaking down function {node.name}",
                        mutation_type="long_function",
                        line_number=node.lineno,
                        confidence=0.7,
                        reasoning=f"Function {node.name} is {func_lines} lines long, consider breaking it down"
                    ))
                    
            # Too many parameters
            if isinstance(node, ast.FunctionDef) and len(node.args.args) > 5:
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=f"def {node.name}(...{len(node.args.args)} parameters...):",
                    mutated_code=f"# Consider using a configuration object for {node.name}",
                    mutation_type="too_many_parameters",
                    line_number=node.lineno,
                    confidence=0.6,
                    reasoning=f"Function {node.name} has {len(node.args.args)} parameters, consider using a config object"
                ))
                
        return mutations
        
    def _find_security_issues_python(self, tree: ast.AST, content: str, file_path: str) -> List[CodeMutation]:
        """Find security issues in Python code"""
        mutations = []
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            # Check for eval() usage
            if (isinstance(node, ast.Call) and 
                isinstance(node.func, ast.Name) and 
                node.func.id == 'eval'):
                
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=lines[node.lineno - 1],
                    mutated_code="# WARNING: eval() is dangerous - consider ast.literal_eval() or other alternatives",
                    mutation_type="security_issue",
                    line_number=node.lineno,
                    confidence=0.95,
                    reasoning="eval() can execute arbitrary code and is a security risk"
                ))
                
            # Check for exec() usage
            if (isinstance(node, ast.Call) and 
                isinstance(node.func, ast.Name) and 
                node.func.id == 'exec'):
                
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=lines[node.lineno - 1],
                    mutated_code="# WARNING: exec() is dangerous - consider alternative approaches",
                    mutation_type="security_issue",
                    line_number=node.lineno,
                    confidence=0.95,
                    reasoning="exec() can execute arbitrary code and is a security risk"
                ))
                
        return mutations
        
    async def _llm_analyze_python(self, file_path: str, content: str, analysis_type: str) -> List[CodeMutation]:
        """Use LLM to analyze Python code for more complex patterns"""
        if not self.anthropic_client and not self.openai_client:
            return []
            
        # Truncate content if too long
        if len(content) > 4000:
            content = content[:4000] + "\n# ... (truncated)"
            
        analysis_prompt = f"""
        Analyze this Python code for {analysis_type} opportunities:
        
        File: {file_path}
        ```python
        {content}
        ```
        
        Please identify specific improvements, optimizations, or issues. For each finding:
        1. Specify the line number
        2. Describe the issue or opportunity
        3. Suggest a specific improvement
        4. Rate confidence (0-1)
        
        Respond in JSON format:
        {{
            "findings": [
                {{
                    "line_number": 10,
                    "issue": "description",
                    "suggestion": "specific improvement",
                    "confidence": 0.8,
                    "type": "category"
                }}
            ]
        }}
        """
        
        try:
            if self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": analysis_prompt}]
                )
                result = response.content[0].text
            elif self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": analysis_prompt}]
                )
                result = response.choices[0].message.content
            else:
                return []
                
            # Parse JSON response
            try:
                data = json.loads(result)
                mutations = []
                
                for finding in data.get("findings", []):
                    mutations.append(CodeMutation(
                        file_path=file_path,
                        original_code=f"# Line {finding['line_number']}",
                        mutated_code=finding["suggestion"],
                        mutation_type=finding.get("type", "llm_suggestion"),
                        line_number=finding["line_number"],
                        confidence=finding.get("confidence", 0.5),
                        reasoning=finding["issue"]
                    ))
                    
                return mutations
                
            except json.JSONDecodeError:
                logger.warning(f"Could not parse LLM response as JSON: {result}")
                return []
                
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}")
            return []
            
    async def _analyze_js_file(self, file_path: str, content: str, analysis_type: str) -> List[CodeMutation]:
        """Analyze JavaScript/TypeScript file"""
        mutations = []
        
        # Basic pattern matching for common issues
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for console.log in production code
            if 'console.log' in line and 'node_modules' not in file_path:
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=line.strip(),
                    mutated_code="// " + line.strip(),
                    mutation_type="debug_code",
                    line_number=i,
                    confidence=0.8,
                    reasoning="Remove console.log statements from production code"
                ))
                
            # Check for var usage
            if line.strip().startswith('var '):
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=line.strip(),
                    mutated_code=line.strip().replace('var ', 'let '),
                    mutation_type="var_to_let",
                    line_number=i,
                    confidence=0.9,
                    reasoning="Use let/const instead of var for better scoping"
                ))
                
        return mutations
        
    async def _analyze_generic_file(self, file_path: str, content: str, language: str, analysis_type: str) -> List[CodeMutation]:
        """Analyze file using LLM for languages without specific parsers"""
        if not self.anthropic_client and not self.openai_client:
            return []
            
        # Use LLM for generic analysis
        return await self._llm_analyze_generic(file_path, content, language, analysis_type)
        
    async def _llm_analyze_generic(self, file_path: str, content: str, language: str, analysis_type: str) -> List[CodeMutation]:
        """Use LLM to analyze code in any language"""
        if len(content) > 4000:
            content = content[:4000] + "\n# ... (truncated)"
            
        analysis_prompt = f"""
        Analyze this {language} code for {analysis_type} opportunities:
        
        File: {file_path}
        ```{language}
        {content}
        ```
        
        Please identify specific improvements, optimizations, or issues. Respond in JSON format:
        {{
            "findings": [
                {{
                    "line_number": 10,
                    "issue": "description",
                    "suggestion": "specific improvement",
                    "confidence": 0.8,
                    "type": "category"
                }}
            ]
        }}
        """
        
        try:
            if self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": analysis_prompt}]
                )
                result = response.content[0].text
            elif self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": analysis_prompt}]
                )
                result = response.choices[0].message.content
            else:
                return []
                
            # Parse and convert to mutations
            try:
                data = json.loads(result)
                mutations = []
                
                for finding in data.get("findings", []):
                    mutations.append(CodeMutation(
                        file_path=file_path,
                        original_code=f"# Line {finding['line_number']}",
                        mutated_code=finding["suggestion"],
                        mutation_type=finding.get("type", "llm_suggestion"),
                        line_number=finding["line_number"],
                        confidence=finding.get("confidence", 0.5),
                        reasoning=finding["issue"]
                    ))
                    
                return mutations
                
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            logger.error(f"Error in generic LLM analysis: {e}")
            return []
            
    async def _check_security_issues(self, file_path: str, language: str) -> List[CodeMutation]:
        """Check for security issues in code"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        mutations = []
        
        if language == "python":
            mutations.extend(self._check_python_security(file_path, content))
        elif language in ["javascript", "typescript"]:
            mutations.extend(self._check_js_security(file_path, content))
            
        return mutations
        
    def _check_python_security(self, file_path: str, content: str) -> List[CodeMutation]:
        """Check Python-specific security issues"""
        mutations = []
        lines = content.split('\n')
        
        # Check for hardcoded secrets
        for i, line in enumerate(lines, 1):
            if any(keyword in line.lower() for keyword in ['password', 'secret', 'api_key', 'token']):
                if '=' in line and '"' in line:
                    mutations.append(CodeMutation(
                        file_path=file_path,
                        original_code=line.strip(),
                        mutated_code="# WARNING: Potential hardcoded secret - use environment variables",
                        mutation_type="hardcoded_secret",
                        line_number=i,
                        confidence=0.7,
                        reasoning="Potential hardcoded secret detected"
                    ))
                    
        return mutations
        
    def _check_js_security(self, file_path: str, content: str) -> List[CodeMutation]:
        """Check JavaScript/TypeScript security issues"""
        mutations = []
        lines = content.split('\n')
        
        # Check for eval usage
        for i, line in enumerate(lines, 1):
            if 'eval(' in line:
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=line.strip(),
                    mutated_code="// WARNING: eval() is dangerous - consider JSON.parse() or other alternatives",
                    mutation_type="security_issue",
                    line_number=i,
                    confidence=0.95,
                    reasoning="eval() can execute arbitrary code and is a security risk"
                ))
                
        return mutations
        
    async def _analyze_performance(self, file_path: str, language: str) -> List[CodeMutation]:
        """Analyze file for performance issues"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        mutations = []
        
        if language == "python":
            mutations.extend(self._check_python_performance(file_path, content))
        elif language in ["javascript", "typescript"]:
            mutations.extend(self._check_js_performance(file_path, content))
            
        return mutations
        
    def _check_python_performance(self, file_path: str, content: str) -> List[CodeMutation]:
        """Check Python performance issues"""
        mutations = []
        lines = content.split('\n')
        
        # Check for inefficient string concatenation
        for i, line in enumerate(lines, 1):
            if '+=' in line and 'str' in line.lower():
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=line.strip(),
                    mutated_code="# Consider using list.append() and ''.join() for string concatenation",
                    mutation_type="inefficient_string_concat",
                    line_number=i,
                    confidence=0.6,
                    reasoning="String concatenation with += is inefficient for large strings"
                ))
                
        return mutations
        
    def _check_js_performance(self, file_path: str, content: str) -> List[CodeMutation]:
        """Check JavaScript performance issues"""
        mutations = []
        lines = content.split('\n')
        
        # Check for inefficient DOM queries
        for i, line in enumerate(lines, 1):
            if 'document.getElementById' in line and 'for' in lines[max(0, i-5):i]:
                mutations.append(CodeMutation(
                    file_path=file_path,
                    original_code=line.strip(),
                    mutated_code="// Consider caching DOM queries outside loops",
                    mutation_type="inefficient_dom_query",
                    line_number=i,
                    confidence=0.7,
                    reasoning="DOM queries inside loops are inefficient"
                ))
                
        return mutations
        
    async def _analyze_code_structure(self, file_path: str, language: str) -> List[CodeMutation]:
        """Analyze code structure for refactoring opportunities"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        mutations = []
        
        if language == "python":
            mutations.extend(self._analyze_python_structure(file_path, content))
            
        return mutations
        
    def _analyze_python_structure(self, file_path: str, content: str) -> List[CodeMutation]:
        """Analyze Python code structure"""
        mutations = []
        
        try:
            tree = ast.parse(content)
            
            # Check for nested complexity
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    complexity = self._calculate_cyclomatic_complexity(node)
                    if complexity > 10:
                        mutations.append(CodeMutation(
                            file_path=file_path,
                            original_code=f"def {node.name}(...):",
                            mutated_code=f"# Function {node.name} has high complexity ({complexity}), consider refactoring",
                            mutation_type="high_complexity",
                            line_number=node.lineno,
                            confidence=0.8,
                            reasoning=f"Function has cyclomatic complexity of {complexity}, consider breaking it down"
                        ))
                        
        except SyntaxError:
            pass
            
        return mutations
        
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function"""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
                
        return complexity
        
    async def _store_analysis(self, file_path: str, mutations: List[CodeMutation]) -> None:
        """Store analysis results in knowledge base"""
        if not mutations:
            return
            
        db = next(get_db())
        
        analysis_content = f"Code analysis for {file_path}\n\n"
        analysis_content += f"Found {len(mutations)} potential improvements:\n\n"
        
        for mutation in mutations:
            analysis_content += f"- Line {mutation.line_number}: {mutation.reasoning}\n"
            analysis_content += f"  Type: {mutation.mutation_type}, Confidence: {mutation.confidence:.1%}\n\n"
            
        knowledge_indexer.add_knowledge(
            title=f"Code Analysis: {Path(file_path).name}",
            content=analysis_content,
            content_type="code_analysis",
            tags=["code_mutation", "analysis", Path(file_path).suffix[1:] if Path(file_path).suffix else "unknown"],
            source=f"code_mutation_agent_{datetime.now().strftime('%Y%m%d')}",
            db=db
        )
        
    def _mutation_to_dict(self, mutation: CodeMutation) -> Dict[str, Any]:
        """Convert mutation to dictionary"""
        return {
            "file_path": mutation.file_path,
            "line_number": mutation.line_number,
            "mutation_type": mutation.mutation_type,
            "confidence": mutation.confidence,
            "reasoning": mutation.reasoning,
            "original_code": mutation.original_code[:100] + "..." if len(mutation.original_code) > 100 else mutation.original_code,
            "suggested_code": mutation.mutated_code[:100] + "..." if len(mutation.mutated_code) > 100 else mutation.mutated_code
        }
        
    def _generate_mutation_summary(self, mutations: List[CodeMutation]) -> Dict[str, Any]:
        """Generate summary of mutations"""
        if not mutations:
            return {"total": 0, "by_type": {}, "high_confidence": 0}
            
        by_type = {}
        high_confidence = 0
        
        for mutation in mutations:
            mutation_type = mutation.mutation_type
            by_type[mutation_type] = by_type.get(mutation_type, 0) + 1
            
            if mutation.confidence > 0.8:
                high_confidence += 1
                
        return {
            "total": len(mutations),
            "by_type": by_type,
            "high_confidence": high_confidence,
            "avg_confidence": sum(m.confidence for m in mutations) / len(mutations)
        }
        
    def _calculate_risk_level(self, security_issues: List[CodeMutation]) -> str:
        """Calculate overall risk level"""
        if not security_issues:
            return "low"
            
        high_risk_types = ["security_issue", "hardcoded_secret"]
        high_risk_count = sum(1 for issue in security_issues if issue.mutation_type in high_risk_types)
        
        if high_risk_count > 0:
            return "high"
        elif len(security_issues) > 5:
            return "medium"
        else:
            return "low"
            
    def _estimate_performance_impact(self, optimizations: List[CodeMutation]) -> str:
        """Estimate performance impact of optimizations"""
        if not optimizations:
            return "none"
            
        high_impact_types = ["inefficient_loop", "inefficient_string_concat", "inefficient_dom_query"]
        high_impact_count = sum(1 for opt in optimizations if opt.mutation_type in high_impact_types)
        
        if high_impact_count > 3:
            return "high"
        elif high_impact_count > 0:
            return "medium"
        else:
            return "low"
            
    def _estimate_complexity_reduction(self, suggestions: List[CodeMutation]) -> str:
        """Estimate complexity reduction from refactoring"""
        if not suggestions:
            return "none"
            
        complexity_types = ["high_complexity", "long_function", "too_many_parameters"]
        complexity_count = sum(1 for s in suggestions if s.mutation_type in complexity_types)
        
        if complexity_count > 2:
            return "significant"
        elif complexity_count > 0:
            return "moderate"
        else:
            return "minimal"
            
    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities of the Code Mutation Agent"""
        return {
            "name": "Code Mutation Agent",
            "description": "Identifies and suggests code improvements through mutations",
            "capabilities": [
                "Code improvement suggestions",
                "Security vulnerability detection",
                "Performance optimization",
                "Refactoring recommendations",
                "Code structure analysis",
                "Pattern detection"
            ],
            "supported_languages": [
                "python",
                "javascript",
                "typescript", 
                "java",
                "cpp",
                "c",
                "go",
                "rust"
            ],
            "mutation_types": [
                "improvement",
                "security",
                "performance",
                "refactor"
            ]
        }