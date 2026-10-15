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
- [x] Scrap bonds issuance letters and download PDFs (both obligacjeskarbowe.pl and finanse.mf.gov.pl as a backup)

# How to use

```
Usage: python -m obligacjeskarbowe [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  bonds           List all currently available bonds.
  buy             Buy the most recent bond, confirming each step.
  history         History of dispositions on your account.
  login           Login to Obligacje Skarbowe.
  logout          Logout from Obligacje Skarbowe.
  portfolio       List all bonds in your portfolio.
  status          Show the account balance available for bond purchases.
  verify-800plus  Compare estimated 500+/800+ entitlement with purchases and cash.
```

Check the cash balance available for buying bonds using the saved session:

```sh
uv run -m obligacjeskarbowe status
```

If a saved session is rejected with HTTP 401 or 403, run `login` again. The login
command starts a fresh session when the saved one is rejected and verifies access
to the portfolio before reporting success. All other HTTP 4xx responses report
the status code and request path while preserving the session. Failed purchase
requests are not automatically retried.

# Verifying the 500+/800+ balance

```sh
uv run -m obligacjeskarbowe verify-800plus
uv run -m obligacjeskarbowe verify-800plus --through-month 2026-09
```

Using `800plus.toml`, this estimates benefits from birth through the selected month
(inclusive, defaulting to the current month), assuming continuous eligibility.
The birth month is prorated and rounded up to 0.10 PLN; full months use 500 PLN
through December 2023 and 800 PLN from January 2024. Whole bonds are rounded down.

The report compares the estimated benefits minus previous ROS/ROD purchases with
the actual cash balance. It shows the remaining family-bond limit, the number of
bonds affordable with the current balance, and the cash needed to buy the entire
remaining limit. The expected balance assumes all benefits were transferred to
the bond account. A difference alone does not establish a missed bank transfer.

Use `--through-month` to exclude benefits for a month not yet paid or transferred.
Only the benefit cutoff changes; purchases and cash are fetched from the account
at the time the command runs. `--dry-run` calculates benefits without accessing
the account.

# Buying bonds

```sh
uv run -m obligacjeskarbowe buy --symbol ROS --amount 16
```

The command asks for keyboard confirmation before each of the three purchase steps.
Answer `y` to proceed; `n`, Enter, or end of input cancels the operation before that
step. The final step shows the number of bonds, issue, total cost, and a warning
that the purchase is irreversible.

After the first confirmation, the command displays the issue code, full name,
interest rate, nominal value per bond, order quantity and value, the purchase
limit returned by the service, and the cash balance. It also shows how many whole
bonds can be bought within both the current balance and the service limit.
This summary is displayed before the second confirmation and also with `--force`.

Use `--force` to complete all steps without keyboard confirmations. The final
warning is still displayed, and balance and purchase limits are still checked.
Use `--dry-run` to list the matching issue without starting the purchase steps.

Previously, `--force` allowed orders exceeding the account balance. That behavior
is now available separately as `--allow-unpaid`, which still requires confirmations
unless combined with `--force`. Issuer purchase limits remain enforced.

# How to setup automated purchase

If you want to automatically purchase ROD bonds at 10th of each month...

1. Set up `OBLIGACJESKARBOWE_USERNAME` and `OBLIGACJESKARBOWE_PASSWORD` env vars.
2. Set up a topic on https://ntfy.sh with a randomized name. Keep in mind, that the 2FA messages will be delivered here unencrypted so keep this private.

    ```sh
    export OBLIGACJESKARBOWE_NTFY_TOPIC="YOURTOPIC"
    ```

    Now, set up Apple Shortcuts automation that will react upon an incoming SMS message that contains `Logowanie do Serwisu obligacyjnego - kod SMS:` that perform a HTTP request to `https://ntfy.sh/YOURTOPIC` posting a file, with content set to automation input. This should take the content of incoming message from `PKO BP BM` with 2FA message and post it to given ntfy.sh topic. This is a way to perform automated 2FA authentication.

    _I'm not an Android user and I'm not aware of a way to do this automatically on that platform._

3. Set up an automated bank transfer earlier than intended automatic purchase date (i.e. 1st of Month).
4. Set up another cron job that will run 10th each month that will purchase bonds from a specified series:

   ```sh
   uv run -m obligacjeskarbowe login
   uv run -m obligacjeskarbowe buy --symbol ROS --amount 16 --force
   ```

   This will select first bond from available list of bonds "ROS" and purchase 16 of them. There are some validation checks to ensure a correct bond will be purchased i.e. sufficient balance etc.

You can tweak the dates above so you don't send the money too early, or too late. It depends on your bank's capabilities and your willingness to give away your cash too early.

# Download letter of issuance PDFs

## Single letter of issuance

```sh
uv run -m obligacjeskarbowe download-pdf TZ1114 --path ~/Documents
```

This will contact `obligacjeskarbowe.pl` looking for letter of issuance. If not found (i.e. bond is obsolete) this tool will contact `finanse.mf.gov.pl` as a backup.

## Complete archive

Download complete archive of bonds listed on `obligacjeskarbowe.pl`

```sh
uv run -m obligacjeskarbowe download-archive --path ~/Documents
```
