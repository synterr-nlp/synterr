# References

Literature and resources used in synterr development.

---

## Core Papers

### Error Taxonomies & Corpora

**Russian Learner Corpus (RLC)**
- Kosakin, F., et al. (2024). "Russian Learner Corpus: Towards Error-Cause Annotation for L2 Russian." *LREC-COLING 2024*.
- https://aclanthology.org/2024.lrec-main.1241/
- https://github.com/Russian-Learner-Corpus/rlc-annotated
- *38-tag taxonomy focused on error causes*

**RULEC-GEC**
- Rozovskaya, A. & Roth, D. (2019). "Grammar Error Correction in Morphologically Rich Languages: The Case of Russian." *TACL*.
- https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00251
- https://github.com/arozovskaya/RULEC-GEC
- *23-tag taxonomy, M2 format, L2/heritage learner data*

**RU-Lang8**
- Trinh, T. & Rozovskaya, A. (2021). "New Dataset and Strong Baselines for the Grammatical Error Correction of Russian." *ACL Findings*.
- https://aclanthology.org/2021.findings-acl.359.pdf
- *Extended RULEC approach with Lang8 crowdsourced data*

**GERA**
- *German-Russian learner corpus, different annotation schema*
- Error types documented in corpus metadata

### GEC Models

**GECToR**
- Omelianchuk, K., et al. (2020). "GECToR – Grammatical Error Correction: Tag, Not Rewrite." *BEA Workshop*.
- https://aclanthology.org/2020.bea-1.16/
- *Sequence tagging approach, defines $KEEP/$DELETE/$REPLACE/$TRANSFORM/$APPEND tags*

### Evaluation Benchmarks

**RuBLiMP**
- Taktasheva, E., et al. (2024). "RuBLiMP: Russian Benchmark of Linguistic Minimal Pairs." *EMNLP 2024*.
- https://github.com/RussianNLP/RuBLiMP
- *45 grammatical phenomena, minimal pair evaluation*
- *Contains reusable resources: aspect pairs, preposition-case mappings*

---

## Linguistic Resources

### Morphology

**Zaliznjak's Grammatical Dictionary**
- Зализняк А.А. (1977/2003). "Грамматический словарь русского языка: Словоизменение."
- *Canonical resource for Russian paradigms, basis for pymorphy2/OpenCorpora*

**pymorphy2/pymorphy3**
- https://github.com/pymorphy2/pymorphy2
- *Python morphological analyzer based on OpenCorpora + Zaliznjak*

**OpenCorpora**
- http://opencorpora.org/
- *Crowdsourced dictionary with Zaliznjak-style markup*

### Prescriptive Grammar

**Rozental (Розенталь)**
- Розенталь Д.Э. "Справочник по правописанию и литературной правке"
- Розенталь Д.Э. "Управление в русском языке"
- *Standard prescriptive references for Russian grammar rules*

### Paronyms

**EGE Materials (ЕГЭ)**
- ФИПИ official exam preparation materials
- *Standardized paronym lists for Russian language exam*

**Vishnyakova Dictionary**
- Вишнякова О.В. (1984). "Словарь паронимов русского языка."
- *Academic reference for Russian paronyms*

---

## NLP Tools & Backends

### Morphological Analysis

| Tool | Use in synterr | Notes |
|------|----------------|-------|
| **stanza** | Default backend | Stanford NLP, best accuracy (~92 sent/s) |
| **natasha** | Fast backend | Slovnet models (~500 sent/s) |
| **spaCy** | Alternative | ru_core_news_* models |
| **pymorphy3** | Inflection | All backends use for word generation |

### Dependency Parsing

- **stanza** — SynTagRus-trained models
- **spaCy** — ru_core_news_lg (95.12% LAS)
- Required for agreement/government error generation

---

## Data Sources

### Training Corpora (for synterr input)

| Source | Format | Size | Notes |
|--------|--------|------|-------|
| Lenta.ru | CSV (corus) | ~2M sentences | News corpus |
| Wikipedia | XML dump | ~5.8GB | General domain |
| CyberLeninka | JSONL | Variable | Scientific articles |

### Evaluation Corpora

| Corpus | Sentences | Error Types | Access |
|--------|-----------|-------------|--------|
| RULEC-GEC | ~12.5K | 23 types | Email request |
| GERA | Variable | Different schema | Public |
| RuLang-8 | Variable | RULEC-derived | With RULEC |

---

## BibTeX

```bibtex
@inproceedings{kosakin-etal-2024-rlc,
    title = "Russian Learner Corpus: Towards Error-Cause Annotation for {L2} {R}ussian",
    author = "Kosakin, Fedor and others",
    booktitle = "Proceedings of LREC-COLING 2024",
    year = "2024",
    url = "https://aclanthology.org/2024.lrec-main.1241/",
}

@article{rozovskaya-roth-2019-rulec,
    title = "Grammar Error Correction in Morphologically Rich Languages: The Case of {R}ussian",
    author = "Rozovskaya, Alla and Roth, Dan",
    journal = "Transactions of the ACL",
    year = "2019",
    url = "https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00251",
}

@inproceedings{trinh-rozovskaya-2021-rulang8,
    title = "New Dataset and Strong Baselines for the Grammatical Error Correction of {R}ussian",
    author = "Trinh, Trieu and Rozovskaya, Alla",
    booktitle = "Findings of ACL 2021",
    year = "2021",
    url = "https://aclanthology.org/2021.findings-acl.359/",
}

@inproceedings{omelianchuk-etal-2020-gector,
    title = "{GECT}o{R} -- Grammatical Error Correction: Tag, Not Rewrite",
    author = "Omelianchuk, Kostiantyn and others",
    booktitle = "Proceedings of BEA Workshop",
    year = "2020",
    url = "https://aclanthology.org/2020.bea-1.16/",
}

@inproceedings{taktasheva-etal-2024-rublimp,
    title = "{R}u{BL}i{MP}: {R}ussian Benchmark of Linguistic Minimal Pairs",
    author = "Taktasheva, Ekaterina and others",
    booktitle = "Proceedings of EMNLP 2024",
    year = "2024",
    url = "https://github.com/RussianNLP/RuBLiMP",
}
```

---

## Related Work (Not Directly Used)

- **RuERRANT** — ERRANT extended for Russian error annotation
  - Fork of Cambridge ERRANT with Russian support via spaCy ru_core_news_lg
  - Repo: https://github.com/Askinkaty/errant
  - Cloned to: `/Users/aleph/Projects/research/ruerrant`
- **ReLCo** — Semi-automatically annotated learner corpus from Revita platform
  - Paper: Katinskaia et al. (2022) https://aclanthology.org/2022.lrec-1.88/
  - Repo: https://github.com/Askinkaty/Russian_learner_corpus_ReLCo
- **Nasyrova & Sorokin (2025)** — SOTA Russian GEC with ruRoBERTa-large
- **DeepPavlov** — Alternative Russian NLP toolkit (not integrated)
