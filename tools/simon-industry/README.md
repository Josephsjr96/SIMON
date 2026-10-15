# simon-industry — maintenance tickets with an audit trail (Intelligent Industry track)

1. `rules.py` — deterministic failure-mode rules (the AI4I 2020 dataset's published physics: heat dissipation,
   power, overstrain, tool-wear zone). They decide the risk; the language model never does.
2. `tickets.py` — for each flagged record, Gemma 4 (through the SIMON gateway) drafts a technician ticket as
   JSON; checks: valid JSON, failure modes equal to the rules, no number the input lacks, no command to stop or
   bypass equipment, marked for human review. The receipt and the exact signed output are stored.
3. `export_ui.py` — turns runs into `ui/src/lib/industry-run.json` for the `/industry` page, which re-checks every
   receipt in the browser.

```bash
python3 rules.py data/ai4i2020.csv                       # rule recall per labelled failure mode
python3 tickets.py --csv data/ai4i2020.csv --model gemma-4-26b-a4b-it-qat-q4_0 --out run.jsonl
```

The sample is predeclared (`sample()`: fixed seed, stratified by rule outcome, includes labelled failures the
rules miss). Runs: `docs/industry/`.

Data: `data/ai4i2020.csv` — AI4I 2020 Predictive Maintenance Dataset, S. Matzka, UCI Machine Learning
Repository, https://doi.org/10.24432/C5HS5C, licensed CC BY 4.0. Synthetic, modelled on a real milling machine;
its labels follow the same physics as the rules, so rule recall here describes the dataset, not a real plant.
