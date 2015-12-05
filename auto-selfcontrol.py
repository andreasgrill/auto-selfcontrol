#!/usr/bin/env python

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
    """ loads json configuration files
    the latter configs overwrite the previous configs
    """

    config = dict()

    for f in config_files:
        with open(f, 'rt') as cfg:
            config.update(json.load(cfg))

    return config

def run(config):
    """ starts self-control with custom parameters, depending on the weekday and the config """

    check_if_running(config["username"])
    
    schedule = next(s for s in config["block-schedules"] if is_schedule_active(s))
    duration = get_duration_minutes(schedule["end-hour"], schedule["end-minute"])

    set_selfcontrol_setting("BlockDuration", duration, config["username"])
    set_selfcontrol_setting("BlockAsWhitelist", 1 if schedule["block-as-whitelist"] else 0, config["username"])
    if schedule["host-blacklist"] is not None:
        set_selfcontrol_setting("HostBlacklist", schedule["host-blacklist"], config["username"])

    # In legacy mode manually set the BlockStartedDate, this should not be required anymore in future versions
    # of SelfControl.
    if config["legacy-mode"]:
        set_selfcontrol_setting("BlockStartedDate", NSDate.date(), config["username"])
    
    # Start SelfControl
    subprocess.call(["{path}/Contents/MacOS/org.eyebeam.SelfControl".format(path = config["selfcontrol-path"]), 
        str(getpwnam(config["username"]).pw_uid),
        "--install"])

    syslog.syslog(syslog.LOG_ALERT, "SelfControl started for {min} minute(s).".format(min = duration))

def check_if_running(username):
    """ checks if self-control is already running and stops auto-selfcontrol if so. """
    defaults = get_selfcontrol_settings(username)
    if not NSDate.distantFuture().isEqualToDate_(defaults["BlockStartedDate"]):
        syslog.syslog(syslog.LOG_ALERT, "SelfControl is already running, ignore current execution of Auto-SelfControl.")
        exit(2)

def is_schedule_active(schedule):
    """ checks if we are right now in the provided schedule or not """
    currenttime = datetime.datetime.today()
    starttime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, schedule["start-hour"], schedule["start-minute"])
    endtime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, schedule["end-hour"], schedule["end-minute"])
    d = endtime - starttime

    weekday_diff = currenttime.isoweekday() % 7 - schedule["weekday"] % 7 

    if weekday_diff == 0:
        return starttime <= currenttime and endtime >= currenttime if d.days == 0 else starttime <= currenttime
    elif weekday_diff == 1 or weekday_diff == -6:
        return d.days != 0 and endtime >= currenttime
    
    return False

def get_duration_minutes(endhour, endminute):
    """ returns the minutes left until the schedule's end-hour and end-minute are reached """
    currenttime = datetime.datetime.today()
    endtime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, endhour, endminute)
    d = endtime - currenttime
    return int(round(d.seconds / 60.0))

def set_selfcontrol_setting(key, value, username):
    """ sets a single default setting of SelfControl for the provied username """
    NSUserDefaults.resetStandardUserDefaults()
    originalUID = os.geteuid()
    os.seteuid(getpwnam(username).pw_uid)
    CFPreferencesSetAppValue(key, value, "org.eyebeam.SelfControl")
    CFPreferencesAppSynchronize("org.eyebeam.SelfControl")
    NSUserDefaults.resetStandardUserDefaults()
    os.seteuid(originalUID)

def get_selfcontrol_settings(username):
    """ returns all default settings of SelfControl for the provided username """
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
    """ returns the string of the launchscript """
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
    """ returns the string of the launchscript start intervals """
    for schedule in config["block-schedules"]:
        yield ('''<dict>
                <key>Weekday</key>
                <integer>{weekday}</integer>
                <key>Minute</key>
                <integer>{startminute}</integer>
                <key>Hour</key>
                <integer>{starthour}</integer>
            </dict>
            '''.format(weekday=schedule["weekday"], startminute=schedule['start-minute'], starthour=schedule['start-hour']))



def install(config):
    """ installs auto-selfcontrol """
    launchplist_path = "/Library/LaunchDaemons/com.parrot-bytes.auto-selfcontrol.plist"

    launchplist_script = get_launchscript(config)
    
    with open(launchplist_path, 'w') as myfile:
        myfile.write(launchplist_script)

    subprocess.call(["launchctl", "unload", "-w", launchplist_path])
    subprocess.call(["launchctl", "load", "-w", launchplist_path])

    print("> Installed\n")

def excepthook(excType, excValue, tb):
    """ this function is called whenever an exception is not catched """
    err = "Uncaught exception:\n{}\n{}\n{}".format(str(excType), excValue, "".join(traceback.format_exception(excType, excValue, tb)))
    syslog.syslog(syslog.LOG_CRIT, err)
    print(err)

if __name__ == "__main__":
    __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    sys.excepthook = excepthook

    syslog.openlog("Auto-SelfControl")

    if os.geteuid() != 0:
        err = "Please make sure to run the script with elevated rights, such as:\nsudo python {file}".format(file=os.path.realpath(__file__))
        syslog.syslog(syslog.LOG_CRIT, err)
        print(err)
        exit(1)

    parser = OptionParser()
    parser.add_option("-r" , "--run", action="store_true",                                                                                   
                      dest="run", default=False)
    (opts,args) = parser.parse_args()
    config = load_config([os.path.join(__location__,"config.json")])

    if opts.run:
        run(config)
    else:
        install(config)
