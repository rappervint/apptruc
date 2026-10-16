import sys
import os

# Đường dẫn thư mục ứng dụng
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Nạp ứng dụng Flask cho PythonAnywhere WSGI
from app import app as application

if __name__ == '__main__':
    application.run()
