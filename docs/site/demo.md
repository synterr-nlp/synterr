# Live demo

The review viewer with ~30 preloaded synthetic errors — the same tool we
use for human verification of generated data. Every example carries its
handler type, §-level schema tag, and applicability rating; the
annotation buttons (or keys ++1++–++4++) record a verdict per example.

<a href="../demo/viewer.html" target="_blank" rel="noopener"><strong>Open
the demo full-screen ↗</strong></a> — or try it right here:

<iframe src="../demo/viewer.html" style="width:100%;height:78vh;border:1px solid #8884;border-radius:8px;"
        title="synterr review viewer demo"></iframe>

Notes:

- The examples are unfiltered generator output over news text — judging
  a few yourself is the fastest way to understand what synterr produces.
- Annotations save to your browser's localStorage only; nothing leaves
  the page. Export/Import round-trips them as JSON.
- The sample data is also downloadable: [sample.jsonl](demo/sample.jsonl).
  The viewer itself ships in the repo as `tools/diff_viewer.html` — drop
  any of your own generated JSONL onto it.

## Quality

Every handler has gone through three independent review passes: an
internal audit against the underlying grammar reference (June, 73
findings, all fixed); a native-speaker annotator's pass using this same
viewer (2,724 items — 98.4% corruption validity, 91.6% intended-type
precision); and an external model-based adversarial audit (July, 47/51
findings confirmed, all fixed). Together they're the basis for treating
synterr's output as trustworthy training and evaluation signal, not just
plausible-looking noise.
