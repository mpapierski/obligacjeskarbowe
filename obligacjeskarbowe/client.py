import requests


LOGIN_BATON = "Zaloguj"


class ObligacjeSkarbowe:
    def __init__(self, username, password):
        self.base_url = "https://www.zakup.obligacjeskarbowe.pl/"
        self.username = username
        self.password = password
        self.session = requests.Session()

    def login(self):
        r = self.session.get(self.base_url + "login.html")
        r.raise_for_status()
        form = {
            "username": self.username,
            "password": self.password,
            "baton": LOGIN_BATON,
        }
        r = self.session.post(self.base_url + "login", data=form)
        r.raise_for_status()
        self.session.cookies.set("obligacje_set", "none")

    def logout(self):
        r = self.session.get(self.base_url + "logout")
        r.raise_for_status()
