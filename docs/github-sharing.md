# Share Doorlight Privately On GitHub

This project contains only synthetic demonstration transactions. Keep the GitHub repository private anyway, and never commit your local `.env` file or an API key.

## 1. Create the private repository

1. Sign in at [github.com](https://github.com/).
2. Select the **+** menu in the upper-right and choose **New repository**.
3. Name it `doorlight-a2a`.
4. Select **Private**.
5. Leave **Add a README**, **Add .gitignore**, and **Choose a license** unchecked because the local project already has its own files.
6. Select **Create repository** and keep the Quick Setup page open.

## 2. Initialize and upload this local project

The project files are prepared, but Git has not been initialized yet. This coding workspace left an empty read-only `.git` placeholder; the first command below removes only that empty placeholder. Then Git creates the real local repository.

On GitHub's Quick Setup page, copy the HTTPS repository URL. It will look like:

```text
https://github.com/YOUR-USERNAME/doorlight-a2a.git
```

Run these commands in WSL, replacing the example URL with the one GitHub gives you:

```bash
cd ~/projects/doorlight-a2a
rmdir .git
git init -b main
git add .
git status
git commit -m "Initial Doorlight A2A MVP"
git remote add origin https://github.com/YOUR-USERNAME/doorlight-a2a.git
git push -u origin main
```

Pause after `git status` and verify that `.env`, `.venv`, `node_modules`, `backend/doorlight.db`, `backend/.cache`, and `dist` are not listed under **Changes to be committed**.

If `git commit` says your identity is unknown, set the name and email that should appear on your commits, then repeat the commit command:

```bash
git config --global user.name "YOUR NAME"
git config --global user.email "YOUR GITHUB EMAIL"
```

GitHub may ask you to authenticate when pushing. A normal GitHub account password is not accepted as a Git command-line password; use a personal access token, GitHub CLI, or SSH if prompted.

## 3. Invite your friend

1. Open the private repository on GitHub.
2. Select **Settings**.
3. In the left sidebar, select **Collaborators** under **Access**.
4. Select **Add people**.
5. Enter your friend's GitHub username or email and send the invitation.
6. Your friend must accept the invitation before the repository is visible to them.

## 4. How your friend runs it

Your friend needs Node.js 22+, Python 3.11+, `uv`, and Ollama if they want the local models. After accepting the invitation:

```bash
git clone https://github.com/YOUR-USERNAME/doorlight-a2a.git
cd doorlight-a2a
npm install
uv sync
cp .env.example .env
npm run dev
```

They must install their own Ollama models:

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5vl:7b
```

The models and your Gemini key are not uploaded to GitHub.

## Later updates

After changing the project, upload a new snapshot with:

```bash
git add .
git commit -m "Describe what changed"
git push
```

Before every commit, use `git status` and confirm that `.env`, `.venv`, `node_modules`, `backend/doorlight.db`, `backend/.cache`, and `dist` are not listed under files to be committed.
