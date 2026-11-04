# THL2: using the EPFL RCP cluster

A lab guide to accessing persistent storage, developing in a container, and running experiments on RCP with Run:ai. The examples target THL2, not MLO or the IC cluster.

**Status:** assembled on 2026-11-04 from the lab's [original gist](https://gist.github.com/mstou/1649155a776df7da56d41ad0e8ddfabd) and the locally used `csub.py`. The helper has offline tests; this guide has not yet been tested against a live RCP account. Start with the [verification checklist](docs/verification.md) for the remaining infrastructure assumptions.

## Understand the three places you work

| Place | Purpose |
| --- | --- |
| Your laptop | Edit code, authenticate, submit jobs, inspect status and logs. |
| `jumphost.rcp.epfl.ch` | SSH access to your personal home and the lab's shared filesystems. |
| A job's container | Run Python and GPU experiments on an allocated compute node. |

A container is temporary. Mounted storage survives container deletion. The lab's `/mnt/thl2/scratch/` on jumphost appears as `/thl2` inside jobs. Your personal home is mounted as `/<username>` inside jobs. See [storage and permissions](docs/storage.md); persistence does not establish a backup guarantee.

## First time here

1. Follow [setup](docs/setup.md): access, SSH, tools, authentication and user configuration.
2. Complete its CPU-only storage smoke test.
3. Read [jobs](docs/jobs.md) for interactive development and training.
4. Set up a persistent Python environment using [development](docs/development.md).

For problems, use [troubleshooting](docs/troubleshooting.md). Commands are labeled **laptop**, **jumphost**, or **container** so you know where to run them.

## Daily use

**Laptop, from this repository with its Python virtual environment activated.** These assume setup is complete and `user.yaml` contains the correct Kubernetes context.

```bash
# Preview an interactive job without contacting the cluster.
python scripts/csub.py --name dev --gpus 1 --time 1h --dry

# Submit it when ready. An existing job with the same name causes an error.
python scripts/csub.py --name dev --gpus 1 --time 1h

# Submit a training script already present on mounted storage.
# Replace YOUR_USERNAME and adapt the script before running this example.
python scripts/csub.py --name experiment-001 --train --gpus 1 \
  --command 'bash /thl2/YOUR_USERNAME/my-project/run.sh'
```

For **Run:ai management commands**, first select the RCP cluster and your project as described in [jobs](docs/jobs.md#inspect-attach-and-stop). Then:

```bash
runai list jobs
runai describe job dev
runai exec dev -it -- zsh
runai logs experiment-001
runai delete job dev
```

Submission success means the workload was accepted; it does not mean it is running. Delete unused interactive jobs. Training scripts should checkpoint and support resuming after interruption.

## Optional Codex skill

The repository includes [`rcp-jobs`](.agents/skills/rcp-jobs/SKILL.md) for submitting and managing THL2 jobs. It uses these docs and the same helper; you can use the guide without Codex.

When working inside this repository, invoke `$rcp-jobs`, for example: “Use $rcp-jobs to prepare a one-GPU training job for my existing run.sh. Show the preview.” Automatic selection is also enabled.

To make it available while working in other experiment repositories, keep this checkout and link the skill into your personal skill directory. **Laptop, from the repository root:**

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "$PWD/.agents/skills/rcp-jobs" "$HOME/.agents/skills/rcp-jobs"
```

If that destination already exists, inspect it before replacing anything. Keep the whole checkout: the skill resolves links back to the shared docs and script. Copying only the skill folder is insufficient. See the [official skill discovery documentation](https://learn.chatgpt.com/docs/build-skills).

## Maintaining this guide

Keep lab procedures in `docs/`, submission behavior in `scripts/csub.py`, and assistant-specific workflow in the skill. Update examples when flags or paths change. Record live checks and their date in [verification](docs/verification.md). The helper's CLI is documented in [jobs](docs/jobs.md#helper-options-and-changes-from-the-old-script).

**Laptop, from the repository root:**

```bash
python -m unittest discover -s tests -v
bash -n examples/train.sh
```

Sources: [THL2 gist](https://gist.github.com/mstou/1649155a776df7da56d41ad0e8ddfabd), [upstream MLO setup](https://github.com/epfml/getting-started) (historical background), [RCP documentation](https://wiki.rcp.epfl.ch), and [RCP console](https://rcpepfl.run.ai/). Current RCP policy takes precedence over inherited defaults in this guide.
