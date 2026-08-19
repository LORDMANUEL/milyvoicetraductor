# BetaAlpha CPU-first beta

BetaAlpha is the performance-first experimental line kept separate from `pruebas` (Engine Hub Beta) and `main` (stable v2.0.1).

Current candidate includes:

- sherpa-onnx Zipformer EN 20M INT8;
- sherpa-onnx Zipformer ZH 14M INT8;
- sherpa-onnx bilingual streaming Paraformer INT8;
- resident streaming ASR with incremental audio and final tail flush;
- adaptive partial cadence from measured RTF P95;
- incremental translation for stable partial prefixes while finals are retranslated in full;
- CPU CTranslate2 compute-type tuning with persistent per-device cache;
- Lite-only private runtime without Torch/Transformers/Google cloud dependencies;
- the same 2 GiB/384 MiB resource contract and Windows/NSIS release gates as the Engine Hub Beta.

No promotion to stable or Engine Hub Beta occurs unless the real Windows benchmarks and quality gates pass.
