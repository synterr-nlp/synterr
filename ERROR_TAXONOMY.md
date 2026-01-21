Good question — you want taxonomies grounded in actual linguistic research, not vibes. Let me find you proper sources.PubMed's not the right place for this. Let me search for computational linguistics resources.Let me fetch the most detailed paper with the actual error taxonomy:Excellent. Here are the key **referenced resources** for Russian grammatical error taxonomies:

---

## Primary Corpora & Taxonomies

### 1. **RLC (Russian Learner Corpus) Error Classification**
- **38 tags** covering spelling, morphology, syntax, lexis, and constructions
- Unique approach: focuses on *error causes* (syntactic relations, derivational patterns) rather than just token-level features
- Categories include: `Gov` (government), `AgrCase/AgrNum/AgrGender/AgrPers` (agreement types), `Asp` (aspect), `Refl` (reflexive), `Morph` (derivational), `Infl` (inflectional), `Constr` (constructional), `Lex`, `Ortho`, etc.

**Key papers:**
- Kosakin et al. (2024) "Russian Learner Corpus: Towards Error-Cause Annotation for L2 Russian" — LREC-COLING 2024 — https://aclanthology.org/2024.lrec-main.1241/
- Rakhilina et al. (2016) "Building a learner corpus for Russian" — https://aclanthology.org/W16-6509/

**Data:** https://github.com/Russian-Learner-Corpus/rlc-annotated

---

### 2. **RULEC-GEC Error Tagset**
- **23 tags** covering morphosyntactic errors, orthography, and lexical errors
- More compact than RLC; designed for minimal annotation burden
- Aligned with English GEC conventions (CoNLL-2014 format)

**Key paper:**
- Rozovskaya & Roth (2019) "Grammar Error Correction in Morphologically Rich Languages: The Case of Russian" — *TACL* — https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00251

**Data:** https://github.com/arozovskaya/RULEC-GEC (email required)

---

### 3. **RU-Lang8 Error Categories**
- Extension of RULEC approach with Lang8 crowdsourced data
- Full error type list in Appendix Table 11 of the paper

**Key paper:**
- Trinh & Rozovskaya (2021) "New Dataset and Strong Baselines for the Grammatical Error Correction of Russian" — ACL Findings — https://aclanthology.org/2021.findings-acl.359.pdf

---

### 4. **RuERRANT**
- ERRANT (Error Annotation Toolkit) extended for Russian
- Uses spaCy ru_core_news_lg for Russian support
- Outputs M2 format with error type classification

**Repo:** https://github.com/Askinkaty/errant

### 5. **ReLCo**
- Semi-automatically annotated learner corpus from Revita language-learning platform
- Errors collected automatically during L2 learner exercises

**Paper:** Katinskaia et al. (2022) "Semi-automatically annotated learner corpus for Russian" — https://aclanthology.org/2022.lrec-1.88/
**Repo:** https://github.com/Askinkaty/Russian_learner_corpus_ReLCo

---

## Summary of Error Categories (from RLC — the most comprehensive)

| Domain | Tags |
|--------|------|
| **Orthography** | `Graph`, `Hyphen`, `Space`, `Ortho`, `Misspell` |
| **Morphology** | `Morph` (derivation), `Altern` (stem alternation), `Infl` (inflection), `Num`, `Gender` |
| **Verbal** | `Tense`, `Asp`, `Refl`, `Brev` (short/long adj), `Passive`, `Mode` (conditional) |
| **Agreement** | `AgrNum`, `AgrCase`, `AgrGender`, `AgrPers` |
| **Syntax** | `Gov` (government), `WO` (word order), `Syntax`, `Gerund`, `Impers`, `Com` (comparative) |
| **Lexis/Semantics** | `Lex`, `Ref` (pronouns), `Aux`, `Prep`, `Conj`, `Idiom`, `Constr`, `CS` (code-switching) |
| **Secondary** | `Miss`, `Extra`, `Transfer` |

For your synthetic error generator, the **RLC taxonomy** is probably your best bet since it's the most linguistically motivated and captures the *causes* of errors (agreement violations, government violations, aspectual confusion, etc.) rather than just surface-level categories.
