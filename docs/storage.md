# Storage and permissions

These mappings are taken from the lab gist and the locally used helper; they have not been checked against a live account in this revision. Track confirmation in [verification](verification.md).

## The same storage has different paths

| Storage | On jumphost | In a job created by this helper | Intended use |
| --- | --- | --- | --- |
| Personal home | Your login `$HOME`; discover it rather than assuming `/home/...` | `/<username>` via PVC `home`; also set as container `$HOME` | Personal environments, configuration and private files, subject to actual permissions and quotas |
| Lab shared scratch | `/mnt/thl2/scratch/` | `/thl2` via PVC `thl2-scratch` | Experiment code, data and outputs; use `/thl2/<username>/` for your work |
| Container filesystem | Not available as a persistent jumphost path | Paths outside mounted home and `/thl2` | Temporary files only |

For example, `/mnt/thl2/scratch/alice/my-project/train.py` on jumphost is `/thl2/alice/my-project/train.py` in a container. A Python environment at `$HOME/venvs/my-project` on jumphost is expected at `/alice/venvs/my-project` in that container. Create that environment **inside a compatible container**, not on your laptop or under an unrelated jumphost Python installation.

Jumphost gives you access to mounted filesystems; it is not necessarily the machine physically storing those bytes. The laptop checkout is separate: editing a file locally does not update a running experiment unless you transfer it or pull a Git commit on cluster storage.

## Keep personal and shared work clear

Treat the scratch tree as shared lab storage. Put your own code, downloads and outputs under `/thl2/<username>/`, and coordinate before creating lab-wide datasets or caches. Never delete, recursively change permissions, or recursively change ownership on a colleague's files or the shared root.

The inherited helper runs with your numeric UID, THL2 GID `11167`, and supplemental group `84730`. These must agree with the storage's access rules. A mounted PVC alone does not grant access. Root inside a container is not a substitute for the correct identity on network storage.

Personal-home privacy and the exact ACLs still need confirmation. Inspect `id`, `ls -ld`, and, where available, `getfacl`. For deliberately shared project files, agree on group ownership and permissions with collaborators. Do not copy the MLO guide's broad `umask` or `chmod` advice without confirming THL2 policy.

## Persistence, quotas and backups

Mounted files survive pod deletion; the rest of the container does not. Keep environments, checkpoints, experiment logs and source code in persistent paths. Use Git for code history and record the commit for each experiment.

No backup, snapshot, retention or quota guarantee for THL2 home or scratch has been established by this guide. In particular, do not equate “scratch” with an archive or assume an MLO storage policy applies here. Ask the lab administrator how to retain publication artifacts and record the answer in [verification](verification.md). Checkpointing helps recover interrupted training, but is not an independent backup.

## Move code and data

**Laptop:** replace the username and local path. These commands upload into your own scratch directory and do not use `--delete`.

```bash
ssh YOUR_USERNAME@jumphost.rcp.epfl.ch 'mkdir -p /mnt/thl2/scratch/YOUR_USERNAME/my-project'
rsync -av --exclude '.git/' --exclude '.venv/' --exclude 'user.yaml' --exclude '.env*' \
  ./my-project/ \
  YOUR_USERNAME@jumphost.rcp.epfl.ch:/mnt/thl2/scratch/YOUR_USERNAME/my-project/
```

Alternatively, clone or pull a repository into your personal scratch subtree from jumphost or a container. For reproducible runs, use a known commit and avoid editing code in place while a job is using it. Transfer only the files intended for the cluster; the exclusions above are examples, not a complete filter for every project.

To download results, **laptop:**

```bash
rsync -av YOUR_USERNAME@jumphost.rcp.epfl.ch:/mnt/thl2/scratch/YOUR_USERNAME/my-project/results/ ./results/
```

## Verify the path mapping

Use a uniquely named small marker inside your own directory. **Jumphost:**

```bash
mkdir -p "/mnt/thl2/scratch/${USER}"
marker=".rcp-storage-check-$(date +%s)-$$"
printf '%s\n' "$marker" > "/mnt/thl2/scratch/${USER}/${marker}"
printf '%s\n' "$marker" > "$HOME/$marker"
printf 'Marker name: %s\n' "$marker"
```

Record the marker name. **Container:** substitute that name and your GASPAR username:

```bash
cat /thl2/YOUR_USERNAME/MARKER_NAME
cat /YOUR_USERNAME/MARKER_NAME
```

Both should contain the marker name. Check `id` as well. After confirmation, remove exactly those two marker files from jumphost. Do not scan or modify other members' home directories to test privacy.
