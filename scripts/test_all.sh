#!/usr/bin/env bash
# Run each capability package's pytest suite from inside that package.
#
#   bash scripts/test_all.sh [<包名>…] [-- <pytest 参数>]
#
# With no package names, every packages/capabilities/dataagent-*/tests
# directory is run. A package's own extras / dependency groups are used:
# `--extra dev` when [project.optional-dependencies].dev is declared and
# `--group dev` when [dependency-groups].dev is declared. `--frozen` keeps
# the checkout clean: the test environment is installed from that package's
# uv.lock, never re-locked from the repository root.
#
# dataagent-cli ships no pyproject.toml (it is a POSIX sh bundle); its
# stdlib unittest suite is still run through pytest in an isolated uv
# environment so that `-- <pytest 参数>` works the same for every package.
#
# Browser acceptance tests need
# packages/capabilities/dataagent-workbench/web/node_modules/playwright.
# A clean checkout has no node_modules: those named tests are deselected and
# reported (not silently skipped). Run `npm ci` in that web directory first
# to include them.
#
# The dataagent-cli real-Mint tests install the s0 preset, whose data-layer
# dependency is the gitignored dataagent-data/packaging/bundle. The runner
# stages that bundle before the CLI suite.
set -uo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CAP_DIR=${CAP:-packages/capabilities}
case $CAP_DIR in
    /*) ;;
    *) CAP_DIR="$ROOT/$CAP_DIR" ;;
esac

usage() {
    sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
}

die() {
    echo "test_all: $*" >&2
    exit 2
}

# section_keys <pyproject> <section>: bare keys declared in a TOML section.
# The section name is passed without brackets, e.g. project.optional-dependencies.
section_keys() {
    awk -v section="$2" '
        /^[[:space:]]*\[/ {
            heading = $0
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", heading)
            in_section = (heading == "[" section "]")
            next
        }
        in_section && /^[[:space:]]*[A-Za-z0-9_-]+[[:space:]]*=/ {
            key = $0
            sub(/[[:space:]]*=.*/, "", key)
            print key
        }
    ' "$1"
}

has_dev() {
    keys=$(section_keys "$1" "$2")
    printf '%s\n' "$keys" | grep -qx 'dev'
}

tests_import() {
    grep -RqsE "^[[:space:]]*(from|import)[[:space:]]+$2" "$1/tests"
}

# dataagent-cli's real-Mint tests install dataagent-s0, whose data-layer
# dependency is the generated packaging/bundle. It is gitignored, so a clean
# checkout has no data bundle even though the application and governance
# bundles are tracked. Stage it before the CLI suite.
stage_cli_fixtures() {
    local pkg_dir=$CAP_DIR/dataagent-data
    [ -d "$pkg_dir" ] || die "dataagent-data not found (needed by dataagent-cli tests)"
    echo "staging $pkg_dir/packaging/bundle for CLI manifest tests" >&2
    (cd "$pkg_dir" && uv run --frozen python scripts/build_bundle.py) \
        || die "failed to stage the data bundle for dataagent-cli tests"
}

[ -d "$CAP_DIR" ] || die "capability directory not found: $CAP_DIR"
command -v uv >/dev/null 2>&1 || die "uv not found on PATH"

# The scenarios browser test defaults to Playwright's bundled Chromium, but
# `npm ci` (the documented web prerequisite) does not download it. Use the
# system Chrome channel when the caller has not chosen one; operations' GUI
# tests already request channel "chrome" explicitly.
export DATAAGENT_CHROMIUM_CHANNEL=${DATAAGENT_CHROMIUM_CHANNEL:-chrome}

packages=()
pytest_args=()
while [ $# -gt 0 ]; do
    case $1 in
        --)
            shift
            pytest_args=("$@")
            break
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            name=$1
            case $name in
                dataagent-*) candidate=$name ;;
                *) candidate=dataagent-$name ;;
            esac
            [ -d "$CAP_DIR/$candidate" ] || die "unknown package: $1"
            packages+=("$candidate")
            shift
            ;;
    esac
done

if [ ${#packages[@]} -eq 0 ]; then
    for tests_dir in "$CAP_DIR"/dataagent-*/tests; do
        [ -d "$tests_dir" ] || continue
        packages+=("$(basename "$(dirname "$tests_dir")")")
    done
fi

[ ${#packages[@]} -gt 0 ] || die "no packages with tests under $CAP_DIR"

failed=()
summaries=()

for pkg in "${packages[@]}"; do
    dir=$CAP_DIR/$pkg
    [ -d "$dir" ] || die "package directory not found: $pkg"
    [ -d "$dir/tests" ] || die "package has no tests directory: $pkg"

    if [ "$pkg" = dataagent-cli ]; then
        stage_cli_fixtures
    fi

    cmd=(uv run)
    if [ -f "$dir/pyproject.toml" ]; then
        cmd+=(--frozen)
        if has_dev "$dir/pyproject.toml" 'project.optional-dependencies'; then
            cmd+=(--extra dev)
        fi
        if has_dev "$dir/pyproject.toml" 'dependency-groups'; then
            cmd+=(--group dev)
        fi
        # Test-only HTTP fixture imports that the package's dev extra does
        # not declare yet. The overlay keeps the clean-checkout suite
        # runnable without re-locking the package (the declaration belongs
        # to that package, not to this runner).
        if tests_import "$dir" fastapi; then
            cmd+=(--with 'fastapi>=0.115,<1')
        fi
        if tests_import "$dir" httpx; then
            cmd+=(--with 'httpx>=0.27,<1')
        fi
        if tests_import "$dir" uvicorn; then
            cmd+=(--with 'uvicorn>=0.30,<1')
        fi
    else
        # No project to lock against: keep pytest itself in an isolated,
        # version-bounded environment. The package tests are stdlib-only.
        cmd+=(--no-project --with 'pytest>=8,<9')
    fi
    cmd+=(python -m pytest -p no:cacheprovider)

    # Browser acceptance tests need the workbench web node_modules
    # (playwright), which a clean checkout does not contain. Skip only
    # those named tests and say so; every other test still runs.
    deselects=()
    browser_module=$CAP_DIR/dataagent-workbench/web/node_modules/playwright
    if [ ! -e "$browser_module" ]; then
        case $pkg in
            dataagent-operations)
                deselects+=(
                    --deselect tests/test_channel_switch.py::test_unknown_api_submission_is_reconciled_by_read_only_browser
                    --deselect tests/test_gui_workflow.py::test_observes_real_page_and_detects_changed_required_field
                    --deselect tests/test_gui_workflow.py::test_browser_blocks_unapproved_requests_and_rejects_hidden_status
                )
                echo "$pkg: skipping 3 browser tests (missing $browser_module)" >&2
                ;;
            dataagent-scenarios)
                deselects+=(
                    --deselect tests/test_business_system_fixture.py::test_browser_creates_attaches_and_submits_shared_record
                )
                echo "$pkg: skipping 1 browser test (missing $browser_module)" >&2
                ;;
        esac
    fi

    log=$(mktemp "${TMPDIR:-/tmp}/dataagent-test-all.XXXXXX") || die "mktemp failed"

    echo "=== $pkg"
    if (cd "$dir" && "${cmd[@]}" ${deselects[@]+"${deselects[@]}"} ${pytest_args[@]+"${pytest_args[@]}"}) >"$log" 2>&1; then
        rc=0
    else
        rc=$?
    fi

    if [ "$rc" -eq 0 ]; then
        count=$(grep -Eo '[0-9]+ passed' "$log" | tail -1 | grep -Eo '[0-9]+' || true)
        [ -n "$count" ] || count=0
        summary=$(grep -E 'passed|no tests ran' "$log" | tail -1 | sed -E 's/^[=[:space:]]+//; s/[=[:space:]]+$//')
        [ -n "$summary" ] || summary="$count passed"
        echo "$pkg: $summary"
        summaries+=("$pkg: $count passed")
    else
        echo "$pkg: FAILED (exit $rc)" >&2
        cat "$log" >&2
        summaries+=("$pkg: FAILED (exit $rc)")
        failed+=("$pkg")
    fi
    rm -f "$log"
done

echo
echo "test_all summary"
for line in "${summaries[@]}"; do
    echo "  $line"
done

if [ ${#failed[@]} -ne 0 ]; then
    echo "test_all: ${#failed[@]} package(s) failed: ${failed[*]}" >&2
    exit 1
fi
echo "test_all: all ${#packages[@]} package(s) passed"
