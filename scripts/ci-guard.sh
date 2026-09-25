#!/usr/bin/env bash
# Accident prevention only: environment variables are not an isolation boundary.
require_hosted_ci() {
    if [[ ${GITHUB_ACTIONS:-} != true || ${RUNNER_ENVIRONMENT:-} != github-hosted || ${RUNNER_OS:-} != Linux || ${1:-} != --ci-only ]]; then
        echo 'Refusing container tests: use the GitHub-hosted Linux workflow, not a local or self-hosted runner.' >&2
        return 1
    fi
}
require_ci_container() {
    require_hosted_ci --ci-only || return
    if [[ ${SERVED_CI_CONTAINER:-} != true || ! -f /.dockerenv ]]; then
        echo 'This entrypoint runs only inside the disposable CI container.' >&2
        return 1
    fi
}
