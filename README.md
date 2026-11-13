# Using the RCP cluster (THL2)

How to get GPU jobs running on EPFL's RCP cluster as a member of THL2. Adapted from the
[MLO getting-started guide](https://github.com/epfml/getting-started) and the [RCP wiki](https://wiki.rcp.epfl.ch).

1. [How the cluster works](#how-the-cluster-works)
2. [Where to put your files](#where-to-put-your-files)
3. Setup: [access](#1-get-access) · [your IDs](#2-find-your-ids-uid-lab-group) · [install tools](#3-install-the-tools-on-your-laptop) · [log in](#4-log-in) · [`csub`](#5-set-up-csub-the-submission-script) · [first job](#6-your-first-job)
4. [Daily workflow](#daily-workflow)
5. [Rules of the cluster](#rules-of-the-cluster)
6. [Using it from an AI agent](#using-it-from-an-ai-agent-claude-code--codex)
7. [Billing](#billing)
8. [Troubleshooting](#troubleshooting)

## How the cluster works

There are three places involved:

| Where | What it is | What you do there |
|---|---|---|
| **Your laptop** | — | Install `kubectl` and `runai`, submit and manage jobs |
| **`jumphost.rcp.epfl.ch`** | A shared login server with the cluster storage mounted | Look up your IDs, copy files, manage code and data. **Not for computing.** |
| **A job (container)** | A temporary machine with GPUs | Run your experiments |

A job's container is wiped when the job ends. Only two folders survive, and they are the same
files you see on jumphost:

| | On jumphost | Inside a job |
|---|---|---|
| **Your home** | `~` (= `/home/<gaspar_username>`) | `/<gaspar_username>` |
| **Lab scratch** | `/mnt/thl2/scratch/` | `/thl2` |

## Where to put your files

The two locations behave quite differently:

| | Home | Lab scratch |
|---|---|---|
| Size | **100 GiB per person**, a hard limit that can't be increased | **10 TB shared by the whole lab** (more can be requested from RCP) |
| Who can access it | Only you (`drwx------`) | Lab members can read your folder, but only you can write to it (see [below](#permissions-in-scratch)) |
| Snapshots | Yes, about 4 weeks | Yes, about 4 weeks |
| Real backup (replicated, off-site) | **No** | **No** |
| Meant for | Code, scripts, configs, environments | Data you're actively computing on |

Both live on RCP's "NAS3" scratch storage system. It is fast, but it has no replication, no
disaster recovery and no ransomware protection. RCP says it is *"not intended for long-term
archiving"*. Snapshots let you recover a file deleted by mistake within a few weeks (see
[Recovering deleted files](#recovering-deleted-files)). They are not a backup.

So put things here:

| What | Where | Why |
|---|---|---|
| **Code** | Home: `~/myproject` (`/<user>/myproject` in jobs). Push to GitHub often. | Small, and private, so it's safe from accidents in the shared folder. Git is your real backup. |
| **Python environments** | Home: `~/venvs/myproject` | Typically a few GB each, which fits comfortably. |
| **Datasets** | Scratch: `/thl2/<user>/data` | Too big for home. |
| **Checkpoints, logs, outputs** | Scratch: `/thl2/<user>/myproject/...` | They grow without limit. If your home hits 100 GiB, every job writing there crashes. |
| **Caches** (pip, Hugging Face, torch) | Scratch: `/thl2/<user>/.cache` | Set automatically by `csub`. A few models in the default `~/.cache` fill your home. |
| **Results you want to keep** | **Off the cluster**: your laptop, W&B, or the lab's long-term storage | Nothing on the cluster is backed up. |

Keep your own files in `/thl2/<gaspar_username>/`, and **never delete or `chmod` other people's
files** in scratch. Clean up old checkpoints and datasets you no longer need, because the 10 TB is
shared. To see how full scratch is, run `df -h /mnt/thl2/scratch` on jumphost.

### Permissions in scratch

Scratch uses normal Unix permissions. Files belong to whoever created them, so jobs must run with
your real UID; `csub` takes care of this. Verified on jumphost on 2026-11-13:

- `/mnt/thl2/scratch` is `drwxrws---`, group `thl2-scratch` (84730). Only lab members can enter
  it, and any member can create a folder at the top level.
- Thanks to the `s` (setgid) bit, everything created inside automatically gets the
  `thl2-scratch` group.
- With the default `umask 022`, your folder is `drwxr-sr-x`: other lab members can **read**
  your files, but can't change or delete them.

To change that for a folder:

```bash
chmod -R g+w /thl2/<user>/shared-project   # let lab members write too (for collaboration)
chmod 700 /thl2/<user>/private-stuff       # hide it from lab members
```

## 1. Get access

Ask Ola to add you to the lab's cluster groups. To check that it's done, go to
[groups.epfl.ch](https://groups.epfl.ch), open **Groups I'm member of**, and search for `thl2`.
You should see all three of:

- `rcp-runai-thl2`
- `runai-thl2`
- `thl2-scratch`

You need to be on the EPFL network or the EPFL VPN for everything below.

## 2. Find your IDs (UID, lab group)

Jobs run as *you*, so that they can read and write your files. For that, the cluster needs your
numeric user ID (UID). You can find it by SSHing into the jumphost with your GASPAR credentials:

```bash
ssh <gaspar_username>@jumphost.rcp.epfl.ch
id
```

The output looks like this:

```
uid=255854(stouras) gid=11167(THL2-StaffU) groups=11167(THL2-StaffU),...,84730(thl2-scratch_AppGrpU),...
    ^^^^^^ ^^^^^^^      ^^^^^^^^^^^^^^^^^^                                ^^^^^
    your UID  username    your primary group (gid)                      scratch group
```

Write down:

- **`uid`**: your personal user ID. Everyone has a different one.
- **`gid`**: your primary group, the number after `gid=`. For lab staff and PhD students it's
  `11167` (`THL2-StaffU`). Students and visitors may have a different one; use whatever `id` shows.
- **Supplemental group** `84730` (`thl2-scratch_AppGrpU`): this is the group that gives access to
  `/thl2`. It's the same for everyone.

If `84730` is missing from `groups=`, you don't have access to the lab scratch yet. Ask Ola.

While you're on jumphost, create your folder in the shared scratch:

```bash
mkdir -p /mnt/thl2/scratch/$USER
```

## 3. Install the tools (on your laptop)

You need `kubectl` (talks to the cluster) and `runai` (the cluster's job manager), plus Python 3.

**kubectl**

```bash
# macOS, Apple Silicon. For Intel Macs use darwin/amd64; for Linux use linux/amd64.
curl -LO "https://dl.k8s.io/release/v1.29.6/bin/darwin/arm64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/kubectl
```

**runai** (the version provided by RCP, *not* a generic Run:ai CLI)

```bash
# macOS. For Linux replace `darwin` with `linux`.
wget --content-disposition https://rcp-caas-prod.rcp.epfl.ch/cli/darwin
chmod +x runai
sudo mv runai /usr/local/bin/runai
```

If that link stops working, download the CLI from the help menu (**?** → *Researcher Command
Line Interface*) of the [RCP web console](https://rcpepfl.run.ai/).

**kubeconfig** (tells `kubectl` where the cluster is)

The kubeconfig is included in this repository as [`kubeconfig.yaml`](kubeconfig.yaml). It has no
secrets, only the cluster's address and public certificate. Clone the repo (if you haven't
already) and copy it into place:

```bash
git clone <this repo's URL> ~/cluster-instructions
mkdir -p ~/.kube
# If you already have a ~/.kube/config for another cluster, back it up first!
cp ~/cluster-instructions/kubeconfig.yaml ~/.kube/config
```

Copy it; don't symlink it. `runai login` writes your personal tokens into `~/.kube/config`, and
those must never end up in the repository.

## 4. Log in

```bash
runai login                               # opens a browser, log in with your EPFL account
runai list projects                       # you should see thl2-<gaspar_username>
runai config project thl2-<gaspar_username>
kubectl get pvc                           # you should see `home` and `thl2-scratch`
```

The login expires from time to time. When commands start failing with authentication errors,
run `runai login` again.

## 5. Set up `csub` (the submission script)

You *can* submit jobs with plain `runai submit ...` commands, but getting the user IDs, mounts and
environment right each time is tedious. `csub` does it for you.

```bash
cd ~/cluster-instructions          # cloned in step 3

cp user.example.yaml user.yaml
# Now edit user.yaml: fill in your GASPAR username and UID from step 2.

# Put `csub` on your PATH:
mkdir -p ~/.local/bin
ln -s "$PWD/csub.py" ~/.local/bin/csub
# If `csub` isn't found afterwards, add this to your ~/.zshrc (or ~/.bashrc):
#   export PATH="$HOME/.local/bin:$PATH"

csub --help
```

`csub` has no dependencies beyond Python 3. It always reads the `user.yaml` that sits next to
`csub.py`, so you can run it from any folder. Optional W&B / Hugging Face tokens can go in
`user.yaml`, or be exported in your shell as `WANDB_API_KEY` / `HF_TOKEN`.

What `csub` sets up in every job:

- it runs as your UID, with the lab groups;
- it mounts your home at `/<user>` and lab scratch at `/thl2`;
- it sets `HOME=/<user>`, and `XDG_CACHE_HOME=/thl2/<user>/.cache`, which keeps pip, Hugging Face and torch caches off your home.

## 6. Your first job

Start an interactive job with one small GPU:

```bash
csub --name dev --gpus 1 --node-type v100
runai describe job dev       # wait until the status is Running
runai bash dev               # opens a shell inside the container
```

Inside the container:

```bash
nvidia-smi                   # you should see your GPU
ls /thl2                     # the shared scratch
ls /$NB_USER                 # your home from jumphost
```

When you're done, **delete the job**. Leaving the shell does *not* stop it:

```bash
runai delete job dev
```

## Daily workflow

### Interactive vs. training jobs

| | Interactive (the default) | Training (`--train`) |
|---|---|---|
| For | Developing and debugging: shell, VS Code, Jupyter | Running experiments |
| What runs | `sleep infinity`, waiting for you to connect | Your `--command`. The job ends when the command exits. |
| GPUs | **1 GPU per person in total**, across all your interactive jobs. Only `v100`, `a100-40g`, `default`. | Any number, any type |
| Time limit | **12 hours**, then it is killed | None |
| Can be interrupted | No | **Yes.** Preempted when the cluster is busy, then restarted automatically |
| Priority | High | Low |

Prefer `v100` or `a100-40g` for interactive work, and leave the big GPUs for training.

Training jobs must be able to **resume on their own**. When a job is preempted it is restarted
from the beginning of your command, so save checkpoints to scratch regularly, and on start-up
load the latest checkpoint if one exists. Never use `sleep` in a training job. A training job
whose GPUs sit idle for more than 2 hours is suspended automatically.

### Choosing resources

| Flag | Meaning | Default |
|---|---|---|
| `--gpus N` | number of GPUs (`0` = CPU only) | 1 |
| `--node-type T` | GPU type: `v100` (32GB), `a100-40g`, `default` (A100 80GB), `h100` (80GB), `h200` (141GB), `b300` (288GB) | any |
| `--cpus N` | CPU cores | 1 |
| `--memory 64G` | CPU RAM (not GPU memory) | 32G |
| `--image I` | Docker image | `ic-registry.epfl.ch/mlo/mlo:v1` |
| `--dry` | print the job definition instead of submitting | |

Run `csub --help` for all options. GPU time is billed to the lab, so request what you use and
delete jobs you no longer need.

To see which GPU types are free right now, and how long jobs are waiting, check the
[cluster overview dashboard](https://portal.rcp.epfl.ch/caas/cluster_overview) before you pick a
`--node-type`.

### A persistent Python environment

Every job starts from a fresh container, so create your virtual environment on persistent
storage once. Run this *inside a job* (not on your laptop or jumphost), so it matches the
container's Python:

```bash
python3 -m venv /$NB_USER/venvs/myproject
source /$NB_USER/venvs/myproject/bin/activate
pip install -r requirements.txt
```

In later jobs, `source` the same path and everything is already installed.

### Getting your code onto the cluster

Either `git clone` your repository into your home (from jumphost or from inside a job), or copy it
from your laptop:

```bash
rsync -av --exclude .git ./myproject/ <gaspar_username>@jumphost.rcp.epfl.ch:~/myproject/
```

Remember that your jumphost home `~/myproject` is `/<gaspar_username>/myproject` inside jobs.

### Running a training job

Write a small script next to your code, e.g. `~/myproject/run.sh`:

```bash
#!/bin/bash
set -e
source /<gaspar_username>/venvs/myproject/bin/activate
cd /<gaspar_username>/myproject
# Outputs and checkpoints go to scratch. The script resumes from the latest checkpoint if one exists.
python train.py --output-dir /thl2/<gaspar_username>/myproject/exp-001 --resume
```

and submit it:

```bash
csub --name exp-001 --train --gpus 1 --node-type h100 --command "bash /<gaspar_username>/myproject/run.sh"
```

### Managing jobs

```bash
runai list jobs              # all your jobs and their status
runai describe job NAME      # details, including why a job is Pending or Failed
runai logs NAME              # output; add --follow to stream it
runai bash NAME              # shell into a running job
runai delete job NAME        # stop and remove a job
```

Job names must be unique, so delete a finished job before reusing its name.

Two web dashboards are useful:

- The [RCP web console](https://rcpepfl.run.ai/) shows *your* jobs, with GPU utilisation and
  memory graphs. You can also stop jobs from the browser.
- The [cluster overview](https://portal.rcp.epfl.ch/caas/cluster_overview) shows the *whole
  cluster*: how busy each GPU type is, which ones are free, and how long jobs are pending.

### VS Code

1. Install the [Kubernetes](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools)
   and [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extensions.
2. In VS Code, open the Kubernetes sidebar, then **rcp-caas-prod → Workloads → Pods**.
3. Right-click your job's pod and choose **Attach Visual Studio Code**.
4. Open your project folder (`/<gaspar_username>/myproject`) and select your venv's Python as the interpreter.

See also the [RCP wiki page](https://wiki.rcp.epfl.ch/en/home/CaaS/FAQ/how-to-vscode).

To edit files without a running job, you can also use the **Remote - SSH** extension to connect
to `jumphost.rcp.epfl.ch`.

### Recovering deleted files

Both home and scratch keep snapshots: hourly for the last few days, then less often, going back
about 4 weeks. They live in a hidden `.snapshot` folder that doesn't show up even with `ls -a`,
but you can `cd` into it on jumphost:

```bash
ls ~/.snapshot/                                    # one folder per snapshot, named by date
cp ~/.snapshot/<snapshot>/myproject/train.py ~/myproject/train.py

ls /mnt/thl2/scratch/.snapshot/                    # same for lab scratch
```

## Rules of the cluster

These are RCP rules. Breaking them can get your processes killed or your access restricted.

- **Jumphost is not for computing.** Use it only to move files, manage code and submit jobs.
  No training, no heavy data processing, no servers or daemons, and **no AI agents** (Claude Code, Codex, ...) running on jumphost.
  Run those on your laptop or inside a job.
- **Jumphost can reboot without warning.** `tmux` and `screen` survive SSH disconnects but not reboots.
- **Delete interactive jobs you're not using.** They hold a GPU for the whole lab.
- **Don't keep idle GPUs in training jobs.** No `sleep`. They are suspended after 2h idle anyway.
- **Be careful in `/thl2`.** It is shared by the whole lab. Only touch files in your own folder.

## Using it from an AI agent (Claude Code / Codex)

[`skills/rcp-jobs/SKILL.md`](skills/rcp-jobs/SKILL.md) is a skill that teaches a coding agent
to submit, monitor, debug and clean up your jobs using `csub` and `runai`. First finish
steps 1–5 above, so that `csub` and `runai` work in your terminal. Then, **on your laptop**, link
the skill into your agent's skills folder:

```bash
cd ~/cluster-instructions

# Claude Code
mkdir -p ~/.claude/skills && ln -s "$PWD/skills/rcp-jobs" ~/.claude/skills/rcp-jobs

# Codex
mkdir -p ~/.agents/skills && ln -s "$PWD/skills/rcp-jobs" ~/.agents/skills/rcp-jobs
```

Because these are symlinks, a `git pull` here updates the skill too. Then, from any project,
you can ask things like *"submit train.py as a training job on one H100 and tell me when it
starts running"*, or *"why is my job exp-001 failing?"*

Remember: run the agent on your laptop, never on jumphost (see the [rules](#rules-of-the-cluster)).

## Billing

The lab pays per hour for each resource a job requests: GPU hours + CPU core hours + RAM GB hours.
You pay for the resources you **request** (`--gpus`, `--cpus`, `--memory`) for as long as the job
runs, not for what it actually uses. For example, if you request 4 GPUs and the job runs for 1 hour
but only uses 1 GPU, you pay for 4 GPU hours.

Prices in CHF per hour (from the [RCP pricing page](https://wiki.rcp.epfl.ch/en/home/CaaS/Pricing), October 2026):

| Node type | GPU | CPU (per core) | RAM (per GB) |
|---|---|---|---|
| `b300` | 1.4683 | 0 | 0 |
| `h200` | 0.53249 | 0.00267 | 0.00028 |
| `h100` | 0.52620 | 0.00264 | 0.00028 |
| `default` (A100 80GB) | 0.28600 | 0.00237 | 0.00052 |
| `a100-40g` | 0.25648 | 0.00339 | 0.00032 |
| `v100` | 0.13118 | 0.00298 | 0.00048 |

To see how much you have spent, check the [consumption page](https://portal.rcp.epfl.ch/caas/consumption).

## Troubleshooting

| Problem | What to do |
|---|---|
| `Unauthorized` / login errors | `runai login` again. Check that you're on the EPFL network/VPN. |
| `runai list projects` is empty | Your group membership isn't complete. Check step 1, then ask Ola. |
| `AlreadyExists` when submitting | A job with that name exists. Pick another name, or `runai delete job NAME`. |
| Job stuck in `Pending` | `runai describe job NAME`, and look at the *Events* at the bottom. Usually there are no free GPUs of that type. Check the [cluster overview](https://portal.rcp.epfl.ch/caas/cluster_overview) to see which types are free, then wait or try another `--node-type`. For interactive jobs, check that you aren't already using your 1 interactive GPU in another job. |
| Training job `Suspended` | Its GPUs were idle for more than 2h. Don't use `sleep` in training jobs; use an interactive job instead. |
| Training job restarted by itself | It was preempted. Make it resume from its last checkpoint. |
| `Disk quota exceeded` | Your 100 GiB home is full. Check with `du -sh ~/* ~/.[!.]* \| sort -h` on jumphost, and move data, checkpoints and caches to `/thl2/<user>/`. |
| `Permission denied` on `/thl2` or your home | Wrong `uid` in `user.yaml`. Compare it with `id` on jumphost. |
| Job finishes immediately / `Failed` | `runai logs NAME`. Usually a wrong path in `--command`, or a venv that doesn't exist. |
| `ErrImagePull` / `ImagePullBackOff` | The `--image` name is wrong or doesn't exist. |
| Interactive job disappeared | Interactive jobs are killed after 12h. |
| CUDA out of memory | That's GPU memory, which `--memory` doesn't change. Use a smaller batch, or a bigger GPU (`--node-type default`/`h100`/`h200`/`b300`). |
| Deleted a file by mistake | Look in `.snapshot`, see [Recovering deleted files](#recovering-deleted-files). |

Other help: the [RCP wiki](https://wiki.rcp.epfl.ch) (in particular its
[FAQ](https://wiki.rcp.epfl.ch/en/home/CaaS/FAQ)), the [RCP console](https://rcpepfl.run.ai/),
the [cluster overview](https://portal.rcp.epfl.ch/caas/cluster_overview), and RCP support at
supportrcp@epfl.ch.
