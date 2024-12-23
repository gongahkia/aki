[![](https://img.shields.io/badge/jikai_1.0-build-orange)](https://github.com/gongahkia/jikai/releases/tag/1.0)

# `Jikai`

Create law hypos.

## Architecture

```mmd
graph TD
    Z([Raw data]) -->|Indexed and labelled| A
    A[(Labelled corpus)] -->|Extract Topic Specific Data|B
    Y(User-specified configuration) -->|Extract Topics|A
    B[Reference data] --> M
    Y -->|Reformat| U
    U[Templated prompt] --> M[Combined prompt and context]
    M -->|Prompt| C{LLM Hypothetical Generation Model}
    C -->|Generate scenario| X[Law hypothetical]
    X --> D{LLM Agent 1:<br>Adherence to Parameters Check}
    X --> E{LLM Agent 2:<br>Similarity to Corpus Check}
    D -->|Pass| F{LLM Agent 3:<br>Performs Legal Analysis}
    E -->|Pass| F
    D -->|Fail| M
    E -->|Fail| M
    F -->|Issue generation| G(Recommended legal analysis)
```

## Usage

Build the local docker image.

```console
$ docker build -t jikai
$ docker run jikai
```

## References

The name `Jikai` is in reference to the sorcery of [Ikuto Hagiwara](https://kagurabachi.fandom.com/wiki/Ikuto_Hagiwara) (萩原 幾兎), the commander of the [Kamunabi's](https://kagurabachi.fandom.com/wiki/Kamunabi) [anti-cloud gouger special forces](https://kagurabachi.fandom.com/wiki/Kamunabi#Anti-Cloud_Gouger_Special_Forces), who opposed [Genichi Sojo](https://kagurabachi.fandom.com/wiki/Genichi_Sojo) in the [Vs. Sojo arc](https://kagurabachi.fandom.com/wiki/Vs._Sojo_Arc) of the manga series [Kagurabachi](https://kagurabachi.fandom.com/wiki/Kagurabachi_Wiki).

![](https://static.wikia.nocookie.net/kagurabachi/images/f/f7/Ikuto_Hagiwara_Portrait.png/revision/latest?cb=20231206044607)
