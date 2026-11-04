# Troubleshooting

Start by checking the exact target. On your **laptop**, use the values from [setup](setup.md):

```bash
kubectl config current-context
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get pvc home thl2-scratch
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get pods
```

Check Run:ai's selected cluster and project before running any Run:ai management or deletion command. Do not share kubeconfig contents, workload YAML with tokens, or unredacted authentication logs.

## Configuration or local helper errors

- **Missing `user.yaml`:** copy `config/user.example.yaml`, fill in your identity, and run from the repository root; or pass `--user /absolute/path/to/user.yaml`.
- **Missing `context` or `supplemental_groups`:** migrate the old configuration using the new example. Verify the context in your kubeconfig and groups with `id` on jumphost.
- **Invalid configuration YAML:** check indentation, duplicate keys and value types. Numeric IDs must be integers; token fields must be strings or omitted. The helper suppresses YAML source excerpts because they may contain credentials.
- **`--time` with a command:** remove `--time`; it only controls idle sleep. It does not cap training runtime.
- **`--train` without a command:** provide the experiment script. For an idle development shell, omit `--train`.
- **`kubectl` not found:** activate the intended shell environment and ensure the binary is on `PATH`. `--dry` does not require kubectl.

## Cannot connect or authenticate

Check EPFL network/VPN access, `KUBECONFIG`, context name and login status. Run `kubectl config get-contexts` and authenticate using the currently supported RCP Run:ai login procedure. A context name in `user.yaml` is a local kubeconfig entry, not an API URL. Do not resolve a TLS error by disabling certificate verification.

If authentication works but access is forbidden, confirm current group membership and project provisioning with the lab administrator. Joining a group may not immediately provision every resource.

## Submission failed or job is missing

The helper submits once with `kubectl create`. An `AlreadyExists` error means it did not update that workload. Inspect the existing job and choose a new name, or delete the old job only when you intend to stop/remove it.

A timeout or lost connection may be ambiguous: the server may have accepted the request. Inspect the exact name in the exact context/namespace before retrying. The helper does not automatically delete, rename, resubmit or retry.

If kubectl reports success but `runai list jobs` shows nothing, verify the CLI's selected cluster/project. Inspect the corresponding Run:ai workload resource directly using the command printed by the helper. API/CLI version differences may affect visibility; the [RCP console](https://rcpepfl.run.ai/) can provide another view. Do not repeatedly submit duplicates to fix a display mismatch.

## Job stays pending

**Laptop**, inspect workload details, then identify its pod:

```bash
runai describe job JOB_NAME
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get pods
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" describe pod POD_NAME
kubectl --context "$RCP_CONTEXT" --namespace "$RCP_NAMESPACE" get events --sort-by=.metadata.creationTimestamp
```

If no pod exists yet, inspect the workload and console scheduler messages. Distinguish capacity/quota constraints from invalid GPU pools, missing PVCs, image pull failures, denied settings or authentication. Change the request only when the diagnostic evidence justifies it. The pool names in the helper are inherited values, not live inventory.

## Permission denied or missing files

Inside the **container**, inspect `id`, `$HOME`, `/thl2`, and your personal subtree with `ls -ld`. Compare with jumphost. Confirm UID/GID/supplemental groups and the two PVC mounts. Use the [marker check](storage.md#verify-the-path-mapping) if the path correspondence is uncertain.

If files are absent, confirm you transferred or cloned them onto persistent storage. Your laptop checkout does not automatically appear there. For persistent environments, check the interpreter path and the image used to create them.

Do not use `chmod -R 777`, run experiments as root, or change permissions on the lab root to bypass an error. Ask the storage administrator to diagnose the correct access rules.

## Container exits immediately or training fails

Check workload status and `runai logs JOB_NAME`, followed by pod events if startup failed. Verify the image exists, the command/script path is in mounted storage, the interpreter exists, and the script explicitly selects its directory. `WORKING_DIR` is not an automatic `cd`.

If a command works interactively but not in training, remove dependence on shell startup files or activation; use a script with explicit interpreter and paths. Test a short training command with the chosen image before launching a full run. A nonzero script exit should be visible as failure; the precise propagation through the inherited entrypoint remains a live verification item.

If an interactive job ends, it may have reached its idle-sleep duration, an RCP time limit, or been preempted. Look at workload/pod events rather than assuming a particular cause. Resume from a checkpoint when supported.

## Out of memory

Distinguish GPU CUDA OOM from a container killed for exceeding host RAM. Inspect logs and pod termination reasons. `--memory` changes host RAM only. Address GPU memory use in the experiment, or select a verified GPU pool with sufficient memory. More requested GPUs do not automatically distribute a model across them.

## Escalate with useful evidence

Share the sanitized job name, target context/project/namespace, resource request, image, status, relevant events and error text. Explain the smallest reproduction and what you already checked. Use the lab's current support contact or the contact listed in the RCP console/docs; support addresses copied from old MLO docs may have changed.
