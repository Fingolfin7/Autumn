"""Shared Click option decorators so filters look the same on every command."""

from __future__ import annotations

from typing import Any, Callable, Optional

import click

from .periods import normalize_period, parse_date_arg


PERIOD_HELP = "today, yesterday, week, fortnight, month, quarter, year, all (or d/w/m/q/y)"


class PeriodType(click.ParamType):
    """A period name, accepting short aliases such as ``w`` or ``2w``."""

    name = "PERIOD"

    def convert(self, value: Any, param: Optional[click.Parameter], ctx: Optional[click.Context]) -> str:
        period = normalize_period(str(value))
        if period is None:
            self.fail(f"'{value}' is not a period. Use {PERIOD_HELP}.", param, ctx)
        return period


PERIOD = PeriodType()


def _date_callback(ctx: click.Context, param: click.Parameter, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        return parse_date_arg(value)
    except ValueError as error:
        raise click.BadParameter(str(error)) from None


def period_option(default: Optional[str] = None, help_suffix: str = "") -> Callable:
    return click.option(
        "--period",
        "-P",
        type=PERIOD,
        default=default,
        help=f"Time period: {PERIOD_HELP}{help_suffix}",
    )


def date_range_options(fn: Callable) -> Callable:
    """Add ``--since/--start-date`` and ``--until/--end-date`` with natural dates."""
    fn = click.option(
        "--until",
        "--end-date",
        "end_date",
        callback=_date_callback,
        help="End date (inclusive); same formats as --since",
    )(fn)
    fn = click.option(
        "--since",
        "--start-date",
        "start_date",
        callback=_date_callback,
        help="Start date: YYYY-MM-DD, yesterday, monday, '3d ago', -2w",
    )(fn)
    return fn


def search_options(what: str = "sessions") -> Callable:
    """Add ``-q/--search`` and ``--related`` (meaning-based matches)."""

    def decorate(fn: Callable) -> Callable:
        fn = click.option(
            "--related",
            is_flag=True,
            help=(
                f"With --search, also include {what} that match by meaning "
                "(needs AI features and an OpenAI key on your account)"
            ),
        )(fn)
        fn = click.option(
            "--search",
            "-q",
            help="Search project names, subproject names and session notes",
        )(fn)
        return fn

    return decorate
