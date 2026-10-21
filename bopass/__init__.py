"""bopass: Automatic selection of compiler optimization passes using Bayesian Optimization."""

# Status values shared by every module.
OK = "OK"
COMPILE_ERROR = "COMPILE_ERROR"
COMPILE_TIMEOUT = "COMPILE_TIMEOUT"
RUN_CRASH = "RUN_CRASH"
RUN_TIMEOUT = "RUN_TIMEOUT"
WRONG_OUTPUT = "WRONG_OUTPUT"

STATUSES = (OK, COMPILE_ERROR, COMPILE_TIMEOUT, RUN_CRASH, RUN_TIMEOUT, WRONG_OUTPUT)
