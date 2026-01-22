#!/bin/env python3

import os
import glob
from datetime import datetime
import argparse
from lxml import etree
import requests
from pathvalidate import sanitize_filename

# Darauf hinweisen, dass das auch mit mehreren Verzeichnissen in Storage-Groups funktioniert
# zweck: kodi-addon gut, aber nfo-dateien auch gut in anderen programmen, zb jellyfin. symlinks mit human readable names praktisch
# auf myth2kodi verweisen


def create_symlink(source, dest, metadata):
    """Create a symlink"""
    try:
        os.symlink(source, dest)
        # Set timestamp to end of recording
        os.utime(dest, times=(metadata['end_datetime'].timestamp(), metadata['end_datetime'].timestamp()), follow_symlinks=False)
        print(f"Created symlink from '{source}' to '{dest}'")
        return True
    except FileExistsError:
        return False


def create_nfo(filepath, metadata):
    """Create and save nfo file"""

    if os.path.isfile(filepath):
        # File already exists
        return False

    with open(filepath, 'w', encoding='utf-8') as nfo_file:
        root = etree.Element('movie')
        etree.SubElement(root, 'title').text = metadata['title_text']
        etree.SubElement(root, 'plot').text = metadata['description']
        etree.SubElement(root, 'runtime').text = metadata['runtime_minutes']
        etree.SubElement(root, 'dateadded').text = metadata['start_datetime'].astimezone().strftime('%Y-%m-%d %H:%M:%S')
        etree.SubElement(root, 'aired').text = metadata['start_datetime'].astimezone().strftime('%Y-%m-%d')
        etree.SubElement(root, 'source').text = 'MythTV'

        if metadata['premiered']:
            etree.SubElement(root, 'premiered').text = metadata['premiered'].astimezone().strftime('%Y-%m-%d')

        unique_id = etree.SubElement(root, 'uniqueid')
        unique_id.attrib['type'] = 'mythtv'
        unique_id.attrib['default'] = 'true'
        unique_id.text = metadata['filename']

        actor = etree.SubElement(root, 'actor')
        for cast_member in metadata['cast']:
            etree.SubElement(actor, 'name').text = cast_member['name']
            etree.SubElement(actor, 'role').text = cast_member['role']

        nfo_file.write(etree.tostring(root, pretty_print=True, xml_declaration = True, encoding='UTF-8', standalone=True).decode('utf-8'))

    os.utime(filepath, times=(metadata['end_datetime'].timestamp(), metadata['end_datetime'].timestamp()), follow_symlinks=False)
    print(f"Created nfo file '{filepath}'")
    return True


def get_text(xml_data, xml_path, default_value=None):
    """Returns value of a xml element as string"""
    try:
        return ' '.join(xml_data.xpath(xml_path)[0].text.strip().splitlines())
    except (IndexError, AttributeError):
        return default_value


def get_datetime_from_iso(xml_data, xml_path, default_value=None):
    """Returns iso8601 value of a xml element as datetime"""
    try:
        return datetime.fromisoformat(get_text(xml_data, xml_path))
    except (IndexError, AttributeError, TypeError):
        return default_value


def get_storage_groups_directory_mapping(api_url):
    """Returns dict: {'storage_group1':['directory1,'directory2',...], ...}"""
    response = requests.get(f"{api_url}/Myth/GetStorageGroupDirs", timeout=15)
    xml_data = etree.XML(response.text.encode('utf-8'))

    mapping = {}
    for storage_group_dir in xml_data.xpath("/StorageGroupDirList/StorageGroupDirs/StorageGroupDir"):
        groupname = get_text(storage_group_dir, 'GroupName')
        # Would be good to know which Storage Groups are actually used for recordings, but I don't know how to figure that out.
        # For now simply assume recordings are in any Storage Group - except the standard ones for Banners, Videos, Trailers, Fanart, ...
        if groupname in [ 'Banners', 'Coverart', 'DB Backups', 'Fanart', 'Screenshots', 'Trailers' ]:
            continue

        directory = get_text(storage_group_dir, 'DirName')
        try:
            mapping[groupname].append(directory)
        except KeyError:
            mapping[groupname] = [directory]

    return mapping


def main():
    """MAIN"""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description = "Create Kodi compatible NFO files for finished MythTV recordings.\n\n" \
            "By default, nfo files are saved in the same directory as the recordings.\n" \
            "If a target directory is set, NFO files are saved in there and symlinks with human readable file names for the recordings get created.\n" \
            "Orphaned NFO files and broken symlinks are deleted automatically.\n" \
            "Requires MythTV >= v34",
        epilog = "To automatically create/delete nfo files for new/deleted recordings, add this script as System Event Command:\n" \
            "In MythTV's web interface, 'Backend Setup', tab 'System Events', enter '%(prog)s' (plus extra options if needed) at 'Recording finished' and 'Recording deleted'",
    )
    parser.add_argument("-s", "--skip", help="Skip recordings in this Recording Groups (comma separated) (default: %(default)s)", default="LiveTV", metavar='RECORDING_GROUPS')
    parser.add_argument("-u", "--url", help="URL to MythTV APIv2 (default: %(default)s)", default="http://127.0.0.1:6544",  metavar='API-URL')
    parser.add_argument("-t", "--target", help="Target directory for pretty named symlinks and nfo files (default: %(default)s)", default=None, metavar='DIRECTORY')

    args = parser.parse_args()
    SKIP_RECORDING_GROUPS = [ x.lower().strip() for x in args.skip.split(',') ] if args.skip else []
    MYTHTV_API_URL = args.url
    TARGET_DIR = args.target

    # Create StorageGroup-Directory mapping
    storage_group_mapping = get_storage_groups_directory_mapping(MYTHTV_API_URL)

    # Get metadata of all finished recordings
    response = requests.get(f"{MYTHTV_API_URL}/Dvr/GetRecordedList", timeout=15)
    xml_data = etree.XML(response.text.encode('utf-8'))
    program_xml = xml_data.xpath("/ProgramList/Programs/Program[Recording/StatusName='Recorded']")
    print(f"Found {len(program_xml)} recordings")

    # Loop through list of recordings
    for recording_xml in program_xml:
        # Skip recordings being in wrong Recording Groups (e.g. LiveTV)
        if get_text(recording_xml, 'Recording/RecGroup').lower() in SKIP_RECORDING_GROUPS:
            continue

        # Gather recording info required for nfo file
        metadata = {
            'season': get_text(recording_xml, 'Season'),
            'episode': get_text(recording_xml, 'Episode'),
            'channel_name': get_text(recording_xml, 'Channel/ChannelName', ''),
            'start_datetime': get_datetime_from_iso(recording_xml, 'StartTime'),
            'end_datetime': get_datetime_from_iso(recording_xml, 'Recording/EndTs'),
            'filename': get_text(recording_xml, 'Recording/FileName'),
            'description': get_text(recording_xml, 'Description'),
            'premiered': get_datetime_from_iso(recording_xml, 'Airdate'),
            'runtime_minutes': str(int((get_datetime_from_iso(recording_xml, 'EndTime') \
                                - get_datetime_from_iso(recording_xml, 'StartTime')).total_seconds() / 60)),
            'damaged': True if "DAMAGED" in get_text(recording_xml, 'VideoPropNames') else False,
            'cast': [],
        }

        for cast_member in recording_xml.xpath("Cast/CastMembers/CastMember"):
            metadata['cast'].append({
                'name': get_text(cast_member, 'Name'),
                'role': get_text(cast_member, 'CharacterName'),
            })

        # Create a sensible title
        # Movie nfo files do not support episode/season metadata, so append it to the title
        metadata['season_episode_text'] = f"S{metadata['season'].zfill(2)}E{metadata['episode'].zfill(2)}" \
            if metadata['season'] != "0" and metadata['episode'] != "0" else None
        metadata['title_text'] = ' '.join(filter(None, [
        ' - '.join(filter(None, [
                get_text(recording_xml, 'Title'),
                metadata['season_episode_text'],
                get_text(recording_xml, 'SubTitle'),
            ])),
        ]))

        # Find video file's directory in Storage Group's directories
        storage_group = get_text(recording_xml, 'Recording/StorageGroup')
        metadata['directory'] = None
        for storage_directory in storage_group_mapping[storage_group]:
            if os.path.isfile(os.path.join(storage_directory, metadata['filename'])):
                metadata['directory'] = storage_directory
                break
        if not metadata['directory']:
            # Video file not found anywhere, probably broken database entry. Skip.
            continue


        # Create nfo file (and symlink)
        (recording_stem, recording_suffix) = os.path.splitext(metadata['filename'])
        if TARGET_DIR:
            # Human readable filename (append datetime and channel to title text)
            human_readable_filename_stem = sanitize_filename(' '.join(filter(None, [
                metadata['title_text'],
               '[' + metadata['start_datetime'].astimezone().strftime('%Y%m%dT%H%M') + ']',
               '[' + metadata['channel_name'] + ']' if metadata['channel_name'] else None,
               '[DAMAGED]' if metadata['damaged'] else None,
            ])))
            create_symlink(
                os.path.join(metadata['directory'], metadata['filename']),
                os.path.join(TARGET_DIR, human_readable_filename_stem + recording_suffix),
                metadata)
            create_nfo(os.path.join(TARGET_DIR, human_readable_filename_stem + '.nfo'), metadata)
        else:
            create_nfo(os.path.join(metadata['directory'], recording_stem + '.nfo'), metadata)


    # Delete broken symlinks
    if TARGET_DIR:
        all_files = glob.glob(os.path.join(TARGET_DIR, r'*'))
        for f in all_files:
            if os.path.islink(f) and not os.path.exists(f):
                os.remove(f)
                print(f"Deleted broken symlink {f}")

    # Loop through all Storage Directories and delete nfo files without video file
    storage_directories = [ TARGET_DIR ] if TARGET_DIR else sum(storage_group_mapping.values(), [])
    for storage_directory in storage_directories:
        all_files = glob.glob(os.path.join(storage_directory, r'*'))
        all_nfo_files = glob.glob(os.path.join(storage_directory, r'*.nfo'))
        video_files = list(set(all_files) - set(all_nfo_files))

        video_files_stem = list(map(lambda x: os.path.splitext(x)[0], video_files))

        for nfo_file in all_nfo_files:
            if os.path.isfile(nfo_file):
                nfo_file_stem = os.path.splitext(nfo_file)[0]
                if nfo_file_stem not in video_files_stem:
                    os.remove(nfo_file)
                    print(f"Deleted orphaned nfo file '{nfo_file}'")


if __name__ == "__main__":
    main()
