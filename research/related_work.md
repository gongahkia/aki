# Related Work

LegalBench-RAG is a legal retrieval benchmark focused on the retrieval step of RAG systems. It uses human-annotated relevant text segments and deterministic precision/recall-style scoring over legal corpora. [Inference] This motivates Jikai's retrieval recall, MRR, and NDCG smoke metrics. Sources: <https://arxiv.org/abs/2408.10343>, <https://github.com/zeroentropy-ai/legalbenchrag>.

LexRAG frames legal RAG as multi-turn legal consultation with expert-annotated conversational retrieval and response-generation tasks. Jikai is narrower: it targets SG tort hypotheticals. [Inference] The LexRAG setup supports evaluating both retrieval and generated answers. Sources: <https://dl.acm.org/doi/10.1145/3726302.3730340>, <https://arxiv.org/html/2502.20640v1>.

LRAGE is an open-source legal RAG evaluation tool with GUI/CLI workflows for comparing retrieval corpora, algorithms, rerankers, LLM backbones, and metrics. [Inference] Jikai's `script/run_jikai_eval.py` and `script/run_ablations.py` mirror that evaluation harness direction at project scale. Sources: <https://arxiv.org/abs/2504.01840>, <https://github.com/hoorangyee/LRAGE>.

Dahl 2024 studies legal hallucinations and reports high hallucination rates across general-purpose LLMs on legal questions. [Inference] The paper supports Jikai's emphasis on faithfulness checks, citation grounding, and avoiding unsourced public quality claims. Sources: <https://arxiv.org/abs/2401.01301>, <https://academic.oup.com/jla/article/16/1/64/7699227>.

Magesh 2025 evaluates commercial legal research assistants and reports non-trivial hallucination rates despite vendor reliability claims. [Inference] It supports Jikai's conservative README language and the decision to label dry-run metrics explicitly. Sources: <https://law.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools/>, <https://isps.yale.edu/research/publications/isps25-33>, <https://onlinelibrary.wiley.com/doi/full/10.1111/jels.12413>.

RAGAS provides RAG evaluation metrics including faithfulness and context-focused measures. Jikai names `ragas_faithfulness` as an eval metric and uses it as a dry-run smoke signal, not as a validated external benchmark score. Sources: <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/>, <https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/>.

TruLens provides RAG evaluation and tracing concepts such as context relevance, groundedness, and answer relevance. [Inference] Its metric taxonomy aligns with Jikai's split between retrieval metrics, faithfulness, and answer quality. Source: <https://www.trulens.org/>.

DeepEval provides LLM-as-judge metrics for faithfulness and contextual relevancy in RAG systems. [Inference] Jikai's faithfulness and retrieval-eval split follows the same separation between generator correctness and context relevance. Sources: <https://deepeval.com/docs/metrics-faithfulness>, <https://deepeval.com/docs/metrics-contextual-relevancy>.

DSPy is a framework for programming and optimizing language-model pipelines through signatures, modules, and optimizers. Jikai does not currently use DSPy. [Speculation] The staged prompt, structured-output, and ablation design could support future optimizer-backed prompt tuning. Sources: <https://dspy.ai/>, <https://github.com/stanfordnlp/dspy>.

SetFit is a prompt-free few-shot fine-tuning method for Sentence Transformers. Jikai uses an optional SetFit backend for multi-label SG tort topic classification when `JIKAI_CLASSIFIER_BACKEND=setfit` is selected. Sources: <https://arxiv.org/abs/2209.11055>, <https://github.com/huggingface/setfit>, <https://huggingface.co/blog/setfit>.

Instructor is a structured-output library centered on Pydantic schemas, validation, and retries. Jikai's structured generation uses local Pydantic schemas directly rather than Instructor. [Inference] Both share schema-first output validation. Source: <https://python.useinstructor.com/>.

Outlines supports constrained structured generation such as JSON Schema, regex, and grammar-constrained decoding. Jikai currently validates structured provider output after generation. [Speculation] Outlines is a candidate for stricter decoding if local model support becomes a priority. Source: <https://dottxt-ai.github.io/outlines/latest/>.
