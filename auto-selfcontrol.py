#!/usr/bin/python

import subprocess
import os
import json
import time
from datetime import datetime
import plistlib
import logging.handlers
import traceback
import sys
import re
from Foundation import NSUserDefaults, CFPreferencesSetAppValue, CFPreferencesAppSynchronize, NSDate
from pwd import getpwnam
from optparse import OptionParser

SETTINGS_DIR = '/usr/local/etc/auto-selfcontrol'

# Configure global logger
LOGGER = logging.getLogger("Auto-SelfControl")
LOGGER.setLevel(logging.INFO)
handler = logging.handlers.SysLogHandler('/var/run/syslog')
handler.setFormatter(logging.Formatter(
    '%(name)s: [%(levelname)s] %(message)s'))
LOGGER.addHandler(handler)


class Api:
    V2 = 2
    V3 = 3


def load_config(path):
    """Load a JSON configuration file"""
    config = dict()

    try:
        with open(path, 'rt') as cfg:
            config.update(json.load(cfg))
    except ValueError as exception:
        exit_with_error("The JSON config file {configfile} is not correctly formatted."
                        "The following exception was raised:\
                        \n{exc}".format(configfile=path, exc=exception))

    return config


def find_config():
    """Looks for the config.json and returns its path"""
    local_config_file = "{path}/config.json".format(
        path=os.path.dirname(os.path.realpath(__file__)))
    global_config_file = "{path}/config.json".format(
        path=SETTINGS_DIR)

    if os.path.exists(local_config_file):
        return local_config_file

    if os.path.exists(global_config_file):
        return global_config_file

    exit_with_error(
        "There was no config file found, please create a config file.")


def detect_api(config):
    """Return the supported API version of the SelfControl"""
    try:
        output = execSelfControl(config, ["--version"])
        m = re.search(
            get_selfcontrol_out_pattern(r'(\d+)\.\d+(\.\d+)*'), output, re.MULTILINE)
        if m is None:
            exit_with_error("Could not parse SelfControl version response!")
        if m and int(m.groups()[0]) >= Api.V3:
            return Api.V3

        exit_with_error("Unexpected version returned from SelfControl '{version}'".format(
            version=m.groups()[0]))
    except:
        # SelfControl < 3.0.0 does not support the --version argument
        return Api.V2


def run(settings_dir):
    """Load config and start SelfControl"""
    run_config = "{path}/run_config.json".format(path=settings_dir)
    if not os.path.exists(run_config):
        exit_with_error(
            "Run config file could not be found in installation location, please make sure that you have Auto-SelfControl activated/installed")

    config = load_config(run_config)
    api = detect_api(config)
    print("> Detected API v{version}".format(version=api))

    if api is Api.V2:
        run_api_v2(config)
    elif api is Api.V3:
        run_api_v3(config, settings_dir)


def run_api_v2(config):
    """Start SelfControl (< 3.0) with custom parameters, depending on the weekday and the config"""

    if check_if_running(Api.V2, config):
        print "SelfControl is already running, exit"
        LOGGER.error(
            "SelfControl is already running, ignore current execution of Auto-SelfControl.")
        exit(2)

    try:
        schedule = next(
            s for s in config["block-schedules"] if is_schedule_active(s))
    except StopIteration:
        print("No Schedule is active at the moment.")
        LOGGER.warn(
            "No schedule is active at the moment. Shutting down.")
        exit(0)

    duration = get_duration_minutes(
        schedule["end-hour"], schedule["end-minute"])

    set_selfcontrol_setting("BlockDuration", duration, config["username"])
    set_selfcontrol_setting("BlockAsWhitelist", 1 if schedule.get("block-as-whitelist", False) else 0,
                            config["username"])

    if schedule.get("host-blacklist", None) is not None:
        set_selfcontrol_setting(
            "HostBlacklist", schedule["host-blacklist"], config["username"])
    elif config.get("host-blacklist", None) is not None:
        set_selfcontrol_setting(
            "HostBlacklist", config["host-blacklist"], config["username"])

    # In legacy mode manually set the BlockStartedDate, this should not be required anymore in future versions
    # of SelfControl.
    if config.get("legacy-mode", True):
        set_selfcontrol_setting(
            "BlockStartedDate", NSDate.date(), config["username"])

    # Start SelfControl
    execSelfControl(config, ["--install"])

    LOGGER.info(
        "SelfControl started for {min} minute(s).".format(min=duration))


def run_api_v3(config, settings_dir):
    """Start SelfControl with custom parameters, depending on the weekday and the config"""

    if check_if_running(Api.V3, config):
        print "SelfControl is already running, exit"
        LOGGER.error(
            "SelfControl is already running, ignore current execution of Auto-SelfControl.")
        exit(2)

    try:
        schedule = next(
            s for s in config["block-schedules"] if is_schedule_active(s))
    except StopIteration:
        print("No Schedule is active at the moment.")
        LOGGER.warn("No schedule is active at the moment. Shutting down.")
        exit(0)

    block_end_date = get_end_date_of_schedule(schedule)
    blocklist_path = "{settings}/blocklist".format(settings=settings_dir)

    update_blocklist(blocklist_path, config, schedule)

    # Start SelfControl
    execSelfControl(config, ["--install", blocklist_path, block_end_date])

    LOGGER.info("SelfControl started until {end} minute(s).".format(
        end=block_end_date))


def get_selfcontrol_out_pattern(content_pattern):
    """Returns a RegEx pattern that matches SelfControl's output with the provided content_pattern"""
    return r'^.*org\.eyebeam\.SelfControl[^ ]+\s*' + content_pattern + r'\s*$'


def check_if_running(api, config):
    """Check if SelfControl is already running."""
    if api is Api.V2:
        username = config["username"]
        defaults = get_selfcontrol_settings(username)
        return defaults.has_key("BlockStartedDate") and not NSDate.distantFuture().isEqualToDate_(defaults["BlockStartedDate"])
    elif api is Api.V3:
        output = execSelfControl(config, ["--is-running"])
        m = re.search(
            get_selfcontrol_out_pattern(r'(NO|YES)'), output, re.MULTILINE)
        if m is None:
            exit_with_error("Could not detect if SelfControl is running.")
        return m.groups()[0] != 'NO'
    else:
        raise Exception(
            "Unknown API version {version} passed.".format(version=api))


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


def get_duration_minutes(endhour, endminute):
    """Return the minutes left until the schedule's end-hour and end-minute are reached."""
    currenttime = datetime.today()
    endtime = datetime(
        currenttime.year, currenttime.month, currenttime.day, endhour, endminute)
    d = endtime - currenttime
    return int(round(d.seconds / 60.0))


def get_end_date_of_schedule(schedule):
    """Return the end date of the provided schedule in ISO 8601 format"""
    currenttime = datetime.today()
    endtime = datetime(
        currenttime.year, currenttime.month, currenttime.day, schedule['end-hour'], schedule['end-minute'])
    # manually create ISO8601 string because of tz issues with Python2
    ts = time.time()
    utc_offset = ((datetime.fromtimestamp(
        ts) - datetime.utcfromtimestamp(ts)).total_seconds()) / 3600
    offset = str(int(abs(utc_offset * 100))).zfill(4)
    sign = "+" if utc_offset >= 0 else "-"

    return endtime.strftime("%Y-%m-%dT%H:%M:%S{sign}{offset}".format(sign=sign, offset=offset))


def get_schedule_weekdays(schedule):
    """Return a list of weekdays the specified schedule is active."""
    return [schedule["weekday"]] if schedule.get("weekday", None) is not None else range(1, 8)


def set_selfcontrol_setting(key, value, username):
    """Set a single default setting of SelfControl for the provided username."""
    NSUserDefaults.resetStandardUserDefaults()
    originalUID = os.geteuid()
    os.seteuid(getpwnam(username).pw_uid)
    CFPreferencesSetAppValue(key, value, "org.eyebeam.SelfControl")
    CFPreferencesAppSynchronize("org.eyebeam.SelfControl")
    NSUserDefaults.resetStandardUserDefaults()
    os.seteuid(originalUID)


def get_selfcontrol_settings(username):
    """Return all default settings of SelfControl for the provided username."""
    NSUserDefaults.resetStandardUserDefaults()
    originalUID = os.geteuid()
    os.seteuid(getpwnam(username).pw_uid)
    defaults = NSUserDefaults.standardUserDefaults()
    defaults.addSuiteNamed_("org.eyebeam.SelfControl")
    defaults.synchronize()
    result = defaults.dictionaryRepresentation()
    NSUserDefaults.resetStandardUserDefaults()
    os.seteuid(originalUID)
    return result


def get_launchscript(config):
    """Return the string of the launchscript."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.parrot-bytes.auto-selfcontrol</string>
        <key>ProgramArguments</key>
        <array>
            <string>/usr/bin/python</string>
            <string>{path}</string>
            <string>-r</string>
        </array>
        <key>StartCalendarInterval</key>
        <array>
            {startintervals}</array>
        <key>RunAtLoad</key>
        <true/>
    </dict>
    </plist>'''.format(path=os.path.realpath(__file__), startintervals="".join(get_launchscript_startintervals(config)))


def get_launchscript_startintervals(config):
    """Return the string of the launchscript start intervals."""
    for schedule in config["block-schedules"]:
        for weekday in get_schedule_weekdays(schedule):
            yield '''<dict>
                    <key>Weekday</key>
                    <integer>{weekday}</integer>
                    <key>Minute</key>
                    <integer>{startminute}</integer>
                    <key>Hour</key>
                    <integer>{starthour}</integer>
                </dict>
                '''.format(weekday=weekday, startminute=schedule['start-minute'], starthour=schedule['start-hour'])


def execSelfControl(config, arguments):
    user_id = str(getpwnam(config["username"]).pw_uid)
    output = subprocess.check_output(
        ["{path}/Contents/MacOS/org.eyebeam.SelfControl".format(
            path=config["selfcontrol-path"]), user_id] + arguments,
        stderr=subprocess.STDOUT
    )
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

    launchplist_script = get_launchscript(config)

    with open(launchplist_path, 'w') as myfile:
        myfile.write(launchplist_script)

    subprocess.call(["launchctl", "load", "-w", launchplist_path])

    print("> Save run configuration")
    if not os.path.exists(settings_dir):
        os.makedirs(settings_dir)

    with open("{dir}/run_config.json".format(dir=settings_dir), 'w') as fp:
        fp.write(json.dumps(config))

    print("> Installed\n")


def check_config(config):
    """ checks whether the config file is correct """
    if not config.has_key("username"):
        exit_with_error("No username specified in config.")
    if config["username"] not in get_osx_usernames():
        exit_with_error(
            "Username '{username}' unknown.\nPlease use your OSX username instead.\n"
            "If you have trouble finding it, just enter the command 'whoami'\n"
            "in your terminal.".format(
                username=config["username"]))
    if not config.has_key("selfcontrol-path"):
        exit_with_error(
            "The setting 'selfcontrol-path' is required and must point to the location of SelfControl.")
    if not os.path.exists(config["selfcontrol-path"]):
        exit_with_error(
            "The setting 'selfcontrol-path' does not point to the correct location of SelfControl. "
            "Please make sure to use an absolute path and include the '.app' extension, "
            "e.g. /Applications/SelfControl.app")
    if not config.has_key("block-schedules"):
        exit_with_error("The setting 'block-schedules' is required.")
    if len(config["block-schedules"]) == 0:
        exit_with_error("You need at least one schedule in 'block-schedules'.")
    if config.get("host-blacklist", None) is None:
        print("WARNING:")
        msg = "It is not recommended to directly use SelfControl's blacklist. Please use the 'host-blacklist' " \
              "setting instead."
        print(msg)
        LOGGER.warn(msg)


def update_blocklist(blocklist_path, config, schedule):
    """Save the blocklist with the current configuration"""
    plist = {
        "HostBlacklist": config["host-blacklist"],
        "BlockAsWhitelist": schedule.get("block-as-whitelist", False)
    }
    with open(blocklist_path, 'wb') as fp:
        plistlib.writePlist(plist, fp)


def get_osx_usernames():
    output = subprocess.check_output(["dscl", ".", "list", "/users"])
    return [s.strip() for s in output.splitlines()]


def excepthook(excType, excValue, tb):
    """ This function is called whenever an exception is not caught. """
    err = "Uncaught exception:\n{}\n{}\n{}".format(str(excType), excValue,
                                                   "".join(traceback.format_exception(excType, excValue, tb)))
    LOGGER.error(err)
    print(err)


def exit_with_error(message):
    LOGGER.error(message)
    print("ERROR:")
    print(message)
    exit(1)


if __name__ == "__main__":
    sys.excepthook = excepthook

    if os.geteuid() != 0:
        exit_with_error("Please make sure to run the script with elevated \
                         rights, such as:\nsudo python {file} \
                         ".format(file=os.path.realpath(__file__)))

    PARSER = OptionParser()
    PARSER.add_option("-r", "--run", action="store_true",
                      dest="run", default=False)
    (OPTS, ARGS) = PARSER.parse_args()

    if OPTS.run:
        run(SETTINGS_DIR)
    else:
        CONFIG_FILE = find_config()
        CONFIG = load_config(CONFIG_FILE)
        check_config(CONFIG)

        api = detect_api(CONFIG)
        print("> Detected API v{version}".format(version=api))

        install(CONFIG, SETTINGS_DIR)
        schedule_is_active = any(
            s for s in CONFIG["block-schedules"] if is_schedule_active(s))

        if schedule_is_active and not check_if_running(api, CONFIG):
            print("> Active schedule found for SelfControl!")
            print("> Start SelfControl (this could take a few minutes)\n")
            run(SETTINGS_DIR)
            print("\n> SelfControl was started.\n")
