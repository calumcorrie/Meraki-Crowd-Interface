# Cisco Meraki Crowd Interface

## Overview

This system is a web-based dashboard for displaying data pulled from cameras and WiFi access points through the Cisco Meraki API. Once set up, it allows a user to view the busyness of spaces compared to historical data in an area displayed on a floorplan. We layer data from multiple sources to create a more accurate picture.

## Requirements and Dependencies
The system runs uses Flask and requires Python 3.6. A full manifest of the module requirements can be found in `requirements.txt`. The version specifiers of these packets indicate those that were used and tested in development. Many of them are not strict, but manual verification of compatibility would have to be performed if altered. It is not anticipated that frequent updates to these requirements specification will be made going forward though they are the most modern available at design time.

The system by design runs on the data provided by the Cisco Meraki Dashboard API and Snapshot API interfaces. As such, it is necessary to have an account linked with an organization with at least one network on the [Meraki Dashboard][1]. From this, the application requires the API key to be provided in the run environment variables. See *Setup*.

### For meaningful data

- Contents of `requirements.txt`
- Meraki Dashboard account and [API Key][2]
- At least 1 geoaligned floorplan
- At least 3 geoaligned APs or 1 MV Sense enabled camera
- At least 1 device or person (in case of camera)
- A WSGI host configuation with TLS
    - Other deployment options available

### Optionally
- A system to receive spike detection webhooks

## Installation
The product conforms to a standard [Flask application][3] pattern. This can be cloned or downloaded and unzipped into the target directory. It does not require installation, apart from its dependencies (see below).

### Dependencies
The project requires Python >= 3.6.

In the project directory, the dependencies can be installed automatically. Use `pip` or `pip3` according to your setup.

    pip3 install -r requirements.txt

## Deployment
There are several options for system deployment outlined in the [deployment section][4] in the Flask docs. Check these to find a deployment option suitable for the intended host setup. 

A requirement on the hosting environment is that is must be able to store the [API Key][2] as an environment variable in the execution environment. Specifically, the 40 character hex string should be stored in the `MERAKI_DASHBOARD_API_KEY` environment variable (see *Requirements*). This can be achieved manually but is best setup in a configuration option or other location. Depending on the permissions granted, this could be a sensitive key and should be protected accordingly. The key only needs read access on the Dashboard.

Before deployment, change `app.py:83:app.secret_key` to a random binary string.

The system can now be started up, and will by default select the first network available to it. This is alterable in the configuration page later.

The system will automatically gather all floorplan and access point data when it is started up.

In the [Dashboard][1], navigate to *Network-wide > General* and find section *Location and Scanning*. Select *Analytics enabled* and *Scanning API enabled*. Add at least one POST URL, which will be of the form

    https://<rooturl>/scanningapi/

With the `<rooturl>` pertaining to the eventual URL of the server.

At least one form of Scanning data is required, but the same URL can be used for both Bluetooth and WiFi data.
Use API **Version 3 (V3)**. The system setup will need to be completed and the server running before clicking the *Validate* button to establish the link.
Set the password to something secure and when the system is started, add it to the Scanning API Secret field of the configuration page.
Similarly, take note of the validator token as it will need to be provided to the configuration also.

The default admin password for the system is `belgium`, which must be changed immediately in the configuration page. In that page, you can also change the network to be modeled, and other parameters. Do not set this to be the same as the Meraki Dashboard password, and make it at least 10 characters long, ideally with number, capitals and symbols.

## User Guide

The index page consists of a list of links to floorplans, with the floorplans visible without overlays above. The header bar appears on all pages, with a link to settings, and a sign out button if you've entered login credentials.

The floorplan pages consist of an image of the floorplan with a periodically updated colour-coded overlay displaying current busyness as compared to historical data. There are three buttons above the floorplan, one to immediately update the overlay, one to pause the live data, and one to restart it again.

The setting page contains a form that allows you to change the network you're viewing, the scanning API secret, the validator token, the admin password, the spike detection threshold, and the webhook targets. Below, the bounds detector setup allows you to set the areas of your floorplan where observations should be ignored. This feature can be enabled or disabled using the toggle button, the latest version can be pushed to the server with the refresh button, or you can erase the boundaries with the erase button. Below that, the Cameras setup allows you to mark the location and field of view of the cameras on the floorplan.

The admin login page contains a box to fill in the admin password, and a button to authenticate once you have done so.

## Technologies

The system is designed to extend a Meraki network. It employs Location Scanning API for AP client proximity estimation, and MV Sense smart detection for person observation analysis.

The Model configuration file is a binary Pickle file. See *Security* for the implications of this.

The web application is based on the standard Flask web app pattern. It runs on Python 3.6+ and uses [Flask 1.1.x][3].
The hosting server must also be set up with TLS as per Meraki specifications for security.

Numerical processing is done using [NumPy][5], and graphical processing is performed by [Pillow][6] Image class at a high level, and NumPy at a low level.

Historical data is stored in Pickle format with BZ2 compression. Each time slot is stored in a different file.

The front end uses hierarchical [Jinja 2][7] HTML templating, with standard JS and CSS styling.

## Security

The hosting server must have a valid TLS certificate. If one is not already configured on the host server, visit [let's encrypt][8] (outwith scope of this document).

On system setup, as discussed above, change `app.py:83:app.secret_key` to a random binary string. You can generate one in python using

    import os; os.urandom(24)

and copying the output to the value of the secret key in `app.py`.

Securely storing the API key is outwith the scope of the project and this must be provided in the runtime environment of the system, as discussed in *Deployment*.

The configuration interface has a password to allow the system owner to configure the system, but prevent the layman from accessing this. As such a rudimentary login system is provided - SHA256 hashed password that is stored in the config file. The config file is **not encrypted**, so should be guarded with permissions to avoid access or replacement by unauthorized users. The program needs read/write privileges.

The password system has protections such as 4 attempt max and timeout on exhaustion. It also has an anti-brute-force delay.

It is important to *Sign Out* after finished with the *Settings* page to avoid CRSF attacks.

The systems API interactions are encrypted over TLS, validated using the API key, and incoming data is validated using the `secret` field that was set in setup and the `validator token` which validates the system receiving the POSTs to the Dashboard.

## More help

For macro documentation on the components of the system, see the other pages of this docs directory.

For micro documentation on the codebase, see the inline docstrings, or import the module and run help.

    from lib.Model import Model
    help(Model)
    # -- or
    help(Model.setFOVs)


[1]:https://dashboard.meraki.com
[2]:https://documentation.meraki.com/General_Administration/Other_Topics/Cisco_Meraki_Dashboard_API "Where to find"
[3]:https://flask.palletsprojects.com "Flask Docs"
[4]:https://flask.palletsprojects.com/en/1.1.x/deploying/
[5]:https://numpy.org/
[6]:https://python-pillow.org/
[7]:https://jinja2docs.readthedocs.io/en/stable/ "Jinja 2 Docs"
[8]:https://letsencrypt.org/