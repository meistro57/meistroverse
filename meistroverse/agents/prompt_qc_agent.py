import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from meistroverse.agents.base import BaseAgent
from meistroverse.database import get_db, Task, PromptTemplate, TaskExecution, Agent
from meistroverse.utils.logger import get_logger
from meistroverse.config import settings

logger = get_logger(__name__)


class PromptQCAgent(BaseAgent):
    """Agent that monitors and improves prompt quality and performance"""
    
    def __init__(self):
        super().__init__(name="PromptQCAgent")
        self.anthropic_client = None
        self.openai_client = None
        self._init_llm_clients()
        
    def _init_llm_clients(self):
        """Initialize LLM clients for prompt evaluation"""
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
        """Execute prompt QC analysis"""
        logger.info(f"Starting prompt QC analysis for task: {task.title}")
        
        db = next(get_db())
        
        # Get task metadata to determine QC type
        qc_type = task.metadata.get("qc_type", "performance_analysis")
        
        if qc_type == "performance_analysis":
            return await self._analyze_prompt_performance(db)
        elif qc_type == "quality_check":
            prompt_template_id = task.metadata.get("prompt_template_id")
            return await self._quality_check_prompt(prompt_template_id, db)
        elif qc_type == "optimization":
            prompt_template_id = task.metadata.get("prompt_template_id")
            return await self._optimize_prompt(prompt_template_id, db)
        elif qc_type == "batch_review":
            return await self._batch_review_prompts(db)
        else:
            raise ValueError(f"Unknown QC type: {qc_type}")
            
    async def _analyze_prompt_performance(self, db: Session) -> Dict[str, Any]:
        """Analyze performance of all prompt templates"""
        logger.info("Analyzing prompt performance across all templates")
        
        # Get all active prompt templates
        templates = db.query(PromptTemplate).filter(PromptTemplate.is_active == True).all()
        
        performance_data = []
        
        for template in templates:
            # Get recent executions for this template
            executions = (
                db.query(TaskExecution)
                .join(Task)
                .filter(Task.agent_type == template.agent_type)
                .filter(TaskExecution.started_at >= datetime.utcnow() - timedelta(days=7))
                .all()
            )
            
            if not executions:
                continue
                
            # Calculate metrics
            total_executions = len(executions)
            successful_executions = sum(1 for e in executions if e.success)
            avg_execution_time = sum(
                (e.completed_at - e.started_at).total_seconds() 
                for e in executions 
                if e.completed_at and e.started_at
            ) / max(total_executions, 1)
            
            success_rate = successful_executions / total_executions
            
            # Analyze failure patterns
            failed_executions = [e for e in executions if not e.success]
            failure_patterns = self._analyze_failure_patterns(failed_executions)
            
            performance_data.append({
                "template_id": template.id,
                "template_name": template.name,
                "agent_type": template.agent_type,
                "total_executions": total_executions,
                "success_rate": success_rate,
                "avg_execution_time": avg_execution_time,
                "current_score": template.performance_score,
                "failure_patterns": failure_patterns,
                "needs_attention": success_rate < 0.8 or avg_execution_time > 30
            })
            
        # Update performance scores
        for data in performance_data:
            template = db.query(PromptTemplate).filter(PromptTemplate.id == data["template_id"]).first()
            if template:
                # Calculate new performance score
                new_score = self._calculate_performance_score(data)
                template.performance_score = new_score
                
        db.commit()
        
        return {
            "analysis_type": "performance_analysis",
            "templates_analyzed": len(performance_data),
            "performance_data": performance_data,
            "recommendations": self._generate_performance_recommendations(performance_data)
        }
        
    def _analyze_failure_patterns(self, failed_executions: List[TaskExecution]) -> List[Dict[str, Any]]:
        """Analyze patterns in failed executions"""
        if not failed_executions:
            return []
            
        # Group by error type
        error_patterns = {}
        for execution in failed_executions:
            if execution.error_message:
                # Extract error type
                error_type = self._extract_error_type(execution.error_message)
                if error_type not in error_patterns:
                    error_patterns[error_type] = []
                error_patterns[error_type].append(execution.error_message)
                
        # Convert to list with counts
        patterns = []
        for error_type, messages in error_patterns.items():
            patterns.append({
                "error_type": error_type,
                "count": len(messages),
                "examples": messages[:3]  # Include up to 3 examples
            })
            
        return sorted(patterns, key=lambda x: x["count"], reverse=True)
        
    def _extract_error_type(self, error_message: str) -> str:
        """Extract error type from error message"""
        # Common error patterns
        if "timeout" in error_message.lower():
            return "timeout"
        elif "rate limit" in error_message.lower():
            return "rate_limit"
        elif "invalid" in error_message.lower():
            return "invalid_input"
        elif "connection" in error_message.lower():
            return "connection_error"
        elif "authentication" in error_message.lower():
            return "auth_error"
        else:
            return "unknown_error"
            
    def _calculate_performance_score(self, data: Dict[str, Any]) -> float:
        """Calculate performance score based on metrics"""
        success_rate = data["success_rate"]
        avg_time = data["avg_execution_time"]
        
        # Base score from success rate (0-70 points)
        score = success_rate * 70
        
        # Time efficiency bonus (0-20 points)
        if avg_time <= 5:
            score += 20
        elif avg_time <= 10:
            score += 15
        elif avg_time <= 20:
            score += 10
        elif avg_time <= 30:
            score += 5
            
        # Consistency bonus (0-10 points)
        if data["total_executions"] >= 10:
            score += 10
        elif data["total_executions"] >= 5:
            score += 5
            
        return min(score, 100)
        
    def _generate_performance_recommendations(self, performance_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate recommendations based on performance analysis"""
        recommendations = []
        
        # Identify problematic templates
        problematic = [d for d in performance_data if d["needs_attention"]]
        
        for data in problematic:
            rec = {
                "template_id": data["template_id"],
                "template_name": data["template_name"],
                "priority": "high" if data["success_rate"] < 0.5 else "medium",
                "issues": [],
                "suggestions": []
            }
            
            if data["success_rate"] < 0.8:
                rec["issues"].append(f"Low success rate: {data['success_rate']:.1%}")
                rec["suggestions"].append("Review prompt clarity and error handling")
                
            if data["avg_execution_time"] > 30:
                rec["issues"].append(f"Slow execution: {data['avg_execution_time']:.1f}s")
                rec["suggestions"].append("Optimize prompt length and complexity")
                
            if data["failure_patterns"]:
                top_pattern = data["failure_patterns"][0]
                rec["issues"].append(f"Common failure: {top_pattern['error_type']}")
                rec["suggestions"].append(f"Address {top_pattern['error_type']} issues")
                
            recommendations.append(rec)
            
        return recommendations
        
    async def _quality_check_prompt(self, prompt_template_id: int, db: Session) -> Dict[str, Any]:
        """Perform quality check on a specific prompt template"""
        template = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_template_id).first()
        
        if not template:
            raise ValueError(f"Prompt template {prompt_template_id} not found")
            
        logger.info(f"Performing quality check on template: {template.name}")
        
        # Analyze prompt structure
        structure_analysis = self._analyze_prompt_structure(template.template)
        
        # Check for best practices
        best_practices = self._check_best_practices(template.template)
        
        # Evaluate clarity with LLM if available
        clarity_score = await self._evaluate_clarity(template.template)
        
        # Generate overall quality score
        quality_score = self._calculate_quality_score(structure_analysis, best_practices, clarity_score)
        
        return {
            "template_id": template.id,
            "template_name": template.name,
            "quality_score": quality_score,
            "structure_analysis": structure_analysis,
            "best_practices": best_practices,
            "clarity_score": clarity_score,
            "recommendations": self._generate_quality_recommendations(structure_analysis, best_practices, clarity_score)
        }
        
    def _analyze_prompt_structure(self, prompt_template: str) -> Dict[str, Any]:
        """Analyze the structure of a prompt template"""
        # Count various elements
        word_count = len(prompt_template.split())
        line_count = len(prompt_template.split('\n'))
        
        # Find variables (assuming {variable} format)
        variables = re.findall(r'\{([^}]+)\}', prompt_template)
        
        # Check for sections
        has_system_prompt = "system" in prompt_template.lower()
        has_examples = "example" in prompt_template.lower()
        has_instructions = any(word in prompt_template.lower() for word in ["please", "you should", "must", "ensure"])
        
        return {
            "word_count": word_count,
            "line_count": line_count,
            "variable_count": len(variables),
            "variables": variables,
            "has_system_prompt": has_system_prompt,
            "has_examples": has_examples,
            "has_instructions": has_instructions,
            "length_category": self._categorize_length(word_count)
        }
        
    def _categorize_length(self, word_count: int) -> str:
        """Categorize prompt length"""
        if word_count < 50:
            return "short"
        elif word_count < 200:
            return "medium"
        elif word_count < 500:
            return "long"
        else:
            return "very_long"
            
    def _check_best_practices(self, prompt_template: str) -> Dict[str, Any]:
        """Check prompt against best practices"""
        practices = {
            "clear_instructions": bool(re.search(r'\b(please|you should|must|ensure)\b', prompt_template, re.IGNORECASE)),
            "specific_format": bool(re.search(r'\b(format|structure|json|markdown)\b', prompt_template, re.IGNORECASE)),
            "examples_provided": "example" in prompt_template.lower(),
            "context_provided": bool(re.search(r'\b(context|background|given)\b', prompt_template, re.IGNORECASE)),
            "constraints_specified": bool(re.search(r'\b(limit|constraint|must not|avoid)\b', prompt_template, re.IGNORECASE)),
            "role_defined": bool(re.search(r'\b(you are|act as|role)\b', prompt_template, re.IGNORECASE)),
            "output_format_specified": bool(re.search(r'\b(output|return|respond with)\b', prompt_template, re.IGNORECASE))
        }
        
        score = sum(practices.values()) / len(practices)
        
        return {
            "practices": practices,
            "score": score,
            "passed_checks": sum(practices.values()),
            "total_checks": len(practices)
        }
        
    async def _evaluate_clarity(self, prompt_template: str) -> Optional[float]:
        """Evaluate prompt clarity using LLM"""
        if not self.anthropic_client and not self.openai_client:
            return None
            
        evaluation_prompt = f"""
        Please evaluate the clarity and effectiveness of this prompt template on a scale of 1-10:
        
        {prompt_template}
        
        Consider:
        - Are the instructions clear and unambiguous?
        - Is the desired output format specified?
        - Are there any confusing or contradictory elements?
        - Would a typical AI assistant understand what is expected?
        
        Respond with just a number from 1-10, followed by a brief explanation.
        """
        
        try:
            if self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=100,
                    messages=[{"role": "user", "content": evaluation_prompt}]
                )
                result = response.content[0].text
            elif self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    max_tokens=100,
                    messages=[{"role": "user", "content": evaluation_prompt}]
                )
                result = response.choices[0].message.content
            else:
                return None
                
            # Extract score
            score_match = re.search(r'(\d+(?:\.\d+)?)', result)
            if score_match:
                return float(score_match.group(1)) / 10.0  # Convert to 0-1 scale
                
        except Exception as e:
            logger.error(f"Error evaluating clarity: {e}")
            
        return None
        
    def _calculate_quality_score(
        self, 
        structure_analysis: Dict[str, Any], 
        best_practices: Dict[str, Any], 
        clarity_score: Optional[float]
    ) -> float:
        """Calculate overall quality score"""
        # Structure score (0-30 points)
        structure_score = 0
        if 50 <= structure_analysis["word_count"] <= 300:
            structure_score += 10
        if structure_analysis["variable_count"] > 0:
            structure_score += 5
        if structure_analysis["has_instructions"]:
            structure_score += 10
        if structure_analysis["has_examples"]:
            structure_score += 5
            
        # Best practices score (0-40 points)
        practices_score = best_practices["score"] * 40
        
        # Clarity score (0-30 points)
        clarity_contribution = (clarity_score * 30) if clarity_score else 20  # Default if no LLM
        
        total_score = structure_score + practices_score + clarity_contribution
        return min(total_score, 100)
        
    def _generate_quality_recommendations(
        self, 
        structure_analysis: Dict[str, Any], 
        best_practices: Dict[str, Any], 
        clarity_score: Optional[float]
    ) -> List[str]:
        """Generate recommendations for improving prompt quality"""
        recommendations = []
        
        # Structure recommendations
        if structure_analysis["word_count"] < 50:
            recommendations.append("Consider adding more detail and context to the prompt")
        elif structure_analysis["word_count"] > 500:
            recommendations.append("Consider simplifying the prompt to reduce complexity")
            
        if structure_analysis["variable_count"] == 0:
            recommendations.append("Add variables to make the prompt more flexible")
            
        # Best practices recommendations
        practices = best_practices["practices"]
        if not practices["clear_instructions"]:
            recommendations.append("Add clear, specific instructions")
        if not practices["examples_provided"]:
            recommendations.append("Include examples to clarify expected output")
        if not practices["output_format_specified"]:
            recommendations.append("Specify the desired output format")
        if not practices["role_defined"]:
            recommendations.append("Define the AI's role or persona")
            
        # Clarity recommendations
        if clarity_score and clarity_score < 0.7:
            recommendations.append("Improve prompt clarity and reduce ambiguity")
            
        return recommendations
        
    async def _optimize_prompt(self, prompt_template_id: int, db: Session) -> Dict[str, Any]:
        """Optimize a prompt template based on performance data"""
        template = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_template_id).first()
        
        if not template:
            raise ValueError(f"Prompt template {prompt_template_id} not found")
            
        logger.info(f"Optimizing template: {template.name}")
        
        # Get performance data
        performance_data = await self._get_template_performance(template.id, db)
        
        # Generate optimization suggestions
        optimizations = await self._generate_optimizations(template, performance_data)
        
        return {
            "template_id": template.id,
            "template_name": template.name,
            "current_performance": performance_data,
            "optimization_suggestions": optimizations,
            "priority": "high" if performance_data["success_rate"] < 0.7 else "medium"
        }
        
    async def _get_template_performance(self, template_id: int, db: Session) -> Dict[str, Any]:
        """Get performance metrics for a specific template"""
        template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()
        
        # Get recent executions
        executions = (
            db.query(TaskExecution)
            .join(Task)
            .filter(Task.agent_type == template.agent_type)
            .filter(TaskExecution.started_at >= datetime.utcnow() - timedelta(days=14))
            .all()
        )
        
        if not executions:
            return {"success_rate": 0, "avg_execution_time": 0, "total_executions": 0}
            
        successful = sum(1 for e in executions if e.success)
        avg_time = sum(
            (e.completed_at - e.started_at).total_seconds() 
            for e in executions 
            if e.completed_at and e.started_at
        ) / len(executions)
        
        return {
            "success_rate": successful / len(executions),
            "avg_execution_time": avg_time,
            "total_executions": len(executions)
        }
        
    async def _generate_optimizations(self, template: PromptTemplate, performance_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate optimization suggestions"""
        optimizations = []
        
        if performance_data["success_rate"] < 0.8:
            optimizations.append({
                "type": "reliability",
                "suggestion": "Add error handling and validation instructions",
                "expected_impact": "Reduce failure rate"
            })
            
        if performance_data["avg_execution_time"] > 20:
            optimizations.append({
                "type": "efficiency",
                "suggestion": "Simplify prompt structure and reduce length",
                "expected_impact": "Faster execution"
            })
            
        # Add more optimization logic based on template analysis
        quality_check = await self._quality_check_prompt(template.id, next(get_db()))
        
        if quality_check["quality_score"] < 70:
            optimizations.append({
                "type": "quality",
                "suggestion": "Improve prompt clarity and structure",
                "expected_impact": "Better output quality"
            })
            
        return optimizations
        
    async def _batch_review_prompts(self, db: Session) -> Dict[str, Any]:
        """Review all prompts and flag those needing attention"""
        logger.info("Performing batch review of all prompt templates")
        
        templates = db.query(PromptTemplate).filter(PromptTemplate.is_active == True).all()
        
        review_results = []
        
        for template in templates:
            # Quick quality check
            structure_analysis = self._analyze_prompt_structure(template.template)
            best_practices = self._check_best_practices(template.template)
            
            quality_score = self._calculate_quality_score(structure_analysis, best_practices, None)
            
            needs_review = (
                quality_score < 60 or 
                template.performance_score < 50 or
                template.updated_at < datetime.utcnow() - timedelta(days=30)
            )
            
            review_results.append({
                "template_id": template.id,
                "template_name": template.name,
                "quality_score": quality_score,
                "performance_score": template.performance_score,
                "needs_review": needs_review,
                "last_updated": template.updated_at.isoformat(),
                "review_reasons": self._get_review_reasons(template, quality_score)
            })
            
        return {
            "review_type": "batch_review",
            "total_templates": len(templates),
            "templates_needing_review": sum(1 for r in review_results if r["needs_review"]),
            "review_results": review_results
        }
        
    def _get_review_reasons(self, template: PromptTemplate, quality_score: float) -> List[str]:
        """Get reasons why a template needs review"""
        reasons = []
        
        if quality_score < 60:
            reasons.append("Low quality score")
        if template.performance_score < 50:
            reasons.append("Poor performance")
        if template.updated_at < datetime.utcnow() - timedelta(days=30):
            reasons.append("Not updated recently")
            
        return reasons
        
    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities of the Prompt QC Agent"""
        return {
            "name": "Prompt QC Agent",
            "description": "Monitors and improves prompt quality and performance",
            "capabilities": [
                "Performance analysis",
                "Quality assessment",
                "Prompt optimization",
                "Batch review",
                "Best practices checking",
                "Structure analysis"
            ],
            "supported_qc_types": [
                "performance_analysis",
                "quality_check",
                "optimization",
                "batch_review"
            ]
        }