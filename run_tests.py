#!/usr/bin/env python3
"""
Test runner for CLI Chat application.
"""

import os
import sys
import unittest
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_tests(test_type=None):
    """Run the specified tests."""
    if test_type == "unit":
        # Run only unit tests
        test_suite = unittest.defaultTestLoader.discover("tests/unit")
    elif test_type == "encryption":
        # Run only encryption tests
        test_suite = unittest.defaultTestLoader.discover("tests/unit/utils", pattern="test_encryption.py")
    elif test_type == "file":
        # Run only file transfer tests
        test_suite = unittest.defaultTestLoader.discover("tests/unit/backend", pattern="test_file_transfer.py")
    elif test_type == "client":
        # Run only client tests
        test_suite = unittest.defaultTestLoader.discover("tests/unit/frontend", pattern="test_client_features.py")
    else:
        # Run all tests
        test_suite = unittest.defaultTestLoader.discover("tests")

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run tests for CLI Chat application.")
    parser.add_argument("--type", choices=["unit", "encryption", "file", "client"], 
                        help="Type of tests to run (default: all)")
    args = parser.parse_args()
    
    sys.exit(run_tests(args.type))
