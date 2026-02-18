[![](https://img.shields.io/badge/jikai_1.0.0-passing-green)](https://github.com/gongahkia/jikai/releases/tag/1.0.0)
[![](https://img.shields.io/badge/jikai_2.0.0-passing-dark_green)](https://github.com/gongahkia/jikai/releases/tag/2.0.0)
![](https://github.com/gongahkia/jikai/actions/workflows/ci.yml/badge.svg)

> [!IMPORTANT]
> Please read through [this disclaimer](#disclaimer) before using [Jikai](https://github.com/gongahkia/jikai).

# `Jikai`

AI-Powered Legal Hypothetical Generator for [Singapore Tort Law](https://www.advlawllc.com/practice/tort-law/#:~:text=Tort%20law%20deals%20with%20civil,defamation%2C%20trespass%2C%20and%20nuisance.).

## Rationale

Over the finals season in December 2024, I found myself wishing I had more tort law [hypotheticals](https://successatmls.com/hypos/) to practise on aside from those [my professor](https://www.linkedin.com/in/jerroldsoh/?originalSubdomain=sg) had provided.

A [quick google search](https://www.reddit.com/r/LawSchool/comments/16istgs/where_to_find_hypos/) revealed this sentiment was shared by many studying law, even [outside of Singapore](https://www.reddit.com/r/findareddit/comments/ssr9wk/a_community_for_hypothetical_legal_questions/). Conducting a [Linkedin poll](https://www.linkedin.com/posts/gabriel-zmong_smu-law-linkedin-activity-7269531363463049217-DXUm?utm_source=share&utm_medium=member_desktop) confirmed these results.

<div align="center">
    <br>
    <img src="./asset/poll.png" width="50%">
    <br><br>
</div>

With these considerations in mind, I created Jikai.

Jikai is a [microservices-based](#container-diagram) application that generates high-quality legal hypotheticals for Singapore Tort Law education with [prompt engineering](#prompt-engineering-architecture), multi-provider LLM support, and an ML-assisted validation pipeline.

Current applications are focused on [Singapore Tort Law](https://www.sal.org.sg/Resources-Tools/Publications/Overview/PublicationsDetails/id/183) but [other domains of law](https://lawforcomputerscientists.pubpub.org/pub/d3mzwako/release/7) can be easily swapped in.

## Stack

* *Backend*: [Python](https://www.python.org/), [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/)
* *TUI*: [Textual](https://textual.textualize.io/), [Rich](https://rich.readthedocs.io/)
* *AI/ML*: [Ollama](https://ollama.ai/), [Anthropic](https://www.anthropic.com/), [Google Gemini](https://ai.google.dev/), [OpenAI](https://openai.com/), [scikit-learn](https://scikit-learn.org/)
* *Embeddings*: [Sentence Transformers](https://www.sbert.net/), [ChromaDB](https://www.trychroma.com/)
* *Database*: [SQLite](https://www.sqlite.org/), [ChromaDB](https://www.trychroma.com/)
* *Testing*: [pytest](https://pytest.org/)
* *Monitoring*: [structlog](https://www.structlog.org/)

## Usage

The below instructions are for locally running `Jikai`.

...

### Local Setup

```console
$ git clone https://github.com/gongahkia/jikai && cd jikai
$ python -m venv .venv && source .venv/bin/activate
$ make setup
$ cp env.example .env
$ make tui
```

### API Key Configuration

Edit `.env` with your provider API keys:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...
OLLAMA_HOST=http://localhost:11434
```


### ML Training

```console
$ make train
```

Or from the TUI: press `t` to open the Train screen.

### Run Modes

```console
$ make tui          # TUI only (default)
$ make api          # API server only
$ make run          # Both TUI + API
```

## API

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Generate a legal hypothetical |
| `/topics` | GET | Get available legal topics |
| `/corpus/entries` | GET | Retrieve corpus entries |
| `/corpus/entries` | POST | Add new corpus entry |
| `/health` | GET | Service health check |
| `/stats` | GET | Generation statistics |
| `/llm/models` | GET | Available LLM models |
| `/llm/health` | GET | LLM service health |
| `/providers` | GET | List providers and models |
| `/providers/default` | PUT | Set default provider |
| `/ml/train` | POST | Trigger ML training |
| `/ml/status` | GET | ML model status and metrics |

### Example API Usage

```console
$ curl -X POST "http://localhost:8000/generate" \
   -H "Content-Type: application/json" \
   -d '{
     "topics": ["negligence", "duty of care"],
     "number_parties": 3,
     "complexity_level": "intermediate"
   }'
$ curl http://localhost:8000/topics
$ curl http://localhost:8000/health
```

## Architecture

...

## Disclaimer

All hypotheticals generated with [Jikai](https://github.com/gongahkia/jikai) are intended for educational and informational purposes only. They do not constitute legal advice and should not be relied upon as such.

### No Liability

By using this tool, you acknowledge and agree that:

1. The creator of this tool shall not be liable for any direct, indirect, incidental, consequential, or special damages arising out of or in connection with the use of the hypotheticals generated, including but not limited to any claims related to defamation or other torts.
2. Any reliance on the information provided by this tool is at your own risk. The creators make no representations or warranties regarding the accuracy, reliability, or completeness of any content generated.
3. The content produced may not reflect current legal standards or interpretations and should not be used as a substitute for professional legal advice.
4. You are encouraged to consult with a qualified legal professional regarding any specific legal questions or concerns you may have. Use of this tool signifies your acceptance of these terms.

## References

The name `Jikai` is in reference to the sorcery of [Ikuto Hagiwara](https://kagurabachi.fandom.com/wiki/Ikuto_Hagiwara) (萩原 幾兎), the commander of the [Kamunabi's](https://kagurabachi.fandom.com/wiki/Kamunabi) [anti-cloud gouger special forces](https://kagurabachi.fandom.com/wiki/Kamunabi#Anti-Cloud_Gouger_Special_Forces), who opposed [Genichi Sojo](https://kagurabachi.fandom.com/wiki/Genichi_Sojo) in the [Vs. Sojo arc](https://kagurabachi.fandom.com/wiki/Vs._Sojo_Arc) of the manga series [Kagurabachi](https://kagurabachi.fandom.com/wiki/Kagurabachi_Wiki).

<div align="center">
  <img src="https://static.wikia.nocookie.net/kagurabachi/images/f/f7/Ikuto_Hagiwara_Portrait.png/revision/latest?cb=20231206044607" width="25%">
</div>

## Research

Jikai would not be where it was today without existing academia.

* [*Focused and Fun: A How-to Guide for Creating Hypotheticals for Law Students*](https://scribes.org/wp-content/uploads/2022/10/Simon-8.23.21.pdf) by Diana J. Simon
* [*Reactive Hypotheticals in Legal Education: Leveraging AI to Create Interactive Fact Patterns*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4763738) by Sean Steward
* [*Legal Theory Lexicon: Hypotheticals*](https://lsolum.typepad.com/legaltheory/2023/01/legal-theory-lexicon-hypotheticals.html) by Legal Theory Blog
