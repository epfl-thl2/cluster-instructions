# Working on this repository

This repository is the standalone THL2 guide for EPFL RCP. Human procedures live in `docs/`; `scripts/csub.py` is the maintained submission helper; `.agents/skills/rcp-jobs/SKILL.md` teaches assistants how to use them. The original gist and MLO material are historical sources, not automatically current THL2 policy.

- Scope edits to this repository. Keep any sibling `getting-started` checkout unchanged.
- Preserve the difference between laptop, jumphost and job-container commands, and between jumphost paths and container mount paths.
- Record infrastructure assumptions and dated live results in `docs/verification.md`. Offline tests do not establish API compatibility, quotas, backups, permissions or GPU availability.
- Do not copy real user configurations, kubeconfigs or tokens into tracked files or output. The example configuration contains no personal UID or credentials.
- For helper changes, run `python -m unittest discover -s tests -v` in an environment with `requirements.txt` installed. Run `bash -n examples/train.sh` after editing it. Validate relative documentation links and the skill's references when moving files.
- Preserve explicit context/namespace targeting, local-only redacted previews, one-attempt submission, and failure on existing names. Keep docs and examples consistent with changed CLI behavior.
- Documentation work and offline testing do not authorize live cluster jobs. Use fake kubectl in tests. If the user requests an actual job, follow the rcp-jobs skill and the authorized scope; do not add a redundant confirmation gate.
- Keep the skill concise and refer to canonical docs instead of duplicating lab facts. Resolve symlinked skill locations back to this checkout.

Jumphost-based submission/Codex execution and distributed training are deferred. Do not expand into them during ordinary guide maintenance.
