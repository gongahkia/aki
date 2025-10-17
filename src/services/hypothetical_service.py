"""
Hypothetical Generation Service - Main orchestration service for generating legal hypotheticals.
Combines prompt engineering, LLM service, and corpus service to create high-quality legal scenarios.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
import structlog

from .llm_service import LLMService, LLMRequest, LLMResponse, llm_service
from .corpus_service import CorpusService, HypotheticalEntry, CorpusQuery, corpus_service
from .prompt_engineering import (
    PromptTemplateManager, 
    PromptContext, 
    PromptTemplateType,
    HypotheticalEntry as PromptHypotheticalEntry
)

logger = structlog.get_logger(__name__)


class GenerationRequest(BaseModel):
    """Request model for hypothetical generation."""
    topics: List[str] = Field(..., min_items=1, max_items=10)
    law_domain: str = Field(default="tort")
    number_parties: int = Field(default=3, ge=2, le=5)
    complexity_level: str = Field(default="intermediate")
    sample_size: int = Field(default=3, ge=1, le=10)
    user_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    """Response model for hypothetical generation."""
    hypothetical: str
    analysis: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    generation_time: float = 0.0
    validation_results: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Model for validation results."""
    adherence_check: Dict[str, Any] = Field(default_factory=dict)
    similarity_check: Dict[str, Any] = Field(default_factory=dict)
    quality_score: float = Field(default=0.0, ge=0.0, le=10.0)
    passed: bool = False


class HypotheticalServiceError(Exception):
    """Custom exception for hypothetical service errors."""
    pass


class HypotheticalService:
    """Main service for generating and validating legal hypotheticals."""
    
    def __init__(self):
        self.llm_service = llm_service
        self.corpus_service = corpus_service
        self.prompt_manager = PromptTemplateManager()
        self._generation_history: List[Dict[str, Any]] = []
    
    async def generate_hypothetical(self, request: GenerationRequest) -> GenerationResponse:
        """Generate a complete legal hypothetical with analysis."""
        try:
            start_time = datetime.utcnow()
            
            logger.info("Starting hypothetical generation", 
                       topics=request.topics,
                       parties=request.number_parties,
                       complexity=request.complexity_level)
            
            # Step 1: Get relevant context from corpus
            context_entries = await self._get_relevant_context(request)
            
            # Step 2: Generate the hypothetical
            hypothetical = await self._generate_hypothetical_text(request, context_entries)
            
            # Step 3: Validate the generated hypothetical
            validation_results = await self._validate_hypothetical(request, hypothetical, context_entries)
            
            # Step 4: Generate legal analysis
            analysis = await self._generate_legal_analysis(request, hypothetical)
            
            # Step 5: Calculate generation time
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create response
            response = GenerationResponse(
                hypothetical=hypothetical,
                analysis=analysis,
                metadata={
                    "topics": request.topics,
                    "law_domain": request.law_domain,
                    "number_parties": request.number_parties,
                    "complexity_level": request.complexity_level,
                    "context_entries_used": len(context_entries),
                    "generation_timestamp": start_time.isoformat()
                },
                generation_time=generation_time,
                validation_results=validation_results.dict()
            )
            
            # Store in history
            self._generation_history.append({
                "timestamp": start_time.isoformat(),
                "request": request.dict(),
                "response": response.dict()
            })
            
            logger.info("Hypothetical generation completed", 
                       generation_time=generation_time,
                       validation_passed=validation_results.passed)
            
            return response
            
        except Exception as e:
            logger.error("Hypothetical generation failed", error=str(e))
            raise HypotheticalServiceError(f"Generation failed: {e}")
    
    async def _get_relevant_context(self, request: GenerationRequest) -> List[HypotheticalEntry]:
        """Get relevant context from corpus based on topics."""
        try:
            query = CorpusQuery(
                topics=request.topics,
                sample_size=request.sample_size,
                min_topic_overlap=1
            )
            
            context_entries = await self.corpus_service.query_relevant_hypotheticals(query)
            
            logger.info("Context retrieved", 
                       topics=request.topics,
                       entries_found=len(context_entries))
            
            return context_entries
            
        except Exception as e:
            logger.error("Failed to get relevant context", error=str(e))
            raise HypotheticalServiceError(f"Context retrieval failed: {e}")
    
    async def _generate_hypothetical_text(self, request: GenerationRequest, context_entries: List[HypotheticalEntry]) -> str:
        """Generate the hypothetical text using LLM."""
        try:
            # Create prompt context
            context = PromptContext(
                topics=request.topics,
                law_domain=request.law_domain,
                number_parties=request.number_parties,
                reference_hypotheticals=[entry.text for entry in context_entries],
                user_preferences=request.user_preferences,
                complexity_level=request.complexity_level
            )
            
            # Get formatted prompt
            prompt_data = self.prompt_manager.format_prompt(
                PromptTemplateType.HYPOTHETICAL_GENERATION,
                context
            )
            
            # Create LLM request
            llm_request = LLMRequest(
                prompt=prompt_data["user"],
                system_prompt=prompt_data["system"],
                temperature=0.7,
                max_tokens=2048
            )
            
            # Generate response
            llm_response = await self.llm_service.generate(llm_request)
            
            # Extract hypothetical from response
            hypothetical = self._extract_hypothetical_from_response(llm_response.content)
            
            logger.info("Hypothetical text generated", 
                       length=len(hypothetical),
                       model=llm_response.model)
            
            return hypothetical
            
        except Exception as e:
            logger.error("Failed to generate hypothetical text", error=str(e))
            raise HypotheticalServiceError(f"Text generation failed: {e}")
    
    async def _validate_hypothetical(self, request: GenerationRequest, hypothetical: str, context_entries: List[HypotheticalEntry]) -> ValidationResult:
        """Validate the generated hypothetical."""
        try:
            # Run adherence check
            adherence_result = await self._check_adherence(request, hypothetical)
            
            # Run similarity check
            similarity_result = await self._check_similarity(hypothetical, context_entries)
            
            # Calculate overall quality score
            quality_score = self._calculate_quality_score(adherence_result, similarity_result)
            
            # Determine if validation passed
            passed = (
                adherence_result.get("overall_compliance", "").upper() == "PASS" and
                similarity_result.get("overall_originality", "").upper() == "PASS" and
                quality_score >= 7.0
            )
            
            validation_result = ValidationResult(
                adherence_check=adherence_result,
                similarity_check=similarity_result,
                quality_score=quality_score,
                passed=passed
            )
            
            logger.info("Validation completed", 
                       passed=passed,
                       quality_score=quality_score)
            
            return validation_result
            
        except Exception as e:
            logger.error("Validation failed", error=str(e))
            raise HypotheticalServiceError(f"Validation failed: {e}")
    
    async def _check_adherence(self, request: GenerationRequest, hypothetical: str) -> Dict[str, Any]:
        """Check adherence to generation parameters."""
        try:
            context = PromptContext(
                topics=request.topics,
                law_domain=request.law_domain,
                number_parties=request.number_parties,
                complexity_level=request.complexity_level
            )
            
            prompt_data = self.prompt_manager.format_prompt(
                PromptTemplateType.ADHERENCE_CHECK,
                context,
                hypothetical=hypothetical
            )
            
            llm_request = LLMRequest(
                prompt=prompt_data["user"],
                system_prompt=prompt_data["system"],
                temperature=0.3,
                max_tokens=1024
            )
            
            llm_response = await self.llm_service.generate(llm_request)
            
            # Parse the adherence check response
            adherence_result = self._parse_validation_response(llm_response.content)
            
            return adherence_result
            
        except Exception as e:
            logger.error("Adherence check failed", error=str(e))
            return {"error": str(e), "overall_compliance": "FAIL"}
    
    async def _check_similarity(self, hypothetical: str, context_entries: List[HypotheticalEntry]) -> Dict[str, Any]:
        """Check similarity to existing corpus."""
        try:
            context = PromptContext(topics=[], law_domain="tort")
            
            prompt_data = self.prompt_manager.format_prompt(
                PromptTemplateType.SIMILARITY_CHECK,
                context,
                generated_hypothetical=hypothetical,
                reference_examples=[entry.text for entry in context_entries]
            )
            
            llm_request = LLMRequest(
                prompt=prompt_data["user"],
                system_prompt=prompt_data["system"],
                temperature=0.3,
                max_tokens=1024
            )
            
            llm_response = await self.llm_service.generate(llm_request)
            
            # Parse the similarity check response
            similarity_result = self._parse_validation_response(llm_response.content)
            
            return similarity_result
            
        except Exception as e:
            logger.error("Similarity check failed", error=str(e))
            return {"error": str(e), "overall_originality": "FAIL"}
    
    async def _generate_legal_analysis(self, request: GenerationRequest, hypothetical: str) -> str:
        """Generate legal analysis for the hypothetical."""
        try:
            # Get all available topics
            all_topics = await self.corpus_service.extract_all_topics()
            
            context = PromptContext(
                topics=request.topics,
                law_domain=request.law_domain
            )
            
            prompt_data = self.prompt_manager.format_prompt(
                PromptTemplateType.LEGAL_ANALYSIS,
                context,
                hypothetical=hypothetical,
                available_topics=all_topics
            )
            
            llm_request = LLMRequest(
                prompt=prompt_data["user"],
                system_prompt=prompt_data["system"],
                temperature=0.5,
                max_tokens=2048
            )
            
            llm_response = await self.llm_service.generate(llm_request)
            
            logger.info("Legal analysis generated", 
                       length=len(llm_response.content),
                       model=llm_response.model)
            
            return llm_response.content
            
        except Exception as e:
            logger.error("Legal analysis generation failed", error=str(e))
            return f"Legal analysis generation failed: {e}"
    
    def _extract_hypothetical_from_response(self, response_content: str) -> str:
        """Extract the hypothetical text from LLM response."""
        # Look for the hypothetical section
        if "HYPOTHETICAL SCENARIO:" in response_content:
            start_marker = "HYPOTHETICAL SCENARIO:"
            end_marker = "SCENARIO METADATA:"
            
            start_idx = response_content.find(start_marker) + len(start_marker)
            end_idx = response_content.find(end_marker)
            
            if end_idx == -1:
                end_idx = len(response_content)
            
            hypothetical = response_content[start_idx:end_idx].strip()
        else:
            # Fallback: use the entire response
            hypothetical = response_content.strip()
        
        return hypothetical
    
    def _parse_validation_response(self, response_content: str) -> Dict[str, Any]:
        """Parse validation response from LLM."""
        result = {}
        
        # Extract overall compliance/originality
        if "OVERALL COMPLIANCE:" in response_content:
            compliance_line = [line for line in response_content.split('\n') if 'OVERALL COMPLIANCE:' in line][0]
            result["overall_compliance"] = compliance_line.split(':')[1].strip()
        elif "OVERALL ORIGINALITY:" in response_content:
            originality_line = [line for line in response_content.split('\n') if 'OVERALL ORIGINALITY:' in line][0]
            result["overall_originality"] = originality_line.split(':')[1].strip()
        
        # Extract score if available
        if "SCORE:" in response_content:
            score_line = [line for line in response_content.split('\n') if 'SCORE:' in line][0]
            try:
                score = float(score_line.split(':')[1].strip().split('/')[0])
                result["score"] = score
            except (ValueError, IndexError):
                pass
        
        # Store the full response for detailed analysis
        result["full_response"] = response_content
        
        return result
    
    def _calculate_quality_score(self, adherence_result: Dict[str, Any], similarity_result: Dict[str, Any]) -> float:
        """Calculate overall quality score from validation results."""
        score = 5.0  # Base score
        
        # Adherence score (0-5 points)
        if adherence_result.get("overall_compliance", "").upper() == "PASS":
            score += 3.0
        elif adherence_result.get("overall_compliance", "").upper() == "FAIL":
            score -= 2.0
        
        # Similarity score (0-5 points)
        if similarity_result.get("overall_originality", "").upper() == "PASS":
            score += 3.0
        elif similarity_result.get("overall_originality", "").upper() == "FAIL":
            score -= 2.0
        
        # Individual scores if available
        if "score" in adherence_result:
            score += (adherence_result["score"] - 5.0) * 0.2
        
        if "score" in similarity_result:
            score += (similarity_result["score"] - 5.0) * 0.2
        
        return max(0.0, min(10.0, score))
    
    async def get_generation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent generation history."""
        return self._generation_history[-limit:]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the hypothetical service."""
        health_status = {
            "service": "hypothetical_service",
            "status": "healthy",
            "dependencies": {}
        }
        
        try:
            # Check LLM service
            llm_health = await self.llm_service.health_check()
            health_status["dependencies"]["llm_service"] = llm_health
            
            # Check corpus service
            corpus_health = await self.corpus_service.health_check()
            health_status["dependencies"]["corpus_service"] = corpus_health
            
            # Overall status
            all_healthy = all(
                any(status for status in dep.values()) if isinstance(dep, dict) else dep
                for dep in health_status["dependencies"].values()
            )
            
            if not all_healthy:
                health_status["status"] = "degraded"
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status


# Global hypothetical service instance
hypothetical_service = HypotheticalService()
