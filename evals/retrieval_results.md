# Local Retrieval Evaluation

## Test environment

- OS: Windows 11 Home Single Language
- CPU: AMD Ryzen 5 5600H
- RAM: 15.4 GB
- GPU: AMD Radeon Graphics
- Inference: CPU only
- Provider: Ollama
- Model: qwen2.5:1.5b
- Context limit: 4096 tokens
- Embedding model: BAAI/bge-small-en-v1.5
- Reranker: Xenova/ms-marco-MiniLM-L-6-v2

## Methodology

Two product document versions containing different prices were combined with 400 unrelated sections to exceed the local model's context window.

The same questions were evaluated with retrieval disabled and enabled, using the same answering model.

Retrieval was explicitly enabled for the comparison.

## Results

| Metric | Retrieval OFF | Retrieval ON |
|---|---:|---:|
| Price checks | 0/2 | 2/2 |
| Source checks | 0/2 | 2/2 |
| Missing-information checks | 0/2 | 0/2 |
| Total | 0/6 | 4/6 |
| Average response latency | 6.03s | 15.83s |

Both correct prices ($120 and $145) were recovered with retrieval enabled.

## Performance

- Cached index initialization: 4.12s and 3.03s
- Average isolated reranking latency: 1.279s
- Candidates per reranking call: 18
- Reranking measurements: 4

## Limitations

- The model failed both missing-information checks, including hallucinating a five-year warranty.
- Retrieval increases response latency on CPU-only hardware.
- Initial testing with qwen3:4b recovered both correct prices but failed the formal evaluation because reasoning consumed the response token budget.
- macOS performance and end-to-end GUI behavior have not been verified locally.
- Token budgeting uses the embedding tokenizer as an approximation of the answering model's tokenizer.
- These results represent a single evaluation run per model and configuration.

## Regression testing

After merging upstream main, all 715 tests passed in 38.28 seconds.

The automated test suite does not require embedding model downloads.

## Reproduction

Run:

`uv run --locked python -m evals.retrieval_faithfulness`

The manual evaluation requires Ollama and locally available models. Initial embedding and reranking model setup may require internet access.