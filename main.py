# This is a sample Python script.
import socket
# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

def handle_input():
    while True:
        data = input().split()
        if len(data) == 0:
            print("Invalid command. Valid inputs are 'connect', 'snapshot', 'loss', 'token', or 'exit'.")
        elif data[0] == "put" and len(data) == 3:
            print(f"put {data[1]} {data[2]}")
            print(type(data[1]))
        elif data[0] == "get" and len(data) == 2:
            print(f"get {data[1]}")
        else:
            print("Invalid command. Valid inputs are 'connect', 'snapshot', 'loss', 'token', or 'exit'.")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # handle_input()
    d = dict()
    d[1] = 1
    d[2] = 2
    print(type(d))
    str(d)
    print(type(d))

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
