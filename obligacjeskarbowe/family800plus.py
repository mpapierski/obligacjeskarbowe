from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


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
    return max(Decimal(0), shares.quantize(Decimal("1"), rounding=ROUND_FLOOR))


def calculate_total_compensation(config, as_of=None):
    """Estimate benefits through the month containing as_of, inclusive.

    Assumes continuous eligibility from birth. The birth month is prorated,
    followed by full months at 500 PLN through December 2023 and 800 PLN
    from January 2024. This estimates entitlement, not actual payments.
    """
    total_comp = Decimal(0)
    today = as_of if as_of is not None else datetime.now().date()
    end_month = next_comp_month(today)

    for kid in config["kids"]:
        birth_date = datetime.strptime(kid["birth_date"], "%Y-%m-%d").date()
        if birth_date > today:
            continue
        birth_month = datetime(
            year=birth_date.year, month=birth_date.month, day=1
        ).date()
        total_days = Decimal(days_in_month(birth_month))
        full_days = Decimal(days_in_month(birth_date))

        # Calculate the prorated first month payment
        if birth_date >= COMP_CHANGE_DATE:
            amount = Decimal(800)
        else:
            amount = Decimal(500)

        first_month = special_round_up(full_days / total_days * amount)
        total_comp += first_month

        first_comp_month = next_comp_month(birth_date)

        months_500plus = max(
            0, diff_month(min(end_month, COMP_CHANGE_DATE), first_comp_month)
        )
        months_800plus = max(
            0, diff_month(end_month, max(first_comp_month, COMP_CHANGE_DATE))
        )
        print(f'Kid {kid["name"]} 500+ months {months_500plus}')
        print(f'Kid {kid["name"]} 800+ months {months_800plus}')
        comp = months_500plus * Decimal(500) + months_800plus * Decimal(800)
        print(
            f'Kid {kid["name"]} total {comp:.2f} PLN (plus {first_month:.2f} PLN for the first month)'
        )
        total_comp += comp
    print(f"Total compensation: {total_comp:.2f} PLN")
    return total_comp
