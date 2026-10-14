"""Числа и даты человеческим языком: «через 5 дней», «2 месяца», «завтра»."""
from __future__ import annotations

from datetime import date

DAYS_IN_MONTH = 30
DAYS_IN_YEAR = 365


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19:
        return many
    n %= 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


def plural_days(n: int) -> str:
    return plural(n, "день", "дня", "дней")


def describe_duration(days: int) -> str:
    """5 → «5 дней», 30 → «1 месяц», 120 → «4 месяца», 365 → «1 год»."""
    if days >= DAYS_IN_YEAR:
        return "1 год"
    if days >= DAYS_IN_MONTH and days % DAYS_IN_MONTH == 0:
        months = days // DAYS_IN_MONTH
        return f"{months} {plural(months, 'месяц', 'месяца', 'месяцев')}"
    return f"{days} {plural_days(days)}"


def describe_interval(days: int) -> str:
    if days == 0:
        return "ещё раз сегодня"
    if days == 1:
        return "завтра"
    duration = describe_duration(days)
    return "через " + duration.removeprefix("1 ")  # «через месяц», «через год»


def describe_date(day: date, today: date) -> str:
    delta = (day - today).days
    if delta <= 0:
        return "сегодня"
    if delta == 1:
        return "завтра"
    return day.strftime("%d.%m.%Y")
