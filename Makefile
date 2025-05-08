# Makefile

# Define source directories (hardcoded)
DIRS := . image_input_service face_analysis_service data_storage_service proto_files

# Define proto files directory
PROTO_DIR := proto_files

# Define output directories for generated Python files
IMAGE_INPUT_PROTO_OUT := image_input_service/proto_generated
FACE_ANALYSIS_PROTO_OUT := face_analysis_service/proto_generated
DATA_STORAGE_PROTO_OUT := data_storage_service/proto_generated

# Define formatting tool (e.g., autopep8, black)
FORMATTER := black

# Define cleaning tool (e.g., autopep8 with --in-place and --aggressive)
CLEANER := autopep8

# Define aggressive cleaning options (if applicable)
CLEANER_OPTIONS := --in-place --aggressive --aggressive

# Define a virtual environment name (optional)
VENV_NAME := .venv

# Activate virtual environment (if applicable)
ACTIVATE_VENV := source $(VENV_NAME)/bin/activate

# Detect the operating system
OS := $(shell uname -s 2>/dev/null || echo Unknown)

# Define commands based on the OS
ifeq ($(OS),Windows_NT)
    DEL := del /q
    RMDIR := rd /s /q
    FIND := where
    FIND_ARGS :=
    DELETE_ARGS :=
else
    DEL := rm -f
    RMDIR := rm -rf
    FIND := find
    FIND_ARGS := -print0
    DELETE_ARGS := -print0 | xargs -0
endif

# Targets
.PHONY: all format clean cleanall install venv help proto

all: format install proto  # add proto

format: ## Format the code in all directories
	@echo "Formatting code in all directories..."
	@for dir in $(DIRS); do \
		echo "Formatting $$dir"; \
		$(FORMATTER) $$dir/*.py; \
	done

clean: ## Clean the code in all directories using $(CLEANER)
	@echo "Cleaning code in all directories..."
	@for dir in $(DIRS); do \
		echo "Cleaning $$dir"; \
		$(CLEANER) $(CLEANER_OPTIONS) $$dir/*.py; \
	done

install: ## Install dependencies in all directories
	@echo "Installing dependencies..."
	@python -m pip install --upgrade pip
	@echo "Installing all dependencies in all directories..."
	@for dir in $(DIRS); do \
		if [ -f "$$dir/requirements.txt" ]; then \
			echo "Installing dependencies in $$dir from requirements.txt"; \
			(cd "$$dir" && $(INSTALLER) requirements.txt); \
		else \
			echo "No requirements.txt found in $$dir, skipping"; \
		fi; \
	done

cleanall: ## Remove all generated files (excluding virtual environment), cleaning each directory's cache
	@echo "Removing generated files and cleaning caches..."
	@for dir in $(DIRS); do \
		echo "Cleaning $$dir"; \
		$(FIND) "$$dir" -name "*.pyc" $(FIND_ARGS) | xargs $(DELETE_ARGS) $(DEL); \
		if [ -d "$$dir/__pycache__" ]; then $(RMDIR) "$$dir/__pycache__"; fi; \
		if [ "$$dir" != "." ]; then \
			$(FIND) "$$dir" -name "*.log" $(FIND_ARGS) | xargs $(DELETE_ARGS) $(DEL); \
			if [ -d "$$dir/.pytest_cache" ]; then $(RMDIR) "$$dir/.pytest_cache"; fi; \
			if [ -d "$$dir/.mypy_cache" ]; then $(RMDIR) "$$dir/.mypy_cache"; fi; \
		fi; \
	done

venv: ## Create a virtual environment
	@echo "Creating virtual environment..."
	@python -m venv $(VENV_NAME)

help: ## Display this help message
	@$(MAKE) -pRrq : | awk -v RS= -F: '/^# File[^.]*Makefile$$/ {getline;while($$0 !~ /^$$/) {print substr($$0,3);getline}}'

proto: ## Generate gRPC files and copy to services
	@echo "Generating gRPC files and copying..."
	@python proto_generator.py