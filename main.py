import argparse

from app import SMSApp
from db.database import initialise_database, seed_demo_data


def main() -> None:
    parser = argparse.ArgumentParser(prog="sms", description="Society Management System (TUI)")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="seed the database with sample data before starting",
    )
    args = parser.parse_args()

    initialise_database()
    if args.demo:
        seed_demo_data()

    SMSApp().run()


if __name__ == "__main__":
    main()