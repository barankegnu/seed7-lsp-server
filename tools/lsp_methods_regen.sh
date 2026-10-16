#!/bin/sh
# Regenerate tools/lsp_methods.tsv -- the LSP methods a client may send this server.
#
# WHY. The inventory has to come from the spec's machine-readable model, not from its HTML page:
# the page renders method names inside markup tags, and scraping it recovered 4 of 20
# `textDocument/' methods (measured). metaModel.json lists every request and notification with its
# direction and its server capability, and gives all 75.
#
# HOW. python3 with the standard library only (json, urllib). Keeps entries in `requests' and
# `notifications' whose `messageDirection' is `clientToServer' or `both', takes `serverCapability'
# as the dotted path when the entry has one and `-' when it has none, sorts by method, and prints
# `method \t kind \t serverCapability' to stdout. `serverCapability' is a plain string in 3.18; the
# dict form ({"name": ...}) is folded to its name so a shape change in the file does not silently
# empty the third column.
#
# Not wired into `make test`, and it must not be: it fetches over the network. The committed
# tools/lsp_methods.tsv is the copy tools/project_graph.sh reads, and tests/graph_test.sh pins it.
#
# shortcut: frozen at 3.18 -- re-run this by hand when the target spec version changes, and review
#           the diff: a new method is a row in the graph, not a bug.
#
# Usage:  sh tools/lsp_methods_regen.sh > tools/lsp_methods.tsv

set -eu
LC_ALL=C
export LC_ALL

URL='https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/metaModel/metaModel.json'

python3 - "$URL" <<'PY'
import json
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=60) as response:
    model = json.load(response)

rows = []
for kind in ("request", "notification"):
    for entry in model[kind + "s"]:
        if entry.get("messageDirection") not in ("clientToServer", "both"):
            continue
        capability = entry.get("serverCapability")
        if isinstance(capability, dict):
            capability = capability.get("name")
        rows.append((entry["method"], kind, capability or "-"))

if not rows:
    sys.exit("metaModel shape changed: no entry matched messageDirection")

for method, kind, capability in sorted(rows):
    print("%s\t%s\t%s" % (method, kind, capability))
PY
