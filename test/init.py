import sys
import os


ROOT_PATH = '\\'.join(os.path.dirname(__file__).split('\\')[:-1])
sys.path.append(ROOT_PATH)