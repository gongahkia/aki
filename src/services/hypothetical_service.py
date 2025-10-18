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
from .validation_service import validation_service
from .database_service import database_service
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
        self.validation_service = validation_service
        self.database_service = database_service
        self.prompt_manager = PromptTemplateManager()
        self._generation_history: List[Dict[str, Any]] = []  # In-memory cache
    
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
            
            # Store in in-memory history (for quick access)
            generation_record = {
                "timestamp": start_time.isoformat(),
                "request": request.dict(),
                "response": response.dict()
            }
            self._generation_history.append(generation_record)

            # Persist to database (async, don't block on this)
            try:
                await self.database_service.save_generation(
                    request_data=request.dict(),
                    response_data=response.dict()
                )
            except Exception as db_error:
                logger.error("Failed to persist to database (non-fatal)", error=str(db_error))
                # Don't raise - generation succeeded, only persistence failed

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
        """
        Validate the generated hypothetical using deterministic checks.
        Much faster and more reliable than LLM-based validation.
        """
        try:
            # Run deterministic validation checks
            validation_result = self.validation_service.validate_hypothetical(
                text=hypothetical,
                required_topics=request.topics,
                expected_parties=request.number_parties,
                law_domain=request.law_domain
            )

            # Run similarity check (lightweight text comparison)
            similarity_result = await self._check_text_similarity(hypothetical, context_entries)

            # Combine results
            passed = validation_result['passed'] and similarity_result['passed']
            quality_score = validation_result['overall_score']

            result = ValidationResult(
                adherence_check=validation_result,
                similarity_check=similarity_result,
                quality_score=quality_score,
                passed=passed
            )

            logger.info("Validation completed (deterministic)",
                       passed=passed,
                       quality_score=quality_score,
                       method="deterministic")

            return result

        except Exception as e:
            logger.error("Validation failed", error=str(e))
            # Return failed validation instead of raising
            return ValidationResult(
                adherence_check={'passed': False, 'error': str(e)},
                similarity_check={'passed': False, 'error': str(e)},
                quality_score=0.0,
                passed=False
            )
    
    async def _check_text_similarity(self, hypothetical: str, context_entries: List[HypotheticalEntry]) -> Dict[str, Any]:
        """
        Check text similarity using simple text overlap.
        Replaces expensive LLM-based similarity check.
        """
        try:
            if not context_entries:
                return {
                    'passed': True,
                    'max_similarity': 0.0,
                    'message': 'No reference examples to compare against'
                }

            # Tokenize hypothetical
            hypo_words = set(hypothetical.lower().split())

            # Calculate Jaccard similarity with each context entry
            similarities = []
            for entry in context_entries:
                entry_words = set(entry.text.lower().split())
                intersection = len(hypo_words & entry_words)
                union = len(hypo_words | entry_words)
                similarity = intersection / union if union > 0 else 0.0
                similarities.append(similarity)

            max_similarity = max(similarities) if similarities else 0.0

            # Pass if max similarity < 0.6 (60% overlap threshold)
            passed = max_similarity < 0.6

            logger.info("Similarity check completed",
                       max_similarity=f"{max_similarity:.2%}",
                       passed=passed,
                       method="jaccard")

            return {
                'passed': passed,
                'max_similarity': max_similarity,
                'threshold': 0.6,
                'message': f"Max similarity: {max_similarity:.1%} (threshold: 60%)"
            }

        except Exception as e:
            logger.error("Similarity check failed", error=str(e))
            return {
                'passed': True,  # Default to pass on error
                'max_similarity': 0.0,
                'error': str(e)
            }
    
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
        """
        Extract the hypothetical text from LLM response with robust fallbacks.
        Handles various response formats gracefully.
        """
        try:
            # Try primary format: Look for "HYPOTHETICAL SCENARIO:" section
            if "HYPOTHETICAL SCENARIO:" in response_content:
                start_marker = "HYPOTHETICAL SCENARIO:"
                start_idx = response_content.find(start_marker) + len(start_marker)

                # Look for end marker
                end_markers = ["SCENARIO METADATA:", "METADATA:", "---", "###"]
                end_idx = len(response_content)

                for marker in end_markers:
                    marker_idx = response_content.find(marker, start_idx)
                    if marker_idx != -1 and marker_idx < end_idx:
                        end_idx = marker_idx

                hypothetical = response_content[start_idx:end_idx].strip()

                # Validate extraction
                if len(hypothetical) > 100:  # Reasonable minimum length
                    logger.info("Extracted hypothetical using markers", length=len(hypothetical))
                    return hypothetical

            # Fallback 1: Look for scenario text between headers
            lines = response_content.split('\n')
            scenario_lines = []
            in_scenario = False

            for line in lines:
                line_lower = line.lower()
                if any(marker in line_lower for marker in ['scenario:', 'hypothetical:', 'case study:']):
                    in_scenario = True
                    continue
                elif any(marker in line_lower for marker in ['metadata:', 'analysis:', 'topics:', '---']):
                    in_scenario = False
                    break
                elif in_scenario and line.strip():
                    scenario_lines.append(line)

            if scenario_lines:
                hypothetical = '\n'.join(scenario_lines).strip()
                if len(hypothetical) > 100:
                    logger.info("Extracted hypothetical using line parsing", length=len(hypothetical))
                    return hypothetical

            # Fallback 2: Use first substantial paragraph
            paragraphs = [p.strip() for p in response_content.split('\n\n') if len(p.strip()) > 100]
            if paragraphs:
                hypothetical = paragraphs[0]
                logger.warning("Using first paragraph as hypothetical (fallback)", length=len(hypothetical))
                return hypothetical

            # Last resort: Return full response (likely contains the scenario)
            hypothetical = response_content.strip()
            logger.warning("Using full response as hypothetical (last resort)", length=len(hypothetical))
            return hypothetical

        except Exception as e:
            logger.error("Failed to extract hypothetical, using full response", error=str(e))
            return response_content.strip()
    
    
    async def get_generation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent generation history.
        First tries database, falls back to in-memory history.
        """
        try:
            # Get from database (persistent)
            history = await self.database_service.get_recent_generations(limit)
            if history:
                return history
        except Exception as e:
            logger.warning("Failed to get history from database, using in-memory", error=str(e))

        # Fallback to in-memory history
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
