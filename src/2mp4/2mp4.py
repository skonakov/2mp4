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


config = AttrDict()


def get_media_info(file):
    result = AttrDict()
    xmlIO  = StringIO()
    sh.mediainfo(
        '--Output=XML',
        '-f', file,
        _out=xmlIO
    )
    mediainfo = MediaInfo(xmlIO.getvalue().encode('utf-8'))
    for track in mediainfo.tracks:
        type = track.track_type.lower()
        if type not in result:
            result[type] = list()

        result[type].append(track)

    if len(result.video) > 1:
        print "2mp4 doesn't support files with multiple video streams :("
        sys.exit(1)

    result.video = result.video[0]
    result.general = result.general[0]

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

    def process_ffmpeg_line(self, line, stdin, process):
        process._stderr.append(line)

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


def convert(filename, args):
    cache_file(filename)
    info = get_media_info(filename)

    if info.video.format == 'AVC':
        method = '1pass'
        video_opts = [
            '-map 0:%s' % info.video.track_id,
            '-codec:v:%s' % info.video.track_id, 'copy'
        ]
    else:
        method = '2pass'
        video_opts = [
            '-map', '0:%s' % info.video.track_id,
            '-b:v', str(info.video.bit_rate),
            '-codec:v', 'libx264',
            '-profile:v', 'high',
            '-level', '4.1'
        ]

    audio_opts = []
    for audio in info.audio:
        if audio.format == 'AAC':
            audio_opts += [
                '-map', '0:%s' % audio.track_id,
                '-codec:a:%s' % audio.track_id, 'copy'
            ]
        else:
            audio_opts += [
                '-map', '0:%s' % audio.track_id,
                '-codec:a:%s' % audio.track_id, 'libfaac',
                '-b:a:%s' % audio.track_id
            ]
            if audio.channel_s >= 6:
                audio_opts.append('320K')
            else:
                audio_opts.append('160K')

    subtitle_opts = [
        '-codec:s', 'copy'
    ]

    input_ops = [
        '-i', '%s' % filename,
    ]

    out_file_name = '%s.mp4' % info.general.file_name
    out_path = os.path.join(info.general.folder_name, out_file_name)
    sys.stderr.write('Encoding %s -> %s\n' % (filename, out_file_name))

    if os.path.exists(out_path):
        print('Destination file exists, skipping...')
        return

    if method == '1pass':
        opts = input_ops + video_opts + audio_opts + subtitle_opts + [
            '-y',
            out_path
        ]
        if args.dry_run:
            print 'ffmpeg ' + ' '.join(opts)
        else:
            progress = EncodingProgress('Pass 1 of 1:', info.video.frame_count)
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
            print 'ffmpeg ' + ' '.join(opts)
        else:
            pass1_progress = EncodingProgress(
                'Pass 1 of 2: ',
                info.video.frame_count
            )
            p = sh.ffmpeg(
                *opts,
                _err=pass1_progress.process_ffmpeg_line,
                _err_bufsize=256
            )
            p.wait()
            pass1_progress.finish()

        opts = input_ops + video_opts + audio_opts + subtitle_opts + [
            '-pass', '2',
            '-y',
            out_path
        ]
        if args.dry_run:
            print 'ffmpeg ' + ' '.join(opts)
        else:
            pass2_progress = EncodingProgress(
                'Pass 2 of 2: ',
                info.video.frame_count
            )
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
        print (
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
        print (
            '%s: unsupported version of ffmpeg installed. '
            'Install ffmpeg version 1.0 or higher'
        ) % PROG_NAME

    if 'libx264' not in out.getvalue():
        print (
            "%s: Installed version of ffmeg doesn't include libx264 support. "
            "Install version of ffmpeg that supports libx264."
        ) % PROG_NAME
        exit(1)

    if 'libfaac' in out.getvalue():
        config.audio_encoder_opts = [
            '-codec:a', 'libfaac'
        ]
    else:
        config.audio_encoder_opts = [
            '-strict', 'experimantal',
            '-codec:a', 'aac'
        ]


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
            Convert [input_file] to mp4. The output video file will be created
            in the same directory named [input_file].mp4
        """
    )
    parser.add_argument(
        'input_file',
        help='file or directory to convert to mp4'
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
        '-v', '--version',
        action='version',
        version='2mp4 ' + pkg_resources.get_distribution('2mp4').version
    )

    args = parser.parse_args()

    input_file = os.path.abspath(args.input_file.strip())
    if not os.path.exists(input_file):
        print '%s: %s: No such file or directory' % (PROG_NAME, input_file)
        exit(1)

    check_required_programs()

    os.chdir(tempfile.gettempdir())

    try:
        if os.path.isfile(input_file):
            convert(input_file, args)
        else:
            for file in os.listdir(input_file):
                name, ext = os.path.splitext(file)
                file = os.path.join(input_file, file)
                if os.path.isfile(file) and ext.lower() in VIDEO_EXTENSIONS:
                    convert(file, args)
    except sh.ErrorReturnCode as e:
        print
        print
        print "OUPS that wasn't supposed to happen!"
        print
        print 'STDERR:'
        for line in StringIO(e.stderr):
            print '\t', line,
        exit(1)
