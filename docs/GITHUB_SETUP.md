# Put Ahmad's implementation into your GitHub repository

## Folder placement

The ZIP contains a single `quantum-camera-placement/` folder. For your team repository, copy **everything inside it** into the repository root. Include `.gitignore`, `.gitattributes` and `.github/` (some file managers hide them). The root should contain `README.md`, `package.json`, `frontend/`, `backend/`, `data/`, `docs/`, `scripts/` and `.github/`.

Keep Huzaifa's three canonical files in `data/results/` using their original filenames: `result_sector_8.json`, `result_sector_12.json`, `result_sector_16.json`. His future solver package can live in a sibling `solver/` folder. The JSON files in this ZIP are byte-for-byte copies of the attachments.

If the team already has files named `README.md`, `.gitignore` or a root `package.json`, merge their contents instead of overwriting teammates' work. For an existing monorepo, this application may stay in its own subfolder, but adjust GitHub Actions `working-directory` and cache paths to that subfolder; the included workflow assumes the app sits at repository root.

## Existing repository (recommended)

Use your real team repository URL and a feature branch. Do not push directly over another person's work.

```bash
git clone YOUR_TEAM_REPOSITORY_URL
cd YOUR_REPOSITORY_FOLDER
git switch -c ahmad/full-stack-camera-ui
```

Copy the package contents into this folder, install/run/check as described in README, then:

```bash
git status --short
git add frontend backend data docs scripts .github .gitignore .gitattributes package.json README.md
git diff --cached --stat
git commit -m "Add camera placement frontend and FastAPI integration"
git push -u origin ahmad/full-stack-camera-ui
```

Open a pull request from the pushed branch. Review the staged files before committing, especially if the repository already contains changes.

## New repository

Create an empty GitHub repository, extract the package and enter its root, then:

```bash
git init -b main
git add .
git status --short
git commit -m "Add quantum camera placement full-stack demo"
git remote add origin YOUR_NEW_REPOSITORY_URL
git push -u origin main
```

Use this only for an empty remote. If the remote already has a README or history, clone it first and follow the existing-repository instructions.

## Commit / ignore

| Commit | Do not commit |
|---|---|
| React source, `package.json`, `package-lock.json`, Vite config | `node_modules/`, `frontend/dist/` |
| FastAPI source, tests and requirements | `.venv/`, `__pycache__/`, Python caches |
| Original `data/results/*.json` | Generated `frontend/public/saved-results/` |
| Docs, scripts, workflow, `.env.example` templates | Real `.env` files, credentials, access tokens |

The included `.gitignore` handles these generated/private paths. Do not use `git add -f` to force them into the repository. No GitHub remote was modified by preparing this deliverable.
