# Makefile

# Define source directories (hardcoded)
DIRS := . image_input_service face_analysis_service agender_analysis_service data_storage_service proto_files

# Define proto files directory
PROTO_DIR := proto_files

# Define output directories for generated Python files
IMAGE_INPUT_PROTO_OUT := image_input_service/proto_generated
FACE_ANALYSIS_PROTO_OUT := face_analysis_service/proto_generated
AGENDER_ANALYSIS_PROTO_OUT := agender_analysis_service/proto_generated
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

# User must set OS_TYPE to 'Windows' or 'Unix' below
# Example: OS_TYPE := Windows
OS_TYPE := Windows

# Validate OS_TYPE
ifndef OS_TYPE
$(error OS_TYPE is not set. Please edit the Makefile and set OS_TYPE to 'Windows' or 'Unix' (e.g., OS_TYPE := Windows))
endif
ifneq ($(OS_TYPE),Windows)
ifneq ($(OS_TYPE),Unix)
$(error OS_TYPE must be 'Windows' or 'Unix'. Got '$(OS_TYPE)')
endif
endif

# Define commands based on OS_TYPE
ifeq ($(OS_TYPE),Windows)
    DEL := del /q
    RMDIR := rd /s /q
    FIND := where
    FIND_ARGS :=
    DELETE_ARGS :=
    KILL := taskkill /IM python.exe /F
else
    DEL := rm -f
    RMDIR := rm -rf
    FIND := find
    FIND_ARGS := -print0
    DELETE_ARGS := -print0 | xargs -0
    KILL := pkill -f python
endif

# Targets
.PHONY: all format clean cleanall install venv help proto test

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
			python -m pip install -r $$dir/requirements.txt; \
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

test: ## Run tests
	@echo "Cleaning up previous test processes..."
	@-$(KILL) || echo "No Python processes to kill."
	@echo "Running tests..."
	@echo "Starting DataStorageService on port 60050 in background..."
	@python data_storage_service/data_storage_service.py --host localhost --port 60050 --mongo-host localhost --mongo-port 27017 --redis-host localhost --redis-port 6379 &
	@echo "Starting FaceAnalysisService on port 60052 in background..."
	@python face_analysis_service/face_analysis_service.py --address [::]:60052 --storage_address localhost:60050 --redis_host localhost --redis_port 6379 &
	@echo "Starting AgenderAnalysisService on port 60054 in background..."
	@python agender_analysis_service/agender_analysis_service.py --address [::]:60054 --storage_address localhost:60050 --redis_host localhost --redis_port 6379 &
	@echo "Starting ImageInputService on port 60053 in background..."
	@python image_input_service/image_input_service.py --face_analysis_address localhost:60052 --agender_analysis_address localhost:60054 --image_input_port 60053 &
	@sleep 10  # Give services time to start
	@echo "Running DataStorageService test client..."
	@python tests/test_client.py --image_input_address localhost:60053
	@echo "Cleaning up test processes..."
	@-$(KILL) || echo "No Python processes to kill."
	@echo "Testing complete."