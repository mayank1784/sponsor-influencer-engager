#!/bin/bash
#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Function to deactivate venv on exit
function deactivate_venv {
    if [ "$VIRTUAL_ENV" != "" ]; then
        deactivate
        echo "Deactivated virtual environment."
    fi
}

# Trap exit signals to ensure venv deactivation
trap deactivate_venv EXIT SIGINT SIGTERM

# Initialize the database if it doesn't exist
if [ ! -f "app.db" ]; then
    python init_db.py
fi

# Run the application
python run.py
