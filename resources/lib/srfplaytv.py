# -*- coding: utf-8 -*-

# Copyright (C) 2018 Alexander Seiler
#
#
# This file is part of plugin.video.srfplaytv.
#
# plugin.video.srfplaytv is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# plugin.video.srfplaytv is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with plugin.video.srfplaytv.
# If not, see <http://www.gnu.org/licenses/>.

import sys
import traceback

from urllib.parse import unquote_plus
from urllib.parse import parse_qsl

import xbmc
import xbmcaddon
import xbmcplugin
import srgssr

ADDON_ID = 'plugin.video.srfplaytv'
REAL_SETTINGS = xbmcaddon.Addon(id=ADDON_ID)
ADDON_NAME = REAL_SETTINGS.getAddonInfo('name')
ADDON_VERSION = REAL_SETTINGS.getAddonInfo('version')
DEBUG = (REAL_SETTINGS.getSetting('Enable_Debugging') == 'true')
CONTENT_TYPE = 'videos'


class SRFPlayTV(srgssr.SRGSSR):
    def __init__(self):
        super(SRFPlayTV, self).__init__(
            int(sys.argv[1]), bu='srf', addon_id=ADDON_ID)


def log(msg, level=xbmc.LOGDEBUG):
    """
    Logs a message using Kodi's logging interface.

    Keyword arguments:
    msg   -- the message to log
    level -- the logging level
    """
    if DEBUG:
        if level == xbmc.LOGERROR:
            msg += ' ,' + traceback.format_exc()
    xbmc.log(ADDON_ID + '-' + ADDON_VERSION + '-' + msg, level)


def get_params():
    return dict(parse_qsl(sys.argv[2][1:]))


def run():
    """
    Run the plugin.
    """
    params = get_params()
    try:
        url = unquote_plus(params["url"])
    except Exception:
        url = None
    try:
        name = unquote_plus(params["name"])
    except Exception:
        name = None
    try:
        mode = int(params["mode"])
    except Exception:
        mode = None
    try:
        page_hash = unquote_plus(params['page_hash'])
    except Exception:
        page_hash = None
    try:
        page = unquote_plus(params['page'])
    except Exception:
        page = None

    log('Mode: ' + str(mode))
    log('URL : ' + str(url))
    log('Name: ' + str(name))
    log('Page Hash: ' + str(page_hash))
    log('Page: ' + str(page))

    if mode is None:
        identifiers = [
            'All_Shows',
            'Favourite_Shows',
            'Newest_Favourite_Shows',
            'Recommendations',
            'Newest_Shows',
            'Most_Clicked_Shows',
            'Soon_Offline',
            'Shows_By_Date',
            # 'Live_TV',
            'Search',
            'SRF_Live',
            'SRF_YouTube'
        ]
        SRFPlayTV().build_main_menu(identifiers)
    elif mode == 10:
        SRFPlayTV().build_all_shows_menu()
    elif mode == 11:
        SRFPlayTV().build_favourite_shows_menu()
    elif mode == 12:
        SRFPlayTV().build_newest_favourite_menu(page=page)
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
        SRFPlayTV().build_live_menu(extract_srf3=True)
    elif mode == 19:
        SRFPlayTV().manage_favourite_shows()
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
    elif mode == 25:
        SRFPlayTV().pick_date()
    # elif mode == 26:
    #     SRFPlayTV().build_tv_menu()
    elif mode == 27:
        SRFPlayTV().build_search_menu()
    elif mode == 28:
        SRFPlayTV().build_search_media_menu(
            mode=mode, name=name, page=page, page_hash=page_hash)
    elif mode == 29:
        SRFPlayTV().build_search_show_menu(name=name)
    elif mode == 70:
        SRFPlayTV().build_recent_search_menu('media')
    elif mode == 71:
        SRFPlayTV().build_recent_search_menu('show')
    elif mode == 30:
        SRFPlayTV().build_youtube_channel_overview_menu(33)
    elif mode == 33:
        SRFPlayTV().build_youtube_channel_menu(
            name, mode, page=page, page_token=page_hash)
    elif mode == 50:
        SRFPlayTV().play_video(name)
    elif mode == 51:
        SRFPlayTV().play_livestream(name)

    xbmcplugin.setContent(int(sys.argv[1]), CONTENT_TYPE)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.endOfDirectory(int(sys.argv[1]), cacheToDisc=True)
