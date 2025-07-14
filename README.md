# MCConsoleAPI

MCConsoleAPI is an HTTP API wrapper for Minecraft servers that gives you the power to create automation and tools for minecraft servers without needing to know a specific programming language. Make simple HTTP requests to the backend and accomplish any task you want in any language you want!

> [!NOTE]
> This project is a WIP and is not guaranteed to be secure in any way. Steps have been taken to mitigate some attack vectors, but no application is 100% safe. This software is provided AS IS without warranty of any kind. Any issues you have, please report them on the [issues](https://github.com/Column01/MCConsoleAPI/issues) page with any relevant information.

## A Preface

This tool is just a backend to manage servers, a frontend or other tooling is required to unlock the full functionality of this project. Some are linked at the bottom of the page, a link to that section is in the below Table of Contents.

## Table of Contents
- [Preface](#a-preface)
- [Table of Contents](#table-of-contents)
- [Setup and Installation](#setup-and-installation)
    - [Pre-requisites](#pre-requisites)
    - [Configuration](#configuration)
        - [API Configuration](#api-configuration)
        - [Minecraft Server Configuration](#minecraft-server-configuration)
    - [Starting the API](#starting-the-api-server)
    - [The Admin API Key](#the-admin-api-key)
    - [API Documentation](#reading-the-api-docs)
- [Conclusion](#conclusion)
- [Other Projects using MCConsoleAPI](#other-projects-using-mcconsoleapi)

## Setup and Installation

### Pre-requisites

1. Install [Python](https://www.python.org/downloads/) (tested on `3.12.3` but *in theory* `>=Python 3.8`)
    - This project uses FastAPI which requires Python 3.8+
    - **Some type hinting in this code probably does not work on older python versions than what was tested!**
2. Download the project
    - You can do this by cloning the repo or clicking [this link](https://github.com/Column01/MCConsoleAPI/archive/refs/heads/master.zip)
    - If you downloaded it as a ZIP file, please extract it to a folder somewhere logical
3. Install Requirements
    - Open a command prompt or terminal
    - Change to the directory of the program: `cd /path/to/extracted/download/` (or `P:\ath\to\extracted\download\` on windows)
    - Windows: `python -m pip install -r requirements.txt`
    - Unix: `pip3 install -r requirements.txt`

### Configuration

The API works with multiple Minecraft servers running behind it, so there are multiple configuration files. Each minecraft server gets its own configuration file placed in the root directory of the Minecraft Server (where `server.properties` is) and the API gets its own configuration for the webserver and other backend things.

The gist is:

- The API Config contains anything required for the backend API server.
- Server configs contains anything relating to that minecraft server instance (Path to the jar, any java flags, additional options for API features etc.).

#### API Configuration

The API configuration contains any options nessecary for managing the web API and for managing servers and their aliases.

1. Open `api_config.toml` which is located in the root of the API folder with your text editor of choice.
2. The main things to check here are the server `host` and the `port`, these are the IP and Port the API will use to serve HTTP requests. You can change these if you like, this is also the info you need to connect your frontend or tools to.
3. Below the general section is the list of servers. 
    - If you wish, you can add servers with their path to the server directory there, a sample is availabe in the config file for editing.
    - When you do so, it allows you to start and stop them via their name alias, rather than having to specify a path to the server. 
    - You can also configure the backend to start the servers when the API starts, but at the moment these starts are not staggered or ordered so it is not encouraged to use this feature as of yet.

#### Minecraft Server Configuration

Each server gets its own configuration file (`config.toml`) because each server needs its own configuration. Inside it is the path to your java install, the jar path to the server jar (wildcards are accepted) and any arguments that get passed to the JVM for the server. There are also some options for managing the server via the backend such as automatic restarts and the regexes configuration for console tracking of things like player connections and chat messages.

Here's how to configure a server:

1. Copy `config_template.toml` from the API folder into the root directory of a Minecraft server where `server.properties` and (usually) the server jar are located.
2. Rename the copied file to `config.toml` and open it in your text editor of choice, though one with syntax hilighting for TOML is handy (Such as Sublime Text 3 for example).
3. Ensure the `java_path`, `server_jar` and `jvm_args` have anything you need setup for your instance. 
    - Sometimes newer or older Minecraft versions need specific java versions. You can install additional Java versions and just put the path to the java binary in the `java_path` configuration option.


### Starting the API Server

As of now, there isn't a convenient way to run the program other than from the main program folder.

This will change in the future as development continues.

For now, you can start the backend API server using this command:

- Windows: `python main.py`
- Linux: `python3 main.py`

### The Admin API key

When you first run the program, you will see a section print out in the console that looks like this:

```txt
================
ADMIN API KEY: ADMIN-API-KEY
================
```

This is an important API key that has special privaledges (such as the ability to create new API keys).
**Copy this somewhere safe**, if you lose it you will need to regenerate it. This API key is also the only API key that can issue a new API key, so you need it if you would like to authorize other clients to use your server's API.

See the next section on viewing the API documentation where you can also see the endpoint for creating a new API key. It is recommended you do this immediately and **DO NOT use the Admin API key for every day tasks.**

### Reading the API docs

Once you have started the program, open your web browser and navigate to the host and port that was printed into the console.

Once opened, you should have been redirected to the `/docs` endpoint contains the API documentation. This page is automatically generated by the program when run and is also interactive so you can test out the backend without having to install a frontend. It's also very useful when debugging any frontend issues you may have. Just **make sure to click the `Authorize` Button in the top right** of the page and enter an API key before you attempt to use any of the endpoints as they will not work otherwise.

I plan to make more development documentation at a later date.

## Conclusion

On that note, that is all there is for the backend. You can technically use it to run servers just using the docs page to run endpoints, but the power comes from external tools and the potential for frontends being free from programming language or platform restrictions. Want to make a Server console for the server you are currently on while inside Minecraft? You can with ComputerCraft or Open Computers!

**With that comes the security issues I warned about at the top of this file. Make sure your api keys are kept secure, if you leak your admin key they could create a hidden api key for themselves and use it sparingly to steal player information or other data, or it could lead to malicous commands being sent to your servers.**

## Other Projects using MCConsoleAPI

Projects using this API can submit a pull-request adding it to the list or submit an issue to the repo to be reviewed. You must include a link to the project using the API (the source code if possible, although not required), as well as include proper attribution somewhere in your project/documentation for using the API in order to qualify for being added to this list ([example](https://github.com/Column01/MCConsolePy?tab=readme-ov-file#acknowledgments)). All projects are subject to removal at the discretion of the maintainers.

- [MCConsolePy](https://github.com/Column01/MCConsolePy) by me - An example of a frontend client made using Tkinter and Requests in Python.
- [MCConsoleCLI](https://github.com/Column01/MCConsoleCLI) by me - An example of a CLI tool for making connections to the backend. Currently only allows for starting, listing, and stopping of servers. Useful if you want a tool for just that
