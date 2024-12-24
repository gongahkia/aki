[![](https://img.shields.io/badge/jikai_1.0-build-orange)](https://github.com/gongahkia/jikai/releases/tag/1.0)

> [!IMPORTANT]  
> Please read through the [disclaimer](#disclaimer) before using [Jikai](https://github.com/gongahkia/jikai).  

# `Jikai`

Create law hypos.

## Usage

Build the local docker image.

```console
$ docker build -t jikai
$ docker run jikai
```

## Architecture

```mermaid
graph TD
    subgraph "Data Preparation"
        Corpus@{ shape: docs } -->|Indexed| Tagged@{ shape: tag-doc }
        Tagged --> A
    end
    A[(Labelled corpus)] -->|Extract Topic Specific Data|B
    Y([User-specified configuration]) --->|Extract Topics|A
    B[Reference data as context] --> M
    Y -->|Reformat| U
    U[Templated prompt] --> M[Combined prompt and context]
    subgraph "Agentic Checks"
        M -->|Prompt| C{LLM Hypothetical Generation Model}
        C -->|Generate scenario| X[Law hypothetical]
        X --> D{LLM Agent 1:<br>Adherence to Parameters Check}
        X --> E{LLM Agent 2:<br>Similarity to Corpus Check}
        D -->|Valid| W[Validated law hypothetical]
        E -->|Valid| W
    end
    W --> F{LLM Agent 3:<br>Performs Legal Analysis}
    W --->|Reformat| V(Final law hypothetical)
    D -->|Invalid| M
    E -->|Invalid| M
    F -->|Issue generation| G(Recommended legal analysis)
```

## References

The name `Jikai` is in reference to the sorcery of [Ikuto Hagiwara](https://kagurabachi.fandom.com/wiki/Ikuto_Hagiwara) (萩原 幾兎), the commander of the [Kamunabi's](https://kagurabachi.fandom.com/wiki/Kamunabi) [anti-cloud gouger special forces](https://kagurabachi.fandom.com/wiki/Kamunabi#Anti-Cloud_Gouger_Special_Forces), who opposed [Genichi Sojo](https://kagurabachi.fandom.com/wiki/Genichi_Sojo) in the [Vs. Sojo arc](https://kagurabachi.fandom.com/wiki/Vs._Sojo_Arc) of the manga series [Kagurabachi](https://kagurabachi.fandom.com/wiki/Kagurabachi_Wiki).

![](https://static.wikia.nocookie.net/kagurabachi/images/f/f7/Ikuto_Hagiwara_Portrait.png/revision/latest?cb=20231206044607)

## Disclaimer

All hypotheticals generated with [Jikai](https://github.com/gongahkia/jikai) are intended for educational and informational purposes only. They do not constitute legal advice and should not be relied upon as such. 

### No Liability

By using this tool, you acknowledge and agree that:

1. The creator of this tool shall not be liable for any direct, indirect, incidental, consequential, or special damages arising out of or in connection with the use of the hypotheticals generated, including but not limited to any claims related to defamation or other torts.
2. Any reliance on the information provided by this tool is at your own risk. The creators make no representations or warranties regarding the accuracy, reliability, or completeness of any content generated.
3. The content produced may not reflect current legal standards or interpretations and should not be used as a substitute for professional legal advice.
4. You are encouraged to consult with a qualified legal professional regarding any specific legal questions or concerns you may have. Use of this tool signifies your acceptance of these terms.
