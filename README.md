# Auto-SelfControl

Small utility to schedule start and stop times of [SelfControl](http://selfcontrolapp.com).

## What is it for?
Auto-SelfControl helps you to create a weekly schedule for [SelfControl](http://selfcontrolapp.com).
You can plan for every weekday if and when SelfControl should start and stop.


## Installation

### With Homebrew (under construction)

The easiest way to install Auto-SelfControl is with [Homebrew](https://brew.sh/). Install Auto-SelfControl by running the following command in the Terminal:

    brew install auto-selfcontrol

If you already have [SelfControl](http://selfcontrolapp.com), start it and **backup your blacklist** as it might get overridden by Auto-SelfControl. 

If you do not have [SelfControl](http://selfcontrolapp.com) already installed on your system, you can install it with [Homebrew Cask](https://caskroom.github.io/):

    brew cask install selfcontrol

### Manual installation

Download this repository to a directory on your system (e.g., `~/auto-selfcontrol/`).

    chmod +x auto-selfcontrol

Run from this specific repository

    ./auto-selfcontrol <config|activate|help>

Or create a symlink in your `/usr/local/bin` folder to access it from anywhere.

## Usage

Edit the time configuration (see [Configuration](#configuration)) first:

    auto-selfcontrol config

When your block-schedule in [config.json](config.json) is ready, activate it by running:

    auto-selfcontrol activate

__Important:__ If you change [config.json](config.json) later, you have to call the `auto-selfcontrol activate` command again or Auto-SelfControl will not take the modifications into account!


## Uninstall

To remove the application (if installed with Homebrew):

    brew uninstall auto-selfcontrol

Or, manually, by removing the directory where you installed the files.

You also need to remove the automatic schedule by executing the following command in the Terminal:

    sudo rm /Library/LaunchDaemons/com.parrot-bytes.auto-selfcontrol.plist

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
                "end-minute": 30
            },
            {
                "weekday": 2,
                "start-hour": 10,
                "start-minute": 0,
                "end-hour": 16,
                "end-minute": 0
            }
        ]
    }
```
- _username_ should be the macOS username.
- _selfcontrol-path_ is the absolute path to [SelfControl](http://selfcontrolapp.com).
- _host-blacklist_ contains the list of sites that should get blacklisted as a string array. Please note that the blacklist in SelfControl might get overridden and should be __backed up__ before using Auto-SelfControl.
- _block-schedules_ contains a list of schedules when SelfControl should be started.
    * The _weekday_ settings specifies the day of the week when SelfControl should get started. Possible values are from 1 (Monday) to 7 (Sunday). If the setting is `null` or omitted the blocking will be scheduled for all week days.
    * _start-hour_ and _start-minute_ denote the time of the day when the blocking should start, while _end-hour_ and _end-minute_ specify the time it should end. The hours must be defined in the 24 hour digit format. If the ending time is before the start time, the block will last until the next day (see example below).

    Please note that it is possible to create multiple schedules on the same day, as long as they are not overlapping. Have a look at the example below.

The following listing shows another example that blocks twitter and reddit every Sunday from 11pm til Monday 5am, Monday from 9am until 7pm and Monday from 10pm to 11pm:
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
                "weekday": 7,
                "start-hour": 23,
                "start-minute": 0,
                "end-hour": 5,
                "end-minute": 0
            },
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
                "end-minute": 0
            }
        ]
    }
```

## Troubleshooting

### ImportError: No module named Foundation

If you've installed another version of Python (e.g., using Homebrew), you'll need to run Auto-SelfControl with the original Python installation from macOS:

    sudo /usr/bin/python auto-selfcontrol.py

There are also other options, including installing `pyobjc` on your own Python version (`pip install pyobjc`). [See this thread for alternative solutions](https://stackoverflow.com/questions/1614648/importerror-no-module-named-foundation#1616361).
