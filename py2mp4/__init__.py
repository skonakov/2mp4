###############################################################################
#
# Copyright (c) 2012 Sergey Konakov
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
###############################################################################


import argparse
import os
import pkg_resources
import re
import sh
import sys
import tempfile

from progressbar import (
    ProgressBar,
    Percentage,
    Bar,
    ETA,
    FileTransferSpeed
)
from pymediainfo import MediaInfo

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


PROG_NAME = '2mp4'
VIDEO_EXTENSIONS = (
    '.avi',
    '.mkv',
    '.mpeg',
    '.mpg',
    '.wmv'
)


class AttrDict(dict):
    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        self.__dict__ = self


config = AttrDict()


def get_out_file_name(in_path, in_file):
    count = 1
    out_file = '%s.mp4' % in_file
    while os.path.exists(os.path.join(in_path, out_file)):
        out_file = '%s__2mp4_%s__.mp4' % (in_file, count)
        count += 1

    return out_file


def get_media_info(file):
    xml_io = StringIO()
    sh.mediainfo(
        '--Output=XML',
        '-f', file,
        _out=xml_io
    )

    info = MediaInfo(xml_io.getvalue())
    tracks = []

    for track in info.tracks:
        track_type = track.track_type.lower()
        if track_type == 'general':
            general_info = track
        else:
            tracks.append(track)

    try:
        track_ids = [int(track.track_id) for track in tracks]
        min_id = min(track_ids)
        track_ids = [int(track.track_id) - min_id for track in tracks]
    except:
        track_ids = []

    if set(track_ids) != set(range(0, len(tracks))):
        track_ids = range(0, len(tracks))

    for index, track in enumerate(tracks):
        track.track_id = track_ids[index]

    folder_name, file_name = os.path.split(file)
    filename, ext = os.path.splitext(file_name)
    general_info.folder_name = folder_name
    general_info.file_name = filename

    return general_info, tracks


class EncodingProgress:
    FRAMES_RE = re.compile(r'^frame=\s*(\d+) .*')

    def __init__(self, title, total_frames):
        widgets = [
            title,
            Percentage(), ' ',
            Bar(), ' ',
            ETA(), ' ',
            FileTransferSpeed(unit='Frames')
        ]
        self.pbar = ProgressBar(
            widgets=widgets,
            maxval=int(total_frames),
            term_width=120
        )
        self.pbar.start()

    def process_ffmpeg_line(self, line, stdin, process):
        process._stderr.append(line.encode())

        lines = line.splitlines()
        for l in lines:
            match = self.FRAMES_RE.match(l)
            if match is not None:
                frame = int(match.groups()[0])
                if frame > self.pbar.max_value:
                    self.pbar.update(value=self.pbar.max_value)
                else:
                    try:
                        self.pbar.update(value=frame)
                    except Exception as e:
                        print('Frame: %s, error: %s' % (frame, e.message))
                        print(line)

    def finish(self):
        self.pbar.finish()


def get_video_opts(index, track, force_encode=False):
    if track.format == 'AVC' and not force_encode:
        method = '1pass'
        video_opts = [
            '-map', '0:%s' % index,
            '-codec:v', 'copy'
        ]
    else:
        video_opts = [
            '-map', '0:%s' % index,
            '-codec:v', 'libx264',
            '-profile:v', 'high',
            '-level', '4.1'
        ]
        if track.bit_rate:
            method = '2pass'
            video_opts = video_opts + ['-b:v', str(track.bit_rate)]
        else:
            method = '1pass'
            video_opts = video_opts + ['-crf', '18']

    return method, video_opts


def get_audio_opts(index, track):
    if track.format == 'AAC':
        audio_opts = [
            '-map', '0:%s' % index,
            '-codec:a:%s' % index, 'copy'
        ]
    else:
        audio_opts = [
            '-map', '0:%s' % index,
            '-codec:a:%s' % index, config.audio_encoder,
            '-b:a:%s' % index
        ]
        if track.channel_s >= 6:
            audio_opts.append('320K')
        else:
            audio_opts.append('160K')

    return audio_opts


def get_subtitle_opts(index, track):
    return [
        '-map', '0:%s' % index,
        '-codec:s', 'mov_text'
    ]


def convert(filename, args):
    cache_file(filename)
    general_info, tracks = get_media_info(filename)

    method = None
    video_opts = None
    audio_opts = []
    subtitle_opts = []
    metadata_opts = [
        '-map_metadata', '0'
    ]
    input_ops = [
        '-i', '%s' % filename,
    ]

    for index, track in enumerate(tracks):
        track_type = track.track_type.lower()
        if track_type == 'video':
            if method is not None:
                raise Exception(
                    "2mp4 currently doesn't support multiple video streams :("
                )
            method, video_opts = get_video_opts(
                track.track_id,
                track,
                force_encode=args.force_encode
            )
            frame_count = track.frame_count
            if frame_count is None:
                frame_count = float(
                    general_info.duration
                ) / 1000 * float(
                    track.original_frame_rate
                )
        elif track_type == 'audio':
            audio_opts += get_audio_opts(track.track_id, track)
        elif track_type == 'text':
            subtitle_opts += get_subtitle_opts(track.track_id, track)

    out_file_name = get_out_file_name(
        general_info.folder_name,
        general_info.file_name
    )
    out_path = os.path.join(general_info.folder_name, out_file_name)
    print('Encoding %s -> %s' % (
        filename, out_file_name)
    )

    if os.path.exists(out_path):
        print('Destination file exists, skipping...')
        return

    # Test that we can write to output path
    try:
        with open(out_path, 'wb'):
            os.unlink(out_path)
    except IOError as e:
        print(e)
        return sys.exit(e.errno)

    if method == '1pass':
        opts = input_ops + video_opts + audio_opts + \
            subtitle_opts + metadata_opts + config.extra_opts + [
                '-y',
                out_path
            ]
        if args.dry_run:
            print('ffmpeg ' + ' '.join(opts))
        else:
            progress = EncodingProgress('Pass 1 of 1:', frame_count)
            p = sh.ffmpeg(
                *opts,
                _err=progress.process_ffmpeg_line,
                _err_bufsize=256
            )
            p.wait()
            progress.finish()
    elif method == '2pass':
        opts = input_ops + video_opts + [
            '-an',
            '-pass', '1',
            '-y',
            '-f', 'rawvideo',
            '/dev/null'
        ]
        if args.dry_run:
            print('ffmpeg ' + ' '.join(opts))
        else:
            pass1_progress = EncodingProgress('Pass 1 of 2: ', frame_count)
            p = sh.ffmpeg(
                *opts,
                _err=pass1_progress.process_ffmpeg_line,
                _err_bufsize=256
            )
            p.wait()
            pass1_progress.finish()

        opts = input_ops + video_opts + audio_opts + \
            subtitle_opts + metadata_opts + [
                '-pass', '2',
                '-y',
                out_path
            ]
        if args.dry_run:
            print('ffmpeg ' + ' '.join(opts))
        else:
            pass2_progress = EncodingProgress('Pass 2 of 2: ', frame_count)
            p = sh.ffmpeg(
                *opts,
                _err=pass2_progress.process_ffmpeg_line,
                _err_bufsize=256
            )
            p.wait()
            pass2_progress.finish()


def check_required_programs():
    # Check that mediainfo is installed
    if sh.which('mediainfo') is None:
        print(
            '%s: Cannot find mediainfo, please install before continuing.'
        ) % (
            PROG_NAME
        )
        exit(1)

    # Check that ffmpeg is installed
    if sh.which('ffmpeg') is None:
        print(
            '%s: Cannot find ffmpeg. '
            'Please install ffmpeg version 1.0 or later.'
        ) % (
            PROG_NAME
        )

    out = StringIO()
    try:
        sh.ffmpeg(
            '-encoders',
            _out=out
        )
    except sh.ErrorReturnCode:
        print(
            '%s: unsupported version of ffmpeg installed. '
            'Install ffmpeg version 1.0 or higher'
        ) % PROG_NAME

    if 'libx264' not in out.getvalue():
        print(
            "%s: Installed version of ffmeg doesn't include libx264 support. "
            "Install version of ffmpeg that supports libx264."
        ) % PROG_NAME
        exit(1)

    config.extra_opts = ['-strict', 'experimental']
    config.audio_encoder = 'libfaac'
    if 'libfaac' not in out.getvalue():
        config.audio_encoder = 'aac'


def cache_file(filename):
    if sh.which('vmtouch') is None:
        return

    sh.vmtouch(
        '-m', '3G'
        '-vt',
        filename,
        _bg=True
    )


def main():
    parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description="""\
            Convert [input_files] to mp4.
        """
    )
    parser.add_argument(
        'input_files',
        nargs='+',
        help='files or directories to convert to mp4'
    )
    parser.add_argument(
        '-n', '--dry-run',
        dest='dry_run',
        action='store_true',
        help=(
            "Don't actually do the conversion, "
            "just show the command(s) that would be executed"
        )
    )
    parser.add_argument(
        '-f', '--force-encode',
        dest='force_encode',
        action='store_true',
        default=False,
        help=(
            "Force a re-encode of the video stream, even if it is already "
            "in a format supported by mp4 container."
        )
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version='2mp4 ' + pkg_resources.get_distribution('2mp4').version
    )

    args = parser.parse_args()

    check_required_programs()

    input_files = [
        os.path.abspath(input_file.strip()) for input_file in args.input_files
    ]

    os.chdir(tempfile.gettempdir())

    for input_file in input_files:
        if not os.path.exists(input_file):
            print(
                '%s: %s: No such file or directory' % (PROG_NAME, input_file)
            )
            exit(1)

        try:
            if os.path.isfile(input_file):
                convert(input_file, args)
            else:
                for file in os.listdir(input_file):
                    name, ext = os.path.splitext(file)
                    file = os.path.join(input_file, file)
                    if(
                        os.path.isfile(file) and
                        ext.lower() in VIDEO_EXTENSIONS
                    ):
                        convert(file, args)
        except sh.ErrorReturnCode as e:
            print('')
            print('')
            print("OUPS that wasn't supposed to happen!")
            print('')
            print('STDERR:')
            for line in StringIO(e.stderr.decode()):
                print('\t %s' % line.strip())
            exit(1)
