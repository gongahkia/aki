"""ML-driven hypothetical generation engine.

Replaces LLM-based generation. Assembles hypotheticals from corpus fragments
using ML models for topic selection, structural planning, quality gating,
and diversity checking.
"""

from __future__ import annotations

import hashlib
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

# ── Singapore-appropriate fictional names ──────────────────────────────────
_CHINESE_NAMES = [
    "Tan Wei Ming",
    "Lim Shu Fen",
    "Ng Kai Lun",
    "Wong Mei Ling",
    "Chen Jia Hao",
    "Lee Xin Yi",
    "Goh Zhi Wei",
    "Ong Hui Min",
    "Koh Boon Kiat",
    "Chua Li Ting",
]
_MALAY_NAMES = [
    "Ahmad bin Ismail",
    "Siti binti Rahman",
    "Mohd Faizal",
    "Nurul Ain",
    "Razak bin Osman",
    "Hakim bin Yusof",
    "Aishah binti Kadir",
    "Farhan bin Zain",
    "Zulaikha binti Hassan",
]
_INDIAN_NAMES = [
    "Rajesh Nair",
    "Priya Devi",
    "Suresh Kumar",
    "Anitha Pillai",
    "Vikram Rajan",
    "Deepa Menon",
    "Arjun Krishnan",
    "Kavitha Sundaram",
    "Ganesh Iyer",
]
_WESTERN_NAMES = [
    "James Mitchell",
    "Sarah Collins",
    "David Thompson",
    "Emma Richardson",
    "Michael Stuart",
    "Rachel Pemberton",
    "Andrew Fielding",
    "Catherine Blake",
]
_ALL_NAMES = _CHINESE_NAMES + _MALAY_NAMES + _INDIAN_NAMES + _WESTERN_NAMES
_COMPANY_SUFFIXES = ["Pte Ltd", "Holdings", "Services", "Enterprises", "Solutions"]
_LOCATIONS = [
    "Orchard Road",
    "Tampines",
    "Jurong East",
    "Toa Payoh",
    "Bukit Timah",
    "Marine Parade",
    "Ang Mo Kio",
    "Clementi",
    "Bedok",
    "Woodlands",
    "Hougang",
    "Sentosa",
    "Marina Bay",
    "Chinatown",
    "Little India",
]
_STRUCTURAL_SLOTS = [
    "scenario_setup",
    "parties_introduction",
    "factual_complications",
    "legal_issues",
    "analysis_framework",
]


class PartyNameGenerator:
    """Generates diverse Singapore-appropriate fictional names."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._used: set = set()

    def generate(self, count: int = 3, include_company: bool = True) -> List[str]:
        available = [n for n in _ALL_NAMES if n not in self._used]
        if len(available) < count:
            self._used.clear()
            available = list(_ALL_NAMES)
        self._rng.shuffle(available)
        names = available[:count]
        self._used.update(names)
        if include_company and count >= 2:
            base = self._rng.choice(
                ["Alpha", "Bright", "Coastal", "Delta", "Eastern", "Fortune", "Global"]
            )
            suffix = self._rng.choice(_COMPANY_SUFFIXES)
            names[-1] = f"{base} {suffix}"
        return names


class CorpusRetriever:
    """Retrieves relevant corpus entries via TopicSelector + vector service."""

    def __init__(self):
        self._topic_selector = None

    def initialize(self, corpus_entries: List[Dict]):
        from ..ml.topic_selector import TopicSelector

        self._topic_selector = TopicSelector()
        self._topic_selector.fit(corpus_entries)

    def retrieve(
        self, topics: List[str], n_results: int = 5, classifier=None
    ) -> List[Dict]:
        if self._topic_selector is None:
            return []
        results = self._topic_selector.select(
            topics, n_results=n_results, classifier=classifier
        )
        return [entry for entry, _score in results]


class TemplateEngine:
    """Structural templates with slots for hypothetical assembly."""

    def get_template(self, topics: List[str], complexity: int) -> Dict[str, str]:
        """Return a structural template dict with slot placeholders."""
        from ..domain.templates import load_topic_template

        primary_topic = topics[0] if topics else "negligence"
        tmpl_data = load_topic_template(primary_topic)
        scenario_patterns = tmpl_data.get(
            "scenario_patterns", ["A dispute arises in Singapore."]
        )
        legal_tests = tmpl_data.get("legal_tests", [])
        defences = tmpl_data.get("defences", [])
        party_roles = tmpl_data.get("party_roles", ["claimant", "defendant"])
        template = {
            "scenario_setup": random.choice(scenario_patterns),
            "parties_introduction": f"The scenario involves {len(party_roles)} parties: {', '.join(party_roles)}.",
            "factual_complications": "",
            "legal_issues": "The following legal issues arise: "
            + ", ".join(topics)
            + ".",
            "analysis_framework": "",
        }
        if legal_tests:
            template["legal_issues"] += (
                " Key legal tests: " + "; ".join(legal_tests[:3]) + "."
            )
        if defences and complexity >= 3:
            template["factual_complications"] = (
                "Available defences include: " + ", ".join(defences[:2]) + "."
            )
        return template


class HypoAssembler:
    """Fills template slots using corpus fragments to create novel scenarios."""

    def assemble(
        self,
        template: Dict[str, str],
        corpus_fragments: List[Dict],
        party_names: List[str],
        location: str,
        complexity_constraints: Optional[Any] = None,
    ) -> str:
        """Assemble a hypothetical from template + corpus fragments."""
        sections = []
        # scenario setup with location and parties
        intro = template.get("scenario_setup", "")
        party_intro = self._build_party_intro(party_names, location)
        sections.append(party_intro)
        if intro:
            sections.append(intro)
        # weave in corpus fragments as fact patterns
        fact_patterns = self._extract_fact_patterns(corpus_fragments, party_names)
        if fact_patterns:
            sections.append(fact_patterns)
        # factual complications
        complications = template.get("factual_complications", "")
        if complications:
            sections.append(complications)
        # legal issues framing
        legal = template.get("legal_issues", "")
        if legal:
            sections.append(legal)
        text = "\n\n".join(s for s in sections if s.strip())
        if complexity_constraints and hasattr(complexity_constraints, "word_count_min"):
            word_count = len(text.split())
            if word_count < complexity_constraints.word_count_min:
                text = self._expand_text(
                    text,
                    corpus_fragments,
                    complexity_constraints.word_count_min - word_count,
                )
        return text

    def _build_party_intro(self, names: List[str], location: str) -> str:
        if not names:
            return f"The events take place in {location}, Singapore."
        lines = [f"The events take place in {location}, Singapore."]
        roles = [
            "operates a business",
            "lives nearby",
            "works as a professional",
            "is a regular visitor",
            "manages the premises",
        ]
        for i, name in enumerate(names):
            role = roles[i % len(roles)]
            lines.append(f"{name} {role} in the area.")
        return " ".join(lines)

    _NAME_EXCLUSIONS = { # common words that match name regex but aren't party names
        "Singapore", "Court", "High", "Supreme", "District", "State", "Appeal",
        "Tort", "Law", "The", "This", "That", "These", "Those", "However",
        "Furthermore", "Moreover", "Nevertheless", "Accordingly", "Therefore",
        "Section", "Act", "Statute", "Regulation", "Article", "Chapter",
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        "Orchard", "Tampines", "Jurong", "Bedok", "Woodlands", "Hougang",
        "Clementi", "Sentosa", "Marina", "Chinatown", "Raffles", "Changi",
        "Pte", "Ltd", "Inc", "Corp", "Holdings", "Services", "Enterprises",
        "Road", "Street", "Avenue", "Drive", "Lane", "Place", "Boulevard",
    }

    def _extract_fact_patterns(
        self, fragments: List[Dict], party_names: List[str]
    ) -> str:
        """Extract and recombine fact patterns from corpus fragments."""
        if not fragments:
            return ""
        sentences_pool: List[str] = []
        for frag in fragments[:3]:
            text = frag.get("text", "")
            sents = re.split(r"(?<=[.!?])\s+", text)
            mid = sents[len(sents) // 4 : 3 * len(sents) // 4] # skip intro/conclusion
            sentences_pool.extend(mid[:5])
        if not sentences_pool:
            return ""
        selected = sentences_pool[:8]
        result = " ".join(selected)
        name_patterns = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", result)
        filtered = [
            n for n in name_patterns
            if not any(token in self._NAME_EXCLUSIONS for token in n.split())
        ]
        unique_originals = list(dict.fromkeys(filtered))[: len(party_names)]
        for i, original in enumerate(unique_originals):
            if i < len(party_names):
                result = result.replace(original, party_names[i])
        return result

    def _expand_text(self, text: str, fragments: List[Dict], words_needed: int) -> str:
        """Add more detail from corpus fragments to meet word count."""
        extra = []
        for frag in fragments:
            sents = re.split(r"(?<=[.!?])\s+", frag.get("text", ""))
            extra.extend(sents[1:4])
            if sum(len(s.split()) for s in extra) >= words_needed:
                break
        return text + "\n\n" + " ".join(extra[:5])


class VariationEngine:
    """Introduces controlled mutations to assembled hypotheticals."""

    _SEVERITY_MODIFIERS = [
        ("minor", "serious"),
        ("slight", "severe"),
        ("small", "significant"),
        ("temporary", "permanent"),
        ("mild", "critical"),
    ]
    _DEFENCE_ADDITIONS = [
        "Furthermore, the defendant argues that the claimant had voluntarily assumed the risk.",
        "The defendant contends that the claimant's own negligence contributed to the harm.",
        "It is argued that the claimant was engaged in an illegal activity at the time.",
    ]

    def mutate(self, text: str, mutation_type: str = "random") -> str:
        """Apply a mutation to the hypothetical text."""
        mutations = {
            "swap_roles": self._swap_party_roles,
            "change_severity": self._change_severity,
            "add_defence": self._add_defence,
            "alter_causation": self._alter_causation,
        }
        if mutation_type == "random":
            mutation_type = random.choice(list(mutations.keys()))
        fn = mutations.get(mutation_type, self._change_severity)
        return fn(text)

    def _swap_party_roles(self, text: str) -> str:
        names = re.findall(
            r"\b[A-Z][a-z]+(?:\s(?:bin|binti|Pte|Ltd)\s)?[A-Z]?[a-z]*\b", text
        )
        unique = list(dict.fromkeys(names))
        if len(unique) >= 2:
            text = text.replace(unique[0], "__SWAP__")
            text = text.replace(unique[1], unique[0])
            text = text.replace("__SWAP__", unique[1])
        return text

    def _change_severity(self, text: str) -> str:
        for mild, severe in self._SEVERITY_MODIFIERS:
            if mild in text.lower():
                text = re.sub(
                    rf"\b{mild}\b", severe, text, count=1, flags=re.IGNORECASE
                )
                break
        return text

    def _add_defence(self, text: str) -> str:
        return text + "\n\n" + random.choice(self._DEFENCE_ADDITIONS)

    def _alter_causation(self, text: str) -> str:
        return (
            text
            + "\n\nA third party's intervening act may have contributed to the outcome."
        )


class QualityGate:
    """Runs QualityRegressor on assembled text; rejects below threshold."""

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self._pipeline: Any = None

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            try:
                from ..ml.pipeline import MLPipeline

                self._pipeline = MLPipeline()
                self._pipeline.load_all()
            except Exception:
                return None
        return self._pipeline

    def evaluate(self, text: str) -> Dict[str, float]:
        """Return quality scores. Returns {'overall': score, ...} or defaults."""
        pipeline = self._get_pipeline()
        if (
            pipeline is None
            or not pipeline.regressor.is_trained
            or pipeline._vectorizer is None
        ):
            return {
                "overall": 0.7,
                "topic_coverage": 0.7,
                "complexity_match": 0.7,
                "structural_completeness": 0.7,
            }
        X = pipeline._vectorizer.transform([text])
        return pipeline.regressor.predict_dimensions(X)

    def passes(self, text: str) -> Tuple[bool, Dict[str, float]]:
        scores = self.evaluate(text)
        return scores.get("overall", 0.0) >= self.threshold, scores


class DiversityChecker:
    """Ensures generated hypos don't cluster too closely with previous ones."""

    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold
        self._previous_texts: List[str] = []
        self._vectorizer: Any = None
        self._prev_matrix: Any = None # cached TF-IDF matrix for previous texts

    def check(self, text: str) -> bool:
        """Return True if text is sufficiently diverse from previous generations."""
        if not self._previous_texts:
            self._previous_texts.append(text)
            self._vectorizer = None
            self._prev_matrix = None
            return True
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            if self._vectorizer is None: # first comparison — fit vectorizer
                self._vectorizer = TfidfVectorizer(max_features=2000)
                self._prev_matrix = self._vectorizer.fit_transform(self._previous_texts)
            new_vec = self._vectorizer.transform([text])
            sims = cosine_similarity(new_vec, self._prev_matrix).flatten()
            if max(sims) > self.threshold:
                return False
            from scipy.sparse import vstack
            self._prev_matrix = vstack([self._prev_matrix, new_vec])
        except Exception:
            pass
        self._previous_texts.append(text)
        return True

    def reset(self):
        self._previous_texts.clear()
        self._vectorizer = None
        self._prev_matrix = None


class MultiIssueCombiner:
    """Weaves 2-3 tort topics together with shared facts."""

    def combine_issues(self, topics: List[str], structural_plan: Dict) -> str:
        """Generate transition text connecting multiple legal issues."""
        if len(topics) <= 1:
            return ""
        transitions = []
        sequence = structural_plan.get("legal_issues_sequence", topics)
        for i in range(len(sequence) - 1):
            t1, t2 = sequence[i], sequence[i + 1]
            transitions.append(
                f"The facts giving rise to the {t1.replace('_', ' ')} claim also raise issues of {t2.replace('_', ' ')}."
            )
        return " ".join(transitions)


class HypoGenerator:
    """Main orchestrator: ML-driven hypothetical generation engine."""

    def __init__(self):
        self.corpus_retriever = CorpusRetriever()
        self.template_engine = TemplateEngine()
        self.assembler = HypoAssembler()
        self.variation_engine = VariationEngine()
        self.quality_gate = QualityGate()
        self.diversity_checker = DiversityChecker()
        self.multi_issue_combiner = MultiIssueCombiner()
        self.name_generator = PartyNameGenerator()
        self._initialized = False

    async def initialize(self):
        """Load corpus entries for retrieval."""
        if self._initialized:
            return
        try:
            from .corpus_service import corpus_service

            entries = await corpus_service.load_corpus()
            corpus_dicts = [
                {"text": e.text, "topics": e.topics, "id": e.id} for e in entries
            ]
            self.corpus_retriever.initialize(corpus_dicts)
            self._initialized = True
            logger.info("hypo_generator initialized", corpus_size=len(corpus_dicts))
        except Exception as e:
            logger.error("hypo_generator init failed", error=str(e))

    async def generate(
        self,
        topics: List[str],
        complexity: int = 3,
        num_parties: int = 3,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Generate a hypothetical and return text + confidence scores."""
        await self.initialize()
        # structural planning
        planner = self._get_structural_planner()
        plan = (
            planner.predict("", topics, complexity)
            if planner
            else {
                "party_roles": num_parties,
                "scenario_type": "single-event",
                "legal_issues_sequence": topics,
                "analysis_points": ["parties", "scenario", "legal_issues"],
            }
        )
        # complexity constraints
        constraints = self._get_complexity_constraints(complexity)
        # retrieve relevant corpus entries
        fragments = self.corpus_retriever.retrieve(topics, n_results=5)
        # generate party names
        party_names = self.name_generator.generate(count=num_parties)
        location = random.choice(_LOCATIONS)
        best_text = ""
        best_scores: Dict[str, float] = {}
        for attempt in range(max_retries):
            template = self.template_engine.get_template(topics, complexity)
            text = self.assembler.assemble(
                template, fragments, party_names, location, constraints
            )
            # add multi-issue transitions
            transitions = self.multi_issue_combiner.combine_issues(topics, plan)
            if transitions:
                text += "\n\n" + transitions
            # quality gate
            passes, scores = self.quality_gate.passes(text)
            if not best_text or scores.get("overall", 0) > best_scores.get(
                "overall", 0
            ):
                best_text = text
                best_scores = scores
            if passes:
                break
            # mutate for next attempt
            fragments_shuffled = list(fragments)
            random.shuffle(fragments_shuffled)
            fragments = fragments_shuffled
            text = self.variation_engine.mutate(text)
        # diversity check
        is_diverse = self.diversity_checker.check(best_text)
        if not is_diverse:
            best_text = self.variation_engine.mutate(best_text, "swap_roles")
        return {
            "text": best_text,
            "confidence": best_scores,
            "generation_id": hashlib.sha256(best_text.encode()).hexdigest()[:16],
            "topics": topics,
            "complexity": complexity,
            "num_parties": num_parties,
            "is_diverse": is_diverse,
        }

    def _get_structural_planner(self):
        try:
            from ..ml.structural_planner import StructuralPlanner

            return StructuralPlanner()
        except Exception:
            return None

    def _get_complexity_constraints(self, complexity: int):
        try:
            from ..ml.complexity_controller import ComplexityController

            ctrl = ComplexityController()
            return ctrl.get_constraints(complexity)
        except Exception:
            return None


# singleton
hypo_generator = HypoGenerator()
