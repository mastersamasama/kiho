# kiho marketplace

A [Claude Code plugin marketplace](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces) hosting the **kiho** plugin and future sibling plugins from the same authoring line.

## Installation

Add this marketplace to Claude Code, then install a plugin from it:

```bash
# 1. Register the marketplace
/plugin marketplace add mastersamasama/kiho

# 2. Install a plugin from it
/plugin install kiho@kiho
```

Or browse and install interactively via `/plugin`.

## Plugins

| Plugin | Version | Description |
| ------ | ------- | ----------- |
| [`kiho`](./plugins/kiho) | 5.21.0 | Single-entry multi-agent orchestration harness — Ralph-style CEO loop, three-tier storage doctrine, cycle-runner kernel. Entry point: `/kiho`. |

## Repository layout

```
.
├── .claude-plugin/
│   └── marketplace.json       # marketplace manifest (this file lists the plugins)
├── plugins/
│   └── kiho/                  # the kiho plugin
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── agents/
│       ├── bin/
│       ├── hooks/
│       ├── references/
│       ├── skills/
│       ├── templates/
│       ├── CHANGELOG.md
│       ├── CLAUDE.md
│       └── README.md
└── README.md                  # this file
```

## Authoring

- Marketplace manifest: `.claude-plugin/marketplace.json`
- Per-plugin manifest: `plugins/<name>/.claude-plugin/plugin.json`
- To add a plugin: drop it under `plugins/<name>/`, then append an entry to the `plugins` array in `marketplace.json`.

## License

MIT. See individual plugins for their own license declarations.
