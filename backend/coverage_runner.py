"""Coverage runner that saves on exit via atexit."""
import os
import sys
import atexit
import coverage

# Start coverage
cov = coverage.Coverage(source=['.'], omit=['tests/*', 'coverage_runner.py'])
cov.start()

def save_coverage():
    print("\nSaving coverage data...")
    cov.stop()
    cov.save()
    print("Coverage data saved to .coverage")

atexit.register(save_coverage)

# Import server and run it
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'outpace_intelligence')
os.environ.setdefault('JWT_SECRET', 'coverage-only-jwt-secret-please-override')

import uvicorn
uvicorn.run("server:app", host="0.0.0.0", port=8001, log_level="info")
