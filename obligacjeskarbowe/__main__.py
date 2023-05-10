import os
from client import ObligacjeSkarbowe


def main():
    username = os.environ['USERNAME']
    password = os.environ['PASSWORD']
    client = ObligacjeSkarbowe(username, password)

    client.login()
    try:
        pass
    finally:
        client.logout()


if __name__ == "__main__":
    main()
