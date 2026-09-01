# AI

A collection of custom AI agent skills.

## Installation

Clone the repo, then run the installation script to symlink all skills into a destination folder.

**macOS / Linux**
```bash
./install.sh /path/to/dist
```

**Windows (PowerShell)**
```powershell
.\install.ps1 -Dist C:\path\to\dist
```

The script skips any skill that already exists in the destination folder.

## Structure

```
skills/       # Custom skill definitions for AI agents
install.sh    # Install script for macOS / Linux
install.ps1   # Install script for Windows
```

## Skills

| Skill                  | Description                                                                                      | Status   |
|------------------------|--------------------------------------------------------------------------------------------------|----------|
| confluence-to-markdown | Converts a Confluence page to Markdown.                                                          | `Stable` |
| figma                  | Use the Figma MCP server for Figma-driven implementation.                                        | `Beta`   |
| fix-defect             | Fixes a defect tracked by a Jira ticket.                                                         | `Stable` |
| implement-design       | Implements a feature from a design document referenced by a Confluence page or a Mark down file. | `Alpha`  |
| polish-docs            | Polishes documents to ensure clear structure and fluent wording.                                 | `Stable` |
