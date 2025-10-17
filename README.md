[![](https://img.shields.io/badge/jikai_1.0.0-passing-green)](https://github.com/gongahkia/jikai/releases/tag/1.0.0) 
[![](https://img.shields.io/badge/jikai_2.0.0-passing-dark_green)](https://github.com/gongahkia/jikai/releases/tag/2.0.0) 

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

Jikai is a production-ready, [microservices-based](#container-diagram) application that generates high-quality legal hypotheticals for Singapore Tort Law education with [prompt engineering](#prompt-engineering-architecture) and a *(somewhat)* scalable architecture.

Current applications are focused on [Singapore Tort Law](https://www.sal.org.sg/Resources-Tools/Publications/Overview/PublicationsDetails/id/183) but [other domains of law](https://lawforcomputerscientists.pubpub.org/pub/d3mzwako/release/7) can be easily swapped in.

## Usage

### Build from source

```console
$ git clone https://github.com/gongahkia/jikai && cd jikai
$ make config
$ cd ./src
$ python3 main.py
```

### Build with Docker Compose

```console
$ git clone https://github.com/gongahkia/jikai && cd jikai
$ cp env.example .env
$ docker-compose up -d
$ curl http://localhost:8000/health # check service health
```

### Local Development with Docker

```console
$ pip install -r requirements.txt
$ cp env.example .env
$ docker run -d -p 11434:11434 ollama/ollama
$ docker exec -it <ollama-container> ollama pull llama2:7b
$ uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 # start the API
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

### DB

Processed hypotheticals are stored in [ChromaDB](https://www.trychroma.com/) per the below schema.

```mermaid
erDiagram
    HYPOTHETICAL {
        string id PK
        text content
        array topics
        json metadata
        timestamp created_at
        timestamp updated_at
    }
    
    VALIDATION_RESULT {
        string id PK
        string hypothetical_id FK
        json adherence_check
        json similarity_check
        float quality_score
        boolean passed
        timestamp validated_at
    }
    
    GENERATION_LOG {
        string id PK
        json request_data
        json response_data
        float generation_time
        timestamp created_at
    }
    
    CORPUS_ENTRY {
        string id PK
        text content
        array topics
        json metadata
        timestamp created_at
        timestamp updated_at
    }
    
    HYPOTHETICAL ||--o{ VALIDATION_RESULT : "validated_by"
    HYPOTHETICAL ||--o{ GENERATION_LOG : "logged_in"
    CORPUS_ENTRY ||--o{ HYPOTHETICAL : "inspires"
```

### Overview

### C4 Diagrams

#### System Context

```mermaid
graph TB
    subgraph "External Systems"
        Student[Law Students]
        Professor[Legal Educators]
        Ollama[Ollama LLM Service]
        OpenAI[OpenAI API]
        AWS[AWS S3 Storage]
    end
    
    subgraph "Jikai System"
        API[Jikai API]
    end
    
    Student -->|Generate Hypotheticals| API
    Professor -->|Access Corpus| API
    API -->|LLM Requests| Ollama
    API -->|LLM Requests| OpenAI
    API -->|Corpus Storage| AWS
    
    classDef external fill:#e1f5fe
    classDef system fill:#f3e5f5
    
    class Student,Professor,Ollama,OpenAI,AWS external
    class API system
```

#### Container Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        WebClient[Web Browser]
        APIClient[API Client]
    end
    
    subgraph "Jikai Application"
        subgraph "API Gateway"
            FastAPI[FastAPI Application<br/>Port 8000]
        end
        
        subgraph "Core Services"
            HypService[Hypothetical Service]
            LLMService[LLM Service]
            CorpusService[Corpus Service]
            PromptService[Prompt Engineering]
        end
        
        subgraph "Data Layer"
            ChromaDB[(ChromaDB<br/>Vector Database)]
            LocalFiles[(Local Corpus Files)]
            S3Storage[(AWS S3<br/>Cloud Storage)]
        end
        
        subgraph "External Services"
            OllamaService[Ollama LLM<br/>Port 11434]
            RedisCache[(Redis Cache<br/>Port 6379)]
        end
    end
    
    WebClient --> FastAPI
    APIClient --> FastAPI
    
    FastAPI --> HypService
    HypService --> LLMService
    HypService --> CorpusService
    HypService --> PromptService
    
    LLMService --> OllamaService
    CorpusService --> ChromaDB
    CorpusService --> LocalFiles
    CorpusService --> S3Storage
    
    FastAPI --> RedisCache
    
    classDef client fill:#e8f5e8
    classDef api fill:#fff3e0
    classDef service fill:#f3e5f5
    classDef data fill:#e1f5fe
    classDef external fill:#fce4ec
    
    class WebClient,APIClient client
    class FastAPI api
    class HypService,LLMService,CorpusService,PromptService service
    class ChromaDB,LocalFiles,S3Storage data
    class OllamaService,RedisCache external
```

#### Hypothetical Service Component Diagram

```mermaid
graph TB
    subgraph "Hypothetical Service Components"
        subgraph "API Layer"
            RESTController[REST Controller]
            ValidationLayer[Request Validation]
        end
        
        subgraph "Business Logic"
            GenerationOrchestrator[Generation Orchestrator]
            ValidationEngine[Validation Engine]
            QualityAssessor[Quality Assessor]
        end
        
        subgraph "Prompt Engineering"
            TemplateManager[Template Manager]
            ContextBuilder[Context Builder]
            PromptFormatter[Prompt Formatter]
        end
        
        subgraph "External Integrations"
            LLMClient[LLM Client]
            CorpusClient[Corpus Client]
            StorageClient[Storage Client]
        end
    end
    
    RESTController --> ValidationLayer
    ValidationLayer --> GenerationOrchestrator
    
    GenerationOrchestrator --> TemplateManager
    GenerationOrchestrator --> ValidationEngine
    GenerationOrchestrator --> QualityAssessor
    
    TemplateManager --> ContextBuilder
    ContextBuilder --> PromptFormatter
    
    LLMClient --> TemplateManager
    CorpusClient --> ContextBuilder
    StorageClient --> QualityAssessor
    
    classDef api fill:#e8f5e8
    classDef business fill:#fff3e0
    classDef prompt fill:#f3e5f5
    classDef integration fill:#e1f5fe
    
    class RESTController,ValidationLayer api
    class GenerationOrchestrator,ValidationEngine,QualityAssessor business
    class TemplateManager,ContextBuilder,PromptFormatter prompt
    class LLMClient,CorpusClient,StorageClient integration
```

#### Prompt Engineering Architecture

```mermaid
graph TD
    subgraph "Prompt Engineering System"
        subgraph "Template Types"
            GenTemplate[Hypothetical Generation<br/>Chain of Thought + Few-shot]
            AdherenceTemplate[Adherence Check<br/>Structured Output]
            SimilarityTemplate[Similarity Check<br/>Context-aware]
            AnalysisTemplate[Legal Analysis<br/>Chain of Thought]
        end
        
        subgraph "Techniques"
            CoT[Chain of Thought]
            FewShot[Few-shot Learning]
            RoleBased[Role-based Prompting]
            Structured[Structured Output]
            ContextAware[Context-aware Prompting]
        end
        
        subgraph "Context Management"
            TopicExtractor[Topic Extractor]
            CorpusRetriever[Corpus Retriever]
            ContextBuilder[Context Builder]
        end
    end
    
    GenTemplate --> CoT
    GenTemplate --> FewShot
    AdherenceTemplate --> Structured
    SimilarityTemplate --> ContextAware
    AnalysisTemplate --> CoT
    
    TopicExtractor --> ContextBuilder
    CorpusRetriever --> ContextBuilder
    ContextBuilder --> GenTemplate
    
    classDef template fill:#e8f5e8
    classDef technique fill:#fff3e0
    classDef context fill:#f3e5f5
    
    class GenTemplate,AdherenceTemplate,SimilarityTemplate,AnalysisTemplate template
    class CoT,FewShot,RoleBased,Structured,ContextAware technique
    class TopicExtractor,CorpusRetriever,ContextBuilder context
```

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

![](https://static.wikia.nocookie.net/kagurabachi/images/f/f7/Ikuto_Hagiwara_Portrait.png/revision/latest?cb=20231206044607)

## Research

Jikai would not be where it was today without existing academia.  

* [*Focused and Fun: A How-to Guide for Creating Hypotheticals for Law Students*](https://scribes.org/wp-content/uploads/2022/10/Simon-8.23.21.pdf) by Diana J. Simon
* [*Reactive Hypotheticals in Legal Education: Leveraging AI to Create Interactive Fact Patterns*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4763738) by Sean Steward
* [*Legal Theory Lexicon: Hypotheticals*](https://lsolum.typepad.com/legaltheory/2023/01/legal-theory-lexicon-hypotheticals.html) by Legal Theory Blog