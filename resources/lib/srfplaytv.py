# -*- coding: utf-8 -*-

# Copyright (C) 2018 Alexander Seiler
#
#
# This file is part of plugin.video.srfplaytv.
#
# plugin.video.srfplaytv is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# plugin.video.srfplaytv is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with plugin.video.srfplaytv.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import re
import traceback

import datetime
import json
import socket
import urllib2
# from urllib import urlencode
import urllib
# from urlparse import parse_qsl
import urlparse

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon


from simplecache import SimpleCache

try:
    compat_str = unicode # Python2 
except NameError:
    compat_str = str # Python3 


ADDON_ID= 'plugin.video.srfplaytv'
REAL_SETTINGS = xbmcaddon.Addon(id=ADDON_ID)
ADDON_NAME    = REAL_SETTINGS.getAddonInfo('name')
ADDON_VERSION = REAL_SETTINGS.getAddonInfo('version')
ICON          = REAL_SETTINGS.getAddonInfo('icon')
FANART        = REAL_SETTINGS.getAddonInfo('fanart')
LANGUAGE      = REAL_SETTINGS.getLocalizedString
SEGMENTS = REAL_SETTINGS.getSetting('Enable_Show_Segments') == 'true'
SEGMENTS_TOPICS = REAL_SETTINGS.getSetting('Enable_Settings_Topics') == 'true'
PREFER_HD = REAL_SETTINGS.getSetting('Prefer_HD') == 'true'

PROFILE = xbmc.translatePath(REAL_SETTINGS.getAddonInfo('profile') ).decode("utf-8")

BU = 'srf'
HOST_URL = 'https://www.srf.ch'
TIMEOUT = 30
CONTENT_TYPE = 'files'
DEBUG     = REAL_SETTINGS.getSetting('Enable_Debugging') == 'true'
NUMBER_OF_EPISODES = 10

FAVOURITE_SHOWS_FILENAME = 'favourite_shows.json'
TODAY = LANGUAGE(30058)
YESTERDAY = LANGUAGE(30059)
WEEKDAYS = (LANGUAGE(30060), LANGUAGE(30061), LANGUAGE(30062), LANGUAGE(30063), LANGUAGE(30064), LANGUAGE(30065), LANGUAGE(30066))


socket.setdefaulttimeout(TIMEOUT)


# General helper function:
# Put these into a seperate script.

def log(msg, level=xbmc.LOGDEBUG):
    if DEBUG:
        if level == xbmc.LOGERROR:
            msg += ' ,' + traceback.format_exc()
    xbmc.log(ADDON_ID + '-' + ADDON_VERSION + '-' + (msg), level)


def get_params():
    return dict(urlparse.parse_qsl(sys.argv[2][1:]))


def str_or_none(inp, default=None):
    # return default if inp is None else compat_str(inp)
    if inp is None:
        return default
    try:
        return unicode(inp, 'utf-8')
    except TypeError:
        return inp


def float_or_none(val, scale=1, invscale=1, default=None):
    if val == '':
        val = None
    if val is None:
        return default
    try:
        return float(val) * float(invscale) / float(scale)
    except ValueError:
        return default

def int_or_none(val, scale=1, invscale=1, default=None):
    if val == '':
        val = None
    if val is None:
        return default
    try:
        return int(val) * invscale // scale
    except ValueError:
        return default

def assemble_query_string(query_list):
    return '&'.join(['{}={}'.format(k, v) for (k, v) in query_list])

def getParams():
    return dict(urlparse.parse_qsl(sys.argv[2][1:]))

def get_duration(duration_string):
    durrex = r'(((?P<hour>\d+):)?(?P<minute>\d+):)?(?P<second>\d+)'
    match = re.match(durrex, duration_string)
    if match:
        hour = int(match.group('hour')) if match.group('hour') else 0
        minute = int(match.group('minute')) if match.group('minute') else 0
        second = int(match.group('second'))
        return 60 * 60 * hour + 60 * minute + second
    log('Cannot convert duration string: &s' % duration_string)
    return None

def parse_datetime(input_string):
    dt = _parse_weekday_time(input_string)
    if dt:
        return dt
    dt = _parse_date_time(input_string)
    if dt:
        return dt
    dt = _parse_date_time_tz(input_string)
    return dt

def _parse_date_time_tz(input_string):
    """
    Creates a datetime object from a string of the form
    %Y-%m-%dT%H:%M:%S<tz>
    where <tz> represents the timezone info and is of the form
    (+|-)%H:%M.
    A NoneType will be returned in the case where it was not possible 
    to create a datetime object.

    Keyword arguments:
    input_string -- a string of the above form
    """
    dt_regex = r'''(?x)
                    (?P<dt>
                        \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}
                    )
                    (?P<tz>
                        [-+]\d{2}:\d{2}
                    )
                '''
    match = re.match(dt_regex, input_string)
    if match:
        dts = match.group('dt')
        # We ignore timezone information for now
        try:
            # Strange behavior of strptime in Kodi?
            # dt = datetime.datetime.strptime(dts, '%Y-%m-%dT%H:%M:%S') # results in a TypeError in some cases...
            year = int(dts[0:4])
            month = int(dts[5:7])
            day = int(dts[8:10])
            hour = int(dts[11:13])
            minute = int(dts[14:16])
            second = int(dts[17:19])
            dt = datetime.datetime(year, month, day, hour, minute, second)
            return dt
        except ValueError:
            return None
    return None

def _parse_weekday_time(input_string):
    """
    Creates a datetime object from a string of the form
    <weekday>,? %H:%M(:S)?
    where <weekday> is either a german name of a weekday ('Montag', 'Dienstag', ...) or 
    'gestern', 'heute', 'morgen'.
    If it is not possible to create a datetime object from the given input string, 
    a NoneType will be returned.

    Keyword arguments:
    input_string -- a string of the above form
    """
    weekdays = (
            'Montag',
            'Dienstag',
            'Mittwoch',
            'Donnerstag',
            'Freitag',
            'Samstag',
            'Sonntag',
            'gestern',
            'heute',
            'morgen',
        )
    recent_date_regex = r'''(?x)
                            (?P<weekday>[a-zA-z]+)
                            \s*,\s*
                            (?P<hour>\d{2}):
                            (?P<minute>\d{2})
                            (:
                                (?P<second>\d{2})
                            )?
                        '''
    recent_date_match = re.match(recent_date_regex, input_string)
    if recent_date_match:
        today = datetime.date.today() # This depends on correct date settings in Kodi...
        wdl = [x for x in weekdays if input_string.startswith(x)]
        if not wdl:
            log('No weekday match found for date string: %s' % input_string)
            return None
        index = weekdays.index(wdl[0])
        if index == 9: # tomorrow
            td = datetime.timedelta(1)
        elif index == 8: # today
            td = datetime.timedelta(0)
        elif index == 7: # yesterday
            td = datetime.timedelta(-1)
        else: # Monday, Tuesday, ..., Sunday
            days_off_pos = (today.weekday() - index) % 7
            td = datetime.timedelta(-days_off_pos)
        try:
            hour = int(recent_date_match.group('hour'))
            minute = int(recent_date_match.group('minute'))
            time = datetime.time(hour, minute)
        except ValueError:
            log('Could not parse time for date string: %s' % input_string)
            return None
        try:
            second = int(recent_date_match.group('second'))
            time = datetime.time(hour, minute, second)
        except (ValueError, TypeError):
            pass
        dt = datetime.datetime.combine(today, time) + td
    else:
        log('No match found for date string: %s' % input_string)
        return None
    return dt

def _parse_date_time(input_string):
    """
    Creates a datetime object from a string of the following form:
    %d.%m.%Y,? %H:%M(:%S)?

    Note that the delimiter between the date and the time is optional, and also
    the seconds in the time are optional.

    If the given string cannot be transformed into a appropriate datetime object, 
    a NoneType will be returned.

    Keyword arguments:
    input_string -- the date and time in the above form
    """
    full_date_regex = r'''(?x)
                        (?P<day>\d{2})\.
                        (?P<month>\d{2})\.
                        (?P<year>\d{4})
                        \s*,?\s*
                        (?P<hour>\d{2}):
                        (?P<minute>\d{2})
                        (:
                            (?P<second>\d{2})
                        )?
                    '''
    full_date_match = re.match(full_date_regex, input_string)
    if full_date_match:
        try:
            year = int(full_date_match.group('year'))
            month = int(full_date_match.group('month'))
            day = int(full_date_match.group('day'))
            hour = int(full_date_match.group('hour'))
            minute = int(full_date_match.group('minute'))
            dt = datetime.datetime(year, month, day, hour, minute)
        except ValueError:
            log('Could not convert date string: %s' % input_string)
            return None
        try:
            second = int(full_date_match.group('second'))
            dt = datetime.datetime(year, month, day, hour, minute, second)
            return dt
        except (ValueError, TypeError):
            return dt
    return None    

class SRFPlayTV:
    def __init__(self):
        log('__init__')
        self.cache = SimpleCache()

    def build_url(self, mode=None, name=None, url=None, hash=None, page=None):
        """Build a URL for this Kodi plugin.

        Keyword arguments:
        mode -- an integer representing the mode
        name -- a string containing some information, e.g. a video id
        url  -- a plugin URL, if another plugin/script needs to called
        hash -- a string (used to get additional videos through the API)
        page -- an integer used to indicate the current page in the list of items
        """
        if mode:
            mode = str(mode)
        if page:
            page = str(page)
        added = False
        qs = (url, mode, name, hash, page)
        qn = ('url', 'mode', 'name', 'hash', 'page')
        purl = sys.argv[0]
        for q, n in zip(qs, qn):
            if q:
                add = '?' if not added else '&'
                purl += '%s%s=%s' % (add, n, urllib.quote_plus(q))
                added = True        
        return purl
    
    def open_url(self, url, use_cache=False): # TODO: change use_cache to true
        """Open and read the content given by a URL.

        Keyword arguments:
        url       -- the URL to open as a string
        use_cache -- boolean to indicate if the cache provided by the 
                     Kodi module SimpleCache should be used (default: True)
        """
        log('open_url, url = ' + str(url))
        try:
            cacheResponse = None
            if use_cache:
                cacheResponse = self.cache.get(ADDON_NAME + '.openURL, url = %s'%url)
            if not cacheResponse:
                request = urllib2.Request(url)
                request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64; rv:59.0) Gecko/20100101 Firefox/59.0')
                response = urllib2.urlopen(request, timeout=TIMEOUT).read()
                self.cache.set(ADDON_NAME + '.openURL, url = %s'%url, response, expiration=datetime.timedelta(hours=2))
            return self.cache.get(ADDON_NAME + '.openURL, url = %s'%url)
        except urllib2.URLError, e: log("openURL Failed! " + str(e), xbmc.LOGERROR)
        except socket.timeout, e: log("openURL Failed! " + str(e), xbmc.LOGERROR)
        except Exception, e:
            log("openURL Failed! " + str(e), xbmc.LOGERROR)
            xbmcgui.Dialog().notification(ADDON_NAME, LANGUAGE(30100), ICON, 4000)
            return ''
    
    def extract_id_list(self, url):
        """
        Opens a webpage and extracts video ids (of the form "id": "<vid>")
        from JavaScript snippets.

        Keyword argmuents:
        url -- the URL of the webpage
        """
        log('extract_id_list, url = %s' % url)
        response = self.open_url(url)
        string_response = str_or_none(response, default='')
        if not string_response:
            log('No video ids found on %s' % url)
        readable_string_response = string_response.replace('&quot;', '"')
        # Note: other business units might have other ids, so this is only expected to
        # work for videos of SRF.
        id_regex = r'\"id\"\s*:\s*\"(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\"'
        id_list = [m.group('id') for m in re.finditer(id_regex, readable_string_response)]
        return id_list

    def read_favourite_show_ids(self):
        """
        Reads the show ids from the file defined by the global
        variable FAVOURITE_SHOWS_FILENAMES and returns a list
        containing these ids.
        """
        file_path = os.path.join(PROFILE, FAVOURITE_SHOWS_FILENAME)
        if not os.path.exists(file_path):
            return []
        with open(file_path, 'r') as f:
            json_file = json.load(f)
            try:
                return [entry['id'] for entry in json_file]
            except KeyError:
                log('Unexpected file structure for %s.' % FAVOURITE_SHOWS_FILENAME)
                return []
    
    def write_favourite_show_ids(self, show_ids):
        """
        Writes a list of show ids to the file defined by the global
        variable FAVOURITE_SHOWS_FILENAME.

        Keyword arguments:
        show_ids -- a list of show ids (as strings)
        """
        show_ids_dict_list = [{'id': show_id} for show_id in show_ids]
        file_path = os.path.join(PROFILE, FAVOURITE_SHOWS_FILENAME)
        with open(file_path, 'w') as f:
            json.dump(show_ids_dict_list, f)

    def add_show_to_favourites(self, new_show_id):
        """
        Adds a show to the list of favourite shows and writes these
        shows to the file defined by the global variable FAVOURITE_SHOWS_FILENAME.

        Keyword arguments:
        new_show_id -- a string containing the id of the show to add to the favourites
        """
        log('add_show_to_favourites: new_show_id = %s' % new_show_id)
        show_ids = self.read_favourite_show_ids()
        show_ids.append(new_show_id)
        self.write_favourite_show_ids(show_ids)
    
    def remove_show_from_favourites(self, old_show_id):
        """
        Removes a show from the list of favourite shows and writes the remaining
        show ids to the file defined by the global variable FAVOURITE_SHOWS_FILENAME.

        Keyword arguments:
        old_show_id -- a string containing the id of the show to remove from
                       the favourites
        """
        log('remove_show_from_favourites: old_show_id = %s' % old_show_id)
        show_ids = self.read_favourite_show_ids()
        try:
            show_ids.remove(old_show_id)
        except ValueError:
            log('remove_show_from_favourites: Show id %s not found in list of favourite shows.' % old_show_id)
            return
        self.write_favourite_show_ids(show_ids)
    
    def build_main_menu(self):
        """
        Builds the main menu of the plugin:

        All shows
        Favourite shows
        Newest favourite shows
        Recommodations
        Newest shows (by topic)
        Most clicked shows (by topic)
        Soon offline
        Shows by date
        (SRF.ch live)
        """
        log('build_main_menu')
        main_menu_list = [
            {'name': LANGUAGE(30050), 'mode': 10}, # All shows
            {'name': LANGUAGE(30051), 'mode': 11}, # Favourite shows
            {'name': LANGUAGE(30052), 'mode': 12}, # Newest favourite shows
            {'name': LANGUAGE(30053), 'mode': 16}, # Recommodations
            {'name': LANGUAGE(30054), 'mode': 13}, # Newest shows (by topic)
            {'name': LANGUAGE(30055), 'mode': 14}, # Most clicked shows (by topic)
            {'name': LANGUAGE(30056), 'mode': 15}, # Soon offline
            {'name': LANGUAGE(30057), 'mode': 17}, # Shows by date
            # {'name': LANGUAGE(30070), 'mode': 18}, # SRF.ch live
        ]
        for mme in main_menu_list:
            list_item = xbmcgui.ListItem(mme['name'])
            list_item.setProperty('IsPlayable', 'false')
            list_item.setArt({'thumb': ICON})
            u = self.build_url(mode=mme['mode'], name=mme['name'])
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=list_item, isFolder=True)

    def build_dates_overview_menu(self):
        """
        Builds the menu containing the folders for episodes of
        the last 10 days.
        """
        log('build_dates_overview_menu')
        def folder_name(d):
            today = datetime.date.today()
            if d == today:
                name = TODAY
            elif d == today + datetime.timedelta(-1):
                name = YESTERDAY
            else:
                name = WEEKDAYS[d.weekday()] + ', %s' % d.strftime('%d.%m.%Y')
            return name

        current_date = datetime.date.today()
        number_of_days = 10

        for i in range(number_of_days):
            d = current_date + datetime.timedelta(-i)
            list_item = xbmcgui.ListItem(label=folder_name(d))
            list_item.setArt({'thumb': ICON})
            name = d.strftime('%d-%m-%Y')
            u = self.build_url(mode=24, name=name)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=list_item, isFolder=True)

    def build_date_menu(self, date_string):
        """
        Builds a list of episodes of a given date.

        Keyword arguments:
        date_string -- a string representing date in the form %d-%m-%Y, 
                       e.g. 12-03-2017
        """
        log('build_date_menu, date_string = %s' % date_string)

        url = HOST_URL + '/play/tv/programDay/%s' % date_string
        id_list = self.extract_id_list(url)

        for vid in id_list:
            self.build_episode_menu(vid, include_segments=False, segment_option=SEGMENTS)

    def build_topics_overview_menu(self, newest_or_most_clicked):
        """
        Builds a list of folders, where each folders represents a 
        topic (e.g. News).

        Keyword arguments:
        newest_or_most_clicked -- a string (either 'Newest' or 'Most clicked')
        """
        log('build_topics_overview_menu, newest_or_most_clicked = %s' % newest_or_most_clicked)
        if newest_or_most_clicked == 'Newest':
            mode = 22
        elif newest_or_most_clicked == 'Most clicked':
            mode = 23
        else:
            log('build_topics_overview_menu: Unknown mode, must be "Newest" or "Most clicked".')
            return
        topics_url = HOST_URL + '/play/tv/topicList'
        topics_json = json.loads(self.open_url(topics_url))
        if type(topics_json) != list or len(topics_json) == 0:
            log('No topics found.')
            return
        for elem in topics_json:
            list_item = xbmcgui.ListItem(label=elem.get('title'))
            list_item.setProperty('IsPlayable', 'false')
            list_item.setArt({'thumb': ICON})
            name = elem.get('id')
            if name:
                u = self.build_url(mode=mode, name=name)
                xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=list_item, isFolder=True)
    
    def build_topics_menu(self, name, topic_id=None, page=1):
        """
        Builds a list of videos (can also be folders) for a given topic.

        Keyword arguments:
        name     -- the type of the list, can be 'Newest', 'Most clicked', 'Soon offline'
                    or 'Trending'.
        topic_id -- the SRF topic id for the given topic, this is only needed for 
                    the types 'Newest' and 'Most clicked' (default: None)
        page     -- an integer representing the current page in the list
        """
        log('build_topics_menu, name = %s, topic_id = %s, page = %s' % (name, topic_id, page))
        number_of_videos = 50
        if name == 'Newest':
            url = HOST_URL + '/play/tv/topic/%s/latest?numberOfVideos=%s' % (topic_id, number_of_videos)
            mode = 22
        elif name == 'Most clicked':
            url = HOST_URL + '/play/tv/topic/%s/mostClicked?numberOfVideos=%s' % (topic_id, number_of_videos)
            mode = 23
        elif name == 'Soon offline':
            url = HOST_URL + '/play/tv/videos/soon-offline-videos?numberOfVideos=%s' % number_of_videos
            mode = 15
        elif name == 'Trending':
            url = HOST_URL + '/play/tv/videos/trending?numberOfVideos=%s&onlyEpisodes=true&includeEditorialPicks=true' % number_of_videos
            mode = 16
        else:
            log('build_topics_menu: Unknown mode.')
            return
        
        id_list = self.extract_id_list(url)
        try:
            page = int(page)
        except TypeError:
            page = 1
        
        reduced_id_list = id_list[(page - 1) * NUMBER_OF_EPISODES : page * NUMBER_OF_EPISODES]
        for vid in reduced_id_list:
            self.build_episode_menu(vid, include_segments=False)
        
        try:
            vid = id_list[page*NUMBER_OF_EPISODES]
            next_item = xbmcgui.ListItem(label='>> Next')
            next_item.setProperty('IsPlayable', 'false')
            name = topic_id if topic_id else ''
            u = self.build_url(mode=mode, name=name, page=page+1)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=next_item, isFolder=True)
        except IndexError:
            return        

    def build_favourite_shows_menu(self):
        """
        Builds a list of folders for the favourite shows.
        """
        log('build_favourite_shows_menu')
        favourite_show_ids = self.read_favourite_show_ids()
        self.build_all_shows_menu(favids=favourite_show_ids)
    
    def build_newest_favourite_shows_menu(self, page=1):
        # TODO: This is only a first sketch of the method.
        log('build_newest_favourite_shows_menu')
        number_of_days = 30
        show_ids = self.read_favourite_show_ids()

        now = datetime.datetime.now()
        current_month_date = datetime.date.today().strftime('%m-%Y') # TODO: This depends on the local time settings        
        list_of_episodes_dict = []
        banners = {}
        for sid in show_ids:
            json_url = '%s/play/tv/show/%s/latestEpisodes?numberOfEpisodes=%d&tillMonth=%s' % (HOST_URL, 
                sid, number_of_days, current_month_date)
            response = json.loads(self.open_url(json_url))
            try:
                banner_image = str_or_none(response['show']['bannerImageUrl'])
            except KeyError:
                banner_image = None
            
            episode_list = response.get('episodes', [])
            for episode in episode_list:
                dt = parse_datetime(str_or_none(episode.get('date'), default=''))
                if dt and dt >= now + datetime.timedelta(-number_of_days):
                    list_of_episodes_dict.append(episode)
                    banners.update({episode.get('id'): banner_image})
        sorted_list_of_episodes_dict = sorted(list_of_episodes_dict, 
            key=lambda k: parse_datetime(str_or_none(k.get('date'), default='')), 
            reverse=True)
        try:
            page = int(page)
        except TypeError:
            page = 1
        reduced_sorted_list_of_episodes_dict = sorted_list_of_episodes_dict[(page - 1) * 
            NUMBER_OF_EPISODES : page * NUMBER_OF_EPISODES]
        for episode in reduced_sorted_list_of_episodes_dict:
            self.build_entry(episode, banner=banners.get(episode.get('id')))
        try:
            sorted_list_of_episodes_dict[page*NUMBER_OF_EPISODES]
            next_item = xbmcgui.ListItem(label='>> Next')
            next_item.setProperty('IsPlayable', 'false')
            u = self.build_url(mode=12, page=page+1)
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), u, next_item, isFolder=True)
        except IndexError:
            pass
    
    def build_all_shows_menu(self, favids=None):
        """
        Builds a list of folders containing the names of all the current
        SRF shows.
        """
        log('build_all_shows_menu')
        json_url = 'http://il.srgssr.ch/integrationlayer/1.0/ue/' + BU + '/tv/assetGroup/editorialPlayerAlphabetical.json'
        json_response = json.loads(self.open_url(json_url))
        try:
            show_list = json_response['AssetGroups']['Show']
        except KeyError:
            log('build_all_shows_menu: No shows found.')
            return
        favourite_show_ids = self.read_favourite_show_ids() if favids is None else favids # TODO: use cache if possible
        if type(show_list) != list:
            log('build_all_shows_menu: No shows found.')
            return
        for jse in show_list:
            try:
                title = str_or_none(jse['title'])
                show_id = str_or_none(jse['id'])
            except KeyError:
                log('build_all_shows_menu: Skipping, no title or id found.')
                continue

            # Skip if we build the 'favourite show menu' and the current
            # show id is not in our favourites:
            if favids is not None and show_id not in favids:
                continue

            list_item = xbmcgui.ListItem(label=title)
            list_item.setProperty('IsPlayable', 'false')
            list_item.setInfo(
                'video',
                {
                    'title': title,
                    'plot': str_or_none(jse.get('lead')),
                }
            )

            # Add context menu to add / remove this show from the favourites:
            if show_id in favourite_show_ids:
                plugin_url = self.build_url(mode=101, name=show_id)
                list_item.addContextMenuItems([('Remove from favourite shows', 'XBMC.RunPlugin(%s)' % plugin_url,),])
            else:
                plugin_url = self.build_url(mode=100, name=show_id)
                list_item.addContextMenuItems([('Add to favourite shows', 'XBMC.RunPlugin(%s)' % plugin_url,),])

            try:
                image_url = str_or_none(jse['Image']['ImageRepresentations']['ImageRepresentation'][0]['url'])
                thumbnail = image_url + '/scale/width/668' if image_url else ICON
            except (KeyError, IndexError):
                image_url = FANART
                thumbnail = ICON

            list_item.setArt({
                'thumb': thumbnail,
                'poster': image_url,
            })
            url = self.build_url(mode=20, name=show_id)
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, list_item, isFolder=True)

    def build_live_menu(self):
        def get_live_ids():
            # TODO: implement this
            return ['386514', '386460']
        
        live_ids = get_live_ids()
        for lid in live_ids:
            api_url = 'https://event.api.swisstxt.ch/v1/events/srf/byEventItemId/?eids=%s' % lid
            try:
                live_json = json.loads(self.open_url(api_url))
                entry = live_json[0]
            except:
                continue
            title = entry.get('title')
            stream_url = entry.get('hls')
            image = entry.get('imageUrl')
            item = xbmcgui.ListItem(label=title)
            item.setProperty('IsPlayable', 'true')
            item.setArt({'thumb': image})
            u = self.build_url(mode=51, name=stream_url)
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), u, item, isFolder=False)
    
    def play_livestream(self, stream_url):
        auth_url = self._get_tokenized_src(stream_url)
        play_item = xbmcgui.ListItem('Live', path=auth_url)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
    
    def build_show_menu(self, show_id, page_hash=None):
        """
        Builds a list of videos (can be folders in case of segmented videos) for a show 
        given by its show id.

        Keyword arguments:
        show_id   -- the SRF id of the show
        page_hash -- the page hash to get the list of another page (default: None)
        """
        log('build_show_menu, show_id = %s, page_hash=%s' % (show_id, page_hash))
        current_month_date = datetime.date.today().strftime('%m-%Y') # TODO: This depends on the local time settings
        if not page_hash:
            json_url = '%s/play/tv/show/%s/latestEpisodes?numberOfEpisodes=%d&tillMonth=%s' % (HOST_URL, 
                show_id, NUMBER_OF_EPISODES, current_month_date)
        else:
            json_url = '%s/play/tv/show/%s/latestEpisodes?nextPageHash=%s&tillMonth=%s' % (HOST_URL, 
                show_id, page_hash, current_month_date)

        json_response = json.loads(self.open_url(json_url))

        try:
            banner_image = str_or_none(json_response['show']['bannerImageUrl'])
        except KeyError:
            banner_image = None
        
        next_page_hash = None
        if 'nextPageUrl' in json_response:
            next_page_url = str_or_none(json_response.get('nextPageUrl'), default='')
            next_page_hash_regex = r'nextPageHash=(?P<hash>[0-9a-f]+)'
            match = re.search(next_page_hash_regex, next_page_url)
            if match:
                next_page_hash = match.group('hash')

        json_episode_list = json_response.get('episodes', [])
        if len(json_episode_list) == 0:
            log('No episodes for show %s found.' % show_id)
            return
        
        for episode_entry in json_episode_list:
            segments = episode_entry.get('segments', [])
            enable_segments = True if SEGMENTS and len(segments) > 0 else False
            self.build_entry(episode_entry, banner=banner_image, is_folder=enable_segments)

        if next_page_hash and page_hash != next_page_hash:
            log('page_hash: %s' % page_hash)
            log('next_hash: %s' % next_page_hash)
            next_item = xbmcgui.ListItem(label='>> Next')
            next_item.setProperty('IsPlayable', 'false')
            url = self.build_url(mode=20, name=show_id, hash=next_page_hash)
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, next_item, isFolder=True)

    def build_episode_menu(self, video_id, include_segments=True, segment_option=SEGMENTS_TOPICS):
        """
        Builds a list entry for a episode by a given video id. The segment entries for 
        that episode can be included too.

        Keyword arguments:
        video_id         -- the SRF id of the video
        include_segments -- indicates if the segments (if available) of the video
                            should be included in the list (default: True)
        segment_option   -- which segment option to use (default: SEGMENTS_TOPCICS)
        """
        log('build_episode_menu, video_id = %s, include_segments = %s' % (video_id, include_segments))
        json_url = 'https://il.srgssr.ch/integrationlayer/2.0/%s/mediaComposition/video/%s.json' % (BU, video_id)
        json_response = json.loads(self.open_url(json_url))

        chapter_urn = json_response.get('chapterUrn', '')        
        segment_urn = json_response.get('segmentUrn', '')

        id_regex = r'[a-z]+:[a-z]+:[a-z]+:(?P<id>.+)'
        match_chapter_id = re.match(id_regex, chapter_urn)
        match_segment_id = re.match(id_regex, segment_urn)
        chapter_id = match_chapter_id.group('id') if match_chapter_id else None
        segment_id = match_segment_id.group('id') if match_segment_id else None

        if not chapter_id:
            log('build_episode_menu: No valid chapter URN available for video_id %s' % video_id)
            return
        
        try:
            banner = str_or_none(json_response['show']['bannerImageUrl'])
        except KeyError:
            banner = None
        
        json_chapter_list = json_response.get('chapterList', [])
        json_chapter = None
        for chapter in json_chapter_list:
            if chapter.get('id') == chapter_id:
                json_chapter = chapter
                break
        if not json_chapter:
            log('build_episode_menu: No chapter ID found for video_id %s' % video_id)
            return
        
        json_segment_list = json_chapter.get('segmentList', [])
        if video_id == chapter_id:
            if include_segments:
                self.build_entry(json_chapter, banner)
                for segment in json_segment_list:
                    self.build_entry(segment, banner)
            else:
                if segment_option and len(json_segment_list) > 0:
                    self.build_entry(json_chapter, banner, is_folder=True)
                else:
                    self.build_entry(json_chapter, banner)
        else:
            json_segment = None
            for segment in json_segment_list:
                if segment.get('id') == segment_id:
                    json_segment = segment
                    break
            if not json_segment:
                log('build_episode_menu: No segment ID found for video_id %s' % video_id)
                return
            self.build_entry(json_segment, banner)
    
    def build_entry(self, json_entry, banner=None, is_folder=False):
        """
        Builds an list item for a video or folder by giving the json part, 
        describing this video.

        Keyword arguments:
        json_entry -- the part of the json describing the video
        banner     -- URL of the show's banner (default: None)
        is_folder  -- indicates if the item is a folder (default: False)
        """
        log('build_entry')
        title = json_entry.get('title')
        vid = json_entry.get('id')
        description = json_entry.get('description')
        image = json_entry.get('imageUrl')
        duration = int_or_none(json_entry.get('duration'), scale=1000)
        if not duration:
            duration = get_duration(json_entry.get('duration'))
        date_string = str_or_none(json_entry.get('date'), default='')
        dto = parse_datetime(date_string)
        kodi_date_string = dto.strftime('%Y-%m-%d') if dto else None

        list_item = xbmcgui.ListItem(label=title)
        list_item.setInfo(
            'video',
            {
                'title': title,
                'plot': description,
                'duration': duration,
                'aired': kodi_date_string,
                # 'count': views,
            }
        )
        list_item.setArt({
            'thumb': image, # TODO
            'poster': image,
            'banner': banner,
        })
        if is_folder:
            list_item.setProperty('IsPlayable', 'false')
            url = self.build_url(mode=21, name=vid)
        else:
            list_item.setProperty('IsPlayable', 'true')
            url = self.build_url(mode=50, name=vid)
        xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, list_item, isFolder=is_folder)

    def getAuthString(self, url):
        #obtain the auth url
        sUrl=urlparse.urlparse(url).path.split('/')
        if len(sUrl) < 3:
            return False
        auth=self.open_url('http://tp.srgssr.ch/akahd/token?acl={path}*'.format(path=urllib.quote_plus('/{p1}/{p2}/'.format(p1=sUrl[1],p2=sUrl[2]))))
        auth = json.loads(auth)
        if 'token' in auth and 'authparams' in auth['token']:
            return auth['token']['authparams']
        else:
            return False

    def _get_tokenized_src(self, url, segment_data=None):
        sp = urlparse.urlparse(url).path.split('/')
        token = json.loads(self.open_url(
            'http://tp.srgssr.ch/akahd/token?acl=/%s/%s/*' % (sp[1], sp[2]))) or {}
        auth_params = token.get('token', {}).get('authparams')
        if segment_data:
            # timestep_string = self._get_timestep_token(segment_data)
            # url += ('?' if '?' not in url else '&') + timestep_string
            pass
        if auth_params:
            url += ('?' if '?' not in url else '&') + auth_params
        return url

    def play_video(self, video_id):
        """
        Gets the video stream information of a video and starts to play it.

        Keyword arguments:
        video_id -- the SRF video of the video to play
        """
        log('Playing video %s.' % video_id)
        json_url = 'https://il.srgssr.ch/integrationlayer/2.0/%s/mediaComposition/video/%s.json' % (BU, video_id)
        json_response = json.loads(self.open_url(json_url))

        # stream_url = json_response['chapterList'][0]['resourceList'][2]['url']
        chapter_list = json_response.get('chapterList')
        # if type(chapter_list) != list and len(chapter_list) != 0:
        if type(chapter_list) != list or len(chapter_list) == 0:
            log('No stream URL found.') # TODO: Error (Notification)
            return
        
        first_chapter = chapter_list[0]
        resource_list = first_chapter.get('resourceList')
        if type(resource_list) != list:
            log('No stream URL found.') # TODO: Error (Notification)
            return
        
        stream_urls = {
            'SD': '',
            'HD': '',
        }
        for resource in resource_list:
            if resource.get('protocol') == 'HLS':
                for key in ('SD', 'HD'):
                    if resource.get('quality') == key:
                        stream_urls[key] = resource.get('url')
        
        if not stream_urls['SD'] and not stream_urls['HD']:
            log('No stream URL found.') # TODO: Error (Notification)
            return

        stream_url = stream_urls['HD'] if (stream_urls['HD'] and PREFER_HD) or not stream_urls['SD'] else stream_urls['SD']
        auth_url = self._get_tokenized_src(stream_url)

        start_time = end_time = None
        if 'segmentUrn' in json_response: # video_id is the ID of a segment
            segment_list = first_chapter.get('segmentList', [])
            for segment in segment_list:
                if segment.get('id') == video_id:
                    start_time = float_or_none(segment.get('markIn'), scale=1000)
                    end_time = float_or_none(segment.get('markOut'), scale=1000)
                    break
            
            if start_time and end_time:
                pr = urlparse.urlparse(auth_url)
                query_list = urlparse.parse_qsl(pr.query)
                updated_query_list = []
                for qi in query_list:
                    if qi[0] == 'start' or qi[0] == 'end':
                        continue
                    updated_query_list.append(qi)
                updated_query_list.append(('start', compat_str(start_time)))
                updated_query_list.append(('end', compat_str(end_time)))
                new_query = assemble_query_string(updated_query_list)
                surl_result = urlparse.ParseResult(
                    pr.scheme, pr.netloc, pr.path, pr.params, new_query, pr.fragment)
                auth_url = surl_result.geturl()

        # log(auth_url)
        play_item = xbmcgui.ListItem(video_id, path=auth_url)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)


params=getParams() # TODO: function name (PEP8)
try: url=urllib.unquote_plus(params["url"])
except: url=None
try: name=urllib.unquote_plus(params["name"])
except: name=None
try: mode=int(params["mode"])
except: mode=None
try: page_hash=urllib.unquote_plus(params['hash'])
except: page_hash = None
try: page=urllib.unquote_plus(params['page'])
except: page = None

log("Mode: "+str(mode))
log("URL : "+str(url))
log("Name: "+str(name))

if mode == None:
    SRFPlayTV().build_main_menu()
elif mode == 10:
    SRFPlayTV().build_all_shows_menu()
elif mode == 11:
    SRFPlayTV().build_favourite_shows_menu()
elif mode == 12:
    SRFPlayTV().build_newest_favourite_shows_menu(page=page)
elif mode == 13:
    SRFPlayTV().build_topics_overview_menu('Newest')
elif mode == 14:
    SRFPlayTV().build_topics_overview_menu('Most clicked')
elif mode == 15:
    SRFPlayTV().build_topics_menu('Soon offline', page=page)
elif mode == 16:
    SRFPlayTV().build_topics_menu('Trending', page=page)
elif mode == 17:
    SRFPlayTV().build_dates_overview_menu()
elif mode == 18:
    SRFPlayTV().build_live_menu()
elif mode == 20:
    SRFPlayTV().build_show_menu(name, page_hash=page_hash)
elif mode == 21:
    SRFPlayTV().build_episode_menu(name)
elif mode == 22:
    SRFPlayTV().build_topics_menu('Newest', name, page=page)
elif mode == 23:
    SRFPlayTV().build_topics_menu('Most clicked', name, page=page)
elif mode == 24:
    SRFPlayTV().build_date_menu(name)
elif mode == 50:
    SRFPlayTV().play_video(name)
elif mode == 51:
    SRFPlayTV().play_livestream(name)
elif mode == 100:
    SRFPlayTV().add_show_to_favourites(name)
elif mode == 101:
    SRFPlayTV().remove_show_from_favourites(name)

xbmcplugin.setContent(int(sys.argv[1]), CONTENT_TYPE)
xbmcplugin.addSortMethod(int(sys.argv[1]) , xbmcplugin.SORT_METHOD_UNSORTED)
xbmcplugin.addSortMethod(int(sys.argv[1]) , xbmcplugin.SORT_METHOD_NONE)
xbmcplugin.addSortMethod(int(sys.argv[1]) , xbmcplugin.SORT_METHOD_LABEL)
xbmcplugin.addSortMethod(int(sys.argv[1]) , xbmcplugin.SORT_METHOD_TITLE)
xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=True)
