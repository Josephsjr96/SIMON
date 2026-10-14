# simon-lidar: which model does a node serve?

A SIMON receipt shows which node signed an output. It does not show which model produced the output. This
tool gives a statistical answer to the second question. It is a pilot, not a proof.

Two layers, both through any OpenAI-compatible endpoint (also the SIMON gateway, where every step is a SIMON
job with a verified receipt):

| Layer | File | What it measures | Based on |
|---|---|---|---|
| Agent behaviour | `lidar.py` | 3 small coding tasks with A/B variants (verify, recover, resolve). An agent with tools runs each task; about 190 features describe what it does. | LIDAR, Tsinghua University, arXiv:2609.28559 |
| Single-token distributions | `onetoken.py` | 10 one-word questions (random number, colour, city, coin...) in English and Polish, temperature 1.0, Jensen-Shannon divergence | Bruckner, "One Token Is Enough", arXiv:2607.10252 |

The authors of LIDAR did not release code, tasks or fingerprints, so this repository builds its own
references. The verdict is open-set: `consistent`, `inconsistent` or `inconclusive`. A model that is not in
the reference set does not get a confident answer.

```bash
python3 lidar.py run    --base http://127.0.0.1:18600/v1 --model M --label M --n 6 --out refs.jsonl
python3 lidar.py eval   --refs refs.jsonl
python3 lidar.py verify --base http://127.0.0.1:18600/v1 --model M --declared M --refs refs.jsonl
python3 onetoken.py run  --base http://127.0.0.1:18600/v1 --model M --label M --n 30 --out ot.jsonl
python3 onetoken.py eval --refs ot.jsonl
```

Limits: the tasks are public and fixed, so a dishonest node can learn them; production needs a secret,
rotating task pool. The single-token layer detects a different configuration (weights, quantization,
engine, sampler), not only different weights. Fingerprints with endpoint errors are dropped and counted.
