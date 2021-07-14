# ftp sync

Sync file pairs over ftp and apply patches to them. Useful for using [ftpd](https://github.com/mtheall/ftpd) to transfer ROM save files to and from your DS if you also play on an emulator. Setup a cron job to check for your DS's ftp server periodically to setup automatic syncing. Untested on windows. It may just work out of the box, unsure though.

## Installation

Clone this repo, cd into it, `pip3 install .`

## Config file format

Default config file location:
- Windows: `Documents\ftp_sync\ftp_sync.yaml'
- Linux/MacOS: `~/.config/ftp_sync/ftp_sync.yaml`

Use either yaml or json. An example yaml file is provided with all of the currently supported options.

If the patcher option is not specified, files will be transfered unmodified.

## Automatic sync behavior

On your first run, you'll likely have to specify one of the to/from commands if both remote and local files exist.

- Will sync if either remote or local file do not exist
- Will sync if either local or remote files change, not both.
- Will not sync if both files change

## Usage

```
Usage: python -m ftp_sync [OPTIONS] COMMAND [ARGS]...

Options:
  -c, --config-file TEXT  Yaml or json config file defining connection and 
                          sync pair settings
  -d, --debug
  --help                  Show this message and exit.

Commands:
  sync           Automatically sync a specified sync pair.
  sync-all       Automatically sync all sync pairs.
  sync-all-from  Sync all sync pairs remote to local.
  sync-all-to    Sync all sync pairs local to remote.
  sync-from      Sync a pair remote to local.
  sync-to        Sync a pair local to remote.
```

The singular sync commands (the ones that aren't sync-all\*) take a `-n/--name` argument which specifies the sync pair to use.

Ex: `python3 -m ftp_sync sync -n pokemon_pearl` will sync the `pokemon_pearl` sync pair in the example yaml file.

## Future work

- [x] Windows support
- [ ] Add directory sync support
- [ ] Sync between multiple sources/servers
- [ ] Cleanup old backup files
- [ ] Define and enforce config file schema
- [ ] Add more patchers (Would love to extract/inject saves from/to VC)
- [ ] Make this README better
- [ ] If enough people like this I'll consider adding it to pypi and turning this into a real REPO with CI, unit tests, etc
- [ ] Suggestions?
