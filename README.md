# Auto-SelfControl

Small utility to schedule start and stop times of [SelfControl](http://selfcontrolapp.com).

## What is it for?

Auto-SelfControl helps you to create a weekly schedule for [SelfControl](http://selfcontrolapp.com).
You can plan for every weekday if and when SelfControl should start and stop.

> :warning: **Auto-SelfControl** is not compatible yet with SelfControl 4.
> We are trying to solve [the issue](https://github.com/andreasgrill/auto-selfcontrol/issues/64), but as of today Auto-SelfControl won't be able to schedule blocks.

## Installation

### Requirements

- Python3 needs to be installed. Check by running the following command in your terminal: `python3 --version`. If Python3 is missing, you should be able to install it through the Xcode developer tools or [Homebrew](https://brew.sh/).
- [SelfControl 4](http://selfcontrolapp.com)

### With Homebrew

The easiest way to install Auto-SelfControl is with [Homebrew](https://brew.sh/). Install Auto-SelfControl by running the following command in the Terminal:

    brew tap andreasgrill/utils
    brew install auto-selfcontrol

If you already have [SelfControl](http://selfcontrolapp.com), start it and **backup your blacklist** as it might get overridden by Auto-SelfControl.

If you do not have [SelfControl](http://selfcontrolapp.com) already installed on your system, you can install it with [Homebrew Cask](https://caskroom.github.io/):

    brew install --cask selfcontrol

### Manual installation

Download this repository to a directory on your system (e.g., `~/auto-selfcontrol/`).

    chmod +x auto-selfcontrol

Run from this specific repository

    ./auto-selfcontrol <config|activate|help>

Optionally create a symlink in your `/usr/local/bin` folder to access it from anywhere:

    sudo ln -s ./auto-selfcontrol /usr/local/bin/auto-selfcontrol

## Usage

1. Open the configuration file:

To specify when and how Auto-SelfControl should activate, you need to configure a block-schedule in the following configuration file:

    ~/.config/auto-selfcontrol/config.json

You can also quickly access the configuration file through with the following command:

    auto-selfcontrol config

2. Configure the block schedules

Check and update the configuration file:

- Change the `username` to your current macOS User
- Upda
- Have a look at the [Configuration](#configuration) section

3. Activate and apply the configuration

Changes to the configuration file are not automatically applied. If you want Auto-SelfControl to apply the configuration, you can use the `activate` command:

    auto-selfcontrol activate

If there is an error in your configuration file, the output of the command should give you a hint where to look.

**Important:** If you change your configuration file later, you have to call the `auto-selfcontrol activate` command again or Auto-SelfControl will ignore the modifications. However, changes to an already running block-schedule are ignored until the block-schedule is over.

## Uninstall

To remove the application (if installed with Homebrew):

    brew uninstall auto-selfcontrol

Or, manually, by removing the directory where you installed the files.

    sudo unlink /usr/local/bin/auto-selfcontrol
    sudo rm -rf /usr/local/etc/auto-selfcontrol
    rm -rf ~/auto-selfcontrol
    rm -rf ~/.config/auto-selfcontrol

You also need to remove the automatic schedule by executing the following command in the Terminal:

    sudo rm -f /Library/LaunchDaemons/com.parrot-bytes.auto-selfcontrol.plist

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
- _host-blacklist_ contains the list of sites that should get blacklisted as a string array. Please note that the blacklist in SelfControl might get overridden and should be **backed up** before using Auto-SelfControl.
- _block-schedules_ contains a list of schedules when SelfControl should be started.

  - The _weekday_ settings specifies the day of the week when SelfControl should get started. Possible values are from 1 (Monday) to 7 (Sunday). If the setting is `null` or omitted the blocking will be scheduled for all week days.
  - _start-hour_ and _start-minute_ denote the time of the day when the blocking should start, while _end-hour_ and _end-minute_ specify the time it should end. The hours must be defined in the 24 hour digit format. If the ending time is before the start time, the block will last until the next day (see example below).

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
