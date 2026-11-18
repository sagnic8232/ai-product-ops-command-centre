| Task | Method | GT positives | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| RAG-vs-text inconsistency | Keyword baseline | 8 | 3 | 5 | 5 | 38% | 38% | 38% |
| RAG-vs-text inconsistency | LLM | 8 | 6 | 0 | 2 | 100% | 75% | 86% |
| Has unresolved risk | Keyword baseline | 16 | 13 | 5 | 3 | 72% | 81% | 76% |
| Has unresolved risk | LLM | 16 | 16 | 0 | 0 | 100% | 100% | 100% |
| Dependency functions (micro) | LLM | 24 | 23 | 10 | 1 | 70% | 96% | 81% |

n = 36 labelled updates. Small sample: one error moves precision/recall by roughly 10-20 points.