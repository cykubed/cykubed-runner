from time import sleep

try:
    for i in range(0, 8):
        print(f'i={i}')
        sleep(2)
except KeyboardInterrupt:
    print("Interrupted - finishing")

