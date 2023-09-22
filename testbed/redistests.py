from time import sleep

from cykubedrunner.common.redisutils import sync_redis


def check_connection_refused():
    redis = sync_redis()
    while True:
        try:
            redis.set('testkey', '100')
            print("set")
        except Exception as ex:
            print(f'Failed: {ex}')

        sleep(10)


if __name__ == '__main__':
    check_connection_refused()


