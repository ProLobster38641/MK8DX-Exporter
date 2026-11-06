#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf build/linux && mkdir -p build/linux && cp -r addon/mk8dx_szs_exporter build/linux/ && mkdir -p build/linux/mk8dx_szs_exporter/bin && cp cli/publish/linux-x64/mk8szs build/linux/mk8dx_szs_exporter/bin/
python3 mkzip.py build/linux/mk8dx_szs_exporter build/test_linux.zip
B=${BLENDER:-blender}
"$B" -b --factory-startup --command extension install-file -r user_default -e build/test_linux.zip
rm -rf "${TMPDIR:-/tmp}"/mk8dx_export_*
cd test && "$B" -b --factory-startup --python-exit-code 1 --python ${1:-blender_test.py} 2>&1 | grep -v "^$\|Deprecat\|use_nodes"
