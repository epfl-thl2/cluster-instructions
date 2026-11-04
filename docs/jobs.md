# Submit and manage jobs

Complete [setup](setup.md) first. Examples run on your **laptop**, from this repository with `.venv` activated, unless labeled otherwise. The helper uses the Kubernetes context in `user.yaml` or its `--context` override and namespace `runai-thl2-<username>`.

## Choose a workload

- **Interactive:** an idle container you can enter for debugging or development. The helper defaults to one GPU and an idle `sleep 3600` (one hour). Use `--gpus 0` for CPU-only development. Stop the workload when finished.
- **Training (`--train`):** a command that starts your experiment and exits when it finishes. A command is required. Let the workload run the experiment as its main process; avoid backgrounding it or appending `sleep infinity`.

The old lab material describes interactive GPU/time limits and possible preemption. Current limits, priorities, quotas and billing are **not verified** here. Do not assume any workload can run uninterrupted. Save checkpoints and make resuming explicit in your experiment code.

## Interactive development

```bash
python scripts/csub.py --name dev --gpus 1 --cpus 4 --memory 16G --time 1h --dry
python scripts/csub.py --name dev --gpus 1 --cpus 4 --memory 16G --time 1h
```

`--dry` performs local validation and prints a redacted manifest; it does not authenticate, validate server-side APIs, reserve resources or submit anything. Its target summary goes to stderr and the YAML goes to stdout. Do not submit the redacted preview YAML: use the helper again without `--dry`.

The sleep is a convenience for idle sessions, not a scheduler deadline. It starts when the container starts; it does not extend when you attach a shell, and can end while you are debugging. RCP may also impose a shorter limit. Use an appropriate duration and a training workload for an actual experiment.

After the job runs, use the attachment commands below. When it ends, a completed workload object may still appear until you remove it; no running container does not imply the object was deleted.

## Training

Put your experiment command in a script on persistent storage. [examples/train.sh](../examples/train.sh) shows how to choose a directory and an absolute environment interpreter. Copy and adapt it as `/thl2/<username>/my-project/run.sh` inside the container (the corresponding jumphost path is `/mnt/thl2/scratch/<username>/my-project/run.sh`).

Replace `YOUR_USERNAME` and ensure the code, environment and script exist before submitting:

```bash
python scripts/csub.py --name experiment-001 --train \
  --gpus 1 --cpus 4 --memory 32G \
  --command 'bash /thl2/YOUR_USERNAME/my-project/run.sh' --dry

python scripts/csub.py --name experiment-001 --train \
  --gpus 1 --cpus 4 --memory 32G \
  --command 'bash /thl2/YOUR_USERNAME/my-project/run.sh'
```

The command is stored in Run:ai's inherited `spec.arguments.value` field. YAML quoting is handled by the helper. It does not rewrite your command, activate a Python environment or change directories. Command/entrypoint behavior still needs a live smoke test with the selected image. A script with explicit paths avoids depending on shell startup files or on how a particular image interprets shell operators.

`--time` is rejected when `--command` is present: the old helper only used it to construct a default sleep, so it never limited training runtime. This helper deliberately does not invent an unverified scheduler deadline field. Verify the current RCP deadline mechanism before relying on a runtime cap.

Training retry count defaults to zero. `--backofflimit N` requests the inherited Run:ai retry setting; use it only if repeated execution and checkpoint recovery are appropriate for the experiment. A retry can repeat downloads, logging or output writes. The helper itself submits once and does not retry a failed or interrupted request.

## Resources and GPU pools

`--gpus` is an integer count; `0` means CPU-only. `--cpus` requests an integer CPU count. `--memory` is **host RAM**, not GPU memory; `32G` and `32Gi` are different Kubernetes quantities. Request resources appropriate for your experiment and check its actual utilization.

The helper retains these pool names from the supplied workflow:

| `--node_type` | Meaning in the inherited script's help; needs live verification |
| --- | --- |
| omitted | No pool constraint; scheduler chooses an eligible pool |
| `default` | A100 80 GB |
| `h100` | H100 80 GB |
| `h200` | H200, described as 140 GB in the old help; confirm actual model/capacity |
| `a100-40g` | A100 40 GB |
| `v100` | V100 32 GB |

These are accepted strings, not a discovered inventory or a guarantee of quota. `default` is a literal pool name, not a Python default. The inherited helper marks **interactive** requests for `default`, `h100`, or `a100-40g` as preemptible. This behavior is retained pending validation; it does not prove that other requests cannot be preempted.

Large `/dev/shm` is enabled once by default, matching the old helper's effective behavior; `--no-large-shm` disables it. `--host_ipc` is opt-in and inherits the old host-IPC setting. Confirm current policy and application need before using host IPC. Resource semantics and scheduling are covered in the [verification checklist](verification.md).

## Inspect, attach and stop

Run:ai management commands need the same cluster/project as submission. **Laptop**, using values configured in [setup](setup.md):

```bash
runai config cluster "$RCP_CLUSTER"
runai config project "thl2-${GASPAR_USERNAME}"
kubectl config current-context
runai list jobs
```

If the displayed Kubernetes context differs from `RCP_CONTEXT`, resolve the CLI configuration before acting. The supplied workflow assumes Run:ai uses this kubeconfig; verify that assumption with your CLI version. In particular, do not manage a same-named job in another project.

```bash
runai describe job dev
runai exec dev -it -- zsh
runai logs experiment-001
runai delete job dev
```

The exact `exec` syntax and available shell depend on your Run:ai version/image. Consult `runai exec --help` if necessary. Exiting an attached shell does **not** stop an idle workload. Delete only the intended job; avoid bulk cleanup commands.

For an explicit Kubernetes target, **laptop**:

```bash
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get interactiveworkloads.run.ai dev -o yaml
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get trainingworkloads.run.ai experiment-001 -o yaml
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get pods
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get events --sort-by=.metadata.creationTimestamp
```

The workload plural names are derived from the inherited Run:ai API kinds; confirm them with `kubectl --context "$RCP_CONTEXT" api-resources --api-group=run.ai` if unavailable. Manifest inspection may expose token values: inspect locally and sanitize any output before sharing. For pod-specific diagnostics, identify the pod belonging to your workload first, then use `describe pod POD_NAME` or `logs POD_NAME` with the same explicit context/namespace.

After successful submission the helper prints an explicitly targeted inspection command. It does not wait for scheduling. Check status and logs to distinguish accepted, pending, running, succeeded and failed workloads.

## Names, retries and repeatable experiments

The helper uses `kubectl create`, so an existing name is an error. It never updates an existing workload with `apply`. Choose a new name for a distinct experiment. If a request loses its connection or returns an ambiguous error, inspect the exact namespace for that name before trying again.

For each experiment, record the job name, Git commit, image tag or digest, command, resource request, configuration and checkpoint/output paths. Avoid sharing a mutable code directory or overwriting another run's outputs. For a sweep, first validate one small run; decide the number of jobs and total resources before launching the sweep.

## Helper options and changes from the old script

Run `python scripts/csub.py --help` for the complete CLI. Existing spellings `--node_type`, `--large_shm`, `--host_ipc` and `--backofflimit` are preserved; hyphenated aliases are also available.

| Option | Behavior |
| --- | --- |
| `-u`, `--user` | Local config path; default `user.yaml` relative to your current directory |
| `--context` | Explicit Kubernetes context override; no global context is changed |
| `-n`, `--name` | Lowercase DNS label, max 63 characters; otherwise generated from username and UTC timestamp |
| `--train` | Training workload; requires a nonempty command |
| `-c`, `--command` | Command passed to the image through Run:ai arguments |
| `-t`, `--time` | Idle sleep duration such as `1h`, `90m`, `1d2h30m`; default one hour |
| `-g`, `--gpus`; `--cpus`; `--memory` | Defaults: one GPU, one CPU, 32G host RAM |
| `-i`, `--image` | Default inherited image `ic-registry.epfl.ch/mlo/mlo:v1`; needs live verification |
| `-d`, `--dry` | Local-only, redacted preview |

The old unused `--port` option is removed; use explicit port forwarding as described in [development](development.md#notebooks-and-port-forwarding). The old README's `--cluster` flag did not exist in the supplied script; use `--context` for the Kubernetes target.

The new configuration requires `context` and `supplemental_groups`. The old `symlinks` key is accepted with a notice but ignored, as in the locally used no-symlinks helper. There is no automatic Conda installation. Secrets are optional and redacted in previews and normal kubectl error output; avoid embedding secrets directly in commands. Actual submission still sends configured tokens as workload environment values, so users with workload-read access may see them. A Kubernetes Secret integration would need a separately verified RCP procedure.
