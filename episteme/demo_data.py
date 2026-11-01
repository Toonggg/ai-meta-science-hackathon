"""A staged research session with a deliberate pivot at step 4.

Based on the scenario in gemini_research.md (TF-IDF -> PubMedBERT), and shaped
so the brief's success criterion ("why did they change approach at step 4?")
can be answered from the log alone.
"""

from datetime import datetime, timedelta


def _ts(hhmmss):
    """Demo events happen 'yesterday', so new entries always sort after them."""
    day = (datetime.now() - timedelta(days=1)).astimezone()
    h, m, sec = map(int, hhmmss.split(":"))
    return day.replace(hour=h, minute=m, second=sec, microsecond=0).isoformat()


DATA = {"name": "mimic-iv-note / discharge", "version": "2.2", "hash": "sha256:9f2c41d7...e41a"}


def demo_events():
    return [
        {
            "id": "E1", "ts": _ts("09:12:04"), "type": "plan", "source": "chat",
            "provenance": "stated",
            "title": "Hypothesis: bag-of-words features from discharge notes predict 30-day readmission",
            "detail": "Plan agreed in a Claude chat: start with a cheap, interpretable baseline (TF-IDF 1-3-grams + logistic regression) "
                      "before trying anything heavier. Prior work reports 0.70-0.78 AUROC for bag-of-words baselines.",
            "expectation": "AUROC >= 0.75",
        },
        {
            "id": "E2", "ts": _ts("10:47:31"), "type": "run", "source": "colab",
            "provenance": "stated", "status": "failed",
            "title": "TF-IDF (1-3-grams) + logistic regression, 5-fold CV",
            "code": "vec = TfidfVectorizer(ngram_range=(1, 3), max_features=None)\n"
                    "X = vec.fit_transform(notes.text)          # OOM on full cohort\n"
                    "vec = TfidfVectorizer(ngram_range=(1, 3), max_features=50_000)\n"
                    "scores = cross_val_score(LogisticRegression(C=1.0), X, y, cv=5, scoring='roc_auc')",
            "params": {"ngram_range": "(1, 3)", "max_features": "None -> 50000", "C": 1.0, "cv": 5},
            "data": DATA,
            "result": "AUROC 0.54 (5-fold CV). First attempt crashed the kernel (out of memory) at max_features=None.",
        },
        {
            "id": "E3", "ts": _ts("10:47:33"), "type": "surprise", "source": "episteme",
            "provenance": "inferred",
            "title": "Expectation contradicted: expected AUROC >= 0.75, observed 0.54",
            "detail": "Auto-detected by the hypothesis ledger: the result of E2 falls short of the expectation stated in E1. "
                      "0.54 is barely above chance.",
            "links": ["E1", "E2"],
        },
        {
            "id": "E4", "ts": _ts("11:20:09"), "type": "pivot", "source": "chat",
            "provenance": "stated",
            "title": "Switch from sparse n-grams to frozen PubMedBERT embeddings",
            "detail": "Answered in the pivot micro-prompt: error analysis (in chat) showed the top TF-IDF features were note "
                      "boilerplate ('patient was discharged home') and that negations ('no evidence of CHF') collapse into the "
                      "same n-grams as positives. N-grams lose the clinical semantics we need. Contextual embeddings handle "
                      "negation and abbreviations; we keep the encoder frozen so it fits the Colab T4 memory budget that the "
                      "OOM in E2 exposed.",
            "links": ["E2", "E3"],
        },
        {
            "id": "E5", "ts": _ts("14:03:52"), "type": "run", "source": "colab",
            "provenance": "stated", "status": "ok",
            "title": "Frozen PubMedBERT [CLS] embeddings + logistic regression, 5-fold CV",
            "code": "enc = AutoModel.from_pretrained('microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract')\n"
                    "emb = embed(notes.text, enc, batch_size=32, max_len=512)   # frozen\n"
                    "scores = cross_val_score(LogisticRegression(C=0.5), emb, y, cv=5, scoring='roc_auc')",
            "params": {"encoder": "PubMedBERT (frozen)", "batch_size": 32, "max_len": 512, "C": 0.5, "seed": 42},
            "data": DATA,
            "result": "AUROC 0.81 (5-fold CV, single seed = 42)",
            "links": ["E4"],
        },
        {
            "id": "E6", "ts": _ts("14:31:10"), "type": "artifact", "source": "github",
            "provenance": "stated",
            "title": "Commit a3f9c21: replace TF-IDF pipeline with PubMedBERT embeddings",
            "detail": "TF-IDF code moved to archive/tfidf_baseline.py (kept as a documented dead end, not deleted).",
            "links": ["E4", "E5"],
        },
        {
            "id": "E7", "ts": _ts("16:55:00"), "type": "note", "source": "manual",
            "provenance": "stated",
            "title": "Caveat: only one seed and one hospital so far",
            "detail": "Before claiming robustness we need >= 3 seeds with confidence intervals. "
                      "No external validation: all notes come from a single hospital system (MIMIC-IV / BIDMC).",
            "links": ["E5"],
        },
    ]


DEMO_PAPER = """Abstract
We demonstrate that contextual embeddings substantially outperform n-gram baselines for predicting 30-day hospital readmission from discharge notes (AUROC 0.81 vs 0.54, Table 2). This proves that semantic representations are necessary for readmission prediction. Our approach generalizes across hospitals and patient populations. These results suggest that clinical language models could support discharge planning.

1 Introduction
Hospital readmissions are costly. Prior work reports AUROC between 0.70 and 0.78 for bag-of-words baselines.

3 Results
Table 2 reports 5-fold cross-validated AUROC on MIMIC-IV discharge notes. The TF-IDF baseline reaches an AUROC of 0.54. Frozen PubMedBERT embeddings reach an AUROC of 0.81 (single run, seed 42). Figure 3 shows that the largest gains come from notes that contain negated findings. The embedding model is also faster to train than the baseline.

4 Discussion
We find that negation handling explains most of the improvement (Figure 3). The model is robust to documentation style.

Table 2: AUROC by representation, 5-fold CV, MIMIC-IV.
Figure 3: AUROC gain by note category (negated vs non-negated findings).
"""
