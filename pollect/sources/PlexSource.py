from pollect.core import Helper
from pollect.core.ValueSet import ValueSet, Value
from pollect.sources.Source import Source
from xml.etree import ElementTree


class PlexSource(Source):
    """
    Collects plex statistics
    """

    def __init__(self, config):
        super().__init__(config)
        self.url = config.get('url')

    def _probe(self):
        stream_movies = 0
        stream_shows = 0
        stream_music = 0
        movies = 0
        shows = 1
        shows_episodes = 0
        shows_seasons = 0
        music_albums = 0
        music_songs = 0

        data = ValueSet()

        sections = ElementTree.fromstring(Helper.get_url(self.url + '/library/sections'))
        for section in sections:
            sec_id = section.attrib['key']
            lib_type = section.attrib['type']
            if lib_type == 'movie':
                library = ElementTree.fromstring(Helper.get_url(self.url + '/library/sections/' + sec_id + '/all'))
                movies += len(library.getchildren())
                continue
            if lib_type == 'show':
                library = ElementTree.fromstring(Helper.get_url(self.url + '/library/sections/' + sec_id + '/all'))
                shows += len(library.getchildren())
                for show in library:
                    # Every entry is a show
                    shows_episodes += int(show.attrib['leafCount'])
                    shows_seasons += int(show.attrib['childCount'])
                continue
            if lib_type == 'artist':
                library = ElementTree.fromstring(Helper.get_url(self.url + '/library/sections/' + sec_id + '/albums'))
                music_albums += len(library.getchildren())
                for show in library:
                    # Every entry is an album
                    music_songs += int(show.attrib['leafCount'])
                continue
            print('Unknown lib type: ' + lib_type)

        streams = ElementTree.fromstring(Helper.get_url(self.url + '/status/sessions'))
        for stream in streams:
            stream_type = stream.attrib.get('type')
            if stream_type == 'movie':
                stream_movies += 1
                continue
            if stream_type == 'episode':
                stream_shows += 1
                continue
            if stream_type == 'track':
                stream_music += 1
                continue

        data.add(Value(stream_movies, name='streams.movies'))
        data.add(Value(stream_shows, name='streams.shows'))
        data.add(Value(stream_music, name='streams.musics'))
        data.add(Value(movies, name='lib.movies'))
        data.add(Value(shows, name='lib.shows'))
        data.add(Value(shows_episodes, name='lib.shows.episodes'))
        data.add(Value(shows_seasons, name='lib.shows.seasons'))
        data.add(Value(music_albums, name='lib.music.albums'))
        data.add(Value(music_songs, name='lib.music.songs'))
        return data
