import pandas as pd
import time
import os

file_path = "./shared_file.txt"

with open(file_path, "w") as f:
    f.write("0")

for filename in os.listdir('./key/'):
    fn = os.path.join('./key/', filename)
    try:
        if os.path.isfile(fn):
            os.remove(fn)
    except Exception as e:
        print(f"Error deleting file: {fn}\n{e}")

try:
    os.remove('serverx_blockchain')
    os.remove('servery_blockchain')
    os.remove('serverz_blockchain')
    os.remove('serverw_blockchain')
    os.remove('serverr_blockchain')
except FileNotFoundError:
    print(f"Path does not exist")

time.sleep(1)
os.system('start cmd /K "python server.py x"')
time.sleep(1)
os.system('start cmd /K "python server.py y"')
time.sleep(1)
os.system('start cmd /K "python server.py z"')
time.sleep(1)
os.system('start cmd /K "python server.py w"')
time.sleep(1)
os.system('start cmd /K "python server.py r"')
# time.sleep(1)
# os.system('start cmd /K "python client.py b"')
# time.sleep(1)
# os.system('start cmd /K "python client.py c"')
