# First-time setup

This workflow submits from your laptop. Installing Codex or submitting experiments on jumphost is outside this guide's current scope. Infrastructure values below come from the lab's supplied workflow and still need the checks in [verification](verification.md).

## 1. Get access and check your identity

Ask the lab's cluster administrator to arrange access. The original lab instructions name Ola as the contact and list these groups at [groups.epfl.ch](https://groups.epfl.ch): `rcp-runai-thl2`, `runai-thl2`, and `thl2-scratch`. Confirm the current contact and groups rather than requesting MLO access.

Use the EPFL network or VPN where required. **Laptop:**

```bash
ssh YOUR_GASPAR_USERNAME@jumphost.rcp.epfl.ch
```

**Jumphost:**

```bash
hostname
id
printf '%s\n' "$HOME"
ls -ld "$HOME" /mnt/thl2/scratch
```

Record your GASPAR username and numeric UID. The inherited THL2 primary group is `THL2-unit` / GID `11167`, with supplemental storage group `84730`. Check these against `id` and the lab administrator if they differ. Do not substitute your laptop's UID or change shared directory permissions to work around an access error.

Exit back to your laptop before continuing. Read [storage](storage.md) to understand the paths you just inspected.

## 2. Install local tools

You need Python **3.10 or later**, `kubectl`, and the **RCP-compatible** Run:ai CLI. macOS and Linux are the intended platforms; Windows users can adapt the Linux workflow in WSL. OS-specific downloads must match your CPU architecture.

- Install `kubectl` using the [official installation instructions](https://kubernetes.io/docs/tasks/tools/). Select a client version supported by the current RCP cluster. The old guide's `v1.29.6` pin has not been revalidated.
- Download the Run:ai CLI from the help/download area of the [RCP console](https://rcpepfl.run.ai/) or the current [RCP quick start](https://wiki.rcp.epfl.ch/en/home/CaaS/Quick_Start). Use the cluster-provided version. The old `https://rcp-caas-prod.rcp.epfl.ch/cli/darwin` endpoint is historical, not a verified current installer.
- For a downloaded Run:ai binary, make it executable and place it on your `PATH`. For example, install it as `$HOME/.local/bin/runai` and add `$HOME/.local/bin` to your shell's `PATH`. If you also use IC, keep its separate CLI and configuration distinct.

Clone this repository from its lab Git URL and enter the checkout. **Laptop, repository root:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
kubectl version --client
runai --help
```

This local `.venv` is for the submission helper. It is separate from the Python environment used to train inside containers.

## 3. Configure RCP authentication

Obtain the current RCP kubeconfig using the RCP quick start or administrator. Keep it separate from existing cluster configurations. **Laptop:**

```bash
mkdir -p "$HOME/.kube"
# Assuming you downloaded the file as rcp-kubeconfig.yaml:
install -m 600 rcp-kubeconfig.yaml "$HOME/.kube/rcp-config"
export KUBECONFIG="$HOME/.kube/rcp-config"
kubectl config get-contexts

export GASPAR_USERNAME=YOUR_GASPAR_USERNAME
export RCP_CONTEXT=rcp-caas
export RCP_CLUSTER=rcp-caas
export RCP_NAMESPACE="runai-thl2-${GASPAR_USERNAME}"
```

Replace `YOUR_GASPAR_USERNAME`. `RCP_CONTEXT` must match a context in your kubeconfig. `RCP_CLUSTER` is the Run:ai cluster identifier; both were called `rcp-caas` in the supplied workflow, but they are different concepts. Confirm both names during setup. Keep these exports available in each new terminal, or add your chosen values to your shell configuration once setup works.

**Laptop:**

```bash
runai config cluster "$RCP_CLUSTER"
runai login
runai list projects
runai config project "thl2-${GASPAR_USERNAME}"

# Explicitly select the context for tools that use the current context.
kubectl config use-context "$RCP_CONTEXT"
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get pvc home thl2-scratch
```

Use the login method supported by your installed CLI. If these commands or names differ, use its help and the current RCP instructions; record the confirmed procedure in [verification](verification.md). Do not overwrite another kubeconfig or paste authentication material into an issue or chat.

The helper always passes `--context` and `--namespace` to `kubectl`. Run:ai commands use the CLI's selected cluster/project; keep those aligned. A personal project `thl2-alice` corresponds to namespace `runai-thl2-alice` in the inherited setup.

## 4. Create your local user configuration

**Laptop, repository root:**

```bash
cp config/user.example.yaml user.yaml
chmod 600 user.yaml
```

Edit `user`, `uid`, and `working_dir` for your account. Confirm `context`, `group`, `gid`, and `supplemental_groups` using the previous steps. The file is ignored by Git. Do not copy another member's personal configuration.

`working_dir` is passed to the image as `WORKING_DIR`; it does not automatically change the directory of every command. Training scripts must select their own directory explicitly.

Weights & Biases and Hugging Face tokens are optional. If needed, supply `WANDB_API_KEY` or `HF_TOKEN` in your local submitting environment using your normal credential workflow. Do not put literal tokens in command-line arguments or tracked scripts. The helper also accepts the old optional `wandb_api_key` and `hf_token` YAML fields. An environment variable overrides its YAML field, including when the variable is empty.

## 5. Check the mounts with a CPU-only job

Preview first. **Laptop, repository root:**

```bash
python scripts/csub.py --name storage-test --gpus 0 --cpus 1 --memory 1G --time 10m --dry
python scripts/csub.py --name storage-test --gpus 0 --cpus 1 --memory 1G --time 10m
runai describe job storage-test
```

If the name already exists, inspect the existing job and choose another name. Wait for the new job to run. Then **laptop:**

```bash
runai exec storage-test -it -- zsh
```

**Container:**

```bash
id
printf '%s\n' "$HOME" "$WORKING_DIR"
ls -ld "$HOME" /thl2
mkdir -p "/thl2/${NB_USER}"
ls -ld "/thl2/${NB_USER}"
```

Compare the container's IDs and directories with jumphost. Follow the cross-mount check in [storage](storage.md#verify-the-path-mapping) if this is the first lab validation. Exit the container, then **laptop:**

```bash
runai logs storage-test
runai delete job storage-test
```

The inherited default image is `ic-registry.epfl.ch/mlo/mlo:v1`. Its availability, startup behavior and current RCP compatibility are **unverified**. If it fails to start, inspect workload and pod events before trying another image. Merely changing images can change shell, UID, environment and entrypoint behavior; see [development](development.md#images-and-reproducibility).

After the smoke test, set up your [container Python environment](development.md) and submit a small [training job](jobs.md).
