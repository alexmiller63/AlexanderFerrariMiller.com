    diagnostic_print(f"Generated collision-free Planet Finders for ISO {year}-W{week:02d} from internal calculations")


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--current", action="store_true", help="generate the current UTC ISO week")
    g.add_argument("--year", type=int, help="ISO week-year")
    p.add_argument("--week", type=int, help="ISO week number; required with --year")
    p.add_argument("--diagnostic-level", type=int, default=None, metavar="N", help="diagnostic verbosity: 0=silent, 1=major events, 2=search detail, 3=forensic detail")
    args = p.parse_args()
    if args.year is not None and args.week is None:
        p.error("--week is required with --year")
    return args


def main():
    args = parse_args()
    if args.diagnostic_level is not None:
        if args.diagnostic_level < 0:
            raise SystemExit("--diagnostic-level must be zero or greater")
        os.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = str(args.diagnostic_level)
    if args.current:
        today = date.today()
        iso = today.isocalendar()
        year, week = iso.year, iso.week
    else:
        year, week = args.year, args.week
    generate_week(year, week)


if __name__ == "__main__":
    main()