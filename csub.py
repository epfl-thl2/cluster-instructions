#!/usr/bin/env python3
"""Submit a job to the EPFL RCP cluster (THL2 lab).

Examples:
  csub --name dev --gpus 1                                   # interactive, sleeps forever
  csub --name exp1 --train --gpus 1 --command "bash /thl2/me/proj/run.sh"
  csub --name dev --dry                                      # print the manifest, don't submit
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RUNAI_CLI_VERSION = "2.22.73"
DEFAULT_IMAGE = "ic-registry.epfl.ch/mlo/mlo:v1"
NODE_TYPES = ["v100", "a100-40g", "default", "h100", "h200", "b300"]
# By default, look for user.yaml next to the real location of this script (works through symlinks).
DEFAULT_CONFIG = Path(__file__).resolve().parent / "user.yaml"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-n", "--name", help="job name, unique among your jobs (default: <user>-<timestamp>)")
    p.add_argument("-c", "--command", help="command to run (default for interactive jobs: sleep infinity)")
    p.add_argument("--train", action="store_true", help="training job instead of interactive (requires --command)")
    p.add_argument("-g", "--gpus", type=int, default=1, help="number of GPUs (default 1, use 0 for CPU only)")
    p.add_argument("--cpus", type=int, default=1, help="number of CPUs (default 1)")
    p.add_argument("--memory", default="32G", help="CPU RAM, not GPU memory (default 32G)")
    p.add_argument("--node-type", "--node_type", default="", choices=["", *NODE_TYPES],
                   help="GPU type: v100, a100-40g, default (=A100-80GB), h100, h200, b300. "
                        "Interactive jobs can only use v100/a100-40g/default.")
    p.add_argument("-i", "--image", default=DEFAULT_IMAGE, help=f"docker image (default {DEFAULT_IMAGE})")
    p.add_argument("--backofflimit", type=int, default=0, help="retries for a failed training job (default 0)")
    p.add_argument("--host-ipc", "--host_ipc", action="store_true", help="use the host's IPC namespace")
    p.add_argument("-u", "--user", type=Path, default=DEFAULT_CONFIG, help=f"config file (default {DEFAULT_CONFIG})")
    p.add_argument("-d", "--dry", action="store_true", help="print the manifest instead of submitting")
    return p.parse_args()


def load_config(path):
    """Read a flat `key: value` YAML file (comments allowed)."""
    if not path.exists():
        sys.exit(f"Config {path} not found. Copy user.example.yaml to user.yaml and fill it in.")
    cfg = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            key, _, value = line.partition(":")
            cfg[key.strip()] = value.strip().strip("\"'")
    missing = [k for k in ("user", "uid", "gid", "group", "supplemental_groups") if not cfg.get(k)]
    if missing:
        sys.exit(f"Config {path} is missing: {', '.join(missing)}")
    return cfg


def build_manifest(args, cfg):
    user = cfg["user"]
    env = {
        "HOME": f"/{user}",
        "NB_USER": user,
        "NB_UID": cfg["uid"],
        "NB_GROUP": cfg["group"],
        "NB_GID": cfg["gid"],
        "WORKING_DIR": cfg.get("working_dir") or f"/thl2/{user}",
        "EPFML_LDAP": user,
        # pip, Hugging Face, torch etc. cache under $XDG_CACHE_HOME. Keep that on the big lab
        # scratch instead of the default ~/.cache, which would quickly fill the 100 GiB home.
        "XDG_CACHE_HOME": f"/thl2/{user}/.cache",
    }
    # Optional tokens: environment variable wins over the config file.
    for var, key in (("WANDB_API_KEY", "wandb_api_key"), ("HF_TOKEN", "hf_token")):
        value = os.environ.get(var) or cfg.get(key)
        if value:
            env[var] = value

    spec = {
        "name": {"value": args.name},
        "arguments": {"value": args.command},
        "environment": {"items": {k: {"value": str(v)} for k, v in env.items()}},
        "gpu": {"value": str(args.gpus)},
        "cpu": {"value": str(args.cpus)},
        "memory": {"value": args.memory},
        "image": {"value": args.image},
        "imagePullPolicy": {"value": "Always"},
        "pvcs": {"items": {
            "pvc--0": {"value": {"claimName": "thl2-scratch", "existingPvc": True, "path": "/thl2", "readOnly": False}},
            "pvc--1": {"value": {"claimName": "home", "existingPvc": True, "path": f"/{user}", "readOnly": False}},
        }},
        "runAsUid": {"value": int(cfg["uid"])},
        "runAsGid": {"value": int(cfg["gid"])},
        "supplementalGroups": {"value": cfg["supplemental_groups"]},
        "runAsUser": {"value": True},
        "username": {"value": user},
        "serviceType": {"value": "ClusterIP"},
        "allowPrivilegeEscalation": {"value": True},
        "largeShm": {"value": True},
    }
    if args.node_type:
        spec["nodePools"] = {"value": args.node_type}
        # Inherited from the lab's original script.
        if args.node_type in ("default", "a100-40g") and not args.train:
            spec["preemptible"] = {"value": True}
    if args.host_ipc:
        spec["hostIpc"] = {"value": True}
    if args.train:
        spec["backoffLimit"] = {"value": args.backofflimit}

    return {
        "apiVersion": "run.ai/v2alpha1",
        "kind": "TrainingWorkload" if args.train else "InteractiveWorkload",
        "metadata": {
            "name": args.name,
            "namespace": f"runai-thl2-{user}",
            "annotations": {"runai-cli-version": RUNAI_CLI_VERSION},
            "labels": {"PreviousJob": "true"},
        },
        "spec": spec,
    }


def main():
    args = parse_args()
    cfg = load_config(args.user)
    if args.train and not args.command:
        sys.exit("--train needs a --command (training jobs run a command and exit).")
    if not args.train and args.node_type in ("h100", "h200", "b300"):
        sys.exit(f"RCP doesn't allow interactive jobs on {args.node_type}. "
                 "Use --train, or --node-type v100/a100-40g/default.")
    args.command = args.command or "sleep infinity"
    args.name = args.name or f"{cfg['user']}-{datetime.now():%Y%m%d-%H%M%S}"

    manifest = build_manifest(args, cfg)

    if args.dry:
        env = manifest["spec"]["environment"]["items"]
        for secret in ("WANDB_API_KEY", "HF_TOKEN"):
            if secret in env:
                env[secret]["value"] = "<redacted>"
        print(json.dumps(manifest, indent=2))
        return

    # `create` (not `apply`) so an existing job with the same name is an error, not silently kept.
    result = subprocess.run(["kubectl", "create", "-f", "-"], input=json.dumps(manifest), text=True)
    if result.returncode != 0:
        sys.exit("Submission failed (see the error above). If the name already exists, "
                 f"pick another name or delete the old job: runai delete job {args.name}")

    n = args.name
    print(f"""
Submitted '{n}'. Useful commands:
  runai describe job {n}    # status and events
  runai logs {n}            # output (add --follow to stream)
  runai bash {n}            # shell inside the container (interactive jobs)
  runai delete job {n}      # stop and remove the job""")


if __name__ == "__main__":
    main()
