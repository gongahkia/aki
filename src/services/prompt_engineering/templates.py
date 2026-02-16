"""
Modern prompt engineering templates for legal hypothetical generation.
Implements various prompt engineering techniques including:
- Chain of Thought (CoT)
- Few-shot learning
- Role-based prompting
- Structured output formatting
- Context-aware prompting
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# topic-specific prompt hints for expanded subtopics
TOPIC_HINTS: Dict[str, str] = {
    "occupiers_liability": "Include premises description, visitor classification (invitee/licensee/trespasser), and state of the premises.",
    "product_liability": "Include product description, manufacturing process, defect type (design/manufacturing/warning), and supply chain.",
    "contributory_negligence": "Include claimant's own conduct contributing to their injury, apportionment of fault.",
    "economic_loss": "Distinguish between pure economic loss and consequential economic loss; include financial impact details.",
    "psychiatric_harm": "Include proximity to event, relationship to victim, means of perception (sight/hearing/aftermath).",
    "employers_liability": "Include workplace conditions, safe system of work, training provided, and employer's knowledge.",
    "breach_of_statutory_duty": "Specify the relevant statute/regulation, the duty imposed, and how it was breached.",
    "rylands_v_fletcher": "Include non-natural use of land, accumulation of dangerous thing, and escape from defendant's land.",
    "consent_defence": "Include express or implied consent, scope of consent, and whether risk was voluntarily assumed.",
    "illegality_defence": "Include the illegal act by the claimant and its connection to the tort claim.",
    "limitation_periods": "Include timeline of events, date of knowledge, and relevant limitation period under Singapore law.",
    "res_ipsa_loquitur": "Include facts where the thing causing injury was under defendant's control and the event would not normally occur without negligence.",
    "novus_actus_interveniens": "Include an intervening act that may break the chain of causation.",
    "volenti_non_fit_injuria": "Include voluntary participation in activity, awareness and acceptance of specific risks.",
}


class PromptTemplateType(str, Enum):
    """Types of prompt templates available."""

    HYPOTHETICAL_GENERATION = "hypothetical_generation"
    ADHERENCE_CHECK = "adherence_check"
    SIMILARITY_CHECK = "similarity_check"
    LEGAL_ANALYSIS = "legal_analysis"
    TOPIC_EXTRACTION = "topic_extraction"
    QUALITY_ASSESSMENT = "quality_assessment"


class PromptTechnique(str, Enum):
    """Prompt engineering techniques used."""

    CHAIN_OF_THOUGHT = "chain_of_thought"
    FEW_SHOT_LEARNING = "few_shot_learning"
    ROLE_BASED = "role_based"
    STRUCTURED_OUTPUT = "structured_output"
    CONTEXT_AWARE = "context_aware"
    ZERO_SHOT = "zero_shot"


@dataclass
class PromptContext:
    """Context information for prompt generation."""

    topics: List[str]
    law_domain: str = "tort"
    number_parties: int = 3
    reference_hypotheticals: Optional[List[str]] = None
    user_preferences: Optional[Dict[str, Any]] = None
    complexity_level: str = "intermediate"  # beginner, intermediate, advanced


class PromptTemplate(BaseModel):
    """Base class for prompt templates."""

    name: str
    template_type: PromptTemplateType
    technique: PromptTechnique
    system_prompt: str
    user_prompt_template: str
    examples: Optional[List[Dict[str, str]]] = None
    output_format: Optional[str] = None

    def format_prompt(self, context: PromptContext, **kwargs) -> Dict[str, str]:
        """Format the prompt with given context."""
        raise NotImplementedError


class HypotheticalGenerationTemplate(PromptTemplate):
    """Template for generating legal hypotheticals using modern prompt engineering."""

    def __init__(self):
        super().__init__(
            name="Advanced Hypothetical Generator",
            template_type=PromptTemplateType.HYPOTHETICAL_GENERATION,
            technique=PromptTechnique.CHAIN_OF_THOUGHT,
            system_prompt=self._get_system_prompt(),
            user_prompt_template=self._get_user_prompt_template(),
            examples=self._get_examples(),
            output_format=self._get_output_format(),
        )

    def _get_system_prompt(self) -> str:
        return """You are an expert legal educator specializing in Singapore Tort Law. Your role is to create realistic, educational hypothetical scenarios that help law students understand complex legal concepts.

EXPERTISE AREAS:
- Singapore Tort Law principles and precedents
- Realistic fact pattern construction
- Educational scenario design
- Legal issue identification and complexity management

TASK APPROACH:
1. Analyze the requested legal topics and their interconnections
2. Design a realistic scenario that naturally incorporates these topics
3. Ensure the scenario is educational and thought-provoking
4. Maintain authenticity to Singapore legal context

QUALITY STANDARDS:
- Factual accuracy and legal realism
- Appropriate complexity for educational purposes
- Clear character motivations and actions
- Natural integration of legal issues
- Engaging narrative structure"""

    def _get_user_prompt_template(self) -> str:
        return """CONTEXT ANALYSIS:
Legal Domain: {law_domain}
Target Topics: {topics}
Number of Parties: {number_parties}
Complexity Level: {complexity_level}

REFERENCE EXAMPLES:
{reference_examples}

TASK INSTRUCTIONS:
Create a comprehensive {law_domain} law hypothetical that incorporates the specified topics. Follow this structured approach:

STEP 1: SCENARIO DESIGN
- Design a realistic setting in Singapore context
- Create {number_parties} distinct parties with clear roles
- Establish a believable sequence of events
- Ensure natural integration of legal issues

STEP 2: FACT PATTERN CONSTRUCTION
- Develop detailed factual circumstances
- Include relevant background information
- Create clear cause-and-effect relationships
- Add realistic complications and nuances

STEP 3: LEGAL ISSUE INTEGRATION
- Naturally incorporate: {topics}
- Ensure each topic is meaningfully addressed
- Create multiple potential legal claims
- Include both primary and secondary issues

{topic_hints}

STEP 4: QUALITY VERIFICATION
- Verify factual consistency
- Check legal accuracy
- Ensure educational value
- Confirm appropriate complexity

REQUIREMENTS:
- Length: 800-1200 words
- Setting: Singapore context
- Parties: Exactly {number_parties} distinct individuals/entities
- Topics: Must include all specified topics naturally
- Style: Professional, clear, engaging narrative
- No legal analysis or issue identification in the text

OUTPUT FORMAT:
{output_format}"""

    def _get_examples(self) -> List[Dict[str, str]]:
        return [
            {
                "input": "Topics: negligence, duty of care, causation. Parties: 3",
                "output": "A detailed hypothetical involving a restaurant owner, customer, and supplier...",
            },
            {
                "input": "Topics: battery, assault, false imprisonment. Parties: 4",
                "output": "A scenario involving security personnel, customers, and management...",
            },
        ]

    def _get_output_format(self) -> str:
        return """HYPOTHETICAL SCENARIO:

[Provide a detailed, realistic scenario that naturally incorporates all specified legal topics. The scenario should be set in Singapore and involve exactly the specified number of parties. Focus on creating a compelling narrative that presents legal issues without explicitly identifying them.]

SCENARIO METADATA:
- Setting: [Brief description of the location/situation]
- Parties: [List of all parties involved]
- Key Events: [Chronological summary of main events]
- Legal Topics Addressed: [Confirmation of topics included]"""

    def format_prompt(self, context: PromptContext, **kwargs) -> Dict[str, str]:
        """Format the hypothetical generation prompt."""
        reference_examples = ""
        if context.reference_hypotheticals:
            for i, hypo in enumerate(context.reference_hypotheticals[:2], 1):
                reference_examples += f"Example {i}:\n{hypo}\n\n"
        hints = []
        for topic in context.topics:
            if topic in TOPIC_HINTS:
                hints.append(f"- {topic}: {TOPIC_HINTS[topic]}")
        topic_hints = "TOPIC-SPECIFIC GUIDANCE:\n" + "\n".join(hints) if hints else ""
        user_prompt = self.user_prompt_template.format(
            law_domain=context.law_domain,
            topics=", ".join(context.topics),
            number_parties=context.number_parties,
            complexity_level=context.complexity_level,
            reference_examples=reference_examples,
            output_format=self.output_format,
            topic_hints=topic_hints,
        )

        return {"system": self.system_prompt, "user": user_prompt}


class AdherenceCheckTemplate(PromptTemplate):
    """Template for checking adherence to generation parameters."""

    def __init__(self):
        super().__init__(
            name="Parameter Adherence Checker",
            template_type=PromptTemplateType.ADHERENCE_CHECK,
            technique=PromptTechnique.STRUCTURED_OUTPUT,
            system_prompt=self._get_system_prompt(),
            user_prompt_template=self._get_user_prompt_template(),
            output_format=self._get_output_format(),
        )

    def _get_system_prompt(self) -> str:
        return """You are a meticulous legal quality assurance specialist. Your role is to evaluate generated legal hypotheticals against specific parameters to ensure they meet educational standards.

EVALUATION CRITERIA:
- Parameter compliance (topics, parties, domain)
- Factual consistency and realism
- Legal accuracy and relevance
- Educational value and complexity
- Narrative coherence and clarity

ANALYSIS APPROACH:
1. Systematic parameter verification
2. Factual consistency checking
3. Legal accuracy assessment
4. Educational value evaluation
5. Overall quality scoring"""

    def _get_user_prompt_template(self) -> str:
        return """EVALUATION TASK:
Analyze the following hypothetical against the specified parameters.

PARAMETERS TO VERIFY:
- Law Domain: {law_domain}
- Required Topics: {topics}
- Number of Parties: {number_parties}
- Complexity Level: {complexity_level}

HYPOTHETICAL TO EVALUATE:
{hypothetical}

EVALUATION CHECKLIST:
Please provide a detailed analysis for each criterion:

1. PARAMETER COMPLIANCE:
   - Does the hypothetical focus on {law_domain} law? [YES/NO + Explanation]
   - Are all required topics present: {topics}? [YES/NO + Explanation]
   - Does it involve exactly {number_parties} parties? [YES/NO + Explanation]
   - Is the complexity appropriate for {complexity_level} level? [YES/NO + Explanation]

2. FACTUAL CONSISTENCY:
   - Are the facts internally consistent? [YES/NO + Explanation]
   - Is the timeline logical? [YES/NO + Explanation]
   - Are character actions believable? [YES/NO + Explanation]

3. LEGAL ACCURACY:
   - Are the legal issues correctly presented? [YES/NO + Explanation]
   - Is the Singapore legal context accurate? [YES/NO + Explanation]
   - Are the legal concepts properly integrated? [YES/NO + Explanation]

4. EDUCATIONAL VALUE:
   - Does it effectively teach the target concepts? [YES/NO + Explanation]
   - Is the complexity appropriate for learning? [YES/NO + Explanation]
   - Are there clear legal issues to analyze? [YES/NO + Explanation]

5. NARRATIVE QUALITY:
   - Is the writing clear and engaging? [YES/NO + Explanation]
   - Is the scenario realistic and relatable? [YES/NO + Explanation]
   - Is the structure well-organized? [YES/NO + Explanation]

OUTPUT FORMAT:
{output_format}"""

    def _get_output_format(self) -> str:
        return """EVALUATION RESULTS:

OVERALL COMPLIANCE: [PASS/FAIL]
OVERALL SCORE: [X/10]

DETAILED ANALYSIS:
[Provide detailed explanations for each criterion above]

RECOMMENDATIONS:
[If FAIL, provide specific suggestions for improvement]

CRITICAL ISSUES:
[List any critical problems that must be addressed]"""

    def format_prompt(  # type: ignore[override]
        self, context: PromptContext, hypothetical: str, **kwargs: Any
    ) -> Dict[str, str]:
        """Format the adherence check prompt."""
        user_prompt = self.user_prompt_template.format(
            law_domain=context.law_domain,
            topics=", ".join(context.topics),
            number_parties=context.number_parties,
            complexity_level=context.complexity_level,
            hypothetical=hypothetical,
            output_format=self.output_format,
        )

        return {"system": self.system_prompt, "user": user_prompt}


class SimilarityCheckTemplate(PromptTemplate):
    """Template for checking similarity to existing corpus."""

    def __init__(self):
        super().__init__(
            name="Corpus Similarity Checker",
            template_type=PromptTemplateType.SIMILARITY_CHECK,
            technique=PromptTechnique.CONTEXT_AWARE,
            system_prompt=self._get_system_prompt(),
            user_prompt_template=self._get_user_prompt_template(),
            output_format=self._get_output_format(),
        )

    def _get_system_prompt(self) -> str:
        return """You are an expert in legal text analysis and plagiarism detection. Your role is to assess the originality and distinctiveness of generated legal hypotheticals compared to existing corpus examples.

ANALYSIS EXPERTISE:
- Legal text similarity assessment
- Factual pattern comparison
- Narrative structure analysis
- Character and setting differentiation
- Legal issue presentation comparison

EVALUATION STANDARDS:
- Originality: Content should be substantially different
- Distinctiveness: Unique scenarios and characters
- Innovation: Fresh approaches to legal issues
- Authenticity: Genuine educational value"""

    def _get_user_prompt_template(self) -> str:
        return """SIMILARITY ANALYSIS TASK:
Compare the generated hypothetical with reference examples from the corpus.

REFERENCE CORPUS EXAMPLES:
{reference_examples}

GENERATED HYPOTHETICAL:
{generated_hypothetical}

COMPARISON ANALYSIS:
Please analyze the following aspects:

1. CONTENT SIMILARITY:
   - Are the factual scenarios too similar? [YES/NO + Explanation]
   - Do they share identical legal issues? [YES/NO + Explanation]
   - Are the character names or situations copied? [YES/NO + Explanation]

2. STRUCTURAL SIMILARITY:
   - Is the narrative structure identical? [YES/NO + Explanation]
   - Are the legal issues presented in the same way? [YES/NO + Explanation]
   - Is the resolution pattern similar? [YES/NO + Explanation]

3. CHARACTER SIMILARITY:
   - Are character names or roles too similar? [YES/NO + Explanation]
   - Do they have identical motivations or actions? [YES/NO + Explanation]
   - Are the relationships between parties copied? [YES/NO + Explanation]

4. SETTING SIMILARITY:
   - Is the location or context identical? [YES/NO + Explanation]
   - Are the circumstances too similar? [YES/NO + Explanation]
   - Is the time period or context copied? [YES/NO + Explanation]

5. LEGAL ISSUE SIMILARITY:
   - Are the legal issues presented identically? [YES/NO + Explanation]
   - Is the legal analysis approach the same? [YES/NO + Explanation]
   - Are the legal outcomes predictable? [YES/NO + Explanation]

ORIGINALITY ASSESSMENT:
- Overall originality score: [X/10]
- Distinctiveness level: [HIGH/MEDIUM/LOW]
- Innovation factor: [HIGH/MEDIUM/LOW]

OUTPUT FORMAT:
{output_format}"""

    def _get_output_format(self) -> str:
        return """SIMILARITY ANALYSIS RESULTS:

OVERALL ORIGINALITY: [PASS/FAIL]
ORIGINALITY SCORE: [X/10]

DETAILED COMPARISON:
[Provide detailed analysis for each aspect above]

SIMILARITY CONCERNS:
[List any specific similarities that are problematic]

RECOMMENDATIONS:
[If FAIL, provide specific suggestions for making the hypothetical more original]

UNIQUE ELEMENTS:
[Highlight what makes this hypothetical distinct and valuable]"""

    def format_prompt(  # type: ignore[override]
        self,
        context: PromptContext,
        generated_hypothetical: str,
        reference_examples: List[str],
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Format the similarity check prompt."""
        reference_text = ""
        for i, example in enumerate(reference_examples[:3], 1):
            reference_text += f"Reference Example {i}:\n{example}\n\n"

        user_prompt = self.user_prompt_template.format(
            reference_examples=reference_text,
            generated_hypothetical=generated_hypothetical,
            output_format=self.output_format,
        )

        return {"system": self.system_prompt, "user": user_prompt}


class LegalAnalysisTemplate(PromptTemplate):
    """Template for legal analysis of generated hypotheticals."""

    def __init__(self):
        super().__init__(
            name="Legal Analysis Expert",
            template_type=PromptTemplateType.LEGAL_ANALYSIS,
            technique=PromptTechnique.CHAIN_OF_THOUGHT,
            system_prompt=self._get_system_prompt(),
            user_prompt_template=self._get_user_prompt_template(),
            output_format=self._get_output_format(),
        )

    def _get_system_prompt(self) -> str:
        return """You are a distinguished Singapore Tort Law expert and legal educator. Your role is to provide comprehensive legal analysis of hypothetical scenarios to guide student learning.

LEGAL EXPERTISE:
- Singapore Tort Law principles and precedents
- Case law analysis and application
- Legal issue identification and prioritization
- Liability assessment and damage evaluation
- Defenses and remedies analysis

ANALYSIS APPROACH:
1. Systematic legal issue identification
2. Detailed liability analysis for each party
3. Comprehensive damage assessment
4. Defense evaluation and counterarguments
5. Practical legal advice and recommendations

EDUCATIONAL FOCUS:
- Clear explanation of legal principles
- Practical application of legal concepts
- Student-friendly language and examples
- Comprehensive coverage of all relevant issues"""

    def _get_user_prompt_template(self) -> str:
        return """LEGAL ANALYSIS TASK:
Provide a comprehensive legal analysis of the following hypothetical scenario.

HYPOTHETICAL SCENARIO:
{hypothetical}

AVAILABLE LEGAL TOPICS:
{available_topics}

ANALYSIS REQUIREMENTS:
Please provide a detailed legal analysis following this structure:

1. PARTY IDENTIFICATION:
   - List all parties involved
   - Identify their roles and relationships
   - Note any relevant background information

2. LEGAL ISSUE IDENTIFICATION:
   - Identify all potential tort law issues
   - Prioritize issues by significance
   - Explain the legal basis for each issue
   - Reference relevant legal topics: {available_topics}

3. LIABILITY ANALYSIS:
   For each identified issue, analyze:
   - Duty of care (if applicable)
   - Breach of duty/standard of care
   - Causation (factual and legal)
   - Remoteness of damage
   - Available defenses

4. DAMAGE ASSESSMENT:
   - Identify types of damages suffered
   - Assess quantum and recoverability
   - Consider special and general damages
   - Evaluate mitigation requirements

5. DEFENSES AND COUNTERARGUMENTS:
   - Identify available defenses
   - Analyze strength of each defense
   - Consider contributory negligence
   - Evaluate other limiting factors

6. PRACTICAL RECOMMENDATIONS:
   - Advise on legal strategy
   - Suggest settlement considerations
   - Identify key evidence requirements
   - Recommend expert witnesses if needed

OUTPUT FORMAT:
{output_format}"""

    def _get_output_format(self) -> str:
        return """LEGAL ANALYSIS REPORT:

EXECUTIVE SUMMARY:
[Brief overview of the main legal issues and likely outcomes]

DETAILED ANALYSIS:

1. PARTY IDENTIFICATION:
[List and describe all parties involved]

2. LEGAL ISSUES:
[Comprehensive analysis of all identified legal issues]

3. LIABILITY ASSESSMENT:
[Detailed liability analysis for each party and issue]

4. DAMAGE EVALUATION:
[Assessment of damages and recoverability]

5. DEFENSES:
[Analysis of available defenses and their strength]

6. RECOMMENDATIONS:
[Practical legal advice and strategic recommendations]

LEARNING OBJECTIVES ACHIEVED:
[Summary of key legal concepts demonstrated in this hypothetical]"""

    def format_prompt(  # type: ignore[override]
        self,
        context: PromptContext,
        hypothetical: str,
        available_topics: List[str],
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Format the legal analysis prompt."""
        user_prompt = self.user_prompt_template.format(
            hypothetical=hypothetical,
            available_topics=", ".join(available_topics),
            output_format=self.output_format,
        )

        return {"system": self.system_prompt, "user": user_prompt}


class PromptTemplateManager:
    """Manager class for handling different prompt templates."""

    def __init__(self):
        self._templates = {
            PromptTemplateType.HYPOTHETICAL_GENERATION: HypotheticalGenerationTemplate(),
            PromptTemplateType.ADHERENCE_CHECK: AdherenceCheckTemplate(),
            PromptTemplateType.SIMILARITY_CHECK: SimilarityCheckTemplate(),
            PromptTemplateType.LEGAL_ANALYSIS: LegalAnalysisTemplate(),
        }

    def get_template(self, template_type: PromptTemplateType) -> PromptTemplate:
        """Get a specific prompt template."""
        if template_type not in self._templates:
            raise ValueError(f"Template type {template_type} not found")
        return self._templates[template_type]

    def list_available_templates(self) -> List[PromptTemplateType]:
        """List all available template types."""
        return list(self._templates.keys())

    def format_prompt(
        self, template_type: PromptTemplateType, context: PromptContext, **kwargs
    ) -> Dict[str, str]:
        """Format a prompt using the specified template."""
        template = self.get_template(template_type)
        return template.format_prompt(context, **kwargs)
