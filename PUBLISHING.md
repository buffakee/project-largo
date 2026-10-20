# Building and publishing the Alpha

Repository: `buffakee/project-largo-alpha` (private). This is separate from the
earlier preservation repository, `buffakee/project-largo`.

The first prerelease is **v0.1.0-alpha.1**. This is a source kit, not a compiled
Linux binary or distro package. Original runtime code/assets are recorded in
`UPSTREAM_SNAPSHOT.json`; initial versioning is in `VERSION`.

## Validate a candidate

```bash
python3 -m unittest discover -s tests -v
python3 tools/check-render.py
python3 tools/check-appearance.py
python3 tools/check-picker.py
python3 tools/check-gdm.py
python3 tools/check-office.py
```

The last five checks require the documented local native dependencies and do not
run in the default Ubuntu source-only CI job. Read DEVELOPMENT.md for isolation
and evidence limits. Update Alpha notes with actual results rather than inferring
interactive or Flatpak support from a source test.

## Build from a committed candidate

Keep `VERSION`, the release tag and Alpha notes consistent. Review status/diff,
commit only intended source files and push the candidate to this existing repo.
Then, from a clean checkout:

```bash
python3 tools/build-alpha.py
python3 tools/check-alpha.py dist/project-largo-alpha-0.1.0-alpha.1.tar.gz
```

The builder uses `git archive HEAD`, giving the source kit one versioned top-level
directory. It excludes ignored files, Git history, runtime state and local caches.
It writes the archive and `SHA256SUMS` under ignored `dist/`. Rebuilding the same
commit with the same Git/Python/compression toolchain produces the same checksum.

The archive check validates member paths/content, extracts into a disposable
directory, performs an installer dry-run and runs the unit suite there. A source
kit check is separate from an interactive clean-machine install.

## Publish the prerelease

After the candidate's checks and GitHub Actions pass, and publication is requested:

```bash
gh release create v0.1.0-alpha.1 \
  dist/project-largo-alpha-0.1.0-alpha.1.tar.gz dist/SHA256SUMS \
  --repo buffakee/project-largo-alpha --target main --prerelease \
  --title "Project Largo Alpha 1" --notes-file ALPHA_NOTES.md
```

For later Alphas, bump the version/tag/notes and retain earlier releases. Do not
change visibility, replace a published asset/tag or create another repository as
part of normal iteration. Source and third-party licenses/notices remain intact.
