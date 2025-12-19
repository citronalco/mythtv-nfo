# myth-nfo

Create Kodi/Jellyfin/Emby compatible NFO files for finished MythTV recordings.

## Description
This script creates NFO files for finished MythTV recordings. All information for the NFO files is taken from MythTV.

Orphaned NFO files and broken symlinks are deleted automatically.

Created NFO files look like this:
```
<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<movie>
  <title>Die Waltons - S03E21 - Jason sucht seinen Weg</title>
  <plot>Jason hat eine besondere musikalische Begabung, auf die auch seine Lehrerin Miss Hunter aufmerksam wird. [...]</plot>
  <runtime>52</runtime>
  <dateadded>2025-12-19 12:49:02</dateadded>
  <aired>2025-12-19</aired>
  <source>MythTV</source>
  <premiered>1975-01-01</premiered>
  <uniqueid type="mythtv" default="true">93324_20251219114700.ts</uniqueid>
  <actor/>
</movie>
```

By default, NFO files are saved into the same directory as the MythTV recordings are:
```
# MythTV's recording directory, e.g. /mnt/mythvideo/:
93324_20251219114700.nfo
93324_20251219114700.ts
93324_20251219114700.ts.png
```
If a `target` directory is set (in example below to `/var/lib/Mythtv-Recordings-with-pretty-names`), NFO files are saved in there, and additionally symlinks with human readable file names for the recordings get created:
```
# /var/lib/Mythtv-Recordings-with-pretty-names/:
Die Waltons - S03E21 - Jason sucht seinen Weg [20251219T1249] [SAT.1 Gold].nfo
Die Waltons - S03E21 - Jason sucht seinen Weg [20251219T1249] [SAT.1 Gold].ts -> /mnt/mythvideo/93324_20251219114700.ts
```

## Requirements
* MythTV >= v34
* Python3 with modules pathvalidate, requests, lxml

## Usage
```
usage: update-nfo.py [-h] [-s RECORDING_GROUPS] [-u API-URL] [-t DIRECTORY]

options:
  -h, --help            show this help message and exit
  -s, --skip RECORDING_GROUPS
                        Skip recordings in this Recording Groups (comma separated) (default: LiveTV)
  -u, --url API-URL     URL to MythTV APIv2 (default: http://127.0.0.1:6544)
  -t, --target DIRECTORY
                        Target directory for pretty named symlinks and nfo files (default: None)
```

## Let MythTV run the script automatically
To automatically create/delete nfo files for new/deleted recordings, add this script as System Event Command:

In MythTV's web interface, 'Backend Setup', tab 'System Events', enter '/path/to/update-nfo.py' (plus extra options if needed) at 'Recording finished' and 'Recording deleted'
