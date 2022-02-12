#!/usr/bin/python3

import subprocess
import os
import json
from datetime import datetime
import plistlib
import logging.handlers
import traceback
import sys
import re
from pwd import getpwnam
import argparse

SETTINGS_DIR = os.path.expanduser("~") + '/.config/auto-selfcontrol'

# Configure global logger
LOGGER = logging.getLogger("Auto-SelfControl")
LOGGER.setLevel(logging.INFO)
handler = logging.handlers.SysLogHandler('/var/run/syslog')
handler.setFormatter(logging.Formatter(
    '%(name)s: [%(levelname)s] %(message)s'))
LOGGER.addHandler(handler)


def load_config(path):
    """Load a JSON configuration file"""
    config = dict()

    try:
        with open(path, 'rt', encoding="utf-8") as cfg:
            config.update(json.load(cfg))
    except ValueError as exception:
        exit_with_error(f'''The JSON config file {path} is not correctly formatted.
                        The following exception was raised:
                        \n{exception}''')

    return config


def run(settings_dir):
    """Load config and start SelfControl"""
    run_config = f"{settings_dir}/run_config.json"
    if not os.path.exists(run_config):
        exit_with_error(
            "Run config file could not be found in installation location, please make sure that you have Auto-SelfControl activated/installed")

    config = load_config(run_config)

    if check_if_running(config):
        print("SelfControl is already running, exit")
        LOGGER.error(
            "SelfControl is already running, ignore current execution of Auto-SelfControl.")
        exit(2)

    start_blocking(config, settings_dir)


def start_blocking(config, settings_dir):
    """Start SelfControl with custom parameters, depending on the weekday and the config"""

    try:
        schedule = next(
            s for s in config["block-schedules"] if is_schedule_active(s))
    except StopIteration:
        print("No Schedule is active at the moment.")
        LOGGER.warning("No schedule is active at the moment. Shutting down.")
        exit(0)

    block_end_date = get_end_date_of_schedule(schedule)
    blocklist_path = f"{settings_dir}/blocklist"

    update_blocklist(blocklist_path, config, schedule)

    # Start SelfControl
    exec_cli(config, ["--start", blocklist_path, block_end_date])

    LOGGER.info("SelfControl started until %s minute(s).", block_end_date)


def get_selfcontrol_out_pattern(content_pattern):
    """Returns a RegEx pattern that matches SelfControl's output with the provided content_pattern"""
    return r'^.*selfcontrol-cli[^ ]+\s*' + content_pattern + r'\s*$'


def check_if_running(config):
    """Check if SelfControl is already running."""
    output = exec_cli(config, ["--is-running"])
    match = re.search(
        get_selfcontrol_out_pattern(r'(NO|YES)'), output, re.MULTILINE)
    if match is None:
        exit_with_error("Could not detect if SelfControl is running.")
    return match.groups()[0] != 'NO'


def is_schedule_active(schedule):
    """Check if we are right now in the provided schedule or not."""
    currenttime = datetime.today()
    starttime = datetime(currenttime.year, currenttime.month, currenttime.day, schedule["start-hour"],
                         schedule["start-minute"])
    endtime = datetime(currenttime.year, currenttime.month, currenttime.day, schedule["end-hour"],
                       schedule["end-minute"])
    d = endtime - starttime

    for weekday in get_schedule_weekdays(schedule):
        weekday_diff = currenttime.isoweekday() % 7 - weekday % 7

        if weekday_diff == 0:
            # schedule's weekday is today
            result = starttime <= currenttime and endtime >= currenttime if d.days == 0 else starttime <= currenttime
        elif weekday_diff == 1 or weekday_diff == -6:
            # schedule's weekday was yesterday
            result = d.days != 0 and currenttime <= endtime
        else:
            # schedule's weekday was on any other day.
            result = False

        if result:
            return result

    return False


def get_end_date_of_schedule(schedule):
    """Return the end date of the provided schedule in ISO 8601 format"""
    end_hour = schedule['end-hour']
    end_minute = schedule['end-minute']
    return datetime.now() \
                   .astimezone() \
                   .replace(hour=end_hour, minute=end_minute, microsecond=0) \
                   .isoformat()

def get_schedule_weekdays(schedule):
    """Return a list of weekdays the specified schedule is active."""
    return [schedule["weekday"]] if schedule.get("weekday", None) is not None else range(1, 8)


def get_launchscript(config, settings_dir):
    """Return the string of the launchscript."""
    path=os.path.realpath(__file__)
    startintervals="".join(get_launchscript_startintervals(config))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.parrot-bytes.auto-selfcontrol</string>
        <key>ProgramArguments</key>
        <array>
            <string>/usr/bin/python3</string>
            <string>{path}</string>
            <string>--run</string>
            <string>--dir</string>
            <string>{settings_dir}</string>
        </array>
        <key>StartCalendarInterval</key>
        <array>
            {startintervals}</array>
        <key>RunAtLoad</key>
        <true/>
    </dict>
    </plist>'''


def get_launchscript_startintervals(config):
    """Return the string of the launchscript start intervals."""
    for schedule in config["block-schedules"]:
        for weekday in get_schedule_weekdays(schedule):
            startminute=schedule['start-minute']
            starthour=schedule['start-hour']
            yield f'''<dict>
                    <key>Weekday</key>
                    <integer>{weekday}</integer>
                    <key>Minute</key>
                    <integer>{startminute}</integer>
                    <key>Hour</key>
                    <integer>{starthour}</integer>
                </dict>
                '''


def exec_cli(config, arguments):
    """Execute the SelfControl CLI"""
    user_id = str(getpwnam(config["username"]).pw_uid)
    path=config["selfcontrol-path"]
    output = subprocess.check_output(
        [f"{path}/Contents/MacOS/selfcontrol-cli", "--uid", user_id] + arguments,
        stderr=subprocess.STDOUT
    ).decode()
    return output


def install(config, settings_dir):
    """ installs auto-selfcontrol """
    print("> Start installation of Auto-SelfControl")

    launchplist_path = "/Library/LaunchDaemons/com.parrot-bytes.auto-selfcontrol.plist"

    # Check for existing plist
    if os.path.exists(launchplist_path):
        print("> Removed previous installation files")
        subprocess.call(["launchctl", "unload", "-w", launchplist_path])
        os.unlink(launchplist_path)

    launchplist_script = get_launchscript(config, settings_dir)

    with open(launchplist_path, 'w', encoding='utf-8') as myfile:
        myfile.write(launchplist_script)

    subprocess.call(["launchctl", "load", "-w", launchplist_path])

    print("> Save run configuration")
    if not os.path.exists(settings_dir):
        os.makedirs(settings_dir)

    with open(f"{settings_dir}/run_config.json", 'w', encoding='utf-8') as file:
        file.write(json.dumps(config))

    print("> Installed\n")


def check_config(config):
    """ checks whether the config file is correct """
    if not "username" in config:
        exit_with_error("No username specified in config.")
    if config["username"] not in get_osx_usernames():
        exit_with_error(
            f'''Username '{config["username"]}' unknown.\nPlease use your OSX username instead.\n
            If you have trouble finding it, just enter the command 'whoami'\n
            in your terminal.''')
    if not "selfcontrol-path" in config:
        exit_with_error(
            "The setting 'selfcontrol-path' is required and must point to the location of SelfControl.")
    if not os.path.exists(config["selfcontrol-path"]):
        exit_with_error(
            "The setting 'selfcontrol-path' does not point to the correct location of SelfControl. "
            "Please make sure to use an absolute path and include the '.app' extension, "
            "e.g. /Applications/SelfControl.app")
    if not "block-schedules" in config:
        exit_with_error("The setting 'block-schedules' is required.")
    if len(config["block-schedules"]) == 0:
        exit_with_error("You need at least one schedule in 'block-schedules'.")
    if config.get("host-blacklist", None) is None:
        print("WARNING:")
        msg = "It is not recommended to directly use SelfControl's blacklist. Please use the 'host-blacklist' " \
              "setting instead."
        print(msg)
        LOGGER.warning(msg)


def update_blocklist(blocklist_path, config, schedule):
    """Save the blocklist with the current configuration"""
    plist = {
        "HostBlacklist": config["host-blacklist"],
        "BlockAsWhitelist": schedule.get("block-as-whitelist", False)
    }
    with open(blocklist_path, 'wb') as fp:
        plistlib.dump(plist, fp)


def get_osx_usernames():
    """Returns a list of all usernames on macOS"""
    output = subprocess.check_output(["dscl", ".", "list", "/users"]).decode()
    return [s.strip() for s in output.splitlines()]


def excepthook(exc_type, exc_value, exc_tb):
    """ This function is called whenever an exception is not caught. """
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    err = f"Uncaught exception:\n{str(exc_type)}\n{exc_value}\n{msg}"

    LOGGER.error(err)
    print(err)


def exit_with_error(message):
    """ Logs an error message and exits """
    LOGGER.error(message)
    print("ERROR:")
    print(message)
    exit(1)


if __name__ == "__main__":
    sys.excepthook = excepthook

    if os.geteuid() != 0:
        exit_with_error(f"Please make sure to run the script with elevated \
                         rights, such as:\nsudo python3 {os.path.realpath(__file__)}")

    parser = argparse.ArgumentParser()

    parser.add_argument("-r", "--run", action="store_true",
                      dest="run", default=False)
    parser.add_argument("-i", "--install", action="store_true",
                      dest="install", default=False)
    parser.add_argument("-d", "--dir", action="store",
                      dest="dir", default=SETTINGS_DIR)
    args = parser.parse_args()

    if args.run:
        run(args.dir)
    elif args.install:
        config_file = f"{args.dir}/config.json"
        if not os.path.exists(config_file):
            exit_with_error(
                f"There was no config file found in {args.dir}, please create a config file.")

        config = load_config(config_file)
        check_config(config)

        install(config, args.dir)
        
        schedule_is_active = any(
            s for s in config["block-schedules"] if is_schedule_active(s))

        if schedule_is_active and not check_if_running(config):
            print("> Active schedule found for SelfControl!")
            print("> Start SelfControl (this could take a few minutes)\n")
            run(args.dir)
            print("\n> SelfControl was started.\n")
    else:
        exit_with_error(
            "No action specified")
