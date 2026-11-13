---
name: rcp-jobs
description: Submit, monitor, debug and delete GPU jobs on the EPFL RCP cluster (THL2 lab) with `csub` and `runai`. Use when the user wants to run something on the cluster, check on a job, read its logs, find out why it is pending or failed, or clean jobs up.
---

# RCP cluster jobs (THL2)

The user has already set things up following the cluster-instructions README: `csub`, `runai`
and `kubectl` are on PATH, and they are logged in. Commands run on the user's laptop. Jobs run in
containers on the cluster.

## Facts you need

- **Storage.** Only two paths persist inside a job. Neither is backed up, but both keep about
  4 weeks of snapshots.
  - `/<user>`: the user's private home (`~` on `jumphost.rcp.epfl.ch`). It has a **hard
    100 GiB limit**. Use it for code (`/<user>/<project>`) and venvs (`/<user>/venvs/<project>`).
  - `/thl2`: the lab's shared scratch (`/mnt/thl2/scratch/` on jumphost). It is 10 TB for the
    whole lab. Use `/thl2/<user>/` for datasets, checkpoints, logs and outputs. It uses normal
    Unix permissions: lab members can usually read each other's folders but not write to them.
    So `Permission denied` when writing into another member's folder is expected; don't
    "fix" it with chmod.
  - Never write big outputs to the home. When it fills up, every job writing there fails.
    `csub` already points caches to scratch (`XDG_CACHE_HOME=/thl2/<user>/.cache`).
  - Everything else in the container is wiped when the job ends.
- **Code location.** The user's laptop files are *not* on the cluster. Code must already be on
  cluster storage (via git, or `rsync` to `<user>@jumphost.rcp.epfl.ch:~/<project>/`) before a
  job can run it.
- **Username.** To find `<user>`, run
  `grep '^user:' "$(dirname "$(readlink -f "$(command -v csub)")")/user.yaml"`.
  The user's jobs live in Kubernetes namespace `runai-thl2-<user>`.
- **Job types.**
  - Interactive (the default) runs `sleep infinity`, for development. At most 1 GPU per user in
    total across all interactive jobs. Only on `v100`, `a100-40g` or `default`. Killed after 12h.
    Never preempted.
  - Training (`--train`) runs `--command` and finishes when that command exits. Any GPUs.
    It can be preempted and is then restarted from scratch automatically, so the command must
    resume from its latest checkpoint on its own. It is suspended if its GPUs sit idle for more
    than 2h, so never put `sleep` in a training job.
- **Billing.** GPU time is billed to the lab.
- **Jumphost.** Use it only for file operations (`ssh`, `rsync`, `ls`, `du`). Never run compute,
  servers, or AI agents on it; RCP forbids this.

## Submitting

```bash
csub --name NAME [--train --command "CMD"] [--gpus N] [--node-type T] [--cpus N] [--memory 64G] [--dry]
```

- `--node-type`: `v100` (32GB), `a100-40g`, `default` (A100 80GB), `h100` (80GB), `h200`
  (141GB), `b300` (288GB). Leave it out for any GPU type. For interactive jobs, prefer `v100` or
  `a100-40g`.
- `--memory` is CPU RAM, not GPU memory. `--gpus 0` gives a CPU-only job.
- Job names: lowercase letters, digits and `-`, unique among the user's jobs. If a name exists,
  `csub` fails. Don't delete the old job to free the name unless the user said so; pick a new name.
- For training, prefer `--command "bash /<user>/<project>/run.sh"`, with a script that activates
  the venv by absolute path, `cd`s into the project, and runs the experiment with outputs under
  `/thl2/<user>/`. Avoid long inline commands with nested quotes. Check that the script exists
  first, e.g. `ssh <user>@jumphost.rcp.epfl.ch ls ~/<project>/`.
- If you're unsure what will be submitted, run with `--dry` first. It prints the manifest
  (with tokens redacted) and submits nothing.

**Ask before you submit** if the request is vague about resources, or would use a lot of them:
more than 1–2 GPUs, many jobs (sweeps), or long runs. GPUs are shared with the whole lab.

## Monitoring

```bash
runai list jobs                 # all of the user's jobs and their status
runai describe job NAME         # status, events, and the reason a job is Pending/Failed
runai logs NAME                 # output; `--tail 100` for the end, `--follow` streams (don't follow forever)
```

Typical states: `Pending` (waiting for a GPU), `ContainerCreating` (pulling the image), then
`Running`, and finally `Succeeded`, `Failed` or `Completed`. Only report what you observed. A
successful submission is not the same as running, and running is not the same as succeeded.

To wait for a state change, poll `runai describe job NAME` every 30–60s, not in a tight loop.
Pending can last minutes to hours when GPUs are busy.

To run a command in a running job without an interactive TTY, use `runai exec NAME -- nvidia-smi`.
If that syntax is rejected, check `runai exec --help`, or use
`kubectl -n runai-thl2-<user> exec POD -- CMD`, where `POD` comes from `kubectl -n runai-thl2-<user> get pods`.
`runai bash NAME` is interactive. Tell the user to run it themselves.

## Debugging

| Symptom | Look at | Usual cause |
|---|---|---|
| Stuck `Pending` | `runai describe job NAME` (events at the bottom) | No free GPUs of that type or quota exceeded. For interactive jobs, the user may already be using their 1 interactive GPU. Point the user to https://portal.rcp.epfl.ch/caas/cluster_overview (it needs their login), which shows free GPUs per type and pending times. Suggest waiting or another `--node-type`. Don't resubmit duplicates. |
| `Suspended` (training) | `runai describe job NAME` | GPUs were idle for more than 2h, e.g. a `sleep` or a stuck data loader |
| Restarted by itself (training) | `runai describe job NAME`, logs | Preempted. Fine if the script resumes from a checkpoint. |
| `Disk quota exceeded` | `ssh <user>@jumphost.rcp.epfl.ch 'du -sh ~/* ~/.[!.]*'` | The 100 GiB home is full. Move outputs to `/thl2/<user>/`. Ask before deleting anything. |
| `ErrImagePull` / `ImagePullBackOff` | describe output | Wrong `--image` |
| `Failed` right after starting | `runai logs NAME` | Wrong path in `--command`, missing venv, or a Python error |
| `Permission denied` on `/thl2` or `/<user>` | logs, then `id` inside the job | Wrong `uid` in `user.yaml` (compare with `id` on jumphost) |
| `CUDA out of memory` | logs | GPU memory. `--memory` doesn't help. Use a smaller batch or a bigger GPU. |
| Killed / `OOMKilled` | `kubectl -n runai-thl2-<user> describe pod POD` | CPU RAM. Increase `--memory`. |
| `Unauthorized` / auth errors | — | The user must run `runai login` (opens a browser), and be on the EPFL network/VPN |

Find the cause before changing anything. Don't blindly resubmit with more resources.

## Cleaning up

```bash
runai delete job NAME
```

- Delete only jobs the user asked you to delete, or jobs you started in this task and that are no
  longer needed, e.g. an interactive job you used for a quick check.
- Never bulk-delete jobs.
- Never delete or modify files under `/thl2` outside `/thl2/<user>/`. That is the lab's shared storage.
- Don't delete the user's data, checkpoints or results unless they asked. If they deleted
  something by mistake, snapshots are in the hidden `~/.snapshot/` and `/mnt/thl2/scratch/.snapshot/`
  folders on jumphost.

## Don'ts

- Don't print or paste `user.yaml` contents, `~/.kube/config`, or full manifests from the
  cluster. They can contain W&B and Hugging Face tokens.
- Don't put tokens in `--command`.
- Don't use `runai submit` directly. `csub` sets the user IDs and storage mounts correctly.
