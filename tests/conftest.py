import sys
import os

# Add project root to sys.path so 'from tools.X import ...' works in tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
