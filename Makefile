# Small native-shell bootstrap; lifecycle and dependency logic live in Python.
.DEFAULT_GOAL := run
ifeq ($(OS),Windows_NT)
SHELL := cmd.exe
.SHELLFLAGS := /d /c
export PYTHON_MANAGER_AUTOMATIC_INSTALL := false
export PYLAUNCHER_ALLOW_INSTALL :=
PYTHON ?= $(or $(shell py -3 -c "import sys; print(sys.executable)" 2>NUL),$(shell python -c "import sys; print(sys.executable)" 2>NUL))
else
PYTHON ?= $(or $(shell python3 -c "import sys; print(sys.executable)" 2>/dev/null),$(shell python -c "import sys; print(sys.executable)" 2>/dev/null))
endif
ifeq ($(strip $(PYTHON)),)
$(error Python is missing. Install Python 3.12+ from python.org; see docs/launcher.md)
endif

.PHONY: run setup backend frontend test lint build check help
run setup backend frontend test lint build check help:
	@"$(PYTHON)" scripts/dev.py $@ --via-make
