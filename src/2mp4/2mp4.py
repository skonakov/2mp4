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

__author__ = 'Sergey Konakov <skonakov@gmail.com>'

import argparse
import tempfile
import os
import psutil
import re
import sh
import sys

from progressbar import (
    ProgressBar,
    Percentage,
    Bar,
    ETA,
    FileTransferSpeed,
    Timer
)
from pymediainfo import MediaInfo
from StringIO import StringIO

PROG_NAME = __name__.split('.')[0]
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


def get_media_info(file):
    result = AttrDict()
    xmlIO  = StringIO()
    sh.mediainfo(
        '--Output=XML',
        '-f', file,
        _out=xmlIO
    )
    mediainfo = MediaInfo(xmlIO.getvalue())
    for track in mediainfo.tracks:
        if track.track_type == 'Video':
            result.video = track
        elif track.track_type == 'Audio':
            result.audio = track
        elif track.track_type == 'Text':
            result.text = track
        elif track.track_type == 'General':
            result.general = track
        else:
            print 'Ignoring track, type: %s' % track.track_type

    return result


class EncodingProgress:
    FRAMES_RE = re.compile(r'^frame=\s*(\d+) .*')
    def __init__(self, title, total_frames):
        widgets = [
            title,
            Percentage(), ' ',
            Bar(), ' ',
            Timer(), ' ',
            ETA(), ' ',
            FileTransferSpeed(unit='Frames')
        ]
        self.pbar = ProgressBar(
            widgets=widgets,
            maxval=int(total_frames),
            term_width=120
        )
        self.pbar.start()

    def process_ffmpeg_line(self, line):
        lines = line.splitlines()
        for l in lines:
            match = self.FRAMES_RE.match(l)
            if match is not None:
                frame = int(match.groups()[0])
                if frame > self.pbar.maxval:
                    self.pbar.update(value=self.pbar.maxval)
                else:
                    try:
                        self.pbar.update(value=frame)
                    except Exception as e:
                        print 'Frame: %s, error: %s' % (frame, e.message)
                        print line

    def finish(self):
        self.pbar.finish()


def convert(filename):
    cache_file(filename)
    info = get_media_info(filename)

    if info.video.format == 'AVC':
        method = '1pass'
        video_opts = [
            '-codec:v', 'copy'
        ]
    else:
        method = '2pass'
        video_opts = [
            '-b:v', info.video.bit_rate,
            '-codec:v', 'libx264',
            '-profile:v', 'high',
            '-level', '4.1'
        ]

    if info.audio.format == 'AAC':
        audio_opts = [
            '-codec:a', 'copy'
        ]
    else:
        audio_opts = [
            '-codec:a', 'libfaac',
            '-b:a', '160K'
        ]

    input_ops = [
        '-i', '%s' % filename,
    ]

    out_file_name = '%s.mp4' % info.general.file_name
    out_path = os.path.join(info.general.folder_name, out_file_name)
    sys.stderr.write('Encoding %s -> %s\n' % (filename, out_file_name))

    if os.path.exists(out_path):
        sys.stderr.write('Destination file exists, skipping...')

    if method == '1pass':
        opts = input_ops + video_opts + audio_opts + [
            '-y',
            out_path
        ]
        progress = EncodingProgress('Pass 1 of 1:', info.video.frame_count)
        p = sh.ffmpeg(
            *opts,
            _err=progress.process_ffmpeg_line,
            _err_bufsize=256
        )
        p.wait()
        progress.finish()
    elif method == '2pass':
        pass1_progress = EncodingProgress('Pass 1 of 2: ', info.video.frame_count)
        opts = input_ops + video_opts + [
            '-an',
            '-pass', '1',
            '-y',
            '-f', 'rawvideo',
            '/dev/null'
        ]
        p = sh.ffmpeg(
            *opts,
            _err=pass1_progress.process_ffmpeg_line,
            _err_bufsize=256
        )
        p.wait()
        pass1_progress.finish()

        pass2_progress = EncodingProgress(
            'Pass 2 of 2: ',
            info.video.frame_count
        )
        opts = input_ops + video_opts + audio_opts + [
            '-pass', '2',
            '-y',
            out_path
        ]
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
        print '%s: Cannot find mediainfo, please install before continuing.' % (
            PROG_NAME
        )
        exit(1)

    # Check that ffmpeg is installed
    if sh.which('ffmpeg') is None:
        print '%s: Cannot find ffmpeg, please install before continuing.' % (
            PROG_NAME
        )

    out = StringIO()
    sh.ffmpeg(
        '-encoders',
        _out=out
    )
    if 'libfaac' not in out.getvalue():
        print "%s: Installed version of ffmpeg doesn't support libfaac" % PROG_NAME
        exit(1)
    if 'libx264' not in out.getvalue():
        print "%s: Installed version of ffmeg doesn't support libx264" % PROG_NAME
        exit(1)


def cache_file(filename):
    if sh.which('vmtouch') is None:
        return

    sh.vmtouch(
        '-m', psutil.avail_phymem(),
        '-vt',
        filename,
        _bg=True
    )


def main():
    parser = argparse.ArgumentParser(
        prog=PROG_NAME
    )
    parser.add_argument(
        'file',
        help='file or directory to convert to mp4'
    )

    check_required_programs()

    args = parser.parse_args()
    filename = args.file.strip()
    if not os.path.exists(filename):
        print '%s: %s: No such file or directory' % (PROG_NAME, filename)
        exit(1)

    os.chdir(tempfile.gettempdir())

    if os.path.isfile(filename):
        convert(filename)
    else:
        for file in os.listdir(filename):
            name, ext = os.path.splitext(file)
            file = os.path.join(filename, file)
            if os.path.isfile(file) and ext.lower() in VIDEO_EXTENSIONS:
                convert(file)
