# Develop in a container

Use an interactive job from [jobs](jobs.md) and wait for it to run. Enter it from your **laptop** with `runai exec dev -it -- zsh`, after aligning the selected Run:ai cluster/project.

## Code and Python environments

Keep your code under `/thl2/<username>/my-project/` and your personal environment under `/<username>/venvs/my-project/`. You can transfer code using [storage](storage.md#move-code-and-data) or clone your experiment repository into your own scratch directory.

**Container**, with the helper-provided `NB_USER`:

```bash
mkdir -p "/thl2/${NB_USER}/my-project" "$HOME/venvs"
python3 -m venv "$HOME/venvs/my-project"
source "$HOME/venvs/my-project/bin/activate"
cd "/thl2/${NB_USER}/my-project"
# Once your project files are here:
python -m pip install -r requirements.txt
```

If `python3 -m venv` is unavailable, select an appropriate lab image or ask its maintainer how to provide it. Do not assume Conda or a Python package is already installed. The inherited Dockerfile and published default image have not been rebuilt or checked in this revision.

An environment on persistent storage survives replacing the pod. It still depends on the image's Python version, OS libraries and CUDA stack. Build it inside a compatible image; do not reuse a laptop/macOS environment on a Linux compute node, or assume an environment remains compatible after changing the image.

For training, use the environment's absolute interpreter path, e.g. `/alice/venvs/my-project/bin/python`. [examples/train.sh](../examples/train.sh) shows this without relying on activation in a noninteractive shell. The helper's `WORKING_DIR` environment variable is informational to the image; the training script explicitly runs `cd`.

## Home, configuration and caches

The helper mounts personal home directly at `/<username>` and sets `HOME` to that path. It does not generate symlinks, install Conda, copy dotfiles or initialize editor settings. The old MLO `symlinks` list and automatic installation instructions do not apply.

Check `printf '%s\n' "$HOME"` and `id` on a fresh job. Tools that respect `$HOME` can put settings there. Other tools may use the Unix account's registered home or a hard-coded path, so check persistence rather than assuming it. Use your own cache paths unless the lab has agreed on a shared cache and its permissions.

## VS Code

On your **laptop**, install VS Code's Kubernetes and Dev Containers extensions. Select the correct RCP context and namespace in the Kubernetes extension, identify the pod belonging to your interactive job, and use **Attach Visual Studio Code**.

Open `/thl2/<username>/my-project` in the attached container. Select `/<username>/venvs/my-project/bin/python` as the interpreter. Confirm that saved files appear on persistent storage. Persistence of VS Code extensions/settings must be checked with the current image and extension versions; the old MLO symlink promise is not carried over.

## Notebooks and port forwarding

Install Jupyter into your chosen persistent environment if needed. **Container:**

```bash
"$HOME/venvs/my-project/bin/python" -m jupyter lab --no-browser --ip=0.0.0.0 --port=8888
```

Keep Jupyter authentication enabled. Identify your pod, then **laptop**:

```bash
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get pods
# Replace POD_NAME with the pod belonging to your job.
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" port-forward --address 127.0.0.1 pod/POD_NAME 8888:8888
```

Open the localhost URL with the Jupyter token in your browser. Do not share that token or logs containing it. Forwarding lasts while the command and pod run. Stop the notebook and delete the interactive job when finished.

## Images and reproducibility

The default image is inherited from the locally used helper: `ic-registry.epfl.ch/mlo/mlo:v1`. A tag alone does not guarantee immutable contents. For reproducible runs, use an agreed versioned image, preferably recorded by digest, and a pinned project environment/lockfile.

A replacement image must work with the requested numeric UID/GID, mounted home, writable directories, shell, Python/CUDA stack, and Run:ai arguments/entrypoint behavior. The helper retains the existing `NB_*`, `HOME`, `WORKING_DIR`, `EPFML_LDAP`, and `allowPrivilegeEscalation` settings because these are part of the supplied workflow; their necessity and permission policy still need validation. Do not infer that an arbitrary CUDA image is a drop-in replacement.

Custom image building/publishing is optional. Registry access, the preferred lab image and supported CUDA/framework versions remain in [verification](verification.md). No upstream Dockerfile or publishing script is copied into this guide until a maintained THL2 image workflow is established.
