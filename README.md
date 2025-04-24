obligacjeskarbowe
====

This is a command line tool to manage your account on https://www.obligacjeskarbowe.pl.

# Why

The motivation to develop this program is the lack of available automation on the government website. I want my bonds to be purchased automatically at the same day each month, so when the bonds will start to expire years later my future-self will appreciate that the money flows at the same day each month.

In case of ROS/ROD bonds you'll have to always remember each month for 18 years to purchase them. That's a lot of mental effort, and quite depressing at the same time if you think about it. I'd rather maintain this tool, and adapt it once there are changes on the government website.

# What works

- [x] Log in through "Bank Polski" credentials (this link: https://www.zakup.obligacjeskarbowe.pl/login.html)
- [x] List your bonds portfolio
- [x] List available bonds in 500+ program ("Rodzinne Obligacje Skarbowe")
- [x] Buy ROS, ROD ("Rodzinne Obligacje Skarbowe")
- [ ] Log in through "Bank Pekao" credentials (this link: https://www.pekao.com.pl/obligacje-skarbowe).
- [x] Buy OTS, ROR, DOR, TOS, COI, EDO series ("obligacje Skarbu Państwa")
- [ ] Konto IKE-Obligacje

# How to use

```
Usage: python -m obligacjeskarbowe [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  bonds           List all currently available bonds.
  buy             Performs automatic purchase of a most recent bond i.e.
  history         History of dispositions on your account.
  login           Login to Obligacje Skarbowe.
  logout          Logout from Obligacje Skarbowe.
  portfolio       List all bonds in your portfolio.
  verify-800plus  Verifies if you can buy 800+ bonds.
```

# How to setup automated purchase

If you want to automatically purchase ROD bonds at 10th of each month...

1. Set up `OBLIGACJESKARBOWE_USERNAME` and `OBLIGACJESKARBOWE_PASSWORD` env vars.
2. Set up a topic on https://ntfy.sh with a randomized name. Keep in mind, that the 2FA messages will be delivered here unencrypted so keep this private.

    ```sh
    export OBLIGACJESKARBOWE_NTFY_TOPIC="YOURTOPIC"
    ```

3. Set up an automated bank transfer earlier than intended automatic purchase date (i.e. 1st of Month).
4. Set up another cron job that will run 10th each month that will purchase bonds from a specified series:

   ```sh
   uv run -m obligacjeskarbowe buy --symbol ROS --amount 16
   ```

   This will select first bond from available list of bonds "ROS" and purchase 16 of them. There are some validation checks to ensure a correct bond will be purchased i.e. sufficient balance etc.

You can tweak the dates above so you don't send the money too early, or too late. It depends on your bank's capabilities and your willingness to give away your cash too early.
