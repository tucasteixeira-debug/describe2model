# Documentation

This is the deep dive — the idea and the mechanism behind it, in full. If you're looking for the pitch, the motivation, or the example, the root [README](../README.md) is the place to start instead.

## Contents

| Page | What's in it |
|---|---|
| [`yaml-guide.md`](yaml-guide.md) | How to go from a plain-English description to a working YAML file: the file's sections, the JsonLogic-style expression syntax, every operation and function-block type, and the patterns that keep you out of dependency-cycle trouble. |
| [`engine-internals.md`](engine-internals.md) | How the engine actually executes a YAML file: building the dependency graph, topological sorting, the scan-cycle loop, and the same-scan-cycle rule — what it is and why it exists. |

Start with the YAML guide if you want to describe a system of your own. Start with engine internals if you want to understand what's actually happening under the hood first.