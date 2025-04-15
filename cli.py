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
    parser.add_argument('--run', action='store_true', help="Periodically run updater.run().")
    parser.add_argument('--interval', type=int, default=5, help="Interval in minutes for --run mode (default: 5).")

    args = parser.parse_args()
    updater = LocationUpdater()

    if args.update:
        updater.update_database()

    if args.upload:
        results = updater.ensure_all_positions_uploaded()
        print(f"{len(results)} entries processed for upload.")

    if args.run:
        interval_seconds = args.interval * 60
        job = CronJob(interval_seconds, updater.run)
        print(f"Starte CronJob: updater.run() alle {args.interval} Minuten.")
        job.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Beende CronJob...")
            job.stop()
            job.join()

    if not any([args.update, args.upload, args.run]):
        print("Keine Aktion angegeben. Nutze --update, --upload oder --run.")

if __name__ == "__main__":
    main()
