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
    weekday = datetime.datetime.today().isoweekday()

    schedule = next(s for s in config["block-schedules"] if weekday % 7 == s["weekday"] % 7 and is_schedule_active(s))
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

def is_schedule_active(schedule):
    currenttime = datetime.datetime.today()
    starttime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, schedule["start-hour"], schedule["start-minute"])
    endtime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, schedule["end-hour"], schedule["end-minute"])
    d = endtime - starttime
     
    if d.days == 0:
        return starttime <= currenttime and endtime >= currenttime
    else:
        return starttime <= currenttime

def get_duration_minutes(endhour, endminute):
    currenttime = datetime.datetime.today()
    endtime = datetime.datetime(currenttime.year, currenttime.month, currenttime.day, endhour, endminute)
    d = endtime - currenttime
    return int(round(d.seconds / 60.0))

def set_selfcontrol_setting(key, value, username):
    NSUserDefaults.resetStandardUserDefaults()
    originalUID = os.geteuid()
    os.seteuid(getpwnam(username).pw_uid)
    CFPreferencesSetAppValue(key, value, "org.eyebeam.SelfControl")
    CFPreferencesAppSynchronize("org.eyebeam.SelfControl")
    NSUserDefaults.resetStandardUserDefaults()
    os.seteuid(originalUID)

def create_launchscript(config):
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
            {startintervals}
        </array>
    </dict>
    </plist>'''.format(path=os.path.realpath(__file__), startintervals="\n".join(get_launchscript_startintervals(config)))

def get_launchscript_startintervals(config):
    for schedule in config["block-schedules"]:
        yield ('''<dict>
                <key>Weekday</key>
                <integer>{weekday}</integer>
                <key>Minute</key>
                <integer>{startminute}</integer>
                <key>Hour</key>
                <integer>{starthour}</integer>
            </dict>'''.format(weekday=schedule["weekday"], startminute=schedule['start-minute'], starthour=schedule['start-hour']))



def install(config):
    """ installs auto-selfcontrol """
    launchplist_path = "/Library/LaunchDaemons/com.parrot-bytes.auto-selfcontrol.plist"

    launchplist_script = create_launchscript(config)
    
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
