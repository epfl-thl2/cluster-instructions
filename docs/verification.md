# What still needs verification

**Prepared: 2026-11-04. Live cluster verification: not performed.** The RCP wiki was inaccessible from the authoring environment. No cluster credentials were used and no jobs were submitted while building this repository.

This guide separates three kinds of evidence:

- **Reported lab setup:** the [THL2 gist](https://gist.github.com/mstou/1649155a776df7da56d41ad0e8ddfabd), whose API metadata reported an update on 2026-02-15; and the locally used `getting-started/csub.py` supplied by the maintainer on 2026-11-04.
- **Locally checked behavior:** the new helper's offline tests, shell syntax, documentation links and skill structure. These cannot validate RCP API compatibility or actual filesystem permissions.
- **Live infrastructure/policy:** the unchecked items below. Record date, tester and a sanitized result when confirming each item. Do not mark a row verified merely because it appears in the old docs or a CLI annotation.

The new repository is independent of the supplied `getting-started` checkout, which is intentionally unchanged. Do not depend on a sibling directory to run these instructions.

## Live checklist

| Status | Item | Inherited value or question | How to verify |
| --- | --- | --- | --- |
| [ ] | Access groups and contact | `rcp-runai-thl2`, `runai-thl2`, `thl2-scratch`; original contact Ola | Lab administrator and groups.epfl.ch |
| [ ] | Network and SSH | `jumphost.rcp.epfl.ch`; EPFL network/VPN requirements | Follow setup from a new member's laptop |
| [ ] | Context, endpoint and authentication | Local context `rcp-caas`, Run:ai cluster `rcp-caas`, project `thl2-<user>`, namespace `runai-thl2-<user>` | Current console/docs, kubeconfig context/server, login and authorized resource queries |
| [ ] | Tool versions | Current supported kubectl and RCP CLI versions; Python 3.10+ is our local requirement | Current RCP help/downloads; old kubectl pin is not carried forward |
| [ ] | CLI targeting | Does this CLI use the chosen `KUBECONFIG` and align its selected cluster/project with kubectl? | Compare both views of a uniquely named smoke-test workload |
| [ ] | Workload API | `run.ai/v2alpha1`, InteractiveWorkload/TrainingWorkload schema, plural resource names | `api-resources --api-group=run.ai`, current CRD/API docs, smoke-test submissions |
| [ ] | Retained metadata | `runai-cli-version: 2.22.73` and `PreviousJob: "true"` | Check whether current RCP needs or ignores these; the annotation does not install or check a CLI |
| [ ] | Storage identity | THL2-unit GID `11167`, supplemental GID `84730`, personal UID | `id` on jumphost and in the container; administrator confirms storage rules |
| [ ] | PVCs and path mapping | `home` → `/<user>` and `thl2-scratch` → `/thl2`; scratch on jumphost `/mnt/thl2/scratch` | PVC queries and the two personal marker-file checks in storage.md |
| [ ] | Privacy, quotas, backup, retention | Personal-home ACLs and home/scratch policies are not established here | Storage administrator; record the policy and archive destination without assuming MLO policy |
| [ ] | Default image | `ic-registry.epfl.ch/mlo/mlo:v1`: registry access, Python/venv, zsh, NB_* startup, HOME behavior | CPU-only interactive test, then fresh-pod persistence and training tests |
| [ ] | Command and exit behavior | Does the image/Run:ai combination execute arguments as expected and preserve failure status? | Tiny training jobs running `/bin/true` and `/bin/false`; inspect status, logs and retries |
| [ ] | GPU pools and policy | `default`, `h100`, `h200`, `a100-40g`, `v100`; actual GPUs/memory, quotas, priorities, preemption and time limits | Current console/policy; a small authorized GPU smoke test after CPU tests |
| [ ] | Resource/security settings | largeShm default, opt-in hostIpc, runAs UID/GID, allowPrivilegeEscalation | Confirm RCP acceptance and image requirements; change inherited settings only with evidence |
| [ ] | Management and editors | `runai exec/logs/describe/delete`, VS Code attachment, notebook forwarding | Test only the user's smoke-test workload; confirm settings persist on a replacement pod |
| [ ] | Runtime cap mechanism | `--time` is only idle sleep; no training deadline is implemented | Current RCP API/policy before adding a deadline feature |
| [ ] | Preferred lab image and registry | Who maintains the image, where to publish, supported CUDA/framework versions | Lab administrator/image maintainer; document an agreed image workflow when available |

## First live validation session

1. Complete [setup](setup.md) using a fresh user configuration. Record the actual CLI versions, context, namespace and PVC names. Inspect the Kubernetes server URL locally; do not share authentication material.
2. Run the CPU-only interactive storage test. Confirm UID, GIDs, home/scratch marker paths and environment persistence on a replacement pod. Delete only those test jobs and marker files.
3. Submit two uniquely named CPU-only training tests with `--command '/bin/true'` and `--command '/bin/false'`. Confirm success/failure status respectively and no automatic retries (default backoff zero). Test a short adapted `examples/train.sh` with the chosen image.
4. Test duplicate-name failure against your own completed test workload; confirm it is not updated. If an operation times out, inspect before retrying.
5. With the intended user's authorization and quota, run a small GPU experiment and check the actual GPU and usable memory. Confirm interruption/recovery expectations and policy with the administrator.
6. Update this checklist and the affected procedures with date, tester, image, versions and results. Remove historical defaults only after their replacement is known to work.

## Local verification

Recorded on **2026-11-04**, using Python 3.13.2 and PyYAML 6.0.3: **15 offline tests passed**, the example script passed `bash -n`, and the `rcp-jobs` skill passed the skill-creator validator. Local Markdown file targets resolved. A before/after SHA-256 comparison confirmed all non-Git files in the supplied `getting-started` checkout were unchanged. Python 3.10 compatibility is declared by the supported syntax, not by a separate interpreter-matrix test.

The offline suite uses temporary user configurations, fake tokens and a fake `kubectl`; it cannot contact RCP. Run it with `python -m unittest discover -s tests -v`. It covers valid manifests, exact target selection, command quoting, redaction, resource/configuration errors, duplicate/failing submission behavior and single-attempt execution. Also check `bash -n examples/train.sh` and validate the skill using Codex's skill-creator validator when available.

## Sources and maintenance

The THL2 gist supplies the access and storage model. The locally used helper supplies the API shape, mounts, image and effective resource settings. [Upstream MLO documentation](https://github.com/epfml/getting-started) is provenance, not authority for THL2 paths, group IDs, symlinks, Conda setup or backup policy. Current [RCP docs](https://wiki.rcp.epfl.ch) and the [console](https://rcpepfl.run.ai/) should establish changing infrastructure details. The [official skill docs](https://learn.chatgpt.com/docs/build-skills) establish local skill discovery/symlink behavior.

Deferred work: running Codex or launching experiments from jumphost, distributed training, a THL2 image build/publish workflow, and an RCP-verified Kubernetes Secret/deadline integration. None is required to use the current laptop-submission workflow.
