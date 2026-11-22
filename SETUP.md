# Setting up your computer for the workshop

Please do this **before the workshop**. It takes about 15–20 minutes and needs an internet connection. You will install three things:

| Tool | What it is for |
|---|---|
| **Git** | Downloads the workshop project and keeps track of changes to it |
| **uv** | Installs Python and the project's packages, and runs the project's scripts |
| **Kilo Desktop** | The AI coding agent you will work with |

You do **not** need to install Python yourself. uv does it for you.

Commands below are typed in a **terminal**:

- **macOS:** the *Terminal* app.
- **Windows:** *PowerShell*, found in the Start menu.
- **Linux:** any terminal.

After installing each tool, **close the terminal and open a new one** so that it finds the tool.

---

## 1. Git

**Check first:** you may already have it. Type `git --version`. If it prints a version number (2.17 or higher), skip to step 2.

- **macOS:** type `xcode-select --install` and confirm the dialog. Or, if you use Homebrew: `brew install git`.
- **Windows:** download and run **Git for Windows** from <https://git-scm.com/downloads/win>. The default options are fine.
- **Linux:** use your package manager, e.g. `sudo apt install git` (Debian/Ubuntu) or `sudo dnf install git` (Fedora).

More options: <https://git-scm.com/downloads>

**Check:** `git --version`

## 2. uv

- **macOS / Linux:**
  ```
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows (PowerShell):**
  ```
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Alternatives: `brew install uv` (macOS) or `winget install --id=astral-sh.uv -e` (Windows). Full instructions: <https://docs.astral.sh/uv/getting-started/installation/>

**Check:** `uv --version`

## 3. Kilo Desktop

1. Download the installer for your system from <https://kilo.ai/install>, run it, and start Kilo Desktop. Installation guide: <https://kilo.ai/docs/desktop/installation>
2. On first start, accept the terms. When asked to **Connect to Kilo**, you can **skip**: a Kilo account is not needed, because we use the university's AI service instead.

> **Mac users:** Kilo Desktop runs only on Apple Silicon Macs (M1 or later). If your Mac has an Intel processor, tell the organisers in advance.

### Connect Kilo to the university AI service

You will receive the **address (base URL)**, your **API key** and the **model name(s)** from the organisers.

1. In Kilo Desktop, open **Settings** (gear icon at the bottom of the sidebar) → **AI settings**.
2. In **AI Providers**, choose **Add AI Provider** → **Add a Custom AI Provider**.
3. Fill in:
   - **Provider name:** e.g. `University`
   - **API format:** **OpenAI Compatible**
   - **Base URL:** the address you received
   - **API key:** your key
   - **Model ID(s):** the model name(s) you received
4. Save. The models now appear in the model picker under the chat box.

Your API key is personal. Do not share it, and do not paste it into project files.

Details: <https://kilo.ai/docs/desktop/settings/ai>

---

## 4. Get the workshop project and test everything

In a terminal, go to a folder where you want to keep the project (e.g. `cd Documents`), then:

```
git clone <REPOSITORY-URL>
cd <REPOSITORY-FOLDER>
uv sync
```

`uv sync` installs the right Python version and all packages the project needs. The first run takes a minute.

Finally, in Kilo Desktop, create a workspace with the project folder (**Create workspace** → select the folder). Select the Model ID that you entered when setting up the university AI service. Then send a short message in the chat, e.g. *"What is this project?"* If you get an answer, you are ready.

## Something didn't work?

- **"command not found" / "not recognized":** close the terminal, open a new one and try again. If that doesn't help, restart the computer.
- **Still stuck?** Write to the organisers before the workshop, and include the exact error message (a screenshot is fine).
