---
name: rcp-jobs
description: "Prepare, submit, inspect and diagnose THL2 Run:ai jobs on the EPFL RCP cluster using the lab submission helper. Use for interactive or training jobs and targeted job cleanup; not for IC/MLO jobs or running Codex on jumphost."
---

# RCP jobs

Use the maintained helper and lab docs in this checkout. A request to prepare a command authorizes preparation; a request to submit or stop a specified job authorizes that operation. Continue within the user's existing authorization without adding a separate approval ritual. Ask only for missing information that materially changes the request or its resource scope.

## Locate the lab workflow

This skill is distributed with the `cluster-instructions` repository, not as a detached folder. Resolve the **actual filesystem path** of this `SKILL.md` (following symlinks); its fourth parent is the repository root. The canonical helper is `scripts/csub.py` there. If those resources are absent, locate the checkout with the user rather than reconstructing a cluster setup from memory.

- Read [jobs](../../../docs/jobs.md) for submission, lifecycle commands and helper semantics.
- Read [storage](../../../docs/storage.md) for paths, identity or transfers; [development](../../../docs/development.md) for environments, images or scripts.
- Read [troubleshooting](../../../docs/troubleshooting.md) for a failure. Consult the relevant unchecked rows in [verification](../../../docs/verification.md) before relying on a changing cluster capability.
- Use [setup](../../../docs/setup.md) only when onboarding or authentication is actually missing.

When a displayed symlink path makes relative links ambiguous, resolve them against the real skill directory. Keep information in these canonical docs; do not create copies in an experiment repository merely to load the skill.

## Prepare and submit

1. Establish the experiment command, image/environment, persistent code/output paths, job type and requested GPU/CPU/RAM. Reuse known user choices. Use a small explicit development request when appropriate; do not infer a large sweep, retries or quota from a vague request.
2. Locate the user's config and inspect only the non-secret fields needed for the target: GASPAR username, cluster context, UID/GID/groups and paths. Do not dump the file, kubeconfig or environment. Use jumphost's `id` evidence for cluster identity, never the laptop's `id`.
3. Run the helper with the checkout's Python environment (or another Python 3.10+ environment with PyYAML), an explicit `--user` path and, where needed, `--context`. The namespace is fixed to `runai-thl2-<user>`. Resolve local paths from the actual current directory; do not assume the experiment repository is this checkout.
4. For a preview, use `--dry`; this makes no cluster calls and redacts configured W&B/HF tokens. Report target, command, image, resource request and any unresolved infrastructure assumption. Do not submit the redacted manifest or add tokens to a command line.
5. For an authorized submission, check relevant target/PVC access with explicitly targeted read-only kubectl commands when available, then invoke the same helper without `--dry`. It uses `create`, not `apply`; an existing name must be inspected, not silently replaced. The helper submits once. A timeout or ambiguous failure requires checking whether the named workload exists before another attempt.
6. After submission, inspect the workload and, when present, its pod/logs in that same context/namespace. Report the job name and **observed** state. Accepted, pending and running are distinct; do not claim an experiment completed without evidence. Keep checking in this task when the user explicitly asks to watch it to a condition.

Do not describe `--time` as a training limit. It sets idle sleep only and cannot accompany `--command`. `--train` requires a command, with retries defaulting to zero. The image must be compatible with the command/entrypoint contract. Use an existing run script with explicit directory and interpreter paths for complex training; avoid depending on shell activation or injecting a token into the command string.

## Inspect and diagnose

Prefer kubectl commands with explicit context/namespace, as printed by the helper. For Run:ai CLI commands, first establish that its selected cluster/project matches the submission target; otherwise use explicit kubectl inspection. Before sharing manifest/log output, sanitize tokens and authentication material. Workload YAML can contain secrets even though the helper's preview is redacted.

For pending/failed jobs, use status, events, container logs and exit reasons to identify scheduling, mounts, identity, image, command or memory failures. Base a changed resource request or retry on that evidence and the authorized scope. Pool strings accepted by the helper are inherited hints, not confirmed live inventory. Do not automatically resubmit, add retries, change images or launch more jobs to hide an unexplained failure.

Stop/delete only the job(s) the user intends, in the established project/namespace. Exiting an attached shell does not stop an idle workload. Do not bulk-delete jobs or touch shared lab files as cleanup. Preserve checkpoints and results unless their removal was requested.
