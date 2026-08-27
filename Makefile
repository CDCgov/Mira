# MIRA dev convenience targets.
#
#   make test-dev            # compile mira-oxide, bring up the dev stack, rerun all local runs
#   make test-dev-list       # just list the runs + commands that would execute
#   make test-dev ARGS="--skip-build --filter '*Flu-Illumina*'"
#
# All work is done by ./test-dev.sh; ARGS is forwarded to it.

ARGS ?=

.PHONY: test-dev test-dev-list

test-dev:
	./test-dev.sh $(ARGS)

test-dev-list:
	./test-dev.sh --list $(ARGS)
