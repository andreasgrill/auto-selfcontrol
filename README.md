# Auto-SelfControl

Small utility to schedule start and stop times of [SelfControl](http://selfcontrolapp.com).

## What is it for?
Auto-SelfControl helps you to create a weekly schedule for [SelfControl](http://selfcontrolapp.com).
You can plan for every weekday if and when SelfControl should start and stop.


## Install
- [SelfControl](http://selfcontrolapp.com) is required and should be installed in the application directory (however, custom paths are also supported).
- Start [SelfControl](http://selfcontrolapp.com) and backup your blacklist as it might get overridden by Auto-SelfControl.
- Download Auto-SelfControl and copy/extract it to a directory on your Mac (e.g. `~/auto-selfcontrol`).
- Edit the config.json (see [Configuration](#configuration) first).
- Open Terminal.app and cd to the directory.
- Execute `sudo python auto-selfcontrol.py` to install Auto-SelfControl with the block-schedule defined in [config.json](config.json). __Important:__ If you change [config.json](config.json) later, you have to call the installation command again or Auto-SelfControl might not start at the right time!


## Uninstall
- Delete the installation directory of Auto-SelfControl
- Execute the following command in the Terminal.app:
```
sudo rm /Library/LaunchDaemons/com.parrot-bytes.auto-selfcontrol.plist
```

## Configuration
The following listing shows an example config.json file that blocks every Monday from 9am to 5.30pm and on every Tuesday from 10am to 4pm:
```
    {
        "username": "MY_USERNAME",
        "selfcontrol-path": "/Applications/SelfControl.app",
        "host-blacklist": [
            "twitter.com",
            "reddit.com"
        ],
        "block-schedules":[
            {
                "weekday": 1,
                "start-hour": 9,
                "start-minute": 0,
                "end-hour": 17,
                "end-minute": 30,
                "block-as-whitelist": false,
                "host-blacklist": null
            },
            {
                "weekday": 2,
                "start-hour": 10,
                "start-minute": 0,
                "end-hour": 16,
                "end-minute": 0,
                "block-as-whitelist": false,
                "host-blacklist": null
            }
        ]
    }
```
- _username_ should be the Mac OS X username.
- _selfcontrol-path_ is the absolute path to [SelfControl](http://selfcontrolapp.com).
- _host-blacklist_ contains the list of sites that should get blacklisted as a string array. It is also possible to blacklist different sites on different schedules, which is described in the _block-schedules_ setting. Please note that the blacklist in SelfControl might get overridden and should be __backed up__ before using Auto-SelfControl.
- _block-schedules_ contains a list of schedules when SelfControl should be started.
    * The _weekday_ settings specifies the day of the week when SelfControl should get started. Possible values are from 1 (Monday) to 7 (Sunday). If the setting is `null` or omitted the blocking will be scheduled for all week days.
    * _start-hour_ and _start-minute_ denote the time of the day when the blocking should start, while _end-hour_ and _end-minute_ specify the time it should end. The hours must be defined in the 24 hour digit format. If the ending time is before the start time, the block will last until the next day (see example below).
    * _block-as-whitelist_ specifies whether a whitelist or blacklist blocking (the latter is recommended) should be used.
    * Finally, _host-blacklist_ may either contain the list of sites that should get blacklisted in this specific schedule as a string array, or `null` if the general _host-blacklist_ setting applies for this schedule too. The setting should be left `null` if all schedules should block the same list of sites.

    Please note that it is possible to create multiple schedules on the same day, as long as they are not overlapping. Have a look at the example below.

The following listing shows another example that blocks twitter and reddit every Sunday from 11pm til Monday 5am and Monday from 9am until 7pm, while additionally blocking netflix every Monday from 10pm to 11pm:
```
    {
        "username": "MY_USERNAME",
        "selfcontrol-path": "/Applications/SelfControl.app",
        "host-blacklist":[
            "twitter.com",
            "reddit.com"
        ],
        "block-schedules":[
            {
                "weekday": 1,
                "start-hour": 9,
                "start-minute": 0,
                "end-hour": 19,
                "end-minute": 0
            },
            {
                "weekday": 1,
                "start-hour": 22,
                "start-minute": 0,
                "end-hour": 23,
                "end-minute": 0,
                "host-blacklist":[
                    "twitter.com",
                    "reddit.com",
                    "netflix.com"
                ]
            },
            {
                "weekday": 7,
                "start-hour": 23,
                "start-minute": 0,
                "end-hour": 5,
                "end-minute": 0
            }
        ]
    }
```

## Troubleshooting

1. ImportError: No module named Foundation

If you've installed python using homebrew you'll need to run `pip install pyobjc` or [there are other options](https://stackoverflow.com/questions/1614648/importerror-no-module-named-foundation#1616361).
