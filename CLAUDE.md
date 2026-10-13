# SIMON — rules for agents

## English prose: ASD-STE100 (Simplified Technical English)

All English prose in this repository follows ASD-STE100 Issue 9, plain mode.
This covers `README.md`, every English file under `docs/`, the slide text in
`docs/zgloszenie/slajdy/*.html`, UI copy in `ui/`, and commit messages.
It does not cover Polish files, code, code comments, identifiers, commands,
file paths, quoted text, numbers with units, or product names. Never change a
fact, a number, or a link to satisfy a rule.

Rules for a document:

1. Classify each passage. Procedural text tells the reader what to do: imperative
   mood, 20 words per sentence, one instruction per sentence. Descriptive text
   explains: simple tenses, 25 words per sentence, one topic per paragraph, six
   sentences per paragraph at most.
2. Condition before command, with a comma: "If the build fails, read the log."
3. Simple tenses, active voice. No present perfect ("has completed" → "completed").
   No "-ing" verb after a comma. Name the actor.
4. Modals: can, will, must. Never should, would, may, might, could.
5. Complete grammar. No contractions. Keep articles and "that".
6. No semicolons and no em-dashes. Write two sentences, or name the relation
   ("because", "but", "for example").
7. One word, one meaning, for the whole document. Noun chains of three words at most.
8. Define a concept term at its first use, in under ten words.
9. State the fact, not its importance. Delete filler: simply, seamlessly, robust,
   powerful, comprehensive, leverage, crucial, "in order to", "it is worth noting".
   No "not just X, it is Y". No decorative triplets.
10. No bold lead-ins, no bold as emphasis, no emoji. A vertical list is for three or
    more parallel items.
11. Warnings: command or condition first, then the risk.
12. American spelling.

Domain terms with one fixed meaning each (do not replace them with "make sure that"):
`verify` = check a receipt signature and binding, offline. `audit` = re-run a forward
pass over `prompt + output`. `receipt` = the Ed25519-signed record of one job.
`slash` = take stake for a provable violation. `node` = a machine that runs jobs.
`verifier` = a party that audits. `settlement` = payment for a job.

Check before you deliver. Count the words in the three longest sentences. Search for
`'`, `has been`, `should`, `may`, `;`, `—`, `, making`, `**`. Then run the linter:

```bash
git clone --depth 1 https://github.com/AminBlg/SimpleEnglish.git /tmp/ste-skill 2>/dev/null; python3 -I /tmp/ste-skill/evals/ste_lint.py --type descriptive README.md
```

The linter counts regex-visible violations. It is a comparison between two versions
of the same text, not a compliance verdict. No tool guarantees ASD-STE100 compliance.
The standard is a free download at asd-ste100.org. Long-document workflow and
sources: `~/brain/plazmidy/asd-ste100.md` (not in this repository).

Chat replies are not covered by this file. The register above is for files.
