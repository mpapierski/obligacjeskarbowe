from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


def next_comp_month(d):
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    else:
        return date(d.year, d.month + 1, 1)


def days_in_month(d):
    next_month = next_comp_month(d)
    return (next_month - d).days


# Compensation was increased from 500 to 800+ in 2024
COMP_CHANGE_DATE = date(year=2024, month=1, day=1)  # Zmiana na 800+


def special_round_up(value):
    if not isinstance(value, Decimal):
        value = Decimal(value)
    return value.quantize(Decimal("0.1"), rounding=ROUND_CEILING)


def calculate_available_bonds(total_compensation, nominal_amount):
    shares = (total_compensation - nominal_amount) / 100
    return shares.quantize(Decimal("1"), rounding=ROUND_CEILING)


def calculate_total_compensation(config):
    # The "Rodzina 800+" program calculates family compensation for each child in two parts:
    #
    # 1. Prorated First Month Payment:
    #    - For the child's birth month, the program calculates a partial payment.
    #    - It does so by determining the number of days remaining in the birth month (full_days)
    #      versus the total number of days in that month (total_days).
    #    - Depending on whether the child was born before or after COMP_CHANGE_DATE (2024-01-01),
    #      the base rate is set to 500 PLN or 800 PLN respectively.
    #    - The prorated amount is computed as (full_days / total_days * base rate) and then rounded up.
    #
    # 2. Full Month Payments:
    #    - The program then calculates the number of full months eligible for compensation.
    #    - The months before the change (from the start of the month after birth up to COMP_CHANGE_DATE)
    #      use a rate of 500 PLN per month.
    #    - The months from the COMP_CHANGE_DATE up to the current date use a rate of 800 PLN per month.
    #
    # For each child, the total compensation is the sum of the prorated first month payment
    # and the full month payments computed using the respective rates.
    #
    # Detailed information (such as the number of 500+ and 800+ months and each component of the
    # child's compensation) is printed to the console, and the overall total compensation is returned.
    total_500plus_months = Decimal(0)
    total_800plus_months = Decimal(0)
    total_comp = Decimal(0)

    today = datetime.now().date()

    for kid in config["kids"]:
        birth_date = datetime.strptime(kid["birth_date"], "%Y-%m-%d").date()
        birth_month = datetime(
            year=birth_date.year, month=birth_date.month, day=1
        ).date()
        total_days = Decimal(days_in_month(birth_month))
        full_days = Decimal(days_in_month(birth_date))

        # Calculate the prorated first month payment
        if birth_date > COMP_CHANGE_DATE:
            amount = Decimal(800)
        else:
            amount = Decimal(500)

        first_month = special_round_up(full_days / total_days * amount)
        total_comp += first_month

        first_comp_month = next_comp_month(birth_date)

        months_500plus = diff_month(COMP_CHANGE_DATE, first_comp_month) + 1
        total_500plus_months += months_500plus
        months_800plus = diff_month(today, COMP_CHANGE_DATE)
        total_800plus_months += months_800plus
        print(f'Kid {kid["name"]} 500+ months {months_500plus}')
        print(f'Kid {kid["name"]} 800+ months {months_800plus}')
        comp = months_500plus * Decimal(500) + months_800plus * Decimal(800)
        print(
            f'Kid {kid["name"]} total {comp:.2f} PLN (plus {first_month:.2f} PLN for the first month)'
        )
        total_comp += comp
    print(f"Total compensation: {total_comp:.2f} PLN")
    return total_comp
