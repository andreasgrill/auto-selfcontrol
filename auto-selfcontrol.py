#!/usr/bin/python

import subprocess
import os
import json
import datetime
import syslog
import traceback
import sys
from Foundation import NSUserDefaults, CFPreferencesSetAppValue, CFPreferencesAppSynchronize, NSDate
from pwd import getpwnam
from optparse import OptionParser


def load_config(config_files):
    """
    Load JSON configuration files.

    The latter configs overwrite the previous configs.
    """
    config = dict()

    for file in config_files:
        try:
            with open(file, 'rt') as cfg:
                config.update(json.load(cfg))
        except ValueError as exception:
            exit_with_error("The JSON config file {configfile} is not correctly formatted."
                            "The following exception was raised:\
                            \n{exc}".format(configfile=file, exc=exception))

    return config


def run(config):
    """Start self-control with custom parameters, depending on the weekday and the config."""
    if check_if_running(config["username"]):
        syslog.syslog(
            syslog.LOG_ALERT, "SelfControl is already running, ignore current execution of Auto-SelfControl.")
        exit(2)

    try:
        schedule = next(
            s for s in config["block-schedules"] if is_schedule_active(s))
    except StopIteration:
        syslog.syslog(syslog.LOG_ALERT,
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
    os.system("{path}/Contents/MacOS/org.eyebeam.SelfControl {userId} --install".format(
        path=config["selfcontrol-path"], userId=str(getpwnam(config["username"]).pw_uid)))

    syslog.syslog(syslog.LOG_ALERT,
                  "SelfControl started for {min} minute(s).".format(min=duration))


def check_if_running(username):
    """Check if self-control is already running."""
    defaults = get_selfcontrol_settings(username)
    return defaults.has_key("BlockStartedDate") and not NSDate.distantFuture().isEqualToDate_(defaults["BlockStartedDate"])


def is_schedule_active(schedule):
    """Check if we are right now in the provided schedule or not."""
    currenttime = datetime.datetime.today()
    starttime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, schedule["start-hour"],
                                  schedule["start-minute"])
    endtime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, schedule["end-hour"],
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
    currenttime = datetime.datetime.today()
    endtime = datetime.datetime(
        currenttime.year, currenttime.month, currenttime.day, endhour, endminute)
    d = endtime - currenttime
    return int(round(d.seconds / 60.0))


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


def install(config):
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
        syslog.syslog(syslog.LOG_WARNING, msg)


def get_osx_usernames():
    output = subprocess.check_output(["dscl", ".", "list", "/users"])
    return [s.strip() for s in output.splitlines()]


def excepthook(excType, excValue, tb):
    """ This function is called whenever an exception is not caught. """
    err = "Uncaught exception:\n{}\n{}\n{}".format(str(excType), excValue,
                                                   "".join(traceback.format_exception(excType, excValue, tb)))
    syslog.syslog(syslog.LOG_CRIT, err)
    print(err)


def exit_with_error(message):
    syslog.syslog(syslog.LOG_CRIT, message)
    print("ERROR:")
    print(message)
    exit(1)


if __name__ == "__main__":
    CONFIG_DIR = os.path.join('/usr/local/etc/auto-selfcontrol')
    CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

    sys.excepthook = excepthook

    syslog.openlog("Auto-SelfControl")

    if os.geteuid() != 0:
        exit_with_error("Please make sure to run the script with elevated \
                         rights, such as:\nsudo python {file} \
                         ".format(file=os.path.realpath(__file__)))

    PARSER = OptionParser()
    PARSER.add_option("-r", "--run", action="store_true",
                      dest="run", default=False)
    (OPTS, ARGS) = PARSER.parse_args()
    CONFIG = load_config([CONFIG_FILE])

    if OPTS.run:
        run(CONFIG)
    else:
        check_config(CONFIG)
        install(CONFIG)
        if not check_if_running(CONFIG["username"]) and \
           any(s for s in CONFIG["block-schedules"] if is_schedule_active(s)):
            print("> Active schedule found for SelfControl!")
            print("> Start SelfControl (this could take a few minutes)\n")
            run(CONFIG)
            print("\n> SelfControl was started.\n")
