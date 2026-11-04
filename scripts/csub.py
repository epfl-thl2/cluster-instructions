#!/usr/bin/env python3
"""Submit THL2 Run:ai workloads. See docs/jobs.md for usage and limitations."""

import argparse
import copy
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

import yaml


DEFAULT_IMAGE = "ic-registry.epfl.ch/mlo/mlo:v1"
NODE_POOLS = ("v100", "h100", "h200", "default", "a100-40g")
SECRET_KEYS = {"WANDB_API_KEY": "wandb_api_key", "HF_TOKEN": "hf_token"}


def nonnegative_int(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return number


def positive_int(value):
    number = nonnegative_int(value)
    if number == 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def duration_seconds(value):
    match = re.fullmatch(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", value)
    if not match or not any(match.groups()):
        raise argparse.ArgumentTypeError("use a duration such as 1h, 90m or 1d2h30m")
    seconds = sum(int(n or 0) * factor for n, factor in zip(match.groups(), (86400, 3600, 60, 1)))
    if seconds == 0:
        raise argparse.ArgumentTypeError("duration must be greater than zero")
    return seconds


def memory_quantity(value):
    match = re.fullmatch(r"(\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+|[EPTGMK]i|[EPTGMkKmun])?", value)
    if not match or not any(ch in "123456789" for ch in match[1]):
        raise argparse.ArgumentTypeError("use a positive Kubernetes quantity, such as 32G or 32Gi")
    return value


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--name", help="unique job name (otherwise generated)")
    parser.add_argument("-c", "--command", help="container command; use a shell script for complex commands")
    parser.add_argument("-t", "--time", type=duration_seconds,
                        help="idle sleep duration, default 1h; cannot be used with --command; not a job deadline")
    parser.add_argument("-g", "--gpus", type=nonnegative_int, default=1)
    parser.add_argument("--cpus", type=positive_int, default=1)
    parser.add_argument("--memory", type=memory_quantity, default="32G", help="CPU RAM, not GPU RAM (default 32G)")
    parser.add_argument("-i", "--image", default=DEFAULT_IMAGE)
    parser.add_argument("-u", "--user", type=Path, default=Path("user.yaml"), help="user configuration file")
    parser.add_argument("--context", help="Kubernetes context; overrides context in user configuration")
    parser.add_argument("--train", action="store_true", help="training workload; requires --command")
    parser.add_argument("-d", "--dry", action="store_true", help="print a redacted manifest without contacting Kubernetes")
    parser.add_argument("--backofflimit", "--backoff-limit", type=nonnegative_int, default=0,
                        help="training retries (default 0)")
    parser.add_argument("--node_type", "--node-type", default="", choices=("", *NODE_POOLS),
                        help="pool names inherited from the lab workflow; availability needs live verification")
    parser.add_argument("--host_ipc", "--host-ipc", action="store_true")
    shm = parser.add_mutually_exclusive_group()
    shm.add_argument("--large_shm", "--large-shm", dest="large_shm", action="store_true",
                     help="large shared memory (default enabled, matching the old helper)")
    shm.add_argument("--no-large-shm", dest="large_shm", action="store_false")
    parser.set_defaults(large_shm=True)
    return parser


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject ambiguous configuration, including duplicate keys."""

    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise ValueError("duplicate YAML keys")
        return mapping


def dns_label(value, label):
    if not isinstance(value, str) or len(value) > 63 or not re.fullmatch(r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?", value):
        raise ValueError(f"{label} must be a lowercase DNS label of at most 63 characters")
    return value


def config_id(value, label):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"\d+", str(value)):
        raise ValueError(f"{label} must be a non-negative integer from id on jumphost")
    return int(value)


def load_config(path):
    try:
        config = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (yaml.YAMLError, ValueError) as exc:
        raise ValueError("invalid configuration YAML; check indentation and duplicate keys") from exc
    if not isinstance(config, dict):
        raise ValueError("user configuration must be a YAML mapping; copy config/user.example.yaml")
    required = ("user", "uid", "group", "gid", "supplemental_groups", "working_dir", "context")
    if any(key not in config for key in required):
        missing = ", ".join(key for key in required if key not in config)
        raise ValueError(f"missing configuration fields: {missing}; see config/user.example.yaml")
    dns_label(config["user"], "user")
    dns_label(f"runai-thl2-{config['user']}", "namespace")
    config["uid"] = config_id(config["uid"], "uid")
    config["gid"] = config_id(config["gid"], "gid")
    groups = config["supplemental_groups"]
    if not isinstance(groups, list):
        groups = str(groups).split(",")
    if not groups:
        raise ValueError("supplemental_groups must contain at least one group ID")
    config["supplemental_groups"] = ",".join(str(config_id(g.strip() if isinstance(g, str) else g, "supplemental_groups")) for g in groups)
    for key in ("group", "context", "working_dir"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    home = f"/{config['user']}"
    directory = config["working_dir"]
    if ".." in directory.split("/") or not any(directory == mount or directory.startswith(mount + "/") for mount in (home, "/thl2")):
        raise ValueError("working_dir must be an absolute path inside /thl2 or your mounted home")
    for key in SECRET_KEYS.values():
        if config.get(key) is not None and not isinstance(config[key], str):
            raise ValueError(f"{key} must be a string or omitted")
    return config


def build_manifest(args, config, environ=None):
    environ = os.environ if environ is None else environ
    if args.train and not args.command:
        raise ValueError("--train requires --command; use an interactive job for an idle shell")
    if args.command is not None and not args.command.strip():
        raise ValueError("--command cannot be empty")
    if args.time is not None and args.command is not None:
        raise ValueError("--time only sets idle sleep duration; it cannot limit --command runtime")
    if args.backofflimit and not args.train:
        raise ValueError("--backofflimit applies only to --train")
    if not args.image.strip():
        raise ValueError("--image cannot be empty")
    user = config["user"]
    name = args.name if args.name is not None else f"{user[:30]}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}"
    dns_label(name, "job name")
    namespace = f"runai-thl2-{user}"
    context = args.context if args.context is not None else config["context"]
    if not context.strip():
        raise ValueError("--context cannot be empty")
    environment = {
        "HOME": f"/{user}", "NB_USER": user, "NB_UID": str(config["uid"]),
        "NB_GROUP": config["group"], "NB_GID": str(config["gid"]),
        "WORKING_DIR": config["working_dir"], "EPFML_LDAP": user,
    }
    for env_name, config_key in SECRET_KEYS.items():
        value = environ.get(env_name, config.get(config_key) or "")
        if value:
            environment[env_name] = value
    spec = {
        "name": {"value": name},
        "arguments": {"value": args.command if args.command is not None else f"sleep {args.time or 3600}"},
        "environment": {"items": {key: {"value": value} for key, value in environment.items()}},
        "gpu": {"value": str(args.gpus)}, "cpu": {"value": str(args.cpus)},
        "memory": {"value": args.memory}, "image": {"value": args.image},
        "imagePullPolicy": {"value": "Always"},
        "pvcs": {"items": {
            "pvc--0": {"value": {"claimName": "thl2-scratch", "existingPvc": True, "path": "/thl2", "readOnly": False}},
            "pvc--1": {"value": {"claimName": "home", "existingPvc": True, "path": f"/{user}", "readOnly": False}},
        }},
        "runAsGid": {"value": config["gid"]}, "runAsUid": {"value": config["uid"]},
        "runAsUser": {"value": True}, "serviceType": {"value": "ClusterIP"},
        "username": {"value": user}, "allowPrivilegeEscalation": {"value": True},
        "supplementalGroups": {"value": config["supplemental_groups"]},
        "largeShm": {"value": args.large_shm},
    }
    if args.node_type:
        spec["nodePools"] = {"value": args.node_type}
    if args.node_type in ("h100", "default", "a100-40g") and not args.train:
        spec["preemptible"] = {"value": True}
    if args.host_ipc:
        spec["hostIpc"] = {"value": True}
    if args.train:
        spec["backoffLimit"] = {"value": args.backofflimit}
    # Retained for compatibility with the supplied local workflow, not a version check.
    manifest = {
        "apiVersion": "run.ai/v2alpha1",
        "kind": "TrainingWorkload" if args.train else "InteractiveWorkload",
        "metadata": {"annotations": {"runai-cli-version": "2.22.73"},
                     "labels": {"PreviousJob": "true"}, "name": name, "namespace": namespace},
        "spec": spec,
    }
    return manifest, context


def secret_values(manifest):
    environment = manifest["spec"]["environment"]["items"]
    return [environment[key]["value"] for key in SECRET_KEYS if key in environment]


def redact(text, secrets):
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "REDACTED")
    return text


def render_manifest(manifest, preview=False):
    document = copy.deepcopy(manifest)
    if preview:
        environment = document["spec"]["environment"]["items"]
        for key in SECRET_KEYS:
            if key in environment:
                environment[key]["value"] = "REDACTED"
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.user)
        manifest, context = build_manifest(args, config)
    except (OSError, ValueError) as exc:
        # YAML parser errors deliberately omit source lines, which can contain tokens.
        parser.error(str(exc))
    namespace, name = manifest["metadata"]["namespace"], manifest["metadata"]["name"]
    secrets = secret_values(manifest)
    print(f"Target: context={context}, namespace={namespace}, name={name}", file=sys.stderr)
    if "symlinks" in config:
        print("Note: legacy symlinks configuration is ignored; see docs/development.md.", file=sys.stderr)
    if args.dry:
        print(redact(render_manifest(manifest, preview=True), secrets), end="")
        return 0
    command = ["kubectl", "--context", context, "--namespace", namespace, "create", "-f", "-"]
    try:
        result = subprocess.run(command, input=render_manifest(manifest), capture_output=True, text=True, check=False)
    except OSError:
        print("Could not run kubectl; check its installation and PATH. No retry was attempted.", file=sys.stderr)
        return 1
    if result.stdout:
        print(redact(result.stdout, secrets), end="")
    if result.stderr:
        print(redact(result.stderr, secrets), file=sys.stderr, end="")
    if result.returncode:
        print("Submission failed. Inspect the target before retrying; an existing job is never updated.", file=sys.stderr)
        return 1
    kind = "trainingworkloads.run.ai" if args.train else "interactiveworkloads.run.ai"
    inspect = ["kubectl", "--context", context, "--namespace", namespace, "get", kind, name, "-o", "yaml"]
    print("Submitted; running state has not been checked.")
    print("Inspect: " + shlex.join(inspect))
    return 0


if __name__ == "__main__":
    sys.exit(main())
