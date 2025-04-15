#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exporter cli
"""
from export import *

def main():
    parser = argparse.ArgumentParser(description="Location updater utility.")
    parser.add_argument('--update', action='store_true', help="Update the database with new location data.")
    parser.add_argument('--upload', action='store_true', help="Ensure all positions are uploaded.")

    args = parser.parse_args()
    updater = LocationUpdater()

    if args.update:
        updater.update_database()

    if args.upload:
        results = updater.ensure_all_positions_uploaded()
        print(f"{len(results)} entries processed for upload.")

    if not args.update and not args.upload:
        print("No action specified. Use --update or --upload.")

if __name__ == "__main__":
    main()
