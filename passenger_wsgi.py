import sys
import os

# Tambahkan path aplikasi ke sys.path
sys.path.insert(0, os.path.dirname(__file__))

from app import app as application
