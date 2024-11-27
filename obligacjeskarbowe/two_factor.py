from dataclasses import dataclass
import datetime
import json
import re

import requests


@dataclass
class Token:
    operacja_nr: int
    data: datetime.date
    kod: int


class Open:
    pass


PAT = re.compile(
    r"^Operacja nr (\d+) z (\d{2}-\d{2}-\d{4}); Logowanie do Serwisu obligacyjnego - kod SMS: (\d+)$"
)


def wait_for_token(topic):
    resp = requests.get(f"https://ntfy.sh/{topic}/json", stream=True)
    for line in resp.iter_lines():
        json_data = json.loads(line.decode("utf-8"))
        if json_data["event"] == "open":
            print(f"Notification stream is open...")
            yield Open()

        elif json_data["event"] == "message":
            message = json_data["message"]
            print(f"Received message: {line!r}...")
            if m := PAT.match(message):
                operacja_nr, data, kod = m.groups()
                yield Token(
                    int(operacja_nr),
                    datetime.datetime.strptime(data, "%d-%m-%Y").date(),
                    int(kod),
                )
        else:
            raise RuntimeError(f"Unknown event received: {json_data!r}")
